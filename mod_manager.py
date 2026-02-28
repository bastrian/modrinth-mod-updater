import asyncio
import datetime
import hashlib
import json
import logging
import os
import shutil
import urllib.parse
import zipfile
from typing import Any

import aiohttp
from tqdm import tqdm

from config_manager import UpdaterConfig
from db import get_mod_version, save_mod_version
from http_client import APIError, RateLimitError, get_with_retry, validate_modrinth_url, validate_url

logger = logging.getLogger(__name__)

MODRINTH_API_BASE = "https://api.modrinth.com/v2"


def get_relative_path(file_path: str | None, base_dir: str = "current") -> str | None:
    """
    Converts an absolute file path (e.g. 'current\\mods\\file.jar')
    to a relative path starting from the mods folder (e.g. 'mods/file.jar').
    """
    if file_path:
        relative = file_path.replace(base_dir + os.sep, "")
        return relative.replace(os.sep, "/")
    return None


def download_and_calculate_hashes(url: str) -> tuple[str | None, str | None, int]:
    """
    Downloads content from a URL and calculates its SHA1 and SHA512 hashes,
    as well as the total size in bytes.
    Returns (sha1, sha512, total_bytes).
    """
    if not validate_url(url):
        logger.error(f"Invalid URL: {url}")
        return None, None, 0
    
    try:
        response = get_with_retry(url)
    except (APIError, RateLimitError) as e:
        logger.error(f"Failed to download URL {url}: {e}")
        return None, None, 0
    except Exception as e:
        logger.error(f"Unexpected error downloading URL {url}: {e}")
        return None, None, 0
    
    sha1_hash = hashlib.sha1()
    sha512_hash = hashlib.sha512()
    total_bytes = 0
    
    import requests
    try:
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=8192):
            total_bytes += len(chunk)
            sha1_hash.update(chunk)
            sha512_hash.update(chunk)
    except requests.RequestException as e:
        logger.error(f"Failed to download URL {url}: {e}")
        return None, None, 0
    
    return sha1_hash.hexdigest(), sha512_hash.hexdigest(), total_bytes


