import logging
import json
import os
from typing import Any

from config import load_config
from config_manager import UpdaterConfig, configure_updater, load_updater_config
from db import init_db
from http_client import close_session
import mod_manager
from menu import (
    console,
    show_main_menu,
    show_mod_menu,
    show_pack_menu,
    show_settings_menu,
    display_mods_table,
    list_mods_interactive,
    add_mod_interactive,
    display_config_table,
    display_import_prompt,
    display_pack_info,
    get_input,
    confirm,
    print_success,
    print_error,
    print_warning,
)


def load_modpack_json(config: UpdaterConfig) -> dict[str, Any]:
    """
    Loads the modpack JSON from the download directory.
    Falls back to config file in the root if necessary.
    """
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


def save_modpack_json(modpack_data: dict[str, Any], config: UpdaterConfig) -> bool:
    """Save modpack JSON to file."""
    index_path = os.path.join(config.download_directory, config.config_file)
    try:
        with open(index_path, "w") as f:
            json.dump(modpack_data, f, indent=4)
        return True
    except Exception as e:
        logging.error(f"Error saving modpack JSON: {e}")
        return False


def update_dependencies_interactive(modpack_data: dict[str, Any]) -> None:
    """
    Updates the modpack dependencies (Minecraft version and mod loader).
    Uses Rich for interactive prompts.
    """
    deps = modpack_data.get("dependencies", {})
    
    current_mc = deps.get("minecraft")
    mc_display = f"Current: [green]{current_mc}[/green]" if current_mc else "[yellow]Not set[/yellow]"
    console.print(f"\n[cyan]Minecraft Version:[/cyan] {mc_display}")
    
    new_mc = get_input("New Minecraft version (Enter to keep current)", default=current_mc or "")
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
        console.print(f"[cyan]Mod Loader:[/cyan] [green]{current_loader}[/green] (version: {current_loader_version})")
    else:
        console.print("[cyan]Mod Loader:[/cyan] [yellow]Not set[/yellow]")
    
    console.print(f"[dim]Allowed: {', '.join(allowed_loaders)}[/dim]")
    new_loader = get_input("New mod loader (Enter to keep current)", default="").strip().lower()
    
    if new_loader:
        if new_loader in allowed_loaders:
            for loader in allowed_loaders:
                deps.pop(loader, None)
            new_loader_version = get_input(f"Version for {new_loader}")
            if new_loader_version:
                deps[new_loader] = new_loader_version
                print_success(f"Updated mod loader to {new_loader} {new_loader_version}")
            else:
                print_warning("No version entered; mod loader not updated.")
        else:
            print_error(f"Invalid mod loader. Allowed: {', '.join(allowed_loaders)}")
    elif current_loader:
        new_version = get_input(f"New version for {current_loader} (Enter to keep current)", default="").strip()
        if new_version:
            deps[current_loader] = new_version
            print_success(f"Updated {current_loader} to version {new_version}")
    
    modpack_data["dependencies"] = deps
    print_success("Dependencies updated!")


def handle_mod_menu(modpack_data: dict[str, Any], updater_config: UpdaterConfig) -> bool:
    """Handle mod operations submenu. Returns True to go back."""
    while True:
        choice = show_mod_menu()
        
        if choice == "1" or choice == "add":
            new_mod = add_mod_interactive(updater_config.mods_dir, use_async=updater_config.async_downloads)
            if new_mod:
                modpack_data.setdefault("files", []).append(new_mod)
        elif choice == "2" or choice == "list":
            list_mods_interactive(modpack_data)
        elif choice == "3" or choice == "remove":
            mod_manager.remove_mod(modpack_data)
        elif choice == "b" or choice == "back":
            return True
        else:
            print_error("Invalid option.")
    
    return True


def handle_pack_menu(modpack_data: dict[str, Any], updater_config: UpdaterConfig, cursor: Any) -> bool:
    """Handle pack operations submenu. Returns True to go back."""
    while True:
        choice = show_pack_menu()
        
        if choice == "1" or choice == "update":
            mod_manager.update_pack(updater_config, modpack_data, cursor)
        elif choice == "2" or choice == "build":
            mod_manager.build_modpack(updater_config, modpack_data, cursor)
        elif choice == "3" or choice == "import":
            version_id, download_choice = display_import_prompt()
            if version_id:
                imported_data = mod_manager.import_modpack(
                    version_id, 
                    updater_config,
                    download_mods=(download_choice == "yes")
                )
                if imported_data:
                    modpack_data.clear()
                    modpack_data.update(imported_data)
                    display_pack_info(modpack_data)
                else:
                    print_error("Failed to import modpack. Check the version ID and try again.")
        elif choice == "b" or choice == "back":
            return True
        else:
            print_error("Invalid option.")
    
    return True


def handle_settings_menu(modpack_data: dict[str, Any], updater_config: UpdaterConfig) -> UpdaterConfig:
    """Handle settings submenu. Returns updated config."""
    while True:
        choice = show_settings_menu()
        
        if choice == "1" or choice == "configure":
            display_config_table(updater_config)
            updater_config = configure_updater()
            updater_config.ensure_directories()
            print_success("Settings updated!")
        elif choice == "2" or choice == "dependencies":
            update_dependencies_interactive(modpack_data)
        elif choice == "b" or choice == "back":
            return updater_config
        else:
            print_error("Invalid option.")
    
    return updater_config


def main() -> None:
    """
    Main entry point for the modpack updater application.
    """
    updater_config = load_updater_config()
    updater_config.ensure_directories()
    
    load_config()
    modpack_data = load_modpack_json(updater_config)
    conn, cursor = init_db()
    
    while True:
        choice = show_main_menu()
        
        if choice == "m" or choice == "mod":
            handle_mod_menu(modpack_data, updater_config)
        elif choice == "p" or choice == "pack":
            handle_pack_menu(modpack_data, updater_config, cursor)
        elif choice == "s" or choice == "settings":
            updater_config = handle_settings_menu(modpack_data, updater_config)
        elif choice == "q" or choice == "quit" or choice == "9":
            if save_modpack_json(modpack_data, updater_config):
                print_success("Modpack saved!")
            console.print("[bold cyan]Goodbye![/bold cyan]")
            break
        else:
            print_error("Invalid option. Please try again.")
    
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
