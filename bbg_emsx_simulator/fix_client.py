import argparse
import time

import quickfix as fix

from bbg_emsx_simulator.client_application import ClientApplication, ExecutionReportType
from settings import get_settings


def main(config_file: str, send_reserve_order_id: str = None, send_fill_order_id: str = None,
         reserve_shares:int = None, fill_shares: int = None) -> None:
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
            if send_reserve_order_id:
                application.send_reserve_request(send_reserve_order_id, reserve_shares)
            if send_fill_order_id:
                application.send_execution_report(send_fill_order_id, fill_shares, ExecutionReportType.NewAck)
                application.send_execution_report(send_fill_order_id, fill_shares, ExecutionReportType.Filled)
                application.send_execution_report(send_fill_order_id, fill_shares, ExecutionReportType.DFD)
    except (fix.ConfigError, Exception) as e:
        print(e)
    finally:
        if initiator:
            initiator.stop()


def parse_args():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('-r', '--send_reserve', type=str, nargs='?', help="Send reserve for this order_id")
    ap.add_argument('-f', '--send_fill', type=str, nargs='?', help="Send fill for this order_id")
    ap.add_argument('-R', '--reserve_shares', type=int, nargs='?', default=100,
                    help="Shares to reserve when sending a reserve request")
    ap.add_argument('-F', '--fill_shares', type=int, nargs='?',
                    help="Shares to fill when sending a fill (0=ND, None=100%)")
    ap.add_argument('config_file', nargs='?')

    return ap.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    main(cli_args.config_file, cli_args.send_reserve, cli_args.send_fill,
         cli_args.reserve_shares, cli_args.fill_shares)
