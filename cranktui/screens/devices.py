"""Devices screen for BLE device discovery and connection."""

import asyncio

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label, Static

from cranktui.ble.scanner import scan_for_devices
from cranktui.state.state import get_state


class DeviceItem(Static):
    """A single device in the list."""

    # Disable Tab focus - only arrow keys
    can_focus_children = False

    def __init__(self, name: str, address: str, rssi: int, is_connected: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.device_name = name
        self.device_address = address
        self.rssi = rssi
        self.is_connected = is_connected
        self.can_focus = True

    def render(self) -> str:
        """Render device information."""
        signal_strength = "●●●" if self.rssi > -60 else "●●○" if self.rssi > -75 else "●○○"
        status = "✓ " if self.is_connected else "  "
        return f"{status}{self.device_name:30} {self.device_address:20} {signal_strength}"


class DevicesScreen(ModalScreen[None]):
    """Modal screen for device discovery and connection."""

    BINDINGS = [
        ("escape", "close_modal", "Close"),
        ("up", "navigate_up", "Up"),
        ("down", "navigate_down", "Down"),
        ("left", "navigate_left", "Left"),
        ("right", "navigate_right", "Right"),
        ("space", "toggle_connection", "Connect/Disconnect"),
        ("tab", "focus_buttons", "Focus Buttons"),
    ]

    CSS = """
    DevicesScreen {
        align: center middle;
    }

    #devices-dialog {
        width: 90%;
        height: 90%;
        border: round white;
        background: $surface;
        padding: 1;
    }

    #header {
        width: 100%;
        height: auto;
        content-align: center middle;
        padding-bottom: 1;
        border-bottom: solid white;
    }

    #device-list {
        width: 100%;
        height: 1fr;
        padding: 0 1;
    }

    DeviceItem {
        margin: 0;
        padding: 0 1;
        background: transparent;
        border: round $surface;
    }

    DeviceItem:focus {
        border: round white;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    #status-bar {
        width: 100%;
        height: auto;
        min-height: 3;
        padding: 1 2;
        content-align: center middle;
        border-top: solid white;
        border-bottom: solid white;
        color: white;
        text-style: bold;
    }

    Button {
        margin: 0 1;
        background: transparent;
        border: round $surface;
        color: white;
    }

    Button:focus {
        border: round white;
    }

    .highlight {
        color: green;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.device_items: list[DeviceItem] = []
        self.current_index = 0
        self.in_button_area = False
        self.state = get_state()
        self.is_scanning = False

    def compose(self) -> ComposeResult:
        """Create dialog widgets."""
        with Container(id="devices-dialog"):
            yield Label("BLE Devices", id="header")
            with Vertical(id="device-list"):
                # Devices will be populated dynamically after scan
                yield Static("Scanning for devices...", id="scanning-placeholder")
            yield Label("Press SPACE on a device to connect", id="status-bar")
            with Horizontal(id="buttons"):
                yield Button("Refresh", id="refresh-btn")
                yield Button("Close", id="close-btn")
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount - start BLE scan."""
        # Start scanning immediately
        self.run_worker(self.scan_devices())

    async def scan_devices(self) -> None:
        """Scan for BLE devices and populate list."""
        if self.is_scanning:
            return

        self.is_scanning = True
        status_bar = self.query_one("#status-bar", Label)
        device_list = self.query_one("#device-list", Vertical)

        try:
            # Clear existing devices and show scanning placeholder
            await device_list.remove_children()
            await device_list.mount(Static("Scanning for devices...", id="scanning-placeholder"))

            # Start scan and countdown timer concurrently
            scan_duration = 5
            scan_task = asyncio.create_task(scan_for_devices(timeout=float(scan_duration)))

            # Update countdown while scanning
            for i in range(scan_duration, 0, -1):
                status_bar.update(f"Scanning... {i}s remaining")
                await asyncio.sleep(1.0)

            # Wait for scan to complete
            devices = await scan_task
            status_bar.update("Scan complete")

            # Remove placeholder and old devices
            device_list = self.query_one("#device-list", Vertical)
            await device_list.remove_children()

            # Check if we have a connected device
            ble_client = await self.state.get_ble_client()
            connected_address = None
            if ble_client is not None and ble_client.is_connected:
                connected_address = ble_client.device_address

            # Build list of devices to show (scan results + connected device if not in scan)
            devices_to_show = []
            scan_addresses = set()

            # Add scanned devices
            for device in devices:
                scan_addresses.add(device.address)
                is_connected = device.address == connected_address
                devices_to_show.append((device.name, device.address, device.rssi, is_connected))

            # If we have a connected device that wasn't in the scan, add it at the top
            if connected_address and connected_address not in scan_addresses:
                devices_to_show.insert(0, (ble_client.device_name or "Unknown", connected_address, -50, True))

            # Populate with devices
            if devices_to_show:
                for name, address, rssi, is_connected in devices_to_show:
                    device_item = DeviceItem(name, address, rssi, is_connected)
                    await device_list.mount(device_item)

                # Update device items list
                self.device_items = list(self.query(DeviceItem))

                # Focus first device
                if self.device_items:
                    self.current_index = 0
                    self.device_items[self.current_index].focus()

                status_bar.update(f"Found {len(devices_to_show)} device(s)")
            else:
                # No devices found
                no_devices = Static(
                    "No devices found.\n\n"
                    "Make sure your trainer is:\n"
                    "  • Powered on\n"
                    "  • Not connected to another device\n"
                    "  • Within Bluetooth range\n\n"
                    "Press Refresh to scan again."
                )
                await device_list.mount(no_devices)
                status_bar.update("No devices found - scan complete")

        except Exception as e:
            # Handle scan errors
            status_bar.update(f"Scan error: {str(e)}")
            device_list = self.query_one("#device-list", Vertical)
            await device_list.remove_children()
            error_msg = Static(f"Error: {str(e)}")
            await device_list.mount(error_msg)

        finally:
            self.is_scanning = False

    def action_navigate_up(self) -> None:
        """Navigate to the previous device or back to devices from buttons."""
        if self.in_button_area:
            # Move back to device list
            self.in_button_area = False
            if self.device_items:
                self.device_items[self.current_index].focus()
        elif self.device_items and self.current_index > 0:
            self.current_index -= 1
            self.device_items[self.current_index].focus()

    def action_navigate_down(self) -> None:
        """Navigate to the next device."""
        if not self.in_button_area:
            if self.device_items and self.current_index < len(self.device_items) - 1:
                self.current_index += 1
                self.device_items[self.current_index].focus()

    def action_navigate_left(self) -> None:
        """Navigate left between buttons."""
        if self.in_button_area:
            refresh_btn = self.query_one("#refresh-btn", Button)
            refresh_btn.focus()

    def action_navigate_right(self) -> None:
        """Navigate right between buttons."""
        if self.in_button_area:
            close_btn = self.query_one("#close-btn", Button)
            close_btn.focus()

    def action_toggle_connection(self) -> None:
        """Toggle connection for the focused device."""
        # Don't toggle connection if we're in the button area
        if self.in_button_area:
            return

        status_bar = self.query_one("#status-bar", Label)
        status_bar.update("Space pressed!")

        if not self.device_items or not (0 <= self.current_index < len(self.device_items)):
            status_bar.update("No device selected")
            return

        device = self.device_items[self.current_index]
        status_bar.update(f"Trying to connect to {device.device_name}")

        # Trigger async connection/disconnection
        self.run_worker(self.connect_device(device))

    async def connect_device(self, device: DeviceItem) -> None:
        """Connect or disconnect from a device.

        Args:
            device: The device to connect/disconnect
        """
        status_bar = self.query_one("#status-bar", Label)

        try:
            ble_client = await self.state.get_ble_client()

            if device.is_connected:
                # Disconnect
                if ble_client:
                    await ble_client.disconnect()
                    await self.state.update_ble_client(None)
                    device.is_connected = False
                    device.refresh()
                    status_bar.update(f"Disconnected from {device.device_name}")
            else:
                # Connect
                if not ble_client:
                    # Create new client
                    from cranktui.ble.client import BLEClient

                    ble_client = BLEClient()

                # Try to connect
                status_bar.update(f"Connecting to {device.device_name}...")
                success, error = await ble_client.connect(device.device_address, device.device_name)

                if success:
                    # Store client in state
                    await self.state.update_ble_client(ble_client)

                    # Update all device items to reflect new connection state
                    for item in self.device_items:
                        item.is_connected = item.device_address == device.device_address
                        item.refresh()

                    status_bar.update(f"Connected to {device.device_name}")

                    # Start data stream for testing
                    data_started = await ble_client.start_data_stream(self._handle_trainer_data)
                    if data_started:
                        status_bar.update(f"Connected - receiving data from {device.device_name}")
                    else:
                        status_bar.update(f"Connected to {device.device_name} (data stream failed)")
                else:
                    status_bar.update(f"Failed to connect: {error}")

        except Exception as e:
            status_bar.update(f"Connection error: {str(e)}")

    def action_refresh(self) -> None:
        """Refresh device list."""
        self.run_worker(self.scan_devices())

    def action_focus_buttons(self) -> None:
        """Focus the first button."""
        self.in_button_area = True
        refresh_btn = self.query_one("#refresh-btn", Button)
        refresh_btn.focus()

    def action_close_modal(self) -> None:
        """Close the devices screen."""
        self.dismiss()

    def _handle_trainer_data(self, data: dict) -> None:
        """Handle incoming trainer data.

        Args:
            data: Dictionary with power_w, cadence_rpm, speed_kmh, distance_m
        """
        # For now, just update the status bar with the data
        status_bar = self.query_one("#status-bar", Label)
        status_bar.update(
            f"Power: {data['power_w']:.0f}W | "
            f"Cadence: {data['cadence_rpm']:.0f}rpm | "
            f"Speed: {data['speed_kmh']:.1f}km/h"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "refresh-btn":
            self.action_refresh()
        elif event.button.id == "close-btn":
            self.action_close_modal()
