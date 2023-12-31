import argparse

import quickfix as fix
import sys, time
from client_application import ClientApplication
from settings import get_settings


def main(config_file: str, send_reserve_order_id: str = None, send_fill_order_id: str = None) -> None:
    initiator = None
    try:
        settings = get_settings(config_file)
        application = ClientApplication()
        storeFactory = fix.FileStoreFactory(settings)
        logFactory = fix.FileLogFactory(settings)
        initiator = fix.SocketInitiator(application, storeFactory, settings, logFactory)
        initiator.start()
        print("FIX Client started.")
        while True:
            time.sleep(1)
            if send_reserve_order_id:
                application.send_reserve_request(send_reserve_order_id)
            if send_fill_order_id:
                application.send_fill_or_dfd(send_fill_order_id, False)
                application.send_fill_or_dfd(send_fill_order_id, True)
    except (fix.ConfigError, Exception) as e:
        print(e)
    finally:
        if initiator:
            initiator.stop()


def parse_args():
    ap = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument('-r', '--send_reserve', type=str, nargs='?', const=1, help="Send reserve for this order_id")
    ap.add_argument('-f', '--send_fill', type=str, nargs='?', const=1, help="Send fill for this order_id")
    ap.add_argument('config_file', nargs='?')

    return ap.parse_args()


if __name__ == "__main__":
    cli_args = parse_args()
    main(cli_args.config_file, cli_args.send_reserve, cli_args.send_fill)
