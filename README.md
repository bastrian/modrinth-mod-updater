# Modrinth Modpack Manager

A Python-based tool for managing and updating your Minecraft modpack by automatically checking for mod updates via the Modrinth API. The tool updates your local `modrinth.index.json` file, downloads new or updated mods into designated folders, and offers several interactive options for building and configuring your modpack.

## Features

- **Automatic Updates:**  
  Automatically fetches the latest mod versions from Modrinth and updates local files accordingly.
- **Selective Downloading:**  
  Only downloads mods that have updates, avoiding unnecessary downloads.
- **Environment Awareness:**  
  Organizes mods based on their usage (e.g., server vs. client).
- **Robust Logging & Error Handling:**  
  Detailed logs are maintained in a logs directory with customizable logging levels.
- **Dedicated Configuration:**  
  Uses two configuration files:
  - `modrinth.index.json` for modpack settings (including dependencies, version, and files).
  - `updater_config.json` for updater-specific settings (logging level, download directories, async download flag, etc.).
- **Asynchronous Downloads:**  
  Supports faster downloads via asynchronous routines using `aiohttp` and `tqdm` for progress visualization.
- **Build Modpack:**  
  Create a packaged modpack without updating/downloading mods, ideal for final distribution.
- **Dependency Updates:**  
  Update the Minecraft version and mod loader interactively. The tool displays current values and suggests allowed mod loaders: **fabric, forge, neoforge, quilt,** and **liteloader**.
- **Interactive Configuration Menu:**  
  Easily adjust updater settings (e.g., logging level, directories) directly from the main menu.

## Getting Started

### Prerequisites

- Python 3.6 or higher
- Required Python packages (listed in `requirements.txt`):
  - `requests`
  - `aiohttp`
  - `tqdm`

### Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/yourusername/modrinth-modpack-manager.git
   cd modrinth-modpack-manager

2. **Set Up the Environment:**

    ***Windows:***

    Run the provided batch script:
    ```bash
    setup.bat

    ***Linux:***
    Make the setup script executable and run it:
    ```bash
    chmod +x setup.sh
    ./setup.sh

3. **Configuration:**
    Place your modrinth.index.json in the project root, or let the tool guide you through the initial setup.
    The updater settings are stored in updater_config.json and can be modified via the interactive configuration menu.

**Usage**
Run the main script with:

***Windows:***
    ```bash
    python main.py

***Linux/Mac:***
    ```bash
    python3 main.py

**Menu Options**

    Add a mod:
    Add a new mod by providing its Version ID and specifying whether it is required for the server or client.
    List mods:
    Display all mods currently in the modpack.
    Remove a mod:
    Remove a mod from the modpack by specifying its Project ID.
    Update modpack:
    Check for mod updates, download new versions, update the JSON, and package the modpack.
    Build modpack:
    Build the modpack (update version and summary) without downloading or updating mods.
    Configure updater settings:
    Update settings such as logging level, directory paths, and whether to use asynchronous downloads.
    Update modpack dependencies:
    Update the Minecraft version and mod loader (with allowed options: fabric, forge, neoforge, quilt, liteloader). The current settings are displayed, and you can choose to update or keep them.
    Exit:
    Save changes and exit the application.