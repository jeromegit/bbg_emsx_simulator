import pdb
from typing import List

import quickfix as fix
from quickfix import Message


class FIXApplication(fix.Application):

    def onCreate(self, sessionID):
        pass

    def onLogon(self, sessionID):
        print(f"Session {sessionID} logged on.")

    def onLogout(self, sessionID):
        print(f"Session {sessionID} logged out.")

    def toAdmin(self, message, sessionID):
        pass

    def fromAdmin(self, message, sessionID):
        pass

    def toApp(self, message, sessionID):
        pass

    def fromApp(self, message, sessionID):
        print(f"Received message:{message_to_string(message)}")


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
