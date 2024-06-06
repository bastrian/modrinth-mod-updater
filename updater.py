import requests
import json
import sqlite3
import hashlib
import os
import datetime
import urllib.parse

# Database setup
db_connection = sqlite3.connect('mod_versions.db')
db_cursor = db_connection.cursor()

# Create table if it does not exist
db_cursor.execute('''
    CREATE TABLE IF NOT EXISTS mod_versions (
        project_id TEXT PRIMARY KEY,
        version_number TEXT,
        file_url TEXT,
        file_size INTEGER,
        sha1 TEXT,
        sha512 TEXT,
        mod_loader TEXT
    )
''')
db_connection.commit()

# Function to download a file and calculate its SHA1, SHA512 hashes, and size
def download_and_calculate_hashes(url):
    response = requests.get(url, stream=True)
    sha1_hash = hashlib.sha1()
    sha512_hash = hashlib.sha512()
    total_bytes = 0
    for chunk in response.iter_content(chunk_size=8192):
        total_bytes += len(chunk)
        sha1_hash.update(chunk)
        sha512_hash.update(chunk)
    return sha1_hash.hexdigest(), sha512_hash.hexdigest(), total_bytes

# Function to get the latest version information from Modrinth
def get_latest_version_info(project_id, game_version, mod_loader):
    api_url = f"https://api.modrinth.com/v2/project/{project_id}/version"
    params = {
        'loaders': json.dumps([mod_loader]),
        'game_versions': json.dumps([game_version])
    }
    response = requests.get(api_url, params=params)
    if response.status_code == 200:
        versions = response.json()
        for version in versions:
            if mod_loader in version['loaders'] and game_version in version['game_versions']:
                return version
    return None

# Function to get version information by version ID from Modrinth
def get_version_info_by_id(version_id):
    api_url = f"https://api.modrinth.com/v2/version/{version_id}"
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get version information for Version ID {version_id}")
        return None

# Function to download a file if not present or outdated
def download_file(url, directory, expected_size=None):
    # Extract the filename and decode it to handle percent-encoded characters
    filename = urllib.parse.unquote(url.split('/')[-1])
    file_path = os.path.join(directory, filename)
    
    try:
        # Check if the directory exists, if not, create it
        os.makedirs(directory, exist_ok=True)

        # Check if the file already exists with the expected size
        if os.path.exists(file_path):
            if expected_size is None or os.path.getsize(file_path) == expected_size:
                print(f"File already exists with the expected size: {file_path}")
                return file_path, False  # No need to download
            else:
                print(f"File size mismatch, re-downloading: {file_path}")

        # Download the file
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Downloaded file to {file_path}")
            return file_path, True  # File was downloaded
        else:
            print(f"Failed to download file from {url}")
            return None, False
    except Exception as e:
        print(f"An error occurred while downloading the file: {e}")
        return None, False
    
# Function to check and update the mod versions, now with downloading check, logging, and mod loader compatibility
def check_and_update_mod_versions(json_data, db_cursor, log_file_path, game_version, mod_loader):
    updates_log = []
    for file_entry in json_data['files']:
        project_id = file_entry['downloads'][0].split('/')[4]
        latest_version_info = get_latest_version_info(project_id, game_version, mod_loader)
        if latest_version_info:
            db_cursor.execute('SELECT version_number, file_url, sha1 FROM mod_versions WHERE project_id = ?', (project_id,))
            current_version = db_cursor.fetchone()
            local_file_path = os.path.join('mods', latest_version_info['files'][0]['filename'])
            
            if current_version:
                if os.path.exists(local_file_path):
                    # Compare local file hash with the hash in the database
                    local_sha1 = calculate_local_file_sha1(local_file_path)
                    if local_sha1 == current_version[2]:
                        print(f"Mod {latest_version_info['files'][0]['filename']} is up-to-date.")
                        continue

            if not current_version or current_version[0] != latest_version_info['version_number']:
                for file_info in latest_version_info['files']:
                    if file_info['primary']:
                        new_url = file_info['url']
                        sha1, sha512, file_size = download_and_calculate_hashes(new_url)
                        file_path = download_file(new_url, 'mods', expected_size=file_size)
                        file_entry['downloads'] = [new_url]
                        file_entry['path'] = file_path
                        file_entry['hashes']['sha1'] = sha1
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
                        print(update_message)
                        updates_log.append(update_message)

    # Log the updates
    if updates_log:
        with open(log_file_path, 'a') as log_file:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file.write(f"Update log {timestamp}:\n")
            log_file.write("\n".join(updates_log) + "\n\n")

