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
WAHOO_DATA_CHAR_UUID = "a026e004-0a7d-4ab3-97fa-f1500f9feb8b"  # Data notifications
WAHOO_TRAINER_CONTROL_UUID = "a026e005-0a7d-4ab3-97fa-f1500f9feb8b"  # Trainer control (ERG/SIM)

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
        self._last_crank_revs: Optional[int] = None
        self._last_crank_time: Optional[int] = None  # in 1/1024 seconds
        self._last_wheel_revs: Optional[int] = None
        self._last_wheel_time: Optional[int] = None  # in 1/1024 seconds
        self._wheel_circumference_m: float = 2.105  # Default ~700c wheel (adjustable later)
        # Track latest values from different characteristics
        self._latest_power_w: float = 0.0
        self._latest_speed_kmh: float = 0.0
        self._latest_cadence_rpm: float = 0.0
        # Rider characteristics for gradient simulation
        self._rider_weight_kg: Optional[float] = None

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

    def set_rider_weight(self, weight_kg: float) -> None:
        """Set rider weight for gradient simulation.

        Args:
            weight_kg: Total weight (rider + bike) in kg
        """
        self._rider_weight_kg = weight_kg
        debug_log(f"Rider weight set to {weight_kg:.1f}kg")

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

    async def write_characteristic(self, characteristic_uuid: str, data: bytes, response: bool = True) -> bool:
        """Write data to a characteristic.

        Args:
            characteristic_uuid: UUID of the characteristic
            data: Bytes to write
            response: Whether to wait for response (default True)

        Returns:
            True if write successful
        """
        if not self.is_connected or not self._client:
            return False

        try:
            debug_log(f"WRITE to {characteristic_uuid}: {data.hex()} (response={response})")
            await self._client.write_gatt_char(characteristic_uuid, data, response=response)
            debug_log(f"WRITE successful")
            return True
        except Exception as e:
            debug_log(f"WRITE failed: {e}")
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

                # Send Wahoo trainer unlock command to enable control
                # This unlocks ERG mode, SIM mode, and other control features
                try:
                    unlock_command = bytes([0x20, 0xEE, 0xFC])  # Wahoo unlock sequence
                    debug_log(f"Sending Wahoo unlock command: {unlock_command.hex()}")
                    await self._client.write_gatt_char(WAHOO_TRAINER_CONTROL_UUID, unlock_command, response=True)
                    await asyncio.sleep(0.2)
                    debug_log("Wahoo trainer unlocked for control")
                except Exception as e:
                    debug_log(f"Unlock command failed: {e}")

                # Send rider characteristics for realistic gradient simulation
                # This is stored as an instance variable to be set by the app
                if hasattr(self, '_rider_weight_kg') and self._rider_weight_kg:
                    try:
                        debug_log(f"Setting rider characteristics: {self._rider_weight_kg:.1f}kg")
                        await self.set_rider_characteristics(self._rider_weight_kg)
                        debug_log("Rider characteristics set")
                    except Exception as e:
                        debug_log(f"Failed to set rider characteristics: {e}")

                await self._client.start_notify(WAHOO_DATA_CHAR_UUID,
                    lambda sender, data: self._handle_wahoo_data(data, callback))

                # Subscribe to trainer control characteristic for responses
                try:
                    await self._client.start_notify(WAHOO_TRAINER_CONTROL_UUID,
                        lambda sender, data: self._handle_wahoo_control_data(data, callback))
                    debug_log(f"Subscribed to trainer control responses {WAHOO_TRAINER_CONTROL_UUID}")
                except Exception as e:
                    debug_log(f"Could not subscribe to trainer control: {e}")

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

    async def set_resistance_level(self, level: int) -> bool:
        """Set resistance load level (0-9 scale).

        Uses Wahoo's load level command (0x41).
        Maps input 0-100 to Wahoo's 0-9 scale.

        Args:
            level: Resistance level 0-100 (will be mapped to 0-9)

        Returns:
            True if command sent successfully
        """
        if not self.is_connected or self._protocol != "wahoo":
            return False

        # Map 0-100 to Wahoo's 0-9 load level scale
        load_level = int((level / 100.0) * 9)
        load_level = max(0, min(9, load_level))  # Clamp to 0-9

        # Wahoo load level command: 0x41 + level (0-9)
        command = bytes([0x41, load_level])
        debug_log(f"Set load level {load_level} (from {level}%): {command.hex()}")
        return await self.write_characteristic(WAHOO_TRAINER_CONTROL_UUID, command, response=True)

    async def set_erg_mode(self, power_watts: int) -> bool:
        """Set ERG mode with target power.

        Uses Wahoo's ERG mode command (0x42).
        The trainer will adjust resistance to maintain target power.

        Args:
            power_watts: Target power in watts (0-2000)

        Returns:
            True if command sent successfully
        """
        if not self.is_connected or self._protocol != "wahoo":
            return False

        # Clamp power to reasonable range
        power_watts = max(0, min(2000, power_watts))

        # Power in little-endian uint16
        power_low = power_watts & 0xFF
        power_high = (power_watts >> 8) & 0xFF

        # Wahoo ERG mode command: 0x42 + power (uint16 little-endian)
        command = bytes([0x42, power_low, power_high])
        debug_log(f"Set ERG mode {power_watts}W: {command.hex()}")
        return await self.write_characteristic(WAHOO_TRAINER_CONTROL_UUID, command, response=True)

    async def set_gradient(self, grade_percent: float) -> bool:
        """Set gradient for SIM mode (grade-based resistance).

        Uses Wahoo's gradient command (0x46).
        The trainer will adjust resistance to simulate riding at the specified grade.

        Args:
            grade_percent: Grade/slope as percentage (-20.0 to +20.0)
                          Examples: 0.0 = flat, 5.0 = 5% uphill, -3.0 = 3% downhill

        Returns:
            True if command sent successfully
        """
        if not self.is_connected or self._protocol != "wahoo":
            return False

        # Clamp gradient to reasonable range
        grade_percent = max(-20.0, min(20.0, grade_percent))

        # Wahoo gradient encoding: (gradient/100.0 + 1.0) * 32768
        # This maps:
        #   -20% -> 26214
        #     0% -> 32768
        #   +20% -> 39322
        encoded_value = int((grade_percent / 100.0 + 1.0) * 32768.0)

        # Encode as uint16 little-endian
        value_low = encoded_value & 0xFF
        value_high = (encoded_value >> 8) & 0xFF

        # Wahoo gradient command: 0x46 + encoded_value (uint16 little-endian)
        command = bytes([0x46, value_low, value_high])
        debug_log(f"Set gradient {grade_percent:.1f}% (encoded={encoded_value}): {command.hex()}")
        return await self.write_characteristic(WAHOO_TRAINER_CONTROL_UUID, command, response=True)

    async def set_rider_characteristics(self, weight_kg: float, crr: float = 0.005, cda: float = 0.55) -> bool:
        """Set rider characteristics for realistic simulation.

        Uses Wahoo's rider characteristics command (0x43).
        These parameters affect how the trainer simulates resistance.

        Args:
            weight_kg: Total weight (rider + bike) in kg (40-150)
            crr: Coefficient of rolling resistance (0.002-0.010, default 0.005 for typical road tires)
            cda: Coefficient of drag area in m² (0.2-0.6, default 0.55 for upright road position)

        Returns:
            True if command sent successfully
        """
        if not self.is_connected or self._protocol != "wahoo":
            return False

        # Clamp values to reasonable ranges
        weight_kg = max(40.0, min(150.0, weight_kg))
        crr = max(0.002, min(0.010, crr))
        cda = max(0.2, min(0.6, cda))

        # Encode weight: kg * 100 as uint16 little-endian
        weight_encoded = int(weight_kg * 100)
        weight_low = weight_encoded & 0xFF
        weight_high = (weight_encoded >> 8) & 0xFF

        # Encode CRR: crr * 10000 as uint16 little-endian
        crr_encoded = int(crr * 10000)
        crr_low = crr_encoded & 0xFF
        crr_high = (crr_encoded >> 8) & 0xFF

        # Encode CdA: cda * 1000 as uint16 little-endian
        cda_encoded = int(cda * 1000)
        cda_low = cda_encoded & 0xFF
        cda_high = (cda_encoded >> 8) & 0xFF

        # Wahoo rider characteristics command: 0x43 + weight + crr + cda (7 bytes total)
        command = bytes([0x43, weight_low, weight_high, crr_low, crr_high, cda_low, cda_high])
        debug_log(f"Set rider: {weight_kg:.1f}kg, CRR={crr:.4f}, CdA={cda:.2f}: {command.hex()}")
        return await self.write_characteristic(WAHOO_TRAINER_CONTROL_UUID, command, response=True)

    def _handle_wahoo_control_data(self, data: bytes, callback) -> None:
        """Parse Wahoo control characteristic data."""
        debug_log(f"Wahoo control data received ({len(data)} bytes): {data.hex()}")
        # Just log it for now - this might contain responses or also data

    def _handle_csc_measurement_data(self, data: bytes, callback) -> None:
        """Parse CSC Measurement characteristic (0x2A5B)."""
        try:
            if len(data) < 1:
                return

            # CSC Measurement format (Bluetooth SIG spec):
            # Byte 0: Flags
            #   Bit 0: Wheel Revolution Data Present
            #   Bit 1: Crank Revolution Data Present
            flags = data[0]
            offset = 1

            speed_kmh = 0.0

            # Bit 0: Wheel Revolution Data Present
            if flags & 0x01:
                if len(data) >= offset + 6:
                    cumulative_wheel_revs = int.from_bytes(data[offset:offset+4], byteorder='little')
                    last_wheel_event_time = int.from_bytes(data[offset+4:offset+6], byteorder='little')

                    # Calculate speed from wheel revolutions
                    if self._last_wheel_revs is not None and self._last_wheel_time is not None:
                        # Handle rollover (16-bit time, 32-bit revs)
                        wheel_revs_delta = cumulative_wheel_revs - self._last_wheel_revs
                        time_delta = last_wheel_event_time - self._last_wheel_time

                        # Handle time rollover at 65536 (1/1024 seconds)
                        if time_delta < 0:
                            time_delta += 65536

                        if time_delta > 0 and wheel_revs_delta > 0:
                            # Time is in 1/1024 seconds
                            time_delta_s = time_delta / 1024.0
                            revs_per_sec = wheel_revs_delta / time_delta_s
                            distance_per_sec = revs_per_sec * self._wheel_circumference_m
                            speed_kmh = distance_per_sec * 3.6  # m/s to km/h

                            # debug_log(f"CSC Speed: {speed_kmh:.1f} km/h (revs_delta={wheel_revs_delta}, time_delta={time_delta})")

                    self._last_wheel_revs = cumulative_wheel_revs
                    self._last_wheel_time = last_wheel_event_time

                    offset += 6

            # Update latest speed and send combined data
            if speed_kmh > 0:
                self._latest_speed_kmh = speed_kmh

                # Send combined data from all characteristics
                parsed = {
                    "power_w": self._latest_power_w,
                    "cadence_rpm": self._latest_cadence_rpm,
                    "speed_kmh": self._latest_speed_kmh,
                    "distance_m": 0.0,
                }
                try:
                    callback(parsed)
                except Exception:
                    # Callback may fail if UI is not ready
                    pass

        except Exception as e:
            debug_log(f"Error parsing CSC measurement data: {e}")

    def _handle_cycling_power_data(self, data: bytes, callback) -> None:
        """Parse Cycling Power Measurement characteristic (0x2A63)."""
        try:
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
                if len(data) >= offset + 4:
                    # Note: KICKR SNAP doesn't actually measure cadence (no crank sensor)
                    # This data is present but not meaningful for wheel-based trainers
                    offset += 4

            # Only log power if it's significant or changed
            # debug_log(f"Cycling Power: flags=0x{flags:04x}, power={power}W, cadence={cadence:.1f}RPM")

            # Update latest power and send combined data
            self._latest_power_w = float(power)

            # If we don't have speed from CSC, calculate from power using physics
            # Note: Speed calculation now happens in the callback handler where we have access to grade
            if self._latest_speed_kmh == 0.0:
                # Will be calculated by callback handler with current grade
                pass

            # Send combined data from all characteristics
            parsed = {
                "power_w": self._latest_power_w,
                "cadence_rpm": self._latest_cadence_rpm,
                "speed_kmh": self._latest_speed_kmh,
                "distance_m": 0.0,
            }

            try:
                callback(parsed)
            except Exception as callback_error:
                # Callback may fail if UI is not ready (e.g., wrong screen)
                # This is normal, just ignore silently
                pass

        except Exception as e:
            debug_log(f"Error parsing cycling power data: {e}")

    def _handle_wahoo_data(self, data: bytes, callback) -> None:
        """Parse Wahoo proprietary data and call callback."""
        try:
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

            # Call the callback with parsed data
            try:
                callback(parsed)
            except Exception:
                # Callback may fail if UI is not ready
                pass

        except Exception as e:
            debug_log(f"Error parsing Wahoo data: {e}")
