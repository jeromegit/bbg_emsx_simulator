import quickfix as fix

def get_settings(config_file):
    settings = fix.SessionSettings(config_file)
    return settings