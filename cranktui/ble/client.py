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

# Wahoo Proprietary Service and Characteristic UUIDs
WAHOO_SERVICE_UUID = "a026ee01-0a7d-4ab3-97fa-f1500f9feb8b"
WAHOO_CONTROL_CHAR_UUID = "a026e002-0a7d-4ab3-97fa-f1500f9feb8b"
WAHOO_DATA_CHAR_UUID = "a026e004-0a7d-4ab3-97fa-f1500f9feb8b"

# Standard Bluetooth SIG Services
CSC_SERVICE_UUID = "00001818-0000-1000-8000-00805f9b34fb"  # Cycling Speed and Cadence
CSC_MEASUREMENT_UUID = "00002a5b-0000-1000-8000-00805f9b34fb"  # CSC Measurement
CYCLING_POWER_SERVICE_UUID = "00001818-0000-1000-8000-00805f9b34fb"
CYCLING_POWER_MEASUREMENT_UUID = "00002a63-0000-1000-8000-00805f9b34fb"


class BLEClient:
    """Client for managing BLE connections to fitness trainers."""

    def __init__(self):
        self._client: Optional[BleakClientImpl] = None
        self._device_address: Optional[str] = None
        self._device_name: Optional[str] = None
        self._protocol: Optional[str] = None  # "ftms" or "wahoo"

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
            wahoo_service = None
            csc_service = None
            available_services = []

            for service in self._client.services:
                available_services.append(service.uuid)
                debug_log(f"  Found service: {service.uuid}")

                # Check for FTMS
                if service.uuid.lower() == FTMS_SERVICE_UUID.lower():
                    ftms_service = service
                    debug_log(f"  ✓ FTMS service found!")

                # Check for Wahoo proprietary service (a026ee01 is the main data service)
                if service.uuid.lower() == WAHOO_SERVICE_UUID.lower():
                    wahoo_service = service
                    debug_log(f"  ✓ Wahoo proprietary service found!")
                    # Log all characteristics in this service
                    for char in service.characteristics:
                        properties = ", ".join(char.properties)
                        debug_log(f"    Characteristic: {char.uuid} [{properties}]")

                # Check for Cycling Speed and Cadence service
                if service.uuid.lower() == CSC_SERVICE_UUID.lower():
                    csc_service = service
                    debug_log(f"  ✓ Cycling Speed and Cadence service found!")
                    # Log all characteristics in this service
                    for char in service.characteristics:
                        properties = ", ".join(char.properties)
                        debug_log(f"    Characteristic: {char.uuid} [{properties}]")

            debug_log(f"Total services found: {len(available_services)}")

            # Determine which protocol to use
            if ftms_service:
                self._protocol = "ftms"
                debug_log("=== Connection complete - using FTMS protocol ===")
                return True, ""
            elif wahoo_service:
                self._protocol = "wahoo"
                debug_log("=== Connection complete - using Wahoo proprietary protocol ===")
                return True, ""
            else:
                # No supported protocol found
                debug_log("No supported protocol found - disconnecting")
                await self.disconnect()
                return False, "No FTMS or Wahoo service found"

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

    async def start_data_stream(self, callback) -> bool:
        """Start receiving trainer data notifications.

        Args:
            callback: Function to call with parsed data dict

        Returns:
            True if data stream started successfully
        """
        if not self.is_connected or not self._client:
            debug_log("Cannot start data stream - not connected")
            return False

        try:
            if self._protocol == "ftms":
                debug_log(f"Starting FTMS data stream on {INDOOR_BIKE_DATA_UUID}")
                await self._client.start_notify(INDOOR_BIKE_DATA_UUID,
                    lambda sender, data: self._handle_ftms_data(data, callback))
                return True
            elif self._protocol == "wahoo":
                debug_log(f"Starting Wahoo data stream on {WAHOO_DATA_CHAR_UUID}")

                # Try sending an unlock/init command first
                # This is a common pattern - some trainers need to be "unlocked"
                try:
                    unlock_command = bytes([0x01, 0x00])  # Simple unlock attempt
                    debug_log(f"Sending unlock command: {unlock_command.hex()}")
                    await self._client.write_gatt_char(WAHOO_CONTROL_CHAR_UUID, unlock_command, response=False)
                    await asyncio.sleep(0.1)
                except Exception as e:
                    debug_log(f"Unlock command failed (may not be needed): {e}")

                await self._client.start_notify(WAHOO_DATA_CHAR_UUID,
                    lambda sender, data: self._handle_wahoo_data(data, callback))

                # Also try the control characteristic in case data comes through there
                try:
                    await self._client.start_notify(WAHOO_CONTROL_CHAR_UUID,
                        lambda sender, data: self._handle_wahoo_control_data(data, callback))
                    debug_log(f"Also subscribed to control characteristic {WAHOO_CONTROL_CHAR_UUID}")
                except Exception as e:
                    debug_log(f"Could not subscribe to control characteristic: {e}")

                # Also try subscribing to Cycling Power Measurement (0x2A63) if available
                try:
                    await self._client.start_notify(CYCLING_POWER_MEASUREMENT_UUID,
                        lambda sender, data: self._handle_cycling_power_data(data, callback))
                    debug_log(f"Also subscribed to Cycling Power Measurement {CYCLING_POWER_MEASUREMENT_UUID}")
                except Exception as e:
                    debug_log(f"Could not subscribe to power measurement: {e}")

                # Also try CSC Measurement (0x2A5B) for speed/cadence
                try:
                    await self._client.start_notify(CSC_MEASUREMENT_UUID,
                        lambda sender, data: self._handle_csc_measurement_data(data, callback))
                    debug_log(f"Also subscribed to CSC Measurement {CSC_MEASUREMENT_UUID}")
                except Exception as e:
                    debug_log(f"Could not subscribe to CSC measurement: {e}")

                return True
            else:
                debug_log("Cannot start data stream - unknown protocol")
                return False
        except Exception as e:
            debug_log(f"Failed to start data stream: {e}")
            return False

    def _handle_ftms_data(self, data: bytes, callback) -> None:
        """Parse FTMS Indoor Bike Data and call callback."""
        # TODO: Implement FTMS parser
        debug_log(f"FTMS data received: {data.hex()}")

    def _handle_wahoo_control_data(self, data: bytes, callback) -> None:
        """Parse Wahoo control characteristic data."""
        debug_log(f"Wahoo control data received ({len(data)} bytes): {data.hex()}")
        # Just log it for now - this might contain responses or also data

    def _handle_csc_measurement_data(self, data: bytes, callback) -> None:
        """Parse CSC Measurement characteristic (0x2A5B)."""
        try:
            debug_log(f"CSC Measurement data received ({len(data)} bytes): {data.hex()}")
            # CSC Measurement can have wheel and/or crank data based on flags
            # This might give us speed and cadence
        except Exception as e:
            debug_log(f"Error parsing CSC measurement data: {e}")

    def _handle_cycling_power_data(self, data: bytes, callback) -> None:
        """Parse Cycling Power Measurement characteristic (0x2A63)."""
        try:
            debug_log(f"Cycling Power data received ({len(data)} bytes): {data.hex()}")

            if len(data) < 4:
                debug_log(f"Power data too short: {len(data)} bytes")
                return

            # Cycling Power Measurement format (Bluetooth SIG spec):
            # Byte 0-1: Flags (uint16 little endian)
            # Byte 2-3: Instantaneous Power (sint16 little endian) in watts
            # Additional optional fields based on flags

            flags = int.from_bytes(data[0:2], byteorder='little')
            power = int.from_bytes(data[2:4], byteorder='little', signed=True)

            offset = 4
            cadence = 0.0

            # Bit 2: Accumulated Energy Present
            if flags & 0x08:
                # Skip 2 bytes for accumulated energy
                offset += 2

            # Bit 4: Crank Revolution Data Present
            if flags & 0x10:
                if len(data) >= offset + 6:
                    cumulative_crank_revs = int.from_bytes(data[offset:offset+2], byteorder='little')
                    last_crank_time = int.from_bytes(data[offset+2:offset+4], byteorder='little')
                    debug_log(f"Crank data: revs={cumulative_crank_revs}, time={last_crank_time}")
                    offset += 4

            debug_log(f"Cycling Power: flags=0x{flags:04x}, power={power}W")

            parsed = {
                "power_w": float(power),
                "cadence_rpm": cadence,
                "speed_kmh": 0.0,  # Not in this characteristic
                "distance_m": 0.0,
            }

            callback(parsed)

        except Exception as e:
            debug_log(f"Error parsing cycling power data: {e}")

    def _handle_wahoo_data(self, data: bytes, callback) -> None:
        """Parse Wahoo proprietary data and call callback."""
        try:
            # Log raw data
            debug_log(f"Wahoo data received ({len(data)} bytes): {data.hex()}")

            # Parse Wahoo data format (based on reverse engineering)
            # This is a simplified parser - we'll refine it as we see actual data
            if len(data) < 6:
                debug_log(f"Wahoo data too short: {len(data)} bytes")
                return

            # Wahoo format (estimated - will refine based on actual data):
            # Bytes 0-1: Power (watts) - little endian uint16
            # Bytes 2-3: Cadence (rpm) - little endian uint16
            # Bytes 4-5: Speed (km/h * 100) - little endian uint16

            power = int.from_bytes(data[0:2], byteorder='little')
            cadence = int.from_bytes(data[2:4], byteorder='little')
            speed_raw = int.from_bytes(data[4:6], byteorder='little')
            speed_kmh = speed_raw / 100.0

            parsed = {
                "power_w": float(power),
                "cadence_rpm": float(cadence),
                "speed_kmh": speed_kmh,
                "distance_m": 0.0,  # Not provided in real-time data
            }

            debug_log(f"Parsed: Power={power}W, Cadence={cadence}rpm, Speed={speed_kmh:.1f}km/h")

            # Call the callback with parsed data
            callback(parsed)

        except Exception as e:
            debug_log(f"Error parsing Wahoo data: {e}")
