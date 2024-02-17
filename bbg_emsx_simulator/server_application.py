import queue
from enum import Enum
from typing import Set, Dict

import quickfix as fix
from pandas import Series

from fix_application import FIXApplication, FIXMessage, get_utc_transactime, log, string_to_message, \
    create_fix_string_from_dict
from order_manager import OrderManager


class MessageAction(Enum):
    NewOrder = fix.MsgType_NewOrderSingle
    ChangeOrder = fix.MsgType_OrderCancelReplaceRequest
    CancelOrder = fix.MsgType_OrderCancelRequest
    RejectOrder = fix.MsgType_ExecutionReport


class ServerApplication(fix.Application):
    order_manager = None
    session_id = None
    uuids_of_interest: Set[str] = set()
    oms_order_id_per_accepted_reserve_clordid: Dict[str, str] = dict()

    def __init__(self):
        super().__init__()
        self.order_manager = OrderManager()
        self.from_app_queue = queue.Queue()

    def onCreate(self, session_id):
        # method mandated by parent class
        pass

    def onLogon(self, session_id):
        ServerApplication.session_id = session_id
        log('SERVER Session',
            f"{session_id} logged on.<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<", '\n')

    def onLogout(self, session_id):
        log('SERVER Session',
            f"{session_id} logged out.>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", '\n')

    def toAdmin(self, message, session_id):
        message = FIXMessage(message)
        msg_type = message.get(fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            log('Sent ADMIN', message)

    def fromAdmin(self, message, session_id):
        message = FIXMessage(message)
        msg_type = message.get(fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            log('Rcvd ADMIN', message)

    def toApp(self, message, session_id):
        log('Sent APP', message)

    def fromApp(self, message, session_id):
        message = FIXMessage(message)
        log('Rcvd APP', message)
        self.process_message(message)

    def process_message_from_app_queue(self):
        if self.from_app_queue.not_empty:
            try:
                self.from_app_queue.get(block=True, timeout=1)
            except queue.Empty:
                return

    def check_for_order_changes(self):
        self.order_manager.check_and_process_order_change_instructions()

    def process_message(self, message: FIXMessage) -> None:
        msg_type = message.get(fix.MsgType())
        if msg_type == fix.MsgType_IOI:
            self.process_ioi_message(message)
        elif msg_type == fix.MsgType_NewOrderSingle:
            self.process_reserve_request_message(message)
        elif msg_type == fix.MsgType_ExecutionReport:
            self.process_execution_report_message(message)

    def process_ioi_message(self, message: FIXMessage):
        uuid = message.get(fix.SenderSubID())
        ServerApplication.uuids_of_interest.add(uuid)
        uuid_orders = self.order_manager.get_orders_for_uuid(uuid)
        for order in uuid_orders:
            ServerApplication.create_order_message(MessageAction.NewOrder, order, True, True)

    def process_reserve_request_message(self, message: FIXMessage):
        order_id = message.get(fix.OrderID())
        current_qty = self.order_manager.get_order_shares(order_id)
        if current_qty is not None:
            qty_to_reserve = int(message.get(fix.OrderQty()))
            corrected_qty = current_qty - qty_to_reserve
            symbol = message.get(fix.Symbol())
            symbol_starts_with_z = symbol.startswith('Z')
            # Reject if the size requested is smaller than what's left
            if corrected_qty >= 0 and not symbol_starts_with_z:
                log('Rcvd APP', 'Reserve request, ACCEPTED')
                # Before sending the accept first send a 35=G with the reduced qty
                self.send_correct_message(order_id, corrected_qty)
                self.send_reserve_accept_message(message)
            else:
                text_message = f"symbol:{symbol} starts with a Z" if symbol_starts_with_z else \
                    f"not enough shares left. current:{current_qty} vs reserve:{qty_to_reserve}"
                log('Rcvd APP', f"Reserve request, REJECTED, because {text_message}")
                self.send_reserve_reject_message(message, text_message)
        else:
            log("ERROR!!!", f"Can't find qty for order_id:{order_id}")

    def process_execution_report_message(self, message: FIXMessage):
        # For now, only do something once we get the Fill or DFD
        if (message.get(fix.OrdStatus()) == fix.OrdStatus_DONE_FOR_DAY or
                message.get(fix.OrdStatus()) == fix.OrdStatus_FILLED):
            clordid = message.get(fix.ClOrdID())
            oms_order_id = self.oms_order_id_per_accepted_reserve_clordid.get(clordid,
                                                                              f'?unknown oms_order_id for clordid:{clordid}')
            # figure out the new qty
            cum_qty = int(message.get(fix.CumQty()))
            updated_qty = self.order_manager.update_order_shares(oms_order_id, -cum_qty)
            if updated_qty is not None:
                self.send_correct_message(oms_order_id, int(updated_qty))
            else:
                log('Rcvd APP', 'Error with order update.')

    def send_correct_message(self, order_id: str, corrected_qty: int = 0):
        correct_message = FIXApplication.get_latest_fix_message_per_oms_order_id(order_id)
        if correct_message:
            correct_message.set(fix.OrderQty(), str(corrected_qty))
            correct_message.set(fix.OrdStatus(), None)
            ServerApplication.create_order_message(MessageAction.ChangeOrder, correct_message, True, True)

    def send_reserve_accept_message(self, reserve_request_message: FIXMessage):
        reserve_accept_message = FIXMessage(reserve_request_message)
        reserve_accept_clordid = FIXApplication.get_next_clordid()
        oms_order_id = reserve_request_message.get(fix.OrderID())
        self.oms_order_id_per_accepted_reserve_clordid[reserve_accept_clordid] = oms_order_id
        log("!!!DEBUG!!!", f"Mapping reserve_accept_clordid:{reserve_accept_clordid} to oms_order_id:{oms_order_id}")
        # Only (un)set the fields that aren't already set in the reserve request
        (reserve_accept_message
         .set(fix.ClOrdID(), reserve_accept_clordid)
         .set(fix.HandlInst(), fix.HandlInst_MANUAL_ORDER_BEST_EXECUTION)
         .set(fix.OrdStatus(), fix.OrdStatus_NEW)
         .set(fix.Text(), f"Firm Up Order: {reserve_request_message.get(fix.OrderID())}")
         .set(fix.TimeInForce(), None)
         .set(fix.ExecBroker(), None)
         .set(fix.ClientID(), reserve_request_message.get(fix.ClOrdID()))
         )
        ServerApplication.create_order_message(MessageAction.NewOrder, reserve_accept_message, True, False)

    def send_reserve_reject_message(self, reserve_request_message: FIXMessage, text_message: str):
        reserve_reject_message = FIXMessage(reserve_request_message)
        # Only (un)set the fields that aren't already set in the reserve request
        (reserve_reject_message
         .set(fix.Currency(), FIXApplication.CURRENCY)
         .set(fix.ExecID(), FIXApplication.get_next_clordid())
         .set(fix.HandlInst(), fix.HandlInst_MANUAL_ORDER_BEST_EXECUTION)
         .set(fix.OrderQty(), "0")
         .set(fix.OrdStatus(), fix.OrdStatus_REJECTED)
         .set(fix.Text(), f"Can Not Firm Up Order: {text_message}")
         .set(fix.ExecBroker(), None)
         .set(fix.ClientID(), None)
         .set(fix.ExecType(), fix.ExecType_REJECTED)
         )
        ServerApplication.create_order_message(MessageAction.RejectOrder, reserve_reject_message, True, False)

    @staticmethod
    def send_message(message: fix.Message):
        fix.Session.sendToTarget(message, ServerApplication.session_id)

    @staticmethod
    def side_str_to_fix(side: str) -> int:
        if side in OrderManager.SIDES:
            return OrderManager.SIDES[side]
        else:
            return 0

    @staticmethod
    def is_uuid_of_interest(uuid: str) -> bool:
        return str(uuid) in ServerApplication.uuids_of_interest

    @staticmethod
    def create_order_message(action: MessageAction, message: Series | FIXMessage,
                             send_message: bool = False, save_message: bool = False) -> fix.Message:
        if isinstance(message, Series):
            # Initiated from the UI
            order_id = message['order_id']
            if action == MessageAction.NewOrder:
                clordid = FIXApplication.get_next_clordid()
                FIXApplication.set_latest_clordid_per_oms_order_id(order_id, clordid)
            else:
                clordid = FIXApplication.get_latest_clordid_per_oms_order_id(order_id)
                if not clordid:
                    log("!!!ERROR!!!", f"Can't find clordid for order_id:{order_id}")
            fix_string = ServerApplication.create_fix_string_from_series(message, clordid)

        else:
            # Initiated by receiving a message from the client
            order_id = message.get(fix.OrderID())
            fix_string = create_fix_string_from_dict(message.to_dict(), '|')

        # Weirdly enough BBG doesn't use tag41 and maintains the same tag11 thru 35=D/F's
        # if action == MessageAction.ChangeOrder or action == MessageAction.CancelOrder:
        #     latest_clordid = FIXApplication.get_latest_clordid_oms_per_order_id(order_id)
        #     fix_string += f" 41={latest_clordid}"

        message = string_to_message(action.value, fix_string)

        if send_message:
            ServerApplication.send_message(message)

        if save_message:
            FIXApplication.set_latest_fix_message_per_oms_order_id(order_id, FIXMessage.message_to_dict(message))

        return message

    @staticmethod
    def create_fix_string_from_series(order: Series, clordid: str) -> str:
        symbol = order['symbol']
        cusip = FIXApplication.KNOWN_SYMBOLS_BY_TICKER.get(symbol, f"??{symbol}??")

        side = ServerApplication.side_str_to_fix(order['side'])
        order_id = order['order_id']
        order_price = float(order['price'])
        if order_price > 0.0:
            order_type = fix.OrdType_LIMIT
        else:
            order_type = fix.OrdType_MARKET
        fix_string = '|'.join([
            f"11={clordid}",
            f"15={FIXApplication.CURRENCY}",
            f"21={fix.HandlInst_MANUAL_ORDER_BEST_EXECUTION}",
            f"22={fix.IDSource_CUSIP}",
            f"37={order_id}",
            f"38={order['shares']}",
            f"44={order_price:.2f}",
            f"40={order_type}",
            f"48={cusip}",
            f"50={order['uuid']}",
            f"54={side}",
            f"55={symbol}",
            f"59={fix.TimeInForce_DAY}",
            f"60={get_utc_transactime()}",
            f"100={FIXApplication.EX_DESTINATION}",
            #            f"115={???}",  # OnBehalfOfCompID
            #            f"116={???}",  # OnBehalfOfSubID
            #            f"128={???}",  # DeliverToCompID
        ])

        return fix_string
