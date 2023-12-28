import quickfix as fix
import sys, time
from client_application import ClientApplication
from settings import get_settings

def main(config_file):
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
    except (fix.ConfigError, Exception) as e:
        print(e)
    finally:
        if initiator:
            initiator.stop()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: fix_client.py <config_file>")
        sys.exit(1)
    main(sys.argv[1])