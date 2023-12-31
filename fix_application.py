import threading
from datetime import datetime
from typing import Dict, Union, Any, Set

import quickfix as fix
from quickfix import Message

self_lock = threading.Lock()


class FIXApplication(fix.Application):
    SESSION_LEVEL_TAGS: Set[str] = {str(tag) for tag in [8, 9, 10, 34, 35, 49, 52, 56]}

    latest_clordid_per_order_id: Dict[str, str] = {}
    latest_fix_message_per_order_id: Dict[str, Dict[str, str]] = {}
    base_clordid = datetime.now().strftime("%Y%m%d%H%M%S")
    current_clordid = 0

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
    def get_next_clordid():
        FIXApplication.current_clordid += 1
        return f"{FIXApplication.base_clordid}{FIXApplication.current_clordid:06}"

    @staticmethod
    def set_latest_clordid_per_order_id(order_id: str, clordid: Union[str, None]) -> str:
        if clordid:
            FIXApplication.latest_clordid_per_order_id[order_id] = clordid
        else:
            # since clordid is None, remove entry if exists
            if order_id in FIXApplication.latest_clordid_per_order_id:
                FIXApplication.latest_clordid_per_order_id.pop(order_id)

    @staticmethod
    def get_latest_clordid_per_order_id(order_id: str) -> Union[str, None]:
        return FIXApplication.latest_clordid_per_order_id.get(order_id, None)

    @staticmethod
    def set_latest_fix_message_per_order_id(order_id: str, message: Union[Dict[str, str], None]) -> None:
        with self_lock:
            if message:
                FIXApplication.latest_fix_message_per_order_id[order_id] = message
            else:
                # since message is None, remove entry if exists
                if order_id in FIXApplication.latest_fix_message_per_order_id:
                    FIXApplication.latest_fix_message_per_order_id.pop(order_id)

    @staticmethod
    def get_latest_fix_message_per_order_id(order_id: str) -> Dict[str, str] | None:
        with self_lock:
            return FIXApplication.latest_fix_message_per_order_id.get(order_id, None)


def string_to_message(message_type: int, fix_string: str, separator: str = ' ') -> Message:
    message = fix.Message()

    header = message.getHeader()
    header.setField(fix.BeginString(fix.BeginString_FIX42))
    header.setField(fix.MsgType(message_type))

    tag_value_pairs = fix_string.split(separator)
    for pair in tag_value_pairs:
        tag, value = pair.split("=")
        if tag not in FIXApplication.SESSION_LEVEL_TAGS:
            message.setField(int(tag), value)
#            print(f"{tag}={value} -> {message_to_string(message)}")

    return message


def message_to_dict(message: Message) -> Dict[str, str]:
    message_dict: Dict[str, str] = {}
    string_with_ctrla = message.toString()
    kv_pairs = string_with_ctrla.split('\x01')
    for kv_pair in kv_pairs:
        if '=' in kv_pair:
            key, value = kv_pair.split('=')
            message_dict[key] = value

    return message_dict


def message_to_string(message: fix.Message | Dict[str, str]) -> str:
    if isinstance(message, fix.Message):
        string_with_ctrla = message.toString()
        string = string_with_ctrla.replace('\x01', '|')
    else:
        string = '|'.join([f"{k}={v}" for k, v in message.items()])

    return string


def get_header_field_value(msg, fobj) -> Union[str, None]:
    if msg.getHeader().isSetField(fobj.getField()):
        msg.getHeader().getField(fobj)
        return fobj.getValue()
    else:
        return None


def get_field_value(message: Dict[str, str], fix_field_obj: Any) -> str:
    fix_key_as_str = str(fix_field_obj.getField())
    field_value = message.get(fix_key_as_str, None)

    return field_value


def set_field_value(message: Dict[str, str], fix_field_obj: Any, field_value: str) -> None:
    fix_key_as_str = str(fix_field_obj.getField())
    message[fix_key_as_str] = field_value


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def get_utc_transactime() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H:%M:%S.%f")
