"""BLE device scanner for discovering trainers."""

import asyncio
from dataclasses import dataclass

from bleak import BleakScanner


@dataclass
class BLEDeviceInfo:
    """Information about a discovered BLE device."""

    name: str
    address: str
    rssi: int


# FTMS (Fitness Machine Service) UUID
FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"


async def scan_for_devices(timeout: float = 5.0) -> list[BLEDeviceInfo]:
    """Scan for BLE fitness devices.

    Args:
        timeout: How long to scan in seconds

    Returns:
        List of discovered devices with name, address, and RSSI
    """
    try:
        # Scan for devices
        devices = await BleakScanner.discover(timeout=timeout, return_adv=True)

        discovered = []
        for device, adv_data in devices.values():
            # Filter for devices that look like trainers
            if device.name and should_include_device(device.name, adv_data.service_uuids):
                discovered.append(
                    BLEDeviceInfo(
                        name=device.name,
                        address=device.address,
                        rssi=adv_data.rssi,
                    )
                )

        return discovered

    except Exception as e:
        # If BLE is not available or scan fails, return empty list
        print(f"BLE scan failed: {e}")
        return []


def should_include_device(name: str, service_uuids: list[str]) -> bool:
    """Determine if a device should be included in results.

    Args:
        name: Device name
        service_uuids: List of advertised service UUIDs

    Returns:
        True if device looks like a fitness trainer
    """
    # Check for FTMS service UUID
    if FTMS_SERVICE_UUID in service_uuids:
        return True

    # Check for known trainer names
    trainer_keywords = ["KICKR", "WAHOO", "TACX", "ELITE", "SARIS", "CADENCE", "HEART"]
    name_upper = name.upper()

    for keyword in trainer_keywords:
        if keyword in name_upper:
            return True

    return False
