import requests
import json
import hashlib
import os
import datetime
import urllib.parse
import shutil
import zipfile
import logging
import asyncio
import aiohttp
from tqdm import tqdm

def get_relative_path(file_path, base_dir="current"):
    """
    Converts an absolute file path (e.g. 'current\\mods\\file.jar')
    to a relative path starting from the mods folder (e.g. 'mods/file.jar').
    """
    if file_path:
        relative = file_path.replace(base_dir + os.sep, "")
        return relative.replace(os.sep, "/")
    return None

def download_and_calculate_hashes(url):
    """
    Downloads content from a URL and calculates its SHA1 and SHA512 hashes,
    as well as the total size in bytes.
    Returns (sha1, sha512, total_bytes).
    """
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Failed to download URL {url}: {e}")
        return None, None, 0

    sha1_hash = hashlib.sha1()
    sha512_hash = hashlib.sha512()
    total_bytes = 0
    for chunk in response.iter_content(chunk_size=8192):
        total_bytes += len(chunk)
        sha1_hash.update(chunk)
        sha512_hash.update(chunk)
    return sha1_hash.hexdigest(), sha512_hash.hexdigest(), total_bytes

def download_file(url, directory, expected_size=None, dry_run=False):
    """
    Synchronously downloads a file from the specified URL into the given directory.
    Checks file size if expected_size is provided.
    If dry_run is True, simulates the download.
    Returns (file_path, downloaded_flag).
    """
    filename = urllib.parse.unquote(url.split('/')[-1])
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
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        logging.info(f"Downloaded file to {file_path}")
        return file_path, True
    except Exception as e:
        logging.error(f"Error downloading file from {url}: {e}")
        return None, False

def calculate_local_file_sha1(file_path):
    """
    Calculates and returns the SHA1 hash of a local file.
    """
    sha1_hash = hashlib.sha1()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha1_hash.update(chunk)
        return sha1_hash.hexdigest()
    except Exception as e:
        logging.error(f"Error calculating SHA1 for {file_path}: {e}")
        return None

def get_latest_version_info(project_id, game_version, mod_loader):
    """
    Retrieves the latest version information for a given project from the Modrinth API.
    """
    api_url = f"https://api.modrinth.com/v2/project/{project_id}/version"
    params = {
        'loaders': json.dumps([mod_loader]),
        'game_versions': json.dumps([game_version])
    }
    try:
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        versions = response.json()
        for version in versions:
            if mod_loader in version['loaders'] and game_version in version['game_versions']:
                return version
    except Exception as e:
        logging.error(f"Error fetching version info for project {project_id}: {e}")
    return None

