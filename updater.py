import requests
import json
import sqlite3
import hashlib
import os
import datetime

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
        sha512 TEXT
    )
''')
db_connection.commit()

# Function to download a file and calculate its SHA1, SHA512 hashes and size
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
def get_latest_version_info(project_id):
    api_url = f"https://api.modrinth.com/v2/project/{project_id}/version"
    params = {
        'loaders': json.dumps(["forge"]),
        'game_versions': json.dumps(["1.20.1"])
    }
    response = requests.get(api_url, params=params)
    if response.status_code == 200:
        versions = response.json()
        for version in versions:
            if "forge" in version['loaders'] and "1.20.1" in version['game_versions']:
                return version
    return None

# Function to get version information by Version ID from Modrinth
def get_version_info_by_id(version_id):
    api_url = f"https://api.modrinth.com/v2/version/{version_id}"
    response = requests.get(api_url)
    if response.status_code == 200:
        return response.json()
    else:
        print(f"Failed to get version information for Version ID {version_id}")
        return None

# Helper function to download a file and save it to a specific directory
def download_file(url, directory, expected_size=None):
    filename = url.split('/')[-1]
    file_path = os.path.join(directory, filename)
    # Check if the file already exists and has the expected size
    if os.path.exists(file_path):
        if expected_size is None or os.path.getsize(file_path) == expected_size:
            print(f"File already exists with the expected size: {file_path}")
            return file_path
        else:
            print(f"File size mismatch, re-downloading: {file_path}")

    # Proceed to download the file
    response = requests.get(url, stream=True)
    if response.status_code == 200:
        os.makedirs(directory, exist_ok=True)
        with open(file_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print(f"Downloaded file to {file_path}")
        return file_path
    else:
        print(f"Failed to download file from {url}")
        return None

# Function to check and update the mod versions, now with logging
# Function to check and update the mod versions, now with downloading check and logging
def check_and_update_mod_versions(json_data, db_cursor, log_file_path):
    updates_log = []
    for file_entry in json_data['files']:
        project_id = file_entry['downloads'][0].split('/')[4]
        latest_version_info = get_latest_version_info(project_id)
        if latest_version_info:
            db_cursor.execute('SELECT version_number FROM mod_versions WHERE project_id = ?', (project_id,))
            current_version = db_cursor.fetchone()
            if not current_version or current_version[0] != latest_version_info['version_number']:
                for file_info in latest_version_info['files']:
                    if file_info['primary']:
                        new_url = file_info['url']
                        sha1, sha512, file_size = download_and_calculate_hashes(new_url)

                        # Determine the directory to download the mod to
                        directory = 'mods'
                        if file_entry['env']['server'] == 'required':
                            directory = 'server'

                        # Download the file if not present or if the file size is different
                        file_path = download_file(new_url, directory, expected_size=file_size)

                        # Update the JSON entry with the new version information
                        file_entry['downloads'] = [new_url]
                        file_entry['path'] = file_path
                        file_entry['hashes']['sha1'] = sha1
                        file_entry['hashes']['sha512'] = sha512
                        file_entry['fileSize'] = file_size

                        db_cursor.execute('''
                            INSERT INTO mod_versions (project_id, version_number, file_url, file_size, sha1, sha512)
                            VALUES (?, ?, ?, ?, ?, ?)
                            ON CONFLICT(project_id) DO UPDATE SET
                            version_number = excluded.version_number,
                            file_url = excluded.file_url,
                            file_size = excluded.file_size,
                            sha1 = excluded.sha1,
                            sha512 = excluded.sha512
                        ''', (project_id, latest_version_info['version_number'], new_url, file_size, sha1, sha512))
                        db_connection.commit()

                        mod_name = file_info['filename']
                        update_message = f"Updated mod {mod_name} to version {latest_version_info['version_number']}"
                        print(update_message)
                        updates_log.append(update_message)

    # Log the updates
    if updates_log:
        with open(log_file_path, 'a') as log_file:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_file.write(f"Update log {timestamp}:\n")
            log_file.write("\n".join(updates_log) + "\n\n")

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

# Main script execution
if __name__ == "__main__":
    # Load the JSON data
    with open('modrinth.index.json', 'r') as file:
        json_data = json.load(file)

    # Define the logs directory and create it if it doesn't exist
    logs_directory = os.path.join(os.getcwd(), "logs")
    if not os.path.exists(logs_directory):
        os.makedirs(logs_directory)

    # Define the log file path with a timestamp within the logs directory
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    log_file_name = f"mod_updates_log_{timestamp}.txt"
    log_file_path = os.path.join(logs_directory, log_file_name)

    # Update existing mods
    check_and_update_mod_versions(json_data, db_cursor, log_file_path)

    # Insert new mods from new.txt
    new_file_path = 'new.txt'
    if os.path.exists(new_file_path):
        insert_new_versions_from_ids(json_data, new_file_path)

    # Write the updated JSON data back to the file
    with open('modrinth.index.json', 'w') as file:
        json.dump(json_data, file, indent=4)

    # Close the database connection
    db_connection.close()
