import os
import json
import logging

CONFIG_FILE = "modrinth.index.json"
DB_FILE = "mod_versions.db"

def guided_setup_config(config_path=CONFIG_FILE):
    """
    Guides the user through setting up a new modpack configuration.
    Prompts for:
      - Modpack name
      - Initial version
      - Forge version
      - Minecraft version

    If an existing modrinth.index.json file is found, its contents are used as the base.
    Otherwise, the user-provided values are used to create a new configuration.
    The resulting configuration includes a "dependencies" key (with minecraft and forge versions)
    and will be saved to CONFIG_FILE.
    """
    print("Starting guided setup for modpack configuration.")
    # If a config already exists, offer to use it as base.
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                existing_config = json.load(f)
            print("Existing modrinth.index.json found. Using its values as defaults.")
            default_name = existing_config.get("name", "")
            default_version = existing_config.get("versionId", "")
            default_forge = existing_config.get("dependencies", {}).get("forge", "")
            default_mc = existing_config.get("dependencies", {}).get("minecraft", "")
        except Exception as e:
            logging.error(f"Error loading existing configuration: {e}")
            default_name = default_version = default_forge = default_mc = ""
    else:
        default_name = default_version = default_forge = default_mc = ""

    modpack_name = input(f"Enter the modpack name [{default_name}]: ").strip() or default_name
    initial_version = input(f"Enter the initial version (e.g., 1.0.0) [{default_version}]: ").strip() or default_version
    forge_version = input(f"Enter the Forge version [{default_forge}]: ").strip() or default_forge
    minecraft_version = input(f"Enter the Minecraft version [{default_mc}]: ").strip() or default_mc

    config_data = {
        "game": "minecraft",
        "formatVersion": 1,
        "versionId": initial_version,
        "name": modpack_name,
        "summary": f"Forge version: {forge_version} | Minecraft version: {minecraft_version}",
        "dependencies": {
            "minecraft": minecraft_version,
            "forge": forge_version
        },
        "files": []
    }

    try:
        with open(config_path, 'w') as f:
            json.dump(config_data, f, indent=4)
        logging.info(f"Configuration file created at {config_path}")
    except Exception as e:
        logging.error(f"Failed to create configuration file: {e}")

    return config_data

def load_config(config_path=CONFIG_FILE):
    """
    Loads the modpack configuration from CONFIG_FILE.
    
    Logic:
      - If the configuration file exists, load and return it.
      - If not, check if a mod_versions.db exists.
          (The existence of the database indicates that a previous setup might have run.)
      - In any case where the configuration file is missing,
        perform a guided setup to create a new configuration.
    
    The guided setup uses any existing modrinth.index.json (if present) as default values.
    """
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            logging.info("Configuration file loaded from modrinth.index.json.")
            return config
        except Exception as e:
            logging.error(f"Error loading configuration: {e}")
    else:
        logging.info("No configuration file found.")
        if os.path.exists(DB_FILE):
            logging.info("Database file mod_versions.db exists. Using existing modrinth.index.json as base if available.")
        else:
            logging.info("No mod_versions.db found; performing guided setup.")
    return guided_setup_config(config_path)