def get_version_info_by_id(version_id):
    """
    Retrieves version information for a specific Version ID from the Modrinth API.
    """
    api_url = f"https://api.modrinth.com/v2/version/{version_id}"
    try:
        response = requests.get(api_url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Failed to get version info for Version ID {version_id}: {e}")
        return None

def get_game_version_and_mod_loader(config):
    """
    Extracts game version and mod loader information from the configuration.
    Expects a 'dependencies' key in the config.
    Returns (game_version, mod_loader, mod_loader_version).
    """
    dependencies = config.get('dependencies', {})
    game_version = dependencies.get('minecraft')
    mod_loaders = ['forge', 'fabric', 'quilt']
    mod_loader = None
    mod_loader_version = None
    for loader in mod_loaders:
        if loader in dependencies:
            mod_loader = loader
            mod_loader_version = dependencies[loader]
            break
    if not game_version or not mod_loader:
        logging.error("Missing game version or mod loader in configuration.")
        return None, None, None
    return game_version, mod_loader, mod_loader_version

async def async_download_file(url, directory, expected_size=None):
    """
    Downloads a file asynchronously using aiohttp and displays a progress bar using tqdm.
    Returns the destination file path.
    """
    filename = urllib.parse.unquote(url.split('/')[-1])
    dest_path = os.path.join(directory, filename)
    os.makedirs(directory, exist_ok=True)
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            total = int(response.headers.get('Content-Length', 0)) if expected_size is None else expected_size
            progress = tqdm(total=total, unit='B', unit_scale=True, desc=filename)
            with open(dest_path, 'wb') as f:
                async for chunk in response.content.iter_chunked(8192):
                    f.write(chunk)
                    progress.update(len(chunk))
            progress.close()
    return dest_path

def download_file_wrapper(url, directory, expected_size=None, dry_run=False, use_async=False):
    """
    Wrapper function that selects asynchronous or synchronous download based on use_async.
    """
    if use_async and not dry_run:
        try:
            dest = asyncio.run(async_download_file(url, directory, expected_size))
            return dest, True
        except Exception as e:
            logging.error(f"Async download error for {url}: {e}")
            return None, False
    else:
        return download_file(url, directory, expected_size, dry_run)

def check_and_update_mod_versions(json_data, db_cursor, log_file_path, game_version, mod_loader, mods_directory, dry_run=False, use_async=False):
    """
    Checks for mod updates and updates the JSON data and database accordingly.
    Downloads new mod files if an update is available.
    """
    updates_log = []
    for file_entry in json_data.get('files', []):
        try:
            project_id = file_entry['downloads'][0].split('/')[4]
        except IndexError:
            logging.error("Failed to extract project ID from downloads URL.")
            continue

        latest_version_info = get_latest_version_info(project_id, game_version, mod_loader)
        if latest_version_info:
            db_cursor.execute('SELECT version_number, file_url, sha1 FROM mod_versions WHERE project_id = ?', (project_id,))
            current_version = db_cursor.fetchone()
            local_file_path = os.path.join(mods_directory, latest_version_info['files'][0]['filename'])
            if current_version:
                if os.path.exists(local_file_path):
                    local_sha1 = calculate_local_file_sha1(local_file_path)
                    if local_sha1 == current_version[2]:
                        logging.info(f"Mod {latest_version_info['files'][0]['filename']} is up-to-date.")
                        continue
            if not current_version or current_version[0] != latest_version_info['version_number']:
                for file_info in latest_version_info['files']:
                    if file_info.get('primary'):
                        new_url = file_info['url']
                        if dry_run:
                            logging.info(f"[DRY RUN] Would update mod {file_info['filename']} to version {latest_version_info['version_number']}")
                            continue
                        sha1, sha512, file_size = download_and_calculate_hashes(new_url)
                        file_path, _ = download_file_wrapper(new_url, mods_directory, expected_size=file_size, dry_run=dry_run, use_async=use_async)
                        relative_file_path = get_relative_path(file_path, base_dir="current")
                        file_entry['downloads'] = [new_url]
                        file_entry['path'] = relative_file_path
                        file_entry.setdefault('hashes', {})['sha1'] = sha1
                        file_entry['hashes']['sha512'] = sha512
                        file_entry['fileSize'] = file_size
                        db_cursor.execute('''
                            INSERT INTO mod_versions (project_id, version_number, file_url, file_size, sha1, sha512, mod_loader)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(project_id) DO UPDATE SET
                                version_number = excluded.version_number,
                                file_url = excluded.file_url,
                                file_size = excluded.file_size,
                                sha1 = excluded.sha1,
                                sha512 = excluded.sha512,
                                mod_loader = excluded.mod_loader
                        ''', (project_id, latest_version_info['version_number'], new_url, file_size, sha1, sha512, mod_loader))
                        update_message = f"Updated mod {file_info['filename']} to version {latest_version_info['version_number']}"
                        logging.info(update_message)
                        updates_log.append(update_message)
    if updates_log and not dry_run:
        try:
            with open(log_file_path, 'a') as log_file:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                log_file.write(f"Update log {timestamp}:\n")
                log_file.write("\n".join(updates_log) + "\n\n")
        except Exception as e:
            logging.error(f"Error writing update log: {e}")

def add_mod_interactive(json_data, mods_directory, use_async=False):
    """
    Adds a new mod to the modpack by prompting the user for information.
    """
    version_id = input("Enter the Version ID: ").strip()
    server_req = input("Is this mod required for the server? (yes/no): ").strip().lower()
    client_req = input("Is this mod required for the client? (yes/no): ").strip().lower()
    server_env = "required" if server_req.startswith('y') else "optional"
    client_env = "required" if client_req.startswith('y') else "optional"
    version_info = get_version_info_by_id(version_id)
    if version_info:
        primary_file = next((f for f in version_info['files'] if f.get('primary')), version_info['files'][0])
        file_path, _ = download_file_wrapper(primary_file['url'], mods_directory, use_async=use_async)
        relative_file_path = get_relative_path(file_path, base_dir="current")
        new_mod_entry = {
            "path": relative_file_path,
            "hashes": primary_file.get('hashes', {}),
            "env": {
                "server": server_env,
                "client": client_env
            },
            "downloads": [primary_file['url']],
            "fileSize": primary_file.get('size', 0)
        }
        json_data.setdefault('files', []).append(new_mod_entry)
        logging.info(f"Inserted new mod version {version_info['version_number']} for mod {primary_file.get('filename', 'unknown')}")
    else:
        logging.error("Failed to retrieve version information.")

def list_mods(json_data):
    """
    Lists all mods in the modpack.
    """
    if not json_data.get('files'):
        print("No mods found in the modpack.")
        return
    print("Mods in the modpack:")
    for idx, file_entry in enumerate(json_data['files'], start=1):
        try:
            project_id = file_entry['downloads'][0].split('/')[4]
        except IndexError:
            project_id = "Unknown"
        filename = file_entry.get('path', 'Unknown file')
        print(f"{idx}. Project ID: {project_id}, File: {filename}")

def remove_mod(json_data):
    """
    Removes a mod from the modpack based on the provided project ID.
    """
    list_mods(json_data)
    mod_id = input("Enter the Project ID of the mod to remove: ").strip()
    initial_count = len(json_data.get('files', []))
    json_data['files'] = [entry for entry in json_data.get('files', []) if entry['downloads'][0].split('/')[4] != mod_id]
    if len(json_data['files']) < initial_count:
        logging.info(f"Mod with Project ID {mod_id} removed.")
    else:
        logging.info(f"No mod with Project ID {mod_id} found.")

def backup_current_version(current_dir, backups_dir):
    """
    Creates a backup of the current modpack version.
    """
    if not os.path.exists(current_dir):
        logging.info("No current version to backup.")
        return
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = os.path.join(backups_dir, f"backup_{timestamp}")
    try:
        shutil.copytree(current_dir, backup_path)
        logging.info(f"Backup created at {backup_path}")
    except Exception as e:
        logging.error(f"Error creating backup: {e}")

def create_zip_package(new_version, current_dir, overrides_dir):
    """
    Creates a zip package (with .mrpack extension) containing the updated modrinth.index.json
    and the contents of the overrides folder (packed under a single 'overrides' directory).
    """
    zip_filename = f"{new_version}.mrpack"
    try:
        with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
            index_path = os.path.join(current_dir, "modrinth.index.json")
            if os.path.exists(index_path):
                zipf.write(index_path, arcname="modrinth.index.json")
            if os.path.exists(overrides_dir):
                for foldername, subfolders, filenames in os.walk(overrides_dir):
                    for filename in filenames:
                        file_path = os.path.join(foldername, filename)
                        # Compute relative path from the overrides folder
                        arcname = os.path.relpath(file_path, overrides_dir)
                        zipf.write(file_path, arcname=os.path.join("overrides", arcname))
        logging.info(f"Package created: {zip_filename}")
    except Exception as e:
        logging.error(f"Error creating zip package: {e}")

def update_pack(json_data, db_cursor, current_dir, mods_directory, backups_dir, overrides_dir, logs_dir, use_async=False):
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
        logging.error("New version is the same as the current version. Update aborted.")
        return
    new_summary = input("Enter a summary for this update: ").strip()
    dry_run_input = input("Perform a dry-run? (yes/no): ").strip().lower()
    dry_run = dry_run_input.startswith('y')

    if os.path.exists(overrides_dir) and os.listdir(overrides_dir):
        print("Warning: The 'overrides' folder is not empty. Please update mods in it manually before running the updater.")
        proceed = input("Do you want to proceed? (yes/no): ").strip().lower()
        if not proceed.startswith('y'):
            logging.info("Update cancelled by user due to overrides warning.")
            return

    if dry_run:
        logging.info("[DRY RUN] No changes will be made.")
    else:
        backup_current_version(current_dir, backups_dir)

    game_version, mod_loader, _ = get_game_version_and_mod_loader(json_data)
    if not game_version or not mod_loader:
        logging.error("Failed to extract game version or mod loader from configuration.")
        return

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_name = f"mod_updates_log_{timestamp}.txt"
    log_file_path = os.path.join(logs_dir, log_file_name)

    check_and_update_mod_versions(json_data, db_cursor, log_file_path, game_version, mod_loader, mods_directory, dry_run, use_async)

    if not dry_run:
        json_data["versionId"] = new_version
        json_data["summary"] = new_summary

        index_path = os.path.join(current_dir, "modrinth.index.json")
        try:
            with open(index_path, 'w') as f:
                json.dump(json_data, f, indent=4)
        except Exception as e:
            logging.error(f"Error writing updated modpack JSON: {e}")
        db_cursor.connection.commit()
        create_zip_package(new_version, current_dir, overrides_dir)
    else:
        logging.info("[DRY RUN] Update simulation complete.")

def build_modpack(json_data, db_cursor, current_dir, mods_directory, backups_dir, overrides_dir, logs_dir):
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
        logging.error("New version is the same as the current version. Build aborted.")
        return
    new_summary = input("Enter a summary for this build: ").strip()
    dry_run_input = input("Perform a dry-run? (yes/no): ").strip().lower()
    dry_run = dry_run_input.startswith('y')
    
    if os.path.exists(overrides_dir) and os.listdir(overrides_dir):
        print("Warning: The 'overrides' folder is not empty. Please ensure it is updated manually if needed.")
        proceed = input("Do you want to proceed? (yes/no): ").strip().lower()
        if not proceed.startswith('y'):
            logging.info("Build cancelled by user due to overrides warning.")
            return
    
    if not dry_run:
        backup_current_version(current_dir, backups_dir)
    
    # No mod downloads; just update the JSON with new version and summary
    json_data["versionId"] = new_version
    json_data["summary"] = new_summary
    
    index_path = os.path.join(current_dir, "modrinth.index.json")
    try:
        with open(index_path, 'w') as f:
            json.dump(json_data, f, indent=4)
    except Exception as e:
        logging.error(f"Error writing updated modpack JSON: {e}")
    db_cursor.connection.commit()
    create_zip_package(new_version, current_dir, overrides_dir)
    if dry_run:
        logging.info("[DRY RUN] Build simulation complete.")
