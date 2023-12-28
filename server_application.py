import queue
from datetime import datetime
from typing import Tuple
from queue import Queue

import quickfix as fix
from fix_application import get_header_field_value, get_field_value, message_to_string, string_to_message
from order_manager import OrderManager


class ServerApplication(fix.Application):
    from_app_queue: Queue[Tuple[fix.Message, str]] = None
    order_manager = None

    def __init__(self):
        super().__init__()
        self.order_manager = OrderManager()
        self.from_app_queue = queue.Queue()
        self.base_clordid = datetime.now().strftime("%Y%m%d%H%M%S")
        self.current_clordid = 0

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
        print(f"SERVER: fromApp message:{message_to_string(message)}")
        #        self.from_app_queue.put((message, session_id))
        self.process_message(message, session_id)

    def get_next_clordid(self):
        self.current_clordid += 1
        return f"{self.base_clordid}{self.current_clordid:06}"

    def process_message_from_app_queue(self):
        if self.from_app_queue.not_empty:
            try:
                item = self.from_app_queue.get(block=True, timeout=1)
            except queue.Empty:
                return

    def process_message(self, message: fix.Message, session_id: str):
        msg_type = get_header_field_value(message, fix.MsgType())
        if msg_type == fix.MsgType_IOI:
            uuid = get_header_field_value(message, fix.SenderSubID())
            uuid_orders = self.order_manager.get_orders_for_uuid(uuid)
            for order in uuid_orders:
#                print(f"order:{order}")
                message = self.create_order_message(order)
                fix.Session.sendToTarget(message, session_id)

    def create_order_message(self, order):
        side = '1' if order['side'] == 'Buy' else '2'
        transact_time = datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")
        fix_string = f"11={self.get_next_clordid()} 50={order['uuid']} " + \
                     f"55={order['symbol']} 54={side} 38={order['shares']} 44={order['price']} " + \
                     f"21=3 40=2 60={transact_time}"

        message = string_to_message(fix.MsgType_NewOrderSingle, fix_string)
        print(f"Create order:{message_to_string(message)}")

        return message
