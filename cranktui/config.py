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


def get_rider_weight_kg() -> float:
    """Get the rider weight in kg.

    Returns:
        Rider weight in kg (default 75.0)
    """
    config = load_config()
    return config.get("rider_weight_kg", 75.0)


def set_rider_weight_kg(weight_kg: float) -> None:
    """Set the rider weight in kg.

    Args:
        weight_kg: Rider weight in kg
    """
    config = load_config()
    config["rider_weight_kg"] = weight_kg
    save_config(config)


def get_bike_weight_kg() -> float:
    """Get the bike weight in kg.

    Returns:
        Bike weight in kg (default 10.0)
    """
    config = load_config()
    return config.get("bike_weight_kg", 10.0)


def set_bike_weight_kg(weight_kg: float) -> None:
    """Set the bike weight in kg.

    Args:
        weight_kg: Bike weight in kg
    """
    config = load_config()
    config["bike_weight_kg"] = weight_kg
    save_config(config)
