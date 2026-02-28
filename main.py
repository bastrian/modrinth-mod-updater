import logging
import json
import os
from typing import Any

from config import load_config
from config_manager import UpdaterConfig, configure_updater, load_updater_config
from db import init_db
from http_client import close_session
import mod_manager


def load_modpack_json(config: UpdaterConfig) -> dict[str, Any]:
    """
    Loads the modpack JSON from the download directory.
    Falls back to config file in the root if necessary.
    """
    import json
    import os
    
    index_path = os.path.join(config.download_directory, config.config_file)
    
    if os.path.exists(index_path):
        try:
            with open(index_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading modpack JSON from {index_path}: {e}")
            return {}
    else:
        if os.path.exists(config.config_file):
            try:
                with open(config.config_file, "r") as f:
                    data = json.load(f)
                with open(index_path, "w") as f:
                    json.dump(data, f, indent=4)
                return data
            except Exception as e:
                logging.error(f"Error copying modpack JSON to {config.download_directory}: {e}")
                return {}
        else:
            logging.info("modrinth.index.json not found. Initializing new modpack structure.")
            return {"dependencies": {}, "files": []}


def update_dependencies(modpack_data: dict[str, Any]) -> None:
    """
    Updates the modpack dependencies (Minecraft version and mod loader).
    Allowed mod loaders: fabric, forge, neoforge, quilt, liteloader.
    Displays currently set values and allows the user to update them.
    If no input is provided, the existing value remains unchanged.
    """
    deps = modpack_data.get("dependencies", {})
    
    current_mc = deps.get("minecraft")
    if current_mc:
        print(f"Current Minecraft version: {current_mc}")
    else:
        print("Minecraft version is not set.")
    
    new_mc = input("Enter new Minecraft version (or press Enter to keep current): ").strip()
    if new_mc:
        deps["minecraft"] = new_mc

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
            for loader in allowed_loaders:
                deps.pop(loader, None)
            new_loader_version = input(f"Enter version for {new_loader}: ").strip()
            if new_loader_version:
                deps[new_loader] = new_loader_version
            else:
                print("No version entered; mod loader value not updated.")
        else:
            print("Invalid mod loader input; value not updated.")
    elif current_loader:
        new_version = input(f"Enter new version for current mod loader ({current_loader}) (or press Enter to keep current): ").strip()
        if new_version:
            deps[current_loader] = new_version
    
    modpack_data["dependencies"] = deps
    print("Modpack dependencies updated.")


def show_menu() -> str:
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


def main() -> None:
    """
    Main entry point for the modpack updater application.
    """
    updater_config = load_updater_config()
    updater_config.ensure_directories()
    
    config = load_config()
    modpack_data = load_modpack_json(updater_config)
    conn, cursor = init_db()
    
    while True:
        choice = show_menu()
        
        if choice == "1":
            mod_manager.add_mod_interactive(modpack_data, updater_config.mods_dir, 
                                           use_async=updater_config.async_downloads)
        elif choice == "2":
            mod_manager.list_mods(modpack_data)
        elif choice == "3":
            mod_manager.remove_mod(modpack_data)
        elif choice == "4":
            mod_manager.update_pack(updater_config, modpack_data, cursor)
        elif choice == "5":
            mod_manager.build_modpack(updater_config, modpack_data, cursor)
        elif choice == "6":
            updater_config = configure_updater()
            updater_config.ensure_directories()
        elif choice == "7":
            update_dependencies(modpack_data)
        elif choice == "8":
            index_path = updater_config.download_directory + "/" + updater_config.config_file
            import json
            try:
                with open(index_path, "w") as f:
                    json.dump(modpack_data, f, indent=4)
            except Exception as e:
                logging.error(f"Error saving modpack JSON: {e}")
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")
    
    conn.close()
    close_session()


if __name__ == "__main__":
    updater_config = load_updater_config()
    logging_level = getattr(logging, updater_config.logging_level, logging.INFO)
    logging.basicConfig(
        level=logging_level,
        format="%(asctime)s - %(levelname)s - %(message)s"
    )
    main()