# Function to calculate the SHA1 hash of a local file
def calculate_local_file_sha1(file_path):
    sha1_hash = hashlib.sha1()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha1_hash.update(chunk)
    return sha1_hash.hexdigest()

# Function to insert new mod versions from Version IDs provided in new.txt
def insert_new_versions_from_ids(json_data, new_file_path):
    with open(new_file_path, 'r') as file:
        lines = [line.strip() for line in file.readlines() if line.strip()]

    for line in lines:
        parts = line.split()
        if len(parts) >= 3:
            version_id, server_env, client_env = parts[0], parts[1], parts[2]
        else:
            print(f"Skipping invalid line: {line}")
            continue

        version_info = get_version_info_by_id(version_id)
        if version_info:
            primary_file = next((f for f in version_info['files'] if f['primary']), version_info['files'][0])

            # Determine the directory to download the mod to
            directory = 'mods'
            if server_env == 'required':
                directory = 'server'

            # Download the file
            file_path = download_file(primary_file['url'], directory)

            new_mod_entry = {
                "path": file_path,
                "hashes": primary_file['hashes'],
                "env": {
                    "server": server_env,
                    "client": client_env
                },
                "downloads": [primary_file['url']],
                "fileSize": primary_file['size']
            }

            json_data['files'].append(new_mod_entry)
            print(f"Inserted new version {version_info['version_number']} for mod {primary_file['filename']} with server env '{server_env}' and client env '{client_env}'")

# Function to automatically extract game version and mod loader from JSON
def get_game_version_and_mod_loader(json_data):
    game_version = json_data['dependencies'].get('minecraft')
    mod_loaders = ['forge', 'fabric', 'quilt']  # List of possible mod loaders
    mod_loader = None
    mod_loader_version = None

    # Iterate over possible mod loaders to find which one is present
    for loader in mod_loaders:
        if loader in json_data['dependencies']:
            mod_loader = loader
            mod_loader_version = json_data['dependencies'][loader]
            break

    if not game_version or not mod_loader:
        print("Could not find necessary game version or mod loader information.")
        return None, None, None

    return game_version, mod_loader, mod_loader_version

# Main script execution
if __name__ == "__main__":
    # Load the JSON data
    try:
        with open('modrinth.index.json', 'r') as file:
            json_data = json.load(file)
    except Exception as e:
        print(f"Failed to load modrinth.index.json: {e}")
        exit()

    # Extract game version and mod loader from JSON
    game_version, mod_loader, mod_loader_version = get_game_version_and_mod_loader(json_data)

    if not game_version or not mod_loader:
        print("Failed to extract game version or mod loader from JSON.")
        exit()

    print(f"Minecraft version: {game_version}, mod loader: {mod_loader} version {mod_loader_version}")

    # Define the logs directory and create it if it doesn't exist
    logs_directory = os.path.join(os.getcwd(), "logs")
    if not os.path.exists(logs_directory):
        os.makedirs(logs_directory)

    # Define the log file path with a timestamp within the logs directory
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_name = f"mod_updates_log_{timestamp}.txt"
    log_file_path = os.path.join(logs_directory, log_file_name)

    # Update existing mods specific to the game version and mod loader
    check_and_update_mod_versions(json_data, db_cursor, log_file_path, game_version, mod_loader)

    # Insert new mods from new.txt
    new_file_path = 'new.txt'
    if os.path.exists(new_file_path):
        insert_new_versions_from_ids(json_data, new_file_path)

    # Write the updated JSON data back to the file
    with open('modrinth.index.json', 'w') as file:
        json.dump(json_data, file, indent=4)

    # Close the database connection
    db_connection.close()