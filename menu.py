import os
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich import box

console = Console()

MENU_STYLE = "bold cyan"
OPTION_STYLE = "cyan"
DESCRIPTION_STYLE = "dim"

MOD_CATEGORY = "mod"
PACK_CATEGORY = "pack"
SETTINGS_CATEGORY = "settings"
EXIT_CATEGORY = "exit"


def print_header(title: str) -> None:
    """Print a styled header."""
    console.print(f"\n[bold cyan]=== {title} ===[/bold cyan]\n")


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/bold green] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red]✗[/bold red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]⚠[/bold yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[bold blue]ℹ[/bold blue] {message}")


def confirm(prompt: str, default: bool = False) -> bool:
    """Show a confirmation dialog."""
    return Confirm.ask(f"[bold yellow]{prompt}[/bold yellow]", default=default)


def get_input(prompt: str, default: str = "") -> str:
    """Get user input with optional default."""
    if default:
        return Prompt.ask(f"[cyan]{prompt}[/cyan]", default=default)
    return Prompt.ask(f"[cyan]{prompt}[/cyan]")


def get_mod_status_input(side: str, current: str = "") -> str:
    """
    Prompt user for mod status (required, optional, unsupported) with Rich UI.
    """
    prompt = f"{side.title()} status"
    if current:
        prompt += f" (current: {current})"
    prompt += " [R/O/U]: "
    
    while True:
        value = get_input(prompt, current or "optional").strip().lower()
        if not value:
            return current if current else "optional"
        if value in ("r", "required"):
            return "required"
        if value in ("o", "optional"):
            return "optional"
        if value in ("u", "unsupported"):
            return "unsupported"
        print_error("Use R (required), O (optional), or U (unsupported)")


def show_mod_menu() -> str:
    """Show mod operations submenu."""
    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    table.add_column("num", style="bold cyan", width=4)
    table.add_column("option", style="cyan")
    table.add_column("desc", style="dim")

    table.add_row("[1]", "Add a mod", "Add a new mod by Version ID")
    table.add_row("[2]", "List mods", "Show all mods in the pack")
    table.add_row("[3]", "Remove a mod", "Remove a mod by Project ID")
    table.add_row("[B]", "Back", "Return to main menu")

    console.print(Panel(table, title="[bold cyan]📦 Mod Operations[/bold cyan]", border_style="cyan", padding=(0, 1)))
    return get_input("Select option").lower()


def show_pack_menu() -> str:
    """Show pack operations submenu."""
    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    table.add_column("num", style="bold cyan", width=4)
    table.add_column("option", style="cyan")
    table.add_column("desc", style="dim")

    table.add_row("[1]", "Update modpack", "Check for updates and download")
    table.add_row("[2]", "Build modpack", "Export as .mrpack file")
    table.add_row("[3]", "Import from Modrinth", "Import by Version ID")
    table.add_row("[B]", "Back", "Return to main menu")

    console.print(Panel(table, title="[bold cyan]📚 Pack Operations[/bold cyan]", border_style="cyan", padding=(0, 1)))
    return get_input("Select option").lower()


def show_settings_menu() -> str:
    """Show settings submenu."""
    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    table.add_column("num", style="bold cyan", width=4)
    table.add_column("option", style="cyan")
    table.add_column("desc", style="dim")

    table.add_row("[1]", "Configure settings", "Logging, directories, async")
    table.add_row("[2]", "Update dependencies", "Minecraft version, mod loader")
    table.add_row("[B]", "Back", "Return to main menu")

    console.print(Panel(table, title="[bold cyan]⚙️ Settings[/bold cyan]", border_style="cyan", padding=(0, 1)))
    return get_input("Select option").lower()


def show_main_menu() -> str:
    """Show main menu."""
    title = "[bold cyan]Minecraft Modpack Manager[/bold cyan]"

    table = Table(box=box.SIMPLE, show_header=False, pad_edge=False)
    table.add_column("key", style="bold cyan", width=8)
    table.add_column("option", style="cyan")
    table.add_column("desc", style="dim")

    table.add_row("[M]", "Mod Operations", "Add, list, remove mods")
    table.add_row("[P]", "Pack Operations", "Update, build, import pack")
    table.add_row("[S]", "Settings", "Configure and update")
    table.add_row("[Q]", "Quit", "Save and exit")

    console.print(Panel(title, border_style="cyan", padding=(0, 1)))
    console.print(table)
    return get_input("Select option").lower()


def get_status_icon(status: str) -> tuple[str, str]:
    """Return icon and color for mod status."""
    if status == "required":
        return "✅", "green"
    elif status == "optional":
        return "○", "yellow"
    elif status == "unsupported":
        return "✗", "red"
    else:
        return "-", "dim"


def display_mods_table(json_data: dict[str, Any]) -> None:
    """Display mods in a formatted table."""
    if not json_data.get("files"):
        console.print("[yellow]No mods found in the modpack.[/yellow]")
        return

    table = Table(title="Modpack Contents", box=box.SIMPLE)
    table.add_column("#", style="bold cyan", width=4)
    table.add_column("File", style="white", max_width=35)
    table.add_column("Server", style="cyan", justify="center")
    table.add_column("Client", style="cyan", justify="center")

    for idx, file_entry in enumerate(json_data.get("files", []), start=1):
        filename = file_entry.get("path", "Unknown")
        env = file_entry.get("env", {})
        server = env.get("server", "optional")
        client = env.get("client", "optional")

        server_icon, server_color = get_status_icon(server)
        client_icon, client_color = get_status_icon(client)

        table.add_row(
            str(idx),
            filename[:35],
            f"[{server_color}]{server_icon} {server}[/{server_color}]",
            f"[{client_color}]{client_icon} {client}[/{client_color}]",
        )

    console.print(table)


def list_mods_interactive(json_data: dict[str, Any]) -> None:
    """Display mods table with edit/delete options."""
    if not json_data.get("files"):
        console.print("[yellow]No mods found in the modpack.[/yellow]")
        return

    display_mods_table(json_data)

    console.print("\n[bold cyan]Options:[/bold cyan]")
    console.print("  [1-" + str(len(json_data["files"])) + "] Edit mod status")
    console.print("  [D]elete a mod")
    console.print("  [Q]uit to menu")

    choice = get_input("Select option").lower()

    if choice == "q" or choice == "":
        return
    elif choice == "d":
        from mod_manager import delete_mod
        delete_mod(json_data)
    else:
        try:
            idx = int(choice)
            if 1 <= idx <= len(json_data["files"]):
                from mod_manager import edit_mod_env
                edit_mod_env(json_data, idx - 1)
            else:
                print_error("Invalid number.")
        except ValueError:
            print_error("Invalid option.")


def display_config_table(config: Any) -> None:
    """Display current configuration."""
    table = Table(title="Current Settings", box=box.SIMPLE)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")

    config_dict = config.to_dict()
    for key, value in config_dict.items():
        table.add_row(key, str(value))

    console.print(table)


def display_import_prompt() -> tuple[str, str]:
    """Show import modpack prompt and return (version_id, download_choice)."""
    console.print("[bold cyan]📥 Import Modpack from Modrinth[/bold cyan]")
    console.print("[dim]You can find the version ID in the modpack URL:[/dim]")
    console.print("[dim]  e.g., https://modrinth.com/modpack/my-pack/version/ABC123XYZ[/dim]")

    version_id = get_input("Enter the Version ID")
    if not version_id:
        print_error("No version ID provided.")
        return "", ""

    download_mods = confirm("Download mod files?", default=True)
    return version_id, "yes" if download_mods else "no"


def display_pack_info(modpack_data: dict[str, Any]) -> None:
    """Display imported pack information."""
    deps = modpack_data.get("dependencies", {})

    info_table = Table(box=box.SIMPLE, show_header=False)
    info_table.add_column("Label", style="bold cyan", width=15)
    info_table.add_column("Value", style="white")

    info_table.add_row("Name", modpack_data.get("name", "Unknown"))
    info_table.add_row("Version", modpack_data.get("versionId", "Unknown"))
    info_table.add_row("Game", modpack_data.get("game", "minecraft"))
    info_table.add_row("Files", str(len(modpack_data.get("files", []))))

    if deps:
        dep_str = ", ".join(f"{k}: {v}" for k, v in deps.items())
        info_table.add_row("Dependencies", dep_str)

    console.print(Panel(info_table, title="[bold green]✓ Import Successful![/bold green]", border_style="green", padding=(0, 1)))


def display_progress(current: int, total: int, filename: str) -> None:
    """Display download progress."""
    console.print(f"[cyan]Downloading:[/cyan] {filename} [{current}/{total}]")


def clear_screen() -> None:
    """Clear the console screen."""
    os.system("cls" if os.name == "nt" else "clear")


def add_mod_interactive(mods_directory: str, use_async: bool = False) -> dict[str, Any] | None:
    """
    Add a mod with Rich UI prompts.
    Returns the mod entry dict to be added to json_data, or None if cancelled.
    """
    from mod_manager import get_version_info_by_id, download_file_wrapper, get_relative_path
    
    console.print("[bold cyan]📦 Add New Mod[/bold cyan]")
    
    version_id = get_input("Enter the Version ID")
    if not version_id:
        print_error("No version ID provided.")
        return None
    
    server_env = get_mod_status_input("server")
    client_env = get_mod_status_input("client")
    
    console.print("[dim]Fetching version info...[/dim]")
    version_info = get_version_info_by_id(version_id)
    if not version_info:
        print_error("Failed to retrieve version information.")
        return None
    
    primary_file = next((f for f in version_info["files"] if f.get("primary")), version_info["files"][0])
    console.print(f"[dim]Downloading {primary_file.get('filename', 'mod file')}...[/dim]")
    
    file_path, success = download_file_wrapper(primary_file["url"], mods_directory, use_async=use_async)
    
    if file_path is None or not success:
        print_error("Failed to download mod file.")
        return None
    
    relative_file_path = get_relative_path(file_path, base_dir="current")
    
    new_mod_entry = {
        "path": relative_file_path,
        "hashes": primary_file.get("hashes", {}),
        "env": {
            "server": server_env,
            "client": client_env,
        },
        "downloads": [primary_file["url"]],
        "fileSize": primary_file.get("size", 0),
    }
    
    print_success(f"Added {primary_file.get('filename', 'mod')}!")
    return new_mod_entry
