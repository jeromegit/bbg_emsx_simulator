import queue
from enum import Enum
from typing import Set

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

    def __init__(self):
        super().__init__()
        self.order_manager = OrderManager()
        self.from_app_queue = queue.Queue()

    def onCreate(self, session_id):
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
        msg_type = message.get_field_value(fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            log('Sent ADMIN', message)

    def fromAdmin(self, message, session_id):
        message = FIXMessage(message)
        msg_type = message.get_field_value(fix.MsgType())
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
        msg_type = message.get_field_value(fix.MsgType())
        if msg_type == fix.MsgType_IOI:
            self.process_ioi_message(message)
        elif msg_type == fix.MsgType_NewOrderSingle:
            self.process_reserve_request_message(message)
        elif msg_type == fix.MsgType_ExecutionReport:
            self.process_execution_report_message(message)

    def process_ioi_message(self, message: FIXMessage):
        uuid = message.get_field_value(fix.SenderSubID())
        ServerApplication.uuids_of_interest.add(uuid)
        uuid_orders = self.order_manager.get_orders_for_uuid(uuid)
        for order in uuid_orders:
            ServerApplication.create_order_message(MessageAction.NewOrder, order, True, True)

    def process_reserve_request_message(self, message: FIXMessage):
        order_id = message.get_field_value(fix.OrderID())
        # odd/even order_id heuristic to decide whether to accept or reject request
        if int(order_id[-1]) % 2 == 0:
            # Before sending the accept first send a 35=G with the reduced qty
            latest_message = FIXApplication.get_latest_fix_message_per_order_id(order_id)
            if latest_message:
                qty_to_reserve = int(message.get_field_value(fix.OrderQty()))
                corrected_qty = int(latest_message.get_field_value(fix.OrderQty())) - qty_to_reserve
                self.send_correct_message(order_id, corrected_qty)

                self.send_reserve_accept_message(message)
        else:
            latest_message = FIXApplication.get_latest_fix_message_per_order_id(order_id)
            if latest_message:
                self.send_reserve_reject_message(message)

    def process_execution_report_message(self, message: FIXMessage):
        # For now, only do something once we get the DFD
        if message.get_field_value(fix.OrdStatus()) == fix.OrdStatus_DONE_FOR_DAY:
            order_id = message.get_field_value(fix.OrderID())
            # figure out the new qty
            cum_qty = int(message.get_field_value(fix.CumQty()))
            order_qty = int(message.get_field_value(fix.OrderQty()))
            new_qty = order_qty - cum_qty
            self.send_correct_message(order_id, int(new_qty))
            # TODO: update csv file

    def send_correct_message(self, order_id: str, corrected_qty: int = 0):
        correct_message = FIXApplication.get_latest_fix_message_per_order_id(order_id)
        if correct_message:
            correct_message.set_field_value(fix.OrderQty(), str(corrected_qty))
            correct_message.set_field_value(fix.OrdStatus(), None)
            ServerApplication.create_order_message(MessageAction.ChangeOrder, correct_message, True, True)

    def send_reserve_accept_message(self, reserve_request_message: FIXMessage):
        reserve_accept_message = FIXMessage(reserve_request_message)
        # Only (un)set the fields that aren't already set in the reserve request
        (reserve_accept_message
         .set_field_value(fix.ClOrdID(), FIXApplication.get_next_clordid())
         .set_field_value(fix.HandlInst(), fix.HandlInst_MANUAL_ORDER_BEST_EXECUTION)
         .set_field_value(fix.OrdStatus(), fix.OrdStatus_NEW)
         .set_field_value(fix.Text(), f"Firm Up Order: {reserve_request_message.get_field_value(fix.OrderID())}")
         .set_field_value(fix.TimeInForce(), None)
         .set_field_value(fix.ExecBroker(), None)
         .set_field_value(fix.ClientID(), reserve_request_message.get_field_value(fix.ClOrdID()))
         )
        ServerApplication.create_order_message(MessageAction.NewOrder, reserve_accept_message, True, False)

    def send_reserve_reject_message(self, reserve_request_message: FIXMessage):
        reserve_reject_message = FIXMessage(reserve_request_message)
        # Only (un)set the fields that aren't already set in the reserve request
        (reserve_reject_message
         .set_field_value(fix.Currency(), FIXApplication.CURRENCY)
         .set_field_value(fix.ExecID(), FIXApplication.get_next_clordid())
         .set_field_value(fix.HandlInst(), fix.HandlInst_MANUAL_ORDER_BEST_EXECUTION)
         .set_field_value(fix.OrderQty(), "0")
         .set_field_value(fix.OrdStatus(), fix.OrdStatus_REJECTED)
         .set_field_value(fix.Text(), "Can Not Firm Up Order: for some odd reason...")
         .set_field_value(fix.ExecBroker(), None)
         .set_field_value(fix.ClientID(), None)
         .set_field_value(fix.ExecType(), fix.ExecType_REJECTED)
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
            fix_string = ServerApplication.create_fix_string_from_series(message)
            order_id = message['order_id']
            clordid = FIXApplication.get_next_clordid()
            FIXApplication.set_latest_clordid_per_order_id(order_id, clordid)
        else:
            # Initiated by receiving a message from the client
            order_id = message.get_field_value(fix.OrderID())
            fix_string = create_fix_string_from_dict(message.to_dict(), '|')

        # Weirdly enough BBG doesn't use tag41 and maintains the same tag11 thru 35=D/F's
        # if action == MessageAction.ChangeOrder or action == MessageAction.CancelOrder:
        #     latest_clordid = FIXApplication.get_latest_clordid_per_order_id(order_id)
        #     fix_string += f" 41={latest_clordid}"

        message = string_to_message(action.value, fix_string)

        if send_message:
            ServerApplication.send_message(message)

        if save_message:
            FIXApplication.set_latest_fix_message_per_order_id(order_id, FIXMessage.message_to_dict(message))

        return message

    @staticmethod
    def create_fix_string_from_series(order: Series) -> str:
        symbol = order['symbol']
        cusip = FIXApplication.KNOWN_SYMBOLS_BY_TICKER.get(symbol, f"??{symbol}??")

        side = ServerApplication.side_str_to_fix(order['side'])
        clordid = FIXApplication.get_next_clordid()
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
