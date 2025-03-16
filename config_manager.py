import os
import json
import logging

UPDATER_CONFIG_FILE = "updater_config.json"

def load_updater_config():
    """
    Loads the updater configuration from UPDATER_CONFIG_FILE.
    If the file does not exist, creates a default configuration.
    """
    if os.path.exists(UPDATER_CONFIG_FILE):
        try:
            with open(UPDATER_CONFIG_FILE, 'r') as f:
                config = json.load(f)
            logging.info("Updater configuration loaded.")
            return config
        except Exception as e:
            logging.error(f"Error reading updater configuration: {e}")
    # Default configuration values
    config = {
        "logging_level": "INFO",          # Can be DEBUG, INFO, WARNING, ERROR
        "async_downloads": True,          # If True, downloads run asynchronously
        "download_directory": "current",  # Base download directory
        "backup_directory": "backups",
        "overrides_directory": "overrides",
        "logs_directory": "logs"
    }
    save_updater_config(config)
    return config

def save_updater_config(config):
    """
    Saves the updater configuration to UPDATER_CONFIG_FILE.
    """
    try:
        with open(UPDATER_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        logging.info("Updater configuration saved.")
    except Exception as e:
        logging.error(f"Error saving updater configuration: {e}")

def configure_updater():
    """
    Allows the user to view and modify the updater configuration via the menu.
    """
    config = load_updater_config()
    print("Current Updater Configuration:")
    for key, value in config.items():
        print(f"  {key}: {value}")
    print("\nEnter the configuration key you wish to change (or press Enter to finish):")
    while True:
        key = input("Key: ").strip()
        if not key:
            break
        if key in config:
            new_val = input(f"Enter new value for {key} (current: {config[key]}): ").strip()
            # For boolean values, interpret 'true'/'false'
            if key == "async_downloads":
                config[key] = new_val.lower() in ['true', '1', 'yes']
            else:
                config[key] = new_val
        else:
            print("Invalid key. Available keys: " + ", ".join(config.keys()))
    save_updater_config(config)
    return config
