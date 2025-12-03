"""BLE client for connecting to and communicating with trainers."""

import asyncio
from datetime import datetime
from typing import Optional

from bleak import BleakClient as BleakClientImpl
from bleak.exc import BleakError


def debug_log(msg: str) -> None:
    """Log debug message to cranktui-debug.log if debug mode is enabled."""
    from cranktui.app import DEBUG_MODE

    if not DEBUG_MODE:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    with open("cranktui-debug.log", "a") as f:
        f.write(f"[{timestamp}] {msg}\n")
        f.flush()


# FTMS Service and Characteristic UUIDs
FTMS_SERVICE_UUID = "00001826-0000-1000-8000-00805f9b34fb"
INDOOR_BIKE_DATA_UUID = "00002ad2-0000-1000-8000-00805f9b34fb"
FTMS_CONTROL_POINT_UUID = "00002ad9-0000-1000-8000-00805f9b34fb"


class BLEClient:
    """Client for managing BLE connections to fitness trainers."""

    def __init__(self):
        self._client: Optional[BleakClientImpl] = None
        self._device_address: Optional[str] = None
        self._device_name: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        """Check if currently connected to a device."""
        return self._client is not None and self._client.is_connected

    @property
    def device_name(self) -> Optional[str]:
        """Get the name of the connected device."""
        return self._device_name

    @property
    def device_address(self) -> Optional[str]:
        """Get the address of the connected device."""
        return self._device_address

    async def connect(self, address: str, name: str = "Unknown") -> tuple[bool, str]:
        """Connect to a BLE device.

        Args:
            address: BLE device address
            name: Device name (for display purposes)

        Returns:
            Tuple of (success, error_message)
        """
        debug_log(f"=== Starting connection to {name} ({address}) ===")
        try:
            # Disconnect from any existing connection
            if self.is_connected:
                debug_log("Disconnecting from existing connection")
                await self.disconnect()

            # Create new client and connect
            debug_log(f"Creating BleakClient for {address}")
            self._client = BleakClientImpl(address)

            debug_log("Attempting to connect (timeout=10s)...")
            await self._client.connect(timeout=10.0)

            if not self._client.is_connected:
                debug_log("Connection failed - client reports not connected")
                return False, "Connection failed"

            debug_log("Connection successful!")

            # Store device info
            self._device_address = address
            self._device_name = name

            # Wait a moment for services to populate
            debug_log("Waiting 0.5s for services to populate...")
            await asyncio.sleep(0.5)

            # Discover services to ensure FTMS is available
            # In bleak, services are available via the services property
            debug_log("Discovering services...")
            ftms_service = None
            available_services = []
            for service in self._client.services:
                available_services.append(service.uuid)
                debug_log(f"  Found service: {service.uuid}")
                if service.uuid.lower() == FTMS_SERVICE_UUID.lower():
                    ftms_service = service
                    debug_log(f"  ✓ FTMS service found!")

            debug_log(f"Total services found: {len(available_services)}")

            if not ftms_service:
                # No FTMS service found - but allow connection anyway for now
                debug_log("FTMS service NOT found - continuing anyway")
                debug_log("=== Connection complete (no FTMS) ===")
                return True, ""

            debug_log("=== Connection complete and FTMS available ===")
            return True, ""

        except BleakError as e:
            debug_log(f"BleakError during connection: {str(e)}")
            if self._client:
                try:
                    await self._client.disconnect()
                except:
                    pass
                self._client = None
            return False, f"BLE error: {str(e)}"
        except Exception as e:
            debug_log(f"Unexpected error during connection: {type(e).__name__}: {str(e)}")
            if self._client:
                try:
                    await self._client.disconnect()
                except:
                    pass
                self._client = None
            return False, f"Error: {str(e)}"

    async def disconnect(self) -> None:
        """Disconnect from the current device."""
        if self._client and self._client.is_connected:
            try:
                await self._client.disconnect()
            except Exception as e:
                print(f"Disconnect error: {e}")
            finally:
                self._client = None
                self._device_address = None
                self._device_name = None

    async def start_notify(self, characteristic_uuid: str, callback) -> bool:
        """Start receiving notifications from a characteristic.

        Args:
            characteristic_uuid: UUID of the characteristic
            callback: Callback function to receive data

        Returns:
            True if notifications started successfully
        """
        if not self.is_connected or not self._client:
            return False

        try:
            await self._client.start_notify(characteristic_uuid, callback)
            return True
        except Exception as e:
            print(f"Failed to start notifications: {e}")
            return False

    async def stop_notify(self, characteristic_uuid: str) -> bool:
        """Stop receiving notifications from a characteristic.

        Args:
            characteristic_uuid: UUID of the characteristic

        Returns:
            True if notifications stopped successfully
        """
        if not self.is_connected or not self._client:
            return False

        try:
            await self._client.stop_notify(characteristic_uuid)
            return True
        except Exception as e:
            print(f"Failed to stop notifications: {e}")
            return False

    async def write_characteristic(self, characteristic_uuid: str, data: bytes) -> bool:
        """Write data to a characteristic.

        Args:
            characteristic_uuid: UUID of the characteristic
            data: Bytes to write

        Returns:
            True if write successful
        """
        if not self.is_connected or not self._client:
            return False

        try:
            await self._client.write_gatt_char(characteristic_uuid, data)
            return True
        except Exception as e:
            print(f"Failed to write characteristic: {e}")
            return False
