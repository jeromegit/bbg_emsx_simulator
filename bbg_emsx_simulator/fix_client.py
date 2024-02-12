import argparse
import time
from typing import List, Dict

import quickfix as fix

from bbg_emsx_simulator.client_application import ClientApplication, ExecutionReportType
from bbg_emsx_simulator.fix_application import FIXMessage, log
from bbg_emsx_simulator.scenario import Scenario, ActionLine, Action
from settings import get_settings

FIX_CLIENTID_TAG50 = str(fix.SenderSubID().getField())
FIX_ORDERID_TAG37 = str(fix.OrderID().getField())
FIX_ORDERQTY_TAG38 = str(fix.OrderQty().getField())

received_app_messages: List[Dict[str, str]] = []


# def main(config_file: str, send_reserve_order_id: str = None, send_fill_order_id: str = None,
#          reserve_shares: int = None, fill_shares: int = None) -> None:
def main(config_file: str, scenario: Scenario) -> None:
    initiator = None
    try:
        settings = get_settings(config_file)
        application = ClientApplication()
        store_factory = fix.FileStoreFactory(settings)
        log_factory = fix.FileLogFactory(settings)
        initiator = fix.SocketInitiator(application, store_factory, settings, log_factory)
        initiator.start()
        print("FIX Client started.")
        while True:
            time.sleep(1)
            dequeue_all_and_store(application)
            if scenario:
                run_scenario(scenario, application)

            # if send_reserve_order_id:
            #
            # if send_fill_order_id:


    except (fix.ConfigError, Exception) as e:
        print(f"CAUGHT EXCEPTION:{e}")
    finally:
        if initiator:
            initiator.stop()


def dequeue_all_and_store(application: ClientApplication):
    while True:
        message: FIXMessage = application.dequeue()
        if message:
            #            log("DEQUEUED", message)
            received_app_messages.append(message)
        else:
            return


def has_message_been_received(message_kvs: Dict[str, str]) -> bool:
    for message in list(received_app_messages):
        if message_kvs.items() <= message.message_dict.items():
            log("FOUND", message_kvs)
            received_app_messages.remove(message)
            return True

    log("NOT FOUND", f"searched:{message_kvs} in {len(received_app_messages)} received messages(s)")
    return False


def run_scenario(scenario: Scenario, application: ClientApplication):
    while True:
        action_line = scenario.get_current_action_line()
        if not action_line.has_been__processed():
            processed = process_action_line(application, action_line)
            if processed:
                is_ready = scenario.ready_next_action_line()
                if not is_ready:
                    return
            else:
                return


def process_action_line(application: ClientApplication, action_line: ActionLine) -> bool:
    log("ACTION PRC", f"Process action_line:{action_line}")

    # commonly used below
    client_id = action_line.get(FIX_CLIENTID_TAG50)
    order_id = action_line.get(FIX_ORDERID_TAG37)
    order_qty = action_line.get(FIX_ORDERQTY_TAG38)

    if action_line.action == Action.LOGON:
        application.send_ioi_query(client_id)
    elif action_line.action == Action.WAIT:
        return has_message_been_received(action_line.key_values)
    elif action_line.action == Action.RESERVE:
        application.send_reserve_request(client_id, order_id, order_qty)
    elif action_line.action == Action.ACK:
        application.send_execution_report(client_id, order_id, order_qty, ExecutionReportType.NewAck)
    elif action_line.action == Action.FILL:
        application.send_execution_report(client_id, order_id, order_qty, ExecutionReportType.Filled)
    elif action_line.action == Action.DFD:
        application.send_execution_report(client_id, order_id, order_qty, ExecutionReportType.DFD)
    elif action_line.action == Action.END:
        log("ACTION", "End of scenario has been requested")
        exit(0)

    else:
        log("ERROR", f"action:{action_line.action} is not supported in action_line:{action_line}")
        return False

    action_line.mark_as_processed()

    return True


def parse_args():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('-s', '--scenario_file', type=str, nargs='?',
                    help="Scenario file path")

    ap.add_argument('config_file', nargs='?')

    return ap.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    if cli_args.scenario_file:
        scenario = Scenario(cli_args.scenario_file)
    else:
        scenario = None
    main(cli_args.config_file, scenario)
