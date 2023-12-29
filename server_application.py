import queue
from datetime import datetime
from enum import Enum
from typing import Tuple, List, Set
from queue import Queue

import quickfix as fix
from pandas import Series

from fix_application import get_header_field_value, get_field_value, message_to_string, string_to_message
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
        ServerApplication.base_clordid = datetime.now().strftime("%Y%m%d%H%M%S")
        ServerApplication.current_clordid = 0

    def onCreate(self, session_id):
        pass

    def onLogon(self, session_id):
        print(f"SERVER Session {session_id} logged on.")

    def onLogout(self, session_id):
        print(f"SERVER Session {session_id} logged out.")

    def toAdmin(self, message, session_id):
        pass

    def fromAdmin(self, message, session_id):
        pass

    def toApp(self, message, session_id):
        pass

    def fromApp(self, message, session_id):
        ServerApplication.session_id = session_id
        print(f"SERVER: fromApp message:{message_to_string(message)}")
        #        self.from_app_queue.put((message, session_id))
        self.process_message(message, session_id)

    @staticmethod
    def get_next_clordid():
        ServerApplication.current_clordid += 1
        return f"{ServerApplication.base_clordid}{ServerApplication.current_clordid:06}"

    def process_message_from_app_queue(self):
        if self.from_app_queue.not_empty:
            try:
                item = self.from_app_queue.get(block=True, timeout=1)
            except queue.Empty:
                return

    def check_for_order_changes(self):
        self.order_manager.check_and_process_order_change_instructions()

    def process_message(self, message: fix.Message, session_id: str):
        msg_type = get_header_field_value(message, fix.MsgType())
        if msg_type == fix.MsgType_IOI:
            uuid = get_header_field_value(message, fix.SenderSubID())
            ServerApplication.uuids_of_interest.add(uuid)
            uuid_orders = self.order_manager.get_orders_for_uuid(uuid)
            for order in uuid_orders:
                #                print(f"order:{order}")
                message = ServerApplication.create_order_message(MessageAction.NewOrder, order)
                ServerApplication.send_message(message)
                fix.Session.sendToTarget(message, session_id)

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
        transact_time = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")
        fix_string = f"11={ServerApplication.get_next_clordid()} 50={order['uuid']} " + \
                     f"55={order['symbol']} 54={side} 38={order['shares']} 44={order['price']} " + \
                     f"21=3 40=2 60={transact_time}"

        message = string_to_message(action.value, fix_string)
        print(f"Created order:{message_to_string(message)}")

        return message
