import quickfix as fix
from fix_application import string_to_message, message_to_string, timestamp


class ClientApplication(fix.Application):
    UUID = 1234

    def onCreate(self, session_id):
        pass

    def onLogon(self, session_id):
        print(f"CLIENT Session {session_id} logged on.")
        self.send_ioi_query(session_id)

    def onLogout(self, session_id):
        print(f"CLIENT Session {session_id} logged out.")

    def toAdmin(self, message, session_id):
        pass

    def fromAdmin(self, message, session_id):
        pass

    def toApp(self, message, session_id):
        pass

    def fromApp(self, message, session_id):
        print(f"{timestamp()} Received message: {message_to_string(message)}")

    def send_ioi_query(self, session_id):
        message = string_to_message(fix.MsgType_IOI, f"23=na 28=N 55=NA 54=1 27=S 50={ClientApplication.UUID}")
        fix.Session.sendToTarget(message, session_id)

    def send_reserve_request(self, session_id):
        # 35=D
        # 50=955663
        # 55=**
        # 54=2
        # 38=30006
        # 11=ITGClOrdID:211710S4096
        # 59=0
        # 60=20231201-18:49:48
        # 76=ITG
        # 40=1
        # 37=211710S4096
        # 150=0
        # 109=211710S4096
        # 100=US
        # 10=054
        #
        message = string_to_message(fix.MsgType_NewOrderSingle,
                                    f"50={ClientApplication.UUID} 55=CAKE 54=2 38=1000 ")
        fix.Session.sendToTarget(message, session_id)
