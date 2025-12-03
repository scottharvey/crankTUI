"""Configuration management for crankTUI."""

import json
from pathlib import Path


def get_config_dir() -> Path:
    """Get the config directory path."""
    config_dir = Path.home() / ".local" / "share" / "cranktui"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_config_file() -> Path:
    """Get the config file path."""
    return get_config_dir() / "config.json"


def load_config() -> dict:
    """Load configuration from file."""
    config_file = get_config_file()
    if config_file.exists():
        try:
            with open(config_file, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_config(config: dict) -> None:
    """Save configuration to file."""
    config_file = get_config_file()
    try:
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        print(f"Failed to save config: {e}")


def get_last_device() -> tuple[str | None, str | None]:
    """Get the last connected device address and name.

    Returns:
        Tuple of (address, name) or (None, None) if no device saved
    """
    config = load_config()
    return config.get("last_device_address"), config.get("last_device_name")


def save_last_device(address: str, name: str) -> None:
    """Save the last connected device.

    Args:
        address: Device BLE address
        name: Device name
    """
    config = load_config()
    config["last_device_address"] = address
    config["last_device_name"] = name
    save_config(config)


def clear_last_device() -> None:
    """Clear the saved last device."""
    config = load_config()
    config.pop("last_device_address", None)
    config.pop("last_device_name", None)
    save_config(config)
