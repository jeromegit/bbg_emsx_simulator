import threading
from datetime import datetime, timedelta
from typing import Dict, Union, Set, Any, Optional, List

import quickfix as fix
from quickfix import Message

self_lock = threading.Lock()


class FIXMessage():
    def __init__(self, message: Dict[str, str] | Message | Optional['FIXMessage'] = None):
        if message:
            if isinstance(message, Message):
                self.message_dict = FIXMessage.message_to_dict(message)
            elif isinstance(message, FIXMessage):
                self.message_dict = dict(message.message_dict)
            else:
                self.message_dict = dict(message)
        else:
            self.message_dict = dict()

    def get(self, fix_field_obj: Any) -> str:
        fix_key_as_str = str(fix_field_obj.getField())
        field_value = self.message_dict.get(fix_key_as_str, None)

        return field_value

    def set(self, fix_field_obj: Any, field_value: str | None) -> Optional['FIXMessage']:
        fix_key_as_str = str(fix_field_obj.getField())
        if field_value is None:
            if fix_key_as_str in self.message_dict:
                del self.message_dict[fix_key_as_str]
        else:
            self.message_dict[fix_key_as_str] = field_value

        return self

    def to_dict(self):
        return dict(self.message_dict)

    def __str__(self):
        return '|'.join([f"{k}={v}" for k, v in self.message_dict.items()])

    @staticmethod
    def message_to_dict(message: Message) -> Dict[str, str]:
        message_dict: Dict[str, str] = {}
        string_with_ctrla = message.toString()
        kv_pairs = string_with_ctrla.split('\x01')
        for kv_pair in kv_pairs:
            if '=' in kv_pair:
                key, value = kv_pair.split('=')
                message_dict[key] = value

        return message_dict

    @staticmethod
    def message_to_string(message: fix.Message | Dict[str, str]) -> str:
        if isinstance(message, fix.Message):
            string_with_ctrla = message.toString()
            string = string_with_ctrla.replace('\x01', '|')
        elif isinstance(message, dict):
            string = '|'.join([f"{k}={v}" for k, v in message.items()])

        return string


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
    CURRENCY = 'USD'

    latest_clordid_per_oms_order_id: Dict[str, str] = {}
    latest_fix_message_per_oms_order_id: Dict[str, FIXMessage] = {}
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
        print(f"Received message:{FIXMessage(message)}")

    @staticmethod
    def get_next_clordid():
        FIXApplication.current_clordid += 1
        return f"{FIXApplication.base_clordid}{FIXApplication.current_clordid:06}"

    @staticmethod
    def set_latest_clordid_per_oms_order_id(order_id: str, clordid: Union[str, None]) -> None:
        if clordid:
            FIXApplication.latest_clordid_per_oms_order_id[order_id] = clordid
        else:
            # since clordid is None, remove entry if exists
            if order_id in FIXApplication.latest_clordid_per_oms_order_id:
                FIXApplication.latest_clordid_per_oms_order_id.pop(order_id)

    @staticmethod
    def get_latest_clordid_per_oms_order_id(order_id: str) -> Union[str, None]:
        return FIXApplication.latest_clordid_per_oms_order_id.get(order_id, None)

    @staticmethod
    def set_latest_fix_message_per_oms_order_id(order_id: str,
                                                message: Union[Dict[str, str], FIXMessage, None]) -> None:
        order_id = str(order_id)
        with self_lock:
            if message:
                if isinstance(message, dict):
                    message = FIXMessage(message)
                FIXApplication.latest_fix_message_per_oms_order_id[order_id] = message
            else:
                # since message is None, remove entry if exists
                if order_id in FIXApplication.latest_fix_message_per_oms_order_id:
                    FIXApplication.latest_fix_message_per_oms_order_id.pop(order_id)

    @staticmethod
    def get_latest_fix_message_per_oms_order_id(oms_order_id: str, issue_error: bool = True) -> FIXMessage | None:
        with self_lock:
            latest_message = FIXApplication.latest_fix_message_per_oms_order_id.get(oms_order_id, None)
            if latest_message:
                return latest_message
            else:
                if issue_error:
                    print(f"ERROR: Can't find a FIX message for order_id:{oms_order_id}. {FIXApplication.latest_fix_message_per_oms_order_id}")
                return None


def string_to_message(message_type: int, fix_string: str, separator: str = '|') -> Message:
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


def create_fix_string_from_dict(message: Dict[str, str], separator: str = '|') -> str:
    tag_value_pairs: List[str] = []
    for tag, value in message.items():
        if tag not in FIXApplication.SESSION_LEVEL_TAGS:
            if tag == fix.TransactTime().getField():  # tag60
                value = get_utc_transactime()
            tag_value_pairs.append(f"{tag}={value}")

    fix_string = separator.join(tag_value_pairs)

    return fix_string


def get_header_field_value(msg, fobj) -> Union[str, None]:
    if msg.getHeader().isSetField(fobj.getField()):
        msg.getHeader().getField(fobj)
        return fobj.getValue()
    else:
        return None


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]


def get_utc_transactime(offset_in_secs: int = 0) -> str:
    utc_time = datetime.utcnow()
    if offset_in_secs:
        utc_time += timedelta(seconds=offset_in_secs)

    return utc_time.strftime("%Y%m%d-%H:%M:%S.%f")


def log(msg_type: str, message: str | Dict[str, str] | fix.Message | FIXMessage | None = None,
        pre_timestamp: str = '') -> None:
    if message == None:
        message = ''
    elif isinstance(message, dict) or isinstance(message, fix.Message):
        message = FIXMessage(message)

    print(f"{pre_timestamp}{timestamp()} {msg_type:<11}: {message}")