def download_file(url: str, directory: str, expected_size: int | None = None, dry_run: bool = False) -> tuple[str | None, bool]:
    """
    Synchronously downloads a file from the specified URL into the given directory.
    Checks file size if expected_size is provided.
    If dry_run is True, simulates the download.
    Returns (file_path, downloaded_flag).
    """
    if not validate_url(url):
        logger.error(f"Invalid URL: {url}")
        return None, False
    
    filename = urllib.parse.unquote(url.split("/")[-1])
    file_path = os.path.join(directory, filename)
    
    if dry_run:
        logging.info(f"[DRY RUN] Would download {url} to {file_path}")
        return file_path, True
    
    try:
        os.makedirs(directory, exist_ok=True)
        
        if os.path.exists(file_path):
            if expected_size is None or os.path.getsize(file_path) == expected_size:
                logging.info(f"File already exists with expected size: {file_path}")
                return file_path, False
            else:
                logging.info(f"File size mismatch, re-downloading: {file_path}")
        
        import requests
        
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        
        with open(file_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        logging.info(f"Downloaded file to {file_path}")
        return file_path, True
    except requests.RequestException as e:
        logger.error(f"Error downloading file from {url}: {e}")
        return None, False
    except OSError as e:
        logger.error(f"Error writing file: {e}")
        return None, False


def calculate_local_file_sha1(file_path: str) -> str | None:
    """
    Calculates and returns the SHA1 hash of a local file.
    """
    sha1_hash = hashlib.sha1()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha1_hash.update(chunk)
        return sha1_hash.hexdigest()
    except OSError as e:
        logger.error(f"Error calculating SHA1 for {file_path}: {e}")
        return None


def get_latest_version_info(project_id: str, game_version: str, mod_loader: str) -> dict[str, Any] | None:
    """
    Retrieves the latest version information for a given project from the Modrinth API.
    """
    api_url = f"{MODRINTH_API_BASE}/project/{project_id}/version"
    params = {
        "loaders": json.dumps([mod_loader]),
        "game_versions": json.dumps([game_version]),
    }
    
    try:
        versions_data = get_with_retry(api_url, params)
        if not isinstance(versions_data, list):
            logger.error(f"Unexpected API response format for project {project_id}")
            return None
        for version in versions_data:
            if mod_loader in version.get("loaders", []) and game_version in version.get("game_versions", []):
                return version
    except (APIError, RateLimitError) as e:
        logger.error(f"Error fetching version info for project {project_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching version info for project {project_id}: {e}")
    
    return None


def get_version_info_by_id(version_id: str) -> dict[str, Any] | None:
    """
    Retrieves version information for a specific Version ID from the Modrinth API.
    """
    api_url = f"{MODRINTH_API_BASE}/version/{version_id}"
    
    try:
        data = get_with_retry(api_url)
        if isinstance(data, dict):
            return data
        logger.error(f"Unexpected API response format for version {version_id}")
    except (APIError, RateLimitError) as e:
        logger.error(f"Failed to get version info for Version ID {version_id}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching version {version_id}: {e}")
    
    return None


def get_game_version_and_mod_loader(config: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    """
    Extracts game version and mod loader information from the configuration.
    Expects a 'dependencies' key in the config.
    Returns (game_version, mod_loader, mod_loader_version).
    """
    dependencies = config.get("dependencies", {})
    game_version = dependencies.get("minecraft")
    mod_loaders = ["forge", "fabric", "quilt", "neoforge", "liteloader"]
    mod_loader = None
    mod_loader_version = None
    
    for loader in mod_loaders:
        if loader in dependencies:
            mod_loader = loader
            mod_loader_version = dependencies[loader]
            break
    
    if not game_version or not mod_loader:
        logger.error("Missing game version or mod loader in configuration.")
        return None, None, None
    
    return game_version, mod_loader, mod_loader_version


async def async_download_file(url: str, directory: str, expected_size: int | None = None) -> str:
    """
    Downloads a file asynchronously using aiohttp and displays a progress bar using tqdm.
    Returns the destination file path.
    """
    filename = urllib.parse.unquote(url.split("/")[-1])
    dest_path = os.path.join(directory, filename)
    os.makedirs(directory, exist_ok=True)
    
    timeout = aiohttp.ClientTimeout(total=300)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length", 0)) if expected_size is None else expected_size
            progress = tqdm(total=total, unit="B", unit_scale=True, desc=filename)
            with open(dest_path, "wb") as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
                    progress.update(len(chunk))
            progress.close()
    
    return dest_path


async def async_download_with_retry(url: str, directory: str, expected_size: int | None = None, max_retries: int = 3) -> str | None:
    """Download a file asynchronously with retry logic."""
    last_error: Exception | None = None
    
    for attempt in range(max_retries):
        try:
            return await async_download_file(url, directory, expected_size)
        except RateLimitError as e:
            logger.warning(f"Rate limited, waiting {e.retry_after}s before retry...")
            await asyncio.sleep(e.retry_after)
        except aiohttp.ClientError as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = 2 ** attempt
                logger.warning(f"Async download failed (attempt {attempt + 1}/{max_retries}), retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
    
    logger.error(f"Failed to download {url} after {max_retries} retries: {last_error}")
    return None


def download_file_wrapper(url: str, directory: str, expected_size: int | None = None, 
                         dry_run: bool = False, use_async: bool = False) -> tuple[str | None, bool]:
    """
    Wrapper function that selects asynchronous or synchronous download based on use_async.
    """
    if use_async and not dry_run:
        try:
            dest = asyncio.run(async_download_with_retry(url, directory, expected_size))
            return dest, dest is not None
        except Exception as e:
            logger.error(f"Async download error for {url}: {e}")
            return None, False
    else:
        return download_file(url, directory, expected_size, dry_run)


def extract_project_id(downloads: list[str]) -> str | None:
    """Extract project ID from downloads URL."""
    if not downloads:
        return None
    try:
        return downloads[0].split("/")[4]
    except IndexError:
        logger.error("Failed to extract project ID from downloads URL.")
        return None


def is_mod_up_to_date(project_id: str, mods_directory: str, latest_version_info: dict[str, Any]) -> bool:
    """Check if a mod is up to date."""
    current_version = get_mod_version(project_id)
    local_file_path = os.path.join(mods_directory, latest_version_info["files"][0]["filename"])
    
    if not current_version:
        return False
    
    if not os.path.exists(local_file_path):
        return False
    
    local_sha1 = calculate_local_file_sha1(local_file_path)
    return local_sha1 == current_version["sha1"]


def update_mod_in_database(project_id: str, version_info: dict[str, Any], file_info: dict[str, Any], 
                           new_url: str, mod_loader: str) -> None:
    """Update mod version information in the database."""
    save_mod_version(
        project_id=project_id,
        version_number=version_info["version_number"],
        file_url=new_url,
        file_size=file_info.get("size", 0),
        sha1=version_info.get("hashes", {}).get("sha1", ""),
        sha512=version_info.get("hashes", {}).get("sha512", ""),
        mod_loader=mod_loader,
    )


def check_single_mod_update(file_entry: dict[str, Any], mods_directory: str, 
                           game_version: str, mod_loader: str, dry_run: bool,
                           use_async: bool) -> str | None:
    """Check and update a single mod. Returns update message if updated, None otherwise."""
    project_id = extract_project_id(file_entry.get("downloads", []))
    if not project_id:
        return None
    
    latest_version_info = get_latest_version_info(project_id, game_version, mod_loader)
    if not latest_version_info:
        return None
    
    if is_mod_up_to_date(project_id, mods_directory, latest_version_info):
        logger.info(f"Mod {latest_version_info['files'][0]['filename']} is up-to-date.")
        return None
    
    current_version = get_mod_version(project_id)
    if current_version and current_version["version_number"] == latest_version_info["version_number"]:
        logger.info(f"Mod {latest_version_info['files'][0]['filename']} version unchanged.")
        return None
    
    for file_info in latest_version_info["files"]:
        if file_info.get("primary"):
            new_url = file_info["url"]
            
            if dry_run:
                logger.info(f"[DRY RUN] Would update mod {file_info['filename']} to version {latest_version_info['version_number']}")
                return f"Would update mod {file_info['filename']} to version {latest_version_info['version_number']}"
            
            sha1, sha512, file_size = download_and_calculate_hashes(new_url)
            if sha1 is None:
                continue
            
            file_path, _ = download_file_wrapper(new_url, mods_directory, expected_size=file_size, 
                                                dry_run=dry_run, use_async=use_async)
            if file_path is None:
                continue
            
            relative_file_path = get_relative_path(file_path, base_dir="current")
            file_entry["downloads"] = [new_url]
            file_entry["path"] = relative_file_path
            file_entry.setdefault("hashes", {})["sha1"] = sha1
            file_entry["hashes"]["sha512"] = sha512
            file_entry["fileSize"] = file_size
            
            update_mod_in_database(project_id, latest_version_info, file_info, new_url, mod_loader)
            
            update_message = f"Updated mod {file_info['filename']} to version {latest_version_info['version_number']}"
            logger.info(update_message)
            return update_message
    
    return None


def check_and_update_mod_versions(json_data: dict[str, Any], log_file_path: str, 
                                   game_version: str, mod_loader: str, 
                                   mods_directory: str, dry_run: bool = False, 
                                   use_async: bool = False) -> list[str]:
    """
    Checks for mod updates and updates the JSON data and database accordingly.
    Downloads new mod files if an update is available.
    """
    updates_log = []
    
    for file_entry in json_data.get("files", []):
        try:
            update_message = check_single_mod_update(
                file_entry, mods_directory, game_version, mod_loader, dry_run, use_async
            )
            if update_message:
                updates_log.append(update_message)
        except Exception as e:
            logger.error(f"Error processing mod: {e}")
    
    if updates_log and not dry_run:
        try:
            with open(log_file_path, "a") as log_file:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_file.write(f"Update log {timestamp}:\n")
                log_file.write("\n".join(updates_log) + "\n\n")
        except OSError as e:
            logger.error(f"Error writing update log: {e}")
    
    return updates_log


def add_mod_interactive(json_data: dict[str, Any], mods_directory: str, use_async: bool = False) -> None:
    """
    Adds a new mod to the modpack by prompting the user for information.
    """
    version_id = input("Enter the Version ID: ").strip()
    if not version_id:
        logger.error("No version ID provided.")
        return
    
    server_req = input("Is this mod required for the server? (yes/no): ").strip().lower()
    client_req = input("Is this mod required for the client? (yes/no): ").strip().lower()
    server_env = "required" if server_req.startswith("y") else "optional"
    client_env = "required" if client_req.startswith("y") else "optional"
    
    version_info = get_version_info_by_id(version_id)
    if not version_info:
        logger.error("Failed to retrieve version information.")
        return
    
    primary_file = next((f for f in version_info["files"] if f.get("primary")), version_info["files"][0])
    file_path, _ = download_file_wrapper(primary_file["url"], mods_directory, use_async=use_async)
    
    if file_path is None:
        logger.error("Failed to download mod file.")
        return
    
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
    json_data.setdefault("files", []).append(new_mod_entry)
    logger.info(f"Inserted new mod version {version_info['version_number']} for mod {primary_file.get('filename', 'unknown')}")


def list_mods(json_data: dict[str, Any]) -> None:
    """
    Lists all mods in the modpack.
    """
    if not json_data.get("files"):
        print("No mods found in the modpack.")
        return
    
    print("Mods in the modpack:")
    for idx, file_entry in enumerate(json_data["files"], start=1):
        project_id = extract_project_id(file_entry.get("downloads", [])) or "Unknown"
        filename = file_entry.get("path", "Unknown file")
        print(f"{idx}. Project ID: {project_id}, File: {filename}")


def remove_mod(json_data: dict[str, Any]) -> None:
    """
    Removes a mod from the modpack based on the provided project ID.
    """
    list_mods(json_data)
    mod_id = input("Enter the Project ID of the mod to remove: ").strip()
    
    initial_count = len(json_data.get("files", []))
    json_data["files"] = [
        entry for entry in json_data.get("files", [])
        if extract_project_id(entry.get("downloads", [])) != mod_id
    ]
    
    if len(json_data["files"]) < initial_count:
        logger.info(f"Mod with Project ID {mod_id} removed.")
    else:
        logger.info(f"No mod with Project ID {mod_id} found.")


def backup_current_version(current_dir: str, backups_dir: str) -> bool:
    """
    Creates a backup of the current modpack version.
    """
    if not os.path.exists(current_dir):
        logger.info("No current version to backup.")
        return False
    
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backups_dir, f"backup_{timestamp}")
    
    try:
        shutil.copytree(current_dir, backup_path)
        logger.info(f"Backup created at {backup_path}")
        return True
    except OSError as e:
        logger.error(f"Error creating backup: {e}")
        return False


def create_zip_package(new_version: str, current_dir: str, overrides_dir: str) -> bool:
    """
    Creates a zip package (with .mrpack extension) containing the updated modrinth.index.json
    and the contents of the overrides folder (packed under a single 'overrides' directory).
    """
    zip_filename = f"{new_version}.mrpack"
    try:
        with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
            index_path = os.path.join(current_dir, "modrinth.index.json")
            if os.path.exists(index_path):
                zipf.write(index_path, arcname="modrinth.index.json")
            
            if os.path.exists(overrides_dir):
                for foldername, subfolders, filenames in os.walk(overrides_dir):
                    for filename in filenames:
                        file_path = os.path.join(foldername, filename)
                        arcname = os.path.relpath(file_path, overrides_dir)
                        zipf.write(file_path, arcname=os.path.join("overrides", arcname))
        
        logger.info(f"Package created: {zip_filename}")
        return True
    except OSError as e:
        logger.error(f"Error creating zip package: {e}")
        return False


def save_modpack_json(json_data: dict[str, Any], current_dir: str) -> bool:
    """Save the modpack JSON file."""
    index_path = os.path.join(current_dir, "modrinth.index.json")
    try:
        with open(index_path, "w") as f:
            json.dump(json_data, f, indent=4)
        return True
    except OSError as e:
        logger.error(f"Error writing updated modpack JSON: {e}")
        return False


def update_pack(config: UpdaterConfig, json_data: dict[str, Any], db_cursor: Any) -> None:
    """
    Updates the modpack by:
      - Displaying the current version.
      - Prompting for a new version number, update summary, and dry-run option.
      - Warning if the overrides folder is non-empty.
      - Creating a backup.
      - Updating mods via check_and_update_mod_versions.
      - Saving updated JSON (with new version and summary) and creating a .mrpack package.
    """
    current_version = json_data.get("versionId", "unknown")
    print(f"Current version is: {current_version}")
    
    new_version = input("Enter the new version number to assign (must be different from current version): ").strip()
    if new_version == current_version:
        logger.error("New version is the same as the current version. Update aborted.")
        return
    
    new_summary = input("Enter a summary for this update: ").strip()
    dry_run_input = input("Perform a dry-run? (yes/no): ").strip().lower()
    dry_run = dry_run_input.startswith("y")

    overrides_dir = config.overrides_directory
    if os.path.exists(overrides_dir) and os.listdir(overrides_dir):
        print("Warning: The 'overrides' folder is not empty. Please update mods in it manually before running the updater.")
        proceed = input("Do you want to proceed? (yes/no): ").strip().lower()
        if not proceed.startswith("y"):
            logger.info("Update cancelled by user due to overrides warning.")
            return

    if dry_run:
        logger.info("[DRY RUN] No changes will be made.")
    else:
        backup_current_version(config.download_directory, config.backup_directory)

    game_version, mod_loader, _ = get_game_version_and_mod_loader(json_data)
    if not game_version or not mod_loader:
        logger.error("Failed to extract game version or mod loader from configuration.")
        return

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_name = f"mod_updates_log_{timestamp}.txt"
    log_file_path = os.path.join(config.logs_directory, log_file_name)

    check_and_update_mod_versions(
        json_data, log_file_path, game_version, mod_loader, 
        config.mods_dir, dry_run, config.async_downloads
    )

    if not dry_run:
        json_data["versionId"] = new_version
        json_data["summary"] = new_summary
        save_modpack_json(json_data, config.download_directory)
        db_cursor.connection.commit()
        create_zip_package(new_version, config.download_directory, config.overrides_directory)
    else:
        logger.info("[DRY RUN] Update simulation complete.")


def build_modpack(config: UpdaterConfig, json_data: dict[str, Any], db_cursor: Any) -> None:
    """
    Builds the modpack without updating/downloading mods.
    This function:
      - Displays the current version.
      - Prompts for a new version and a build summary.
      - Optionally creates a backup.
      - Updates the modpack JSON with the new version and summary.
      - Creates a .mrpack package.
    """
    current_version = json_data.get("versionId", "unknown")
    print(f"Current version is: {current_version}")
    
    new_version = input("Enter the new version number to assign (must be different from current version): ").strip()
    if new_version == current_version:
        logger.error("New version is the same as the current version. Build aborted.")
        return
    
    new_summary = input("Enter a summary for this build: ").strip()
    dry_run_input = input("Perform a dry-run? (yes/no): ").strip().lower()
    dry_run = dry_run_input.startswith("y")
    
    overrides_dir = config.overrides_directory
    if os.path.exists(overrides_dir) and os.listdir(overrides_dir):
        print("Warning: The 'overrides' folder is not empty. Please ensure it is updated manually if needed.")
        proceed = input("Do you want to proceed? (yes/no): ").strip().lower()
        if not proceed.startswith("y"):
            logger.info("Build cancelled by user due to overrides warning.")
            return
    
    if not dry_run:
        backup_current_version(config.download_directory, config.backup_directory)
    
    json_data["versionId"] = new_version
    json_data["summary"] = new_summary
    
    save_modpack_json(json_data, config.download_directory)
    db_cursor.connection.commit()
    create_zip_package(new_version, config.download_directory, config.overrides_directory)
    
    if dry_run:
        logger.info("[DRY RUN] Build simulation complete.")
