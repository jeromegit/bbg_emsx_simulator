import quickfix as fix
from fix_application import string_to_message, message_to_string


class ClientApplication(fix.Application):
    def onCreate(self, sessionID):
        pass

    def onLogon(self, sessionID):
        print(f"CLIENT Session {sessionID} logged on.")
        self.send_ioi_query(sessionID)

    def onLogout(self, sessionID):
        print(f"CLIENT Session {sessionID} logged out.")

    def toAdmin(self, message, sessionID):
        pass

    def fromAdmin(self, message, sessionID):
        pass

    def toApp(self, message, sessionID):
        pass

    def fromApp(self, message, sessionID):
        print(f"CLIENT Received message: {message_to_string(message)}")

    def send_ioi_query(self, sessionID):
        uuid = 1234
        message = string_to_message(fix.MsgType_IOI, f"23=na 28=N 55=NA 54=1 27=S 50={uuid}")
        fix.Session.sendToTarget(message, sessionID)

