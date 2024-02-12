import queue
from enum import Enum
from typing import Dict, Union

import quickfix as fix

from fix_application import FIXApplication, FIXMessage, string_to_message, get_utc_transactime, log


class ExecutionReportType(Enum):
    NewAck = fix.OrdStatus_NEW
    Filled = fix.OrdStatus_FILLED
    DFD = fix.OrdStatus_DONE_FOR_DAY


class ClientApplication(fix.Application):
    session_id = None
    reserve_request_sent = False
    reserve_request_accepted = False
    dfd_sent = False
    accepted_reserve_clordid_per_oms_order_id: Dict[str, str] = dict()

    def __init__(self):
        super().__init__()
        self.from_app_queue = queue.Queue()
        self.from_app_received_msgs = []

    def onCreate(self, session_id):
        pass

    def onLogon(self, session_id):
        self.session_id = session_id
        log('CLIENT Session', f"{session_id} logged on.<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<", '\n')
        self.reserve_request_sent = False
        self.reserve_request_accepted = False
        self.dfd_sent = False

    def onLogout(self, session_id):
        log('CLIENT Session', f"{session_id} logged out.>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")

    def toAdmin(self, message, session_id):
        message = FIXMessage(message)
        msg_type = message.get(fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            log('Sent ADMIN', message)

    def fromAdmin(self, message, session_id):
        message = FIXMessage(message)
        msg_type = message.get(fix.MsgType())
        if msg_type != fix.MsgType_Heartbeat:
            log('Rcvd ADMIN', message)

    def toApp(self, message, session_id):
        log('Sent APP', message)

    def fromApp(self, message, session_id):
        message = FIXMessage(message)
        log('Rcvd APP', message)
        self.from_app_queue.put(message)
        self.process_message(message)

    def process_message(self, message: FIXMessage) -> None:
        msg_type = message.get(fix.MsgType())
        oms_order_id = message.get(fix.OrderID())
        if msg_type == fix.MsgType_NewOrderSingle:
            #                msg_type == fix.MsgType_OrderCancelReplaceRequest):
            if message.get(fix.OrdStatus()) == fix.OrdStatus_NEW:
                self.reserve_request_accepted = True
                clordid = message.get(fix.ClOrdID())
                log('Rcvd APP', f'Reserve request, ACCEPTED (on clordid:{clordid})')
                self.accepted_reserve_clordid_per_oms_order_id[oms_order_id] = clordid
            else:
                FIXApplication.set_latest_fix_message_per_oms_order_id(oms_order_id, message)

        elif message.get(fix.OrdStatus()) == fix.OrdStatus_REJECTED:
            log('Rcvd APP', 'Reserve request, REJECTED')

        elif msg_type == fix.MsgType_OrderCancelRequest:
            FIXApplication.set_latest_fix_message_per_oms_order_id(oms_order_id, None)

    def dequeue(self) -> Union[str, None]:
        # if there's nothing to dequeue, the get method will throw an exception
        try:
            message = self.from_app_queue.get(block=False)
            return message
        except Exception as e:
            #            print(f"In Dequeue. Received execption:{e}")
            return None

    def send_ioi_query(self, client_id: str):
        message = string_to_message(fix.MsgType_IOI, '|'.join([
            f"28={fix.IOITransType_NEW}",
            f"50={client_id}"
        ]))
        fix.Session.sendToTarget(message, self.session_id)

    def send_reserve_request(self, uuid: str, oms_order_id: str, reserve_shares: str):
        if self.reserve_request_sent:
            return

        latest_message = FIXApplication.get_latest_fix_message_per_oms_order_id(oms_order_id)
        if latest_message:
            oms_order_id = latest_message.get(fix.OrderID())
            clordid = "ITGClOrdID:" + latest_message.get(fix.OrderID())
            message = string_to_message(fix.MsgType_NewOrderSingle, '|'.join([
                #                f"11={FIXApplication.get_next_clordid()}",
                f"11={clordid}",
                f"37={oms_order_id}",
                f"38={reserve_shares}",
                f"40={latest_message.get(fix.OrdType())}",
                f"44={latest_message.get(fix.Price())}",
                f"50={uuid}",
                f"54={latest_message.get(fix.Side())}",
                f"55={latest_message.get(fix.Symbol())}",
                f"60={get_utc_transactime()}",
                f"76={FIXApplication.EXEC_BROKER}",
                f"100={FIXApplication.EX_DESTINATION}",
                f"109={oms_order_id}",
                f"150={fix.ExecType_NEW}",
            ]))

            log("Snd RESERVE", message)
            fix.Session.sendToTarget(message, self.session_id)

            self.reserve_request_sent = True

    def send_execution_report(self, uuid: str, oms_order_id: str, fill_shares: str | None = None,
                              execution_type: ExecutionReportType = ExecutionReportType.NewAck):
        if not self.reserve_request_accepted or self.dfd_sent:
            return

        latest_message = FIXApplication.get_latest_fix_message_per_oms_order_id(oms_order_id)
        if latest_message:
            order_qty = int(latest_message.get(fix.OrderQty()))
            oms_order_id = latest_message.get(fix.OrderID())
            clordid = self.accepted_reserve_clordid_per_oms_order_id[oms_order_id]
            expire_time = get_utc_transactime(5 * 60)  # expire 5 mins from now
            price = '11.22'
            cum_qty = fill_shares
            if execution_type == ExecutionReportType.NewAck:
                price = '0'
                cum_qty = '0'
                last_px = '0'
                last_shares = '0'
                order_status = fix.OrdStatus_NEW
                exec_type = fix.ExecType_NEW
                log_msg_type = 'Snd ACK'
                leaves_qty = order_qty
            elif execution_type == ExecutionReportType.DFD:
                last_px = '0'
                last_shares = '0'
                order_status = fix.OrdStatus_DONE_FOR_DAY
                exec_type = fix.ExecType_DONE_FOR_DAY
                log_msg_type = 'Snd DFD'
                leaves_qty = 0
            else:
                if fill_shares is None:
                    fill_shares = order_qty
                else:
                    fill_shares = int(fill_shares)
                if fill_shares == 0:
                    # nothing to fill. skip this report
                    return
                assert order_qty >= fill_shares, f"fill_shares:{fill_shares} > order's qty:{order_qty}"

                last_px = price
                last_shares = fill_shares
                if order_qty == fill_shares:
                    exec_type = fix.ExecType_FILL
                    order_status = fix.OrdStatus_FILLED
                    log_msg_type = 'Snd Fill'
                else:
                    exec_type = fix.ExecType_PARTIAL_FILL
                    order_status = fix.OrdStatus_PARTIALLY_FILLED
                    log_msg_type = 'Snd Partial'
                leaves_qty = int(order_qty) - fill_shares

            message = string_to_message(fix.MsgType_ExecutionReport, '|'.join([
                f"6={price}",
                f"11={clordid}",
                f"14={cum_qty}",
                f"15={FIXApplication.CURRENCY}",
                f"17={oms_order_id}-gate",
                f"20={fix.ExecTransType_NEW}",
                f"29={fix.LastCapacity_AGENT}",
                f"30={FIXApplication.LAST_MARKET}",
                f"31={last_px}",
                f"32={last_shares}",
                f"37={oms_order_id}-caprona",
                f"38={order_qty}",
                f"39={order_status}",
                f"40={latest_message.get(fix.OrdType())}",
                f"41={clordid}",
                f"47={fix.Rule80A_AGENCY_SINGLE_ORDER}",
                f"50={uuid}",
                f"54={latest_message.get(fix.Side())}",
                f"55={latest_message.get(fix.Symbol())}",
                f"59={latest_message.get(fix.TimeInForce())}",
                f"60={get_utc_transactime()}",
                f"76={FIXApplication.EXEC_BROKER}",
                f"126={expire_time}",
                f"150={exec_type}",
                f"151={leaves_qty}",
            ]))

            log(log_msg_type, message)
            fix.Session.sendToTarget(message, self.session_id)

            if execution_type == ExecutionReportType.DFD:
                self.dfd_sent = True
