# Modrinth Mod Updater

A Python script designed to automatically check for mod updates on Modrinth using their API, update the local `modrinth.index.json` file accordingly, and download updated or new mods into designated folders.

## Features

- **Automatic Updates**: Fetches the latest mod versions from Modrinth and updates local files.
- **Selective Downloading**: Downloads new or updated mods while avoiding unnecessary downloads.
- **Environment Awareness**: Sorts mods into `server` or `mods` directories based on environment requirements.
- **Logging**: Maintains detailed logs of updates in a `logs` directory with timestamps.

## Getting Started

### Prerequisites

- Python 3.6 or higher
- `requests` library

### Installation

1. Clone the repository or download the script to your local machine.
2. Install the required Python packages:

```shell
pip install requests
```
### Configuration

1. Place your `modrinth.index.json` in the same directory as the script.
2. If adding new mods, create a `new.txt` file in the same directory with the format:
VersionID ServerENV ClientENV

For example:
abcdefgh required optional

This indicates the mod version ID, and whether it is required or optional on the server or client.

### Usage

Run the script with the following command:

• Bash 
```shell 
python updater.py
```

• Linux Terminal default python 
```shell
python3 updater.py
```

• Windows 
```shell
python .\updater.py
```

Check the logs directory for an update log named with the timestamp of when the script was run.

## Contributing

Contributions are welcome! If you have a suggestion that would improve this, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement". Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## License

Distributed under the MIT License. See `LICENSE` for more information.
