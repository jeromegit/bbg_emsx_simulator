from typing import Dict

import quickfix as fix

from fix_application import string_to_message, message_to_string, timestamp, FIXApplication, \
    get_field_value, get_utc_transactime, message_to_dict


class ClientApplication(fix.Application):
    UUID = 1234
    EXEC_BROKER = 'ITG'
    EX_DESTINATION = 'US'
    session_id = None
    reserve_request_sent = False

    def onCreate(self, session_id):
        pass

    def onLogon(self, session_id):
        self.session_id = session_id
        print(
            f"\n{timestamp()} CLIENT Session {session_id} logged on.<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<")
        self.reserve_request_sent = False
        self.send_ioi_query(session_id)

    def onLogout(self, session_id):
        print(f"{timestamp()} CLIENT Session {session_id} logged out.>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

    def toAdmin(self, message, session_id):
        message = message_to_dict(message)
        msg_type = get_field_value(message, fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            print(f"{timestamp()} Sent ADMIN: {message_to_string(message)}")

    def fromAdmin(self, message, session_id):
        message = message_to_dict(message)
        msg_type = get_field_value(message, fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            print(f"{timestamp()} Rcvd ADMIN: {message_to_string(message)}")

    def toApp(self, message, session_id):
        message = message_to_dict(message)
        print(f"{timestamp()} Sent APP  : {message_to_string(message)}")

    def fromApp(self, message, session_id):
        #        print("!!!!!!!!!!!!!!!!!!!!!! fromApp !!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        message = message_to_dict(message)
        print(f"{timestamp()} Rcvd APP  : {message_to_string(message)}")
        self.process_message(message)

    def process_message(self, message: Dict[str, str]) -> None:
        msg_type = get_field_value(message, fix.MsgType())
        order_id = get_field_value(message, fix.OrderID())
        if (msg_type == fix.MsgType_NewOrderSingle or
                msg_type == fix.MsgType_OrderCancelReplaceRequest):
            FIXApplication.set_latest_fix_message_per_order_id(order_id, message)
        elif msg_type == fix.MsgType_OrderCancelRequest:
            FIXApplication.set_latest_fix_message_per_order_id(order_id, None)

    def send_ioi_query(self, session_id):
        message = string_to_message(fix.MsgType_IOI,
                                    f"23=na 28=N 55=NA 54=1 27=S 50={ClientApplication.UUID}")
        fix.Session.sendToTarget(message, session_id)

    def send_reserve_request(self, order_id: str):
        if self.reserve_request_sent:
            return

        latest_message = FIXApplication.get_latest_fix_message_per_order_id(order_id)
        if latest_message:
            order_id = get_field_value(latest_message, fix.OrderID())
            clordid = "ITGClOrdID:" + get_field_value(latest_message, fix.OrderID())
            message = string_to_message(fix.MsgType_NewOrderSingle, " ".join([
#                f"11={FIXApplication.get_next_clordid()}",
                f"11={clordid}",
                f"37={order_id}",
                f"38={get_field_value(latest_message, fix.OrderQty())}",
                f"40={get_field_value(latest_message, fix.OrdType())}",
                f"50={ClientApplication.UUID}",
                f"54={get_field_value(latest_message, fix.Side())}",
                f"55={get_field_value(latest_message, fix.Symbol())}",
                f"60={get_utc_transactime()}",
                f"76={ClientApplication.EXEC_BROKER}",
                f"100={ClientApplication.EX_DESTINATION}",
                f"109={order_id}",
                f"150={0}",  # ExecType: New/Ack
            ]))

            print(f"{timestamp()} Sending REQUEST message: {message_to_string(message)}")
            fix.Session.sendToTarget(message, self.session_id)

            self.reserve_request_sent = True
