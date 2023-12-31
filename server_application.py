import queue
from enum import Enum
from typing import Set, Dict, List

import quickfix as fix
from pandas import Series

from fix_application import message_to_string, string_to_message, FIXApplication, timestamp, \
    get_utc_transactime, get_field_value, message_to_dict, set_field_value, log

from order_manager import OrderManager


class MessageAction(Enum):
    NewOrder = fix.MsgType_NewOrderSingle
    ChangeOrder = fix.MsgType_OrderCancelReplaceRequest
    CancelOrder = fix.MsgType_OrderCancelRequest


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
        log('SERVER Session', f"{session_id} logged on.<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<", '\n')

    def onLogout(self, session_id):
        log('SERVER Session', f"{session_id} logged out.>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>", '\n')

    def toAdmin(self, message, session_id):
        message = message_to_dict(message)
        msg_type = get_field_value(message, fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            log('Sent ADMIN', message)

    def fromAdmin(self, message, session_id):
        message = message_to_dict(message)
        msg_type = get_field_value(message, fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            log('Rcvd ADMIN', message)

    def toApp(self, message, session_id):
        log('Sent APP', message)

    def fromApp(self, message, session_id):
        message = message_to_dict(message)
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

    def process_message(self, message: Dict[str, str]) -> None:
        msg_type = get_field_value(message, fix.MsgType())
        if msg_type == fix.MsgType_IOI:
            self.process_ioi_message(message)
        elif msg_type == fix.MsgType_NewOrderSingle:
            self.process_reserve_request_message(message)

    def process_ioi_message(self, message: Dict[str, str]):
        uuid = get_field_value(message, fix.SenderSubID())
        ServerApplication.uuids_of_interest.add(uuid)
        uuid_orders = self.order_manager.get_orders_for_uuid(uuid)
        for order in uuid_orders:
            ServerApplication.create_order_message(MessageAction.NewOrder, order, True, True)

    def process_reserve_request_message(self, message: Dict[str, str]):
        order_id = get_field_value(message, fix.OrderID())
        # odd/even order_id heuristic to decide whether to accept or reject request
        if int(order_id[-1]) % 2 == 0:
            # Before sending the accept first send a 35=G with the reduced qty
            qty_to_reserve = get_field_value(message, fix.OrderQty())
            self.send_correct_message(order_id, int(qty_to_reserve))

            self.send_reserve_accept_message(order_id, message)

    def send_correct_message(self, order_id: str, qty_to_reserve: int = 0):
        correct_message = FIXApplication.get_latest_fix_message_per_order_id(order_id)
        if correct_message:
            new_order_qty = int(get_field_value(correct_message, fix.OrderQty())) - qty_to_reserve
            set_field_value(correct_message, fix.OrderQty(), str(new_order_qty))
            ServerApplication.create_order_message(MessageAction.ChangeOrder, correct_message, True, False)

    def send_reserve_accept_message(self, order_id: str, reserve_request_message: Dict[str, str]):
        reserve_accept_message = FIXApplication.get_latest_fix_message_per_order_id(order_id)
        if reserve_accept_message:
            set_field_value(reserve_accept_message, fix.OrdStatus(), fix.OrdStatus_NEW)
            set_field_value(reserve_accept_message, fix.ClOrdID(),
                            get_field_value(reserve_request_message, fix.ClOrdID()))
            ServerApplication.create_order_message(MessageAction.NewOrder, reserve_accept_message, True, False)

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
    def create_order_message(action: MessageAction, order: Series | Dict[str, str],
                             send_message: bool = False, save_message: bool = False) -> fix.Message:
        if isinstance(order, Series):
            fix_string = ServerApplication.create_fix_string_from_series(order)
            order_id = order['order_id']
            clordid = FIXApplication.get_next_clordid()
            FIXApplication.set_latest_clordid_per_order_id(order_id, clordid)
        else:
            fix_string = ServerApplication.create_fix_string_from_dict(order)
            order_id = get_field_value(order, fix.OrderID())

        # Weirdly enough BBG doesn't use tag41 and maintains the same tag11 thru 35=D/F's
        # if action == MessageAction.ChangeOrder or action == MessageAction.CancelOrder:
        #     latest_clordid = FIXApplication.get_latest_clordid_per_order_id(order_id)
        #     fix_string += f" 41={latest_clordid}"

        message = string_to_message(action.value, fix_string)
        #        print(f"!!!!!!!!!!!!!!!!!Created order:{message_to_string(message)}\nfrom{fix_string}")

        if send_message:
            ServerApplication.send_message(message)

        if save_message:
            FIXApplication.set_latest_fix_message_per_order_id(order_id, message_to_dict(message))

        return message

    @staticmethod
    def create_fix_string_from_series(order: Series) -> str:
        side = ServerApplication.side_str_to_fix(order['side'])
        clordid = FIXApplication.get_next_clordid()
        order_id = order['order_id']
        currency = 'USD'
        order_price = float(order['price'])
        if order_price > 0.0:
            order_type = fix.OrdType_LIMIT
        else:
            order_type = fix.OrdType_MARKET
        fix_string = ' '.join([
            f"11={clordid}",
            f"15={currency}",
            f"21={fix.HandlInst_MANUAL_ORDER_BEST_EXECUTION}",
            f"37={order_id}",
            f"38={order['shares']}",
            f"44={order_price:.2f}",
            f"40={order_type}",
            f"50={order['uuid']}",
            f"54={side}",
            f"55={order['symbol']}",
            f"59={fix.TimeInForce_DAY}",
            f"60={get_utc_transactime()}",
            f"100={FIXApplication.EX_DESTINATION}",
            #            f"115={???}",  # OnBehalfOfCompID
            #            f"116={???}",  # OnBehalfOfSubID
            #            f"128={???}",  # DeliverToCompID
        ])

        return fix_string

    @staticmethod
    def create_fix_string_from_dict(order: Dict[str, str]) -> str:
        tag_value_pairs: List[str] = []
        for tag, value in order.items():
            if tag not in FIXApplication.SESSION_LEVEL_TAGS:
                if tag == fix.TransactTime().getField():  # tag60
                    value = get_utc_transactime()
                tag_value_pairs.append(f"{tag}={value}")

        fix_string = ' '.join(tag_value_pairs)

        return fix_string
