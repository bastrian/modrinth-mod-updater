import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

UPDATER_CONFIG_FILE = "updater_config.json"


@dataclass
class UpdaterConfig:
    """Configuration class for the updater application."""
    logging_level: str = "INFO"
    async_downloads: bool = True
    download_directory: str = "current"
    backup_directory: str = "backups"
    overrides_directory: str = "overrides"
    logs_directory: str = "logs"
    
    # Computed properties (set after initialization)
    _mods_dir: str = field(init=False, repr=False)
    _config_file: str = field(init=False, repr=False)
    
    def __post_init__(self) -> None:
        """Set computed properties after initialization."""
        self._mods_dir = os.path.join(self.download_directory, "mods")
        self._config_file = "modrinth.index.json"
    
    @property
    def mods_dir(self) -> str:
        """Get the mods directory path."""
        return self._mods_dir
    
    @property
    def config_file(self) -> str:
        """Get the config file name."""
        return self._config_file
    
    def ensure_directories(self) -> None:
        """Create all required directories."""
        for directory in [self.download_directory, self.mods_dir, self.backup_directory, 
                         self.overrides_directory, self.logs_directory]:
            os.makedirs(directory, exist_ok=True)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for JSON serialization."""
        return {
            "logging_level": self.logging_level,
            "async_downloads": self.async_downloads,
            "download_directory": self.download_directory,
            "backup_directory": self.backup_directory,
            "overrides_directory": self.overrides_directory,
            "logs_directory": self.logs_directory,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UpdaterConfig":
        """Create config from dictionary."""
        return cls(
            logging_level=data.get("logging_level", "INFO"),
            async_downloads=data.get("async_downloads", True),
            download_directory=data.get("download_directory", "current"),
            backup_directory=data.get("backup_directory", "backups"),
            overrides_directory=data.get("overrides_directory", "overrides"),
            logs_directory=data.get("logs_directory", "logs"),
        )


def load_updater_config() -> UpdaterConfig:
    """
    Loads the updater configuration from UPDATER_CONFIG_FILE.
    If the file does not exist, creates a default configuration.
    """
    if os.path.exists(UPDATER_CONFIG_FILE):
        try:
            with open(UPDATER_CONFIG_FILE, "r") as f:
                config_data = json.load(f)
            logger.info("Updater configuration loaded.")
            return UpdaterConfig.from_dict(config_data)
        except json.JSONDecodeError as e:
            logger.error(f"Error parsing updater configuration: {e}")
        except OSError as e:
            logger.error(f"Error reading updater configuration: {e}")
    
    config = UpdaterConfig()
    save_updater_config(config)
    return config


def save_updater_config(config: UpdaterConfig) -> None:
    """
    Saves the updater configuration to UPDATER_CONFIG_FILE.
    """
    try:
        with open(UPDATER_CONFIG_FILE, "w") as f:
            json.dump(config.to_dict(), f, indent=4)
        logger.info("Updater configuration saved.")
    except OSError as e:
        logger.error(f"Error saving updater configuration: {e}")


def configure_updater() -> UpdaterConfig:
    """
    Allows the user to view and modify the updater configuration via the menu.
    """
    config = load_updater_config()
    print("Current Updater Configuration:")
    for key, value in config.to_dict().items():
        print(f"  {key}: {value}")
    print("\nEnter the configuration key you wish to change (or press Enter to finish):")
    
    config_dict = config.to_dict()
    while True:
        key = input("Key: ").strip()
        if not key:
            break
        if key in config_dict:
            new_val = input(f"Enter new value for {key} (current: {config_dict[key]}): ").strip()
            if key == "async_downloads":
                config.async_downloads = new_val.lower() in ["true", "1", "yes"]
            elif key == "logging_level":
                config.logging_level = new_val.upper()
            else:
                setattr(config, key, new_val)
            config_dict = config.to_dict()
        else:
            print("Invalid key. Available keys: " + ", ".join(config_dict.keys()))
    
    save_updater_config(config)
    return config
