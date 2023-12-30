import queue
from datetime import datetime
from enum import Enum
from typing import Tuple, Set
from queue import Queue

import quickfix as fix
from pandas import Series

from fix_application import get_header_field_value, message_to_string, string_to_message, FIXApplication, timestamp, \
    get_utc_transactime

from order_manager import OrderManager


class MessageAction(Enum):
    NewOrder = fix.MsgType_NewOrderSingle
    ChangeOrder = fix.MsgType_OrderCancelReplaceRequest
    CancelOrder = fix.MsgType_OrderCancelRequest


class ServerApplication(fix.Application):
    from_app_queue: Queue[Tuple[fix.Message, str]] = None
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
        print(f"SERVER Session {session_id} logged on.")

    def onLogout(self, session_id):
        print(f"SERVER Session {session_id} logged out.")

    def toAdmin(self, message, session_id):
        msg_type = get_header_field_value(message, fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            print(f"{timestamp()} Sent ADMIN message: {message_to_string(message)}")

    def fromAdmin(self, message, session_id):
        msg_type = get_header_field_value(message, fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            print(f"{timestamp()} Rcvd ADMIN message: {message_to_string(message)}")

    def toApp(self, message, session_id):
        print(f"{timestamp()} Sent APP message: {message_to_string(message)}")

    def fromApp(self, message, session_id):
        print(f"{timestamp()} Rcvd APP message: {message_to_string(message)}")
        self.process_message(message)

    def process_message_from_app_queue(self):
        if self.from_app_queue.not_empty:
            try:
                self.from_app_queue.get(block=True, timeout=1)
            except queue.Empty:
                return

    def check_for_order_changes(self):
        self.order_manager.check_and_process_order_change_instructions()

    def process_message(self, message: fix.Message)->None:
        msg_type = get_header_field_value(message, fix.MsgType())
        if msg_type == fix.MsgType_IOI:
            uuid = get_header_field_value(message, fix.SenderSubID())
            ServerApplication.uuids_of_interest.add(uuid)
            uuid_orders = self.order_manager.get_orders_for_uuid(uuid)
            for order in uuid_orders:
                #                print(f"order:{order}")
                message = ServerApplication.create_order_message(MessageAction.NewOrder, order)
                ServerApplication.send_message(message)

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
    def create_order_message(action: MessageAction, order: Series) -> fix.Message:
        side = ServerApplication.side_str_to_fix(order['side'])
        clordid = FIXApplication.get_next_clordid()
        order_id = order['order_id']
        fix_string = f"11={clordid} 50={order['uuid']} 37={order_id} " + \
                     f"55={order['symbol']} 54={side} 38={order['shares']} 44={order['price']:.2f} " + \
                     f"21=3 40=2 60={get_utc_transactime()}"
        if action == MessageAction.ChangeOrder or action == MessageAction.CancelOrder:
            latest_clordid = FIXApplication.get_latest_clordid_per_order_id(order_id)
            fix_string += f" 41={latest_clordid}"

        FIXApplication.set_latest_clordid_per_order_id(order_id, clordid)

        message = string_to_message(action.value, fix_string)
        # print(f"Created order:{message_to_string(message)}")

        return message
