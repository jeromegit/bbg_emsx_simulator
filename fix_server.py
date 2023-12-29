import quickfix as fix
import sys, time
from server_application import ServerApplication
from settings import get_settings

def main(config_file):
    try:
        settings = get_settings(config_file)
        application = ServerApplication()
        storeFactory = fix.FileStoreFactory(settings)
        logFactory = fix.FileLogFactory(settings)
        acceptor = fix.SocketAcceptor(application, storeFactory, settings, logFactory)
        acceptor.start()
        print("FIX Server started.")
        while True:
            time.sleep(.5)
            application.check_for_order_changes()
            if application.from_app_queue.not_empty:
                application.process_message_from_app_queue()

    except (fix.ConfigError, Exception) as e:
        print(e)
    finally:
        acceptor.stop()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: fix_server.py <config_file>")
        sys.exit(1)
    main(sys.argv[1])