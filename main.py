import os
import json
import logging
from config import load_config
from db import init_db
import mod_manager
import config_manager

# Load updater configuration from updater_config.json
updater_config = config_manager.load_updater_config()

# Global folder settings from updater configuration
CURRENT_DIR = updater_config.get("download_directory", "current")
MODS_DIR = os.path.join(CURRENT_DIR, "mods")
BACKUPS_DIR = updater_config.get("backup_directory", "backups")
OVERRIDES_DIR = updater_config.get("overrides_directory", "overrides")
LOGS_DIR = updater_config.get("logs_directory", "logs")
CONFIG_FILE = "modrinth.index.json"

# Ensure necessary directories exist
os.makedirs(CURRENT_DIR, exist_ok=True)
os.makedirs(MODS_DIR, exist_ok=True)
os.makedirs(BACKUPS_DIR, exist_ok=True)
os.makedirs(OVERRIDES_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)

def load_modpack_json():
    """
    Loads the modpack JSON from CURRENT_DIR.
    Falls back to CONFIG_FILE in the root if necessary.
    """
    index_path = os.path.join(CURRENT_DIR, CONFIG_FILE)
    if os.path.exists(index_path):
        try:
            with open(index_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading modpack JSON from {index_path}: {e}")
            return {}
    else:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    data = json.load(f)
                with open(index_path, 'w') as f:
                    json.dump(data, f, indent=4)
                return data
            except Exception as e:
                logging.error(f"Error copying modpack JSON to {CURRENT_DIR}: {e}")
                return {}
        else:
            logging.info("modrinth.index.json not found. Initializing new modpack structure.")
            return {"dependencies": {}, "files": []}

def update_dependencies(modpack_data):
    """
    Updates the modpack dependencies (Minecraft version and mod loader).
    Allowed mod loaders: fabric, forge, neoforge, quilt, liteloader.
    Displays currently set values and allows the user to update them.
    If no input is provided, the existing value remains unchanged.
    """
    deps = modpack_data.get("dependencies", {})
    
    # Update Minecraft version
    current_mc = deps.get("minecraft", None)
    if current_mc:
        print(f"Current Minecraft version: {current_mc}")
    else:
        print("Minecraft version is not set.")
    new_mc = input("Enter new Minecraft version (or press Enter to keep current): ").strip()
    if new_mc:
        deps["minecraft"] = new_mc

    # Update mod loader
    allowed_loaders = ["fabric", "forge", "neoforge", "quilt", "liteloader"]
    current_loader = None
    current_loader_version = None
    for loader in allowed_loaders:
        if loader in deps:
            current_loader = loader
            current_loader_version = deps[loader]
            break
    if current_loader:
        print(f"Current mod loader: {current_loader} (version: {current_loader_version})")
    else:
        print("Mod loader is not set.")
    print("Allowed mod loaders: " + ", ".join(allowed_loaders))
    new_loader = input("Enter new mod loader (or press Enter to keep current): ").strip().lower()
    if new_loader:
        if new_loader in allowed_loaders:
            # Remove any previously set mod loader keys
            for loader in allowed_loaders:
                deps.pop(loader, None)
            new_loader_version = input(f"Enter version for {new_loader}: ").strip()
            if new_loader_version:
                deps[new_loader] = new_loader_version
            else:
                print("No version entered; mod loader value not updated.")
        else:
            print("Invalid mod loader input; value not updated.")
    else:
        # If no new mod loader provided, allow updating the version of the current loader if one exists
        if current_loader:
            new_version = input(f"Enter new version for current mod loader ({current_loader}) (or press Enter to keep current): ").strip()
            if new_version:
                deps[current_loader] = new_version
    modpack_data["dependencies"] = deps
    print("Modpack dependencies updated.")

def show_menu():
    """
    Displays the menu options.
    """
    print("\nModpack Updater Menu:")
    print("1. Add a mod")
    print("2. List mods")
    print("3. Remove a mod")
    print("4. Update modpack")
    print("5. Build modpack")
    print("6. Configure updater settings")
    print("7. Update modpack dependencies (game and mod loader)")
    print("8. Exit")
    return input("Enter your choice: ").strip()

def main():
    global updater_config  # Ensure changes to updater_config persist
    config = load_config()  # Loads modpack config (guided setup if needed)
    modpack_data = load_modpack_json()
    conn, cursor = init_db()
    while True:
        choice = show_menu()
        if choice == "1":
            mod_manager.add_mod_interactive(modpack_data, MODS_DIR, use_async=updater_config.get("async_downloads", True))
        elif choice == "2":
            mod_manager.list_mods(modpack_data)
        elif choice == "3":
            mod_manager.remove_mod(modpack_data)
        elif choice == "4":
            mod_manager.update_pack(
                modpack_data, cursor, CURRENT_DIR, MODS_DIR, BACKUPS_DIR, OVERRIDES_DIR, LOGS_DIR,
                use_async=updater_config.get("async_downloads", True)
            )
        elif choice == "5":
            mod_manager.build_modpack(modpack_data, cursor, CURRENT_DIR, MODS_DIR, BACKUPS_DIR, OVERRIDES_DIR, LOGS_DIR)
        elif choice == "6":
            updater_config = config_manager.configure_updater()
        elif choice == "7":
            update_dependencies(modpack_data)
        elif choice == "8":
            index_path = os.path.join(CURRENT_DIR, CONFIG_FILE)
            try:
                with open(index_path, 'w') as f:
                    json.dump(modpack_data, f, indent=4)
            except Exception as e:
                logging.error(f"Error saving modpack JSON: {e}")
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")
    conn.close()

if __name__ == "__main__":
    # Set logging level based on updater configuration
    logging_level = updater_config.get("logging_level", "INFO").upper()
    logging.basicConfig(level=getattr(logging, logging_level), format='%(asctime)s - %(levelname)s - %(message)s')
    main()
