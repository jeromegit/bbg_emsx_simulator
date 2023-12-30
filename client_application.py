import copy
import threading
from datetime import datetime
from typing import Dict, Union, Any

import quickfix as fix
from quickfix import Message

from fix_application import string_to_message, message_to_string, timestamp, get_header_field_value, FIXApplication, \
    get_field_value, get_utc_transactime, message_to_dict

self_lock = threading.Lock()


class ClientApplication(fix.Application):
    UUID = 1234
    EXEC_BROKER = 'ITG'
    EX_DESTINATION = 'US'
    latest_fix_message_per_order_id: Dict[str, Dict[str, str]] = {}
    session_id = None
    reserve_request_sent = False

    def onCreate(self, session_id):
        pass

    def onLogon(self, session_id):
        self.session_id = session_id
        print(f"CLIENT Session {session_id} logged on.")
        self.send_ioi_query(session_id)

    def onLogout(self, session_id):
        print(f"CLIENT Session {session_id} logged out.")

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

    def process_message(self, message: fix.Message) -> None:
        msg_type = get_header_field_value(message, fix.MsgType())
        order_id = get_field_value(message, fix.OrderID())
        if (msg_type == fix.MsgType_NewOrderSingle or
                msg_type == fix.MsgType_OrderCancelReplaceRequest):
            self.set_latest_fix_message_per_order_id(order_id, message)
        elif msg_type == fix.MsgType_OrderCancelRequest:
            self.set_latest_fix_message_per_order_id(order_id, None)

    def send_ioi_query(self, session_id):
        message = string_to_message(fix.MsgType_IOI,
                                    f"23=na 28=N 55=NA 54=1 27=S 50={ClientApplication.UUID}")
        fix.Session.sendToTarget(message, session_id)

    def send_reserve_request(self, order_id):
        if self.reserve_request_sent:
            return

        latest_message = self.get_latest_fix_message_per_order_id(order_id)
        if latest_message:
            order_id = self.get_field_value(latest_message, fix.OrderID())
            message = string_to_message(fix.MsgType_NewOrderSingle, " ".join([
                f"11={FIXApplication.get_next_clordid()}",
                f"37={order_id}",
                f"38={self.get_field_value(latest_message, fix.OrderQty())}",
                f"40={self.get_field_value(latest_message, fix.OrdType())}",
                f"50={ClientApplication.UUID}",
                f"54={self.get_field_value(latest_message, fix.Side())}",
                f"55={self.get_field_value(latest_message, fix.Symbol())}",
                f"60={get_utc_transactime()}",
                f"76={ClientApplication.EXEC_BROKER}",
                f"100={ClientApplication.EX_DESTINATION}",
                f"109={order_id}",
                f"150={0}",  # ExecType: New/Ack
            ]))

            print(f"{timestamp()} Sending REQUEST message: {message_to_string(message)}")
            fix.Session.sendToTarget(message, self.session_id)

            self.reserve_request_sent = True

    def set_latest_fix_message_per_order_id(self, order_id: str, message: Union[Message, None]) -> None:
        with self_lock:
            if message:
                self.latest_fix_message_per_order_id[order_id] = message_to_dict(message)
            else:
                # since message is None, remove entry if exists
                if order_id in self.latest_fix_message_per_order_id:
                    self.latest_fix_message_per_order_id.pop(order_id)

    def get_latest_fix_message_per_order_id(self, order_id: str) -> Message | None:
        with self_lock:
            return self.latest_fix_message_per_order_id.get(order_id, None)

    def get_field_value(self, message_dict:Dict[str, str], fix_field_obj:Any)->str:
        fix_key_as_str = str(fix_field_obj.getField())
        field_value = message_dict.get(fix_key_as_str, None)

        return field_value

