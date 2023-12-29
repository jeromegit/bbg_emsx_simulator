from datetime import datetime
from typing import Dict

import quickfix as fix
from quickfix import Message


class FIXApplication(fix.Application):
    latest_clordid_per_order_id: Dict[str, str] = {}

    def onCreate(self, session_id):
        pass

    def onLogon(self, session_id):
        print(f"Session {session_id} logged on.")

    def onLogout(self, session_id):
        print(f"Session {session_id} logged out.")

    def toAdmin(self, message, session_id):
        pass

    def fromAdmin(self, message, session_id):
        pass

    def toApp(self, message, session_id):
        pass

    def fromApp(self, message, session_id):
        print(f"Received message:{message_to_string(message)}")

    @staticmethod
    def set_latest_clordid_per_order_id(order_id: str, clordid: str) -> str:
        FIXApplication.latest_clordid_per_order_id[order_id] = clordid

    @staticmethod
    def get_latest_clordid_per_order_id(order_id: str) -> str:
        return FIXApplication.latest_clordid_per_order_id.get(order_id, None)


def string_to_message(message_type: int, fix_string: str, separator: str = ' ') -> Message:
    message = fix.Message()

    header = message.getHeader()
    header.setField(fix.BeginString(fix.BeginString_FIX42))
    header.setField(fix.MsgType(message_type))

    tag_value_pairs = fix_string.split(separator)
    for pair in tag_value_pairs:
        tag, value = pair.split("=")
        message.setField(int(tag), value)

    return message


def message_to_string(message: Message) -> str:
    string_with_ctrla = message.toString()
    string = string_with_ctrla.replace('\x01', '|')

    return string


def get_header_field_value(msg, fobj):
    if msg.getHeader().isSetField(fobj.getField()):
        msg.getHeader().getField(fobj)
        return fobj.getValue()
    else:
        return None


def get_field_value(msg, fobj):
    if msg.isSetField(fobj.getField()):
        msg.getField(fobj)
        return fobj.getValue()
    else:
        return None


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
