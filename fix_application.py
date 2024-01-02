import threading
from datetime import datetime, timedelta
from typing import Dict, Union, Any, Set

import quickfix as fix
from quickfix import Message

self_lock = threading.Lock()


class FIXApplication(fix.Application):
    SESSION_LEVEL_TAGS: Set[str] = {str(tag) for tag in [8, 9, 10, 34, 35, 49, 52, 56]}
    KNOWN_SYMBOLS_BY_TICKER: Dict[str, str] = {
        "BOOM": "23291C10",
        "CAKE": "16307210",
        "FUN": "15018510",
        "HEINY": "42301230",
        "HOG": "41282210",
        "LUV": "84474110",
        "PLAY": "23833710",
        "ROCK": "37468910",
        "ZEUS": "68162K10",
        "ZVZZT": "0ZVZZT88",
    }
    KNOWN_SYMBOLS_BY_CUSIP: Dict[str, str] = {v: k for k, v in KNOWN_SYMBOLS_BY_TICKER.items()}

    EXEC_BROKER = 'ITGI'
    LAST_MARKET = 'ITGI'
    EX_DESTINATION = 'US'
    UUID = 1234

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
    def set_latest_clordid_per_order_id(order_id: str, clordid: Union[str, None]) -> None:
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
    def get_latest_fix_message_per_order_id(order_id: str, issue_error: bool = True) -> Dict[str, str] | None:
        with self_lock:
            latest_message = FIXApplication.latest_fix_message_per_order_id.get(order_id, None)
            if latest_message:
                return latest_message
            else:
                if issue_error:
                    print(f"ERROR: Can't find a FIX message for order_id:{order_id}")
                return None


def string_to_message(message_type: int, fix_string: str, separator: str = ' ') -> Message:
    message = fix.Message()

    header = message.getHeader()
    header.setField(fix.BeginString(fix.BeginString_FIX42))
    header.setField(fix.MsgType(message_type))

    tag_value_pairs = fix_string.split(separator)
    for pair in tag_value_pairs:
        try:
            tag, value = pair.split("=")
        except Exception as e:
            print(f"ERROR! Can't extract key/value from:{pair} with exception:{e}")
            continue
        if tag not in FIXApplication.SESSION_LEVEL_TAGS:
            message.setField(int(tag), value)

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


def set_field_value(message: Dict[str, str], fix_field_obj: Any, field_value: str | None) -> None:
    fix_key_as_str = str(fix_field_obj.getField())
    if field_value is None:
        if fix_key_as_str in message:
            del message[fix_key_as_str]
    else:
        message[fix_key_as_str] = field_value


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def get_utc_transactime(offset_in_secs: int = 0) -> str:
    utc_time = datetime.utcnow()
    if offset_in_secs:
        utc_time += timedelta(seconds=offset_in_secs)

    return utc_time.strftime("%Y%m%d-%H:%M:%S.%f")


def log(msg_type: str, message: str | Dict[str, str] | fix.Message | None = None, pre_timestamp: str = '') -> None:
    if message == None:
        message = ''
    elif isinstance(message, dict) or isinstance(message, fix.Message):
        message = message_to_string(message)

    print(f"{pre_timestamp}{timestamp()} {msg_type:<11}: {message}")
