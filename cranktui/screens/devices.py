"""Devices screen for BLE device discovery and connection."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label, Static


class DeviceItem(Static):
    """A single device in the list."""

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
        status = "[Connected]" if self.is_connected else ""
        return f"{self.device_name} {status}\n{self.device_address}  Signal: {signal_strength}"


class DevicesScreen(ModalScreen[None]):
    """Modal screen for device discovery and connection."""

    BINDINGS = [
        ("escape", "close_modal", "Close"),
        ("up", "navigate_up", "Up"),
        ("down", "navigate_down", "Down"),
        ("space", "toggle_connection", "Connect/Disconnect"),
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
        padding: 1 2;
    }

    #header {
        width: 100%;
        height: auto;
        content-align: center middle;
        margin-bottom: 1;
        padding-bottom: 1;
        border-bottom: solid white;
    }

    #status {
        width: 100%;
        height: auto;
        margin-bottom: 1;
        text-align: center;
    }

    #device-list {
        width: 100%;
        height: 1fr;
        border: round white;
        padding: 1;
    }

    DeviceItem {
        margin: 1 0;
        padding: 1;
        background: transparent;
        border: none;
    }

    DeviceItem:focus {
        border: round white;
        background: $surface;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
        margin-top: 1;
    }

    Button {
        margin: 0 1;
        background: transparent;
        border: none;
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

    def compose(self) -> ComposeResult:
        """Create dialog widgets."""
        with Container(id="devices-dialog"):
            yield Label("BLE Devices", id="header")
            yield Static("Scanning for devices...", id="status")
            with VerticalScroll(id="device-list"):
                # Mock devices for now
                yield DeviceItem("KICKR SNAP 12345", "AA:BB:CC:DD:EE:FF", -55)
                yield DeviceItem("KICKR CORE 67890", "11:22:33:44:55:66", -70)
                yield DeviceItem("Heart Rate Monitor", "AA:11:BB:22:CC:33", -80)
                yield DeviceItem("KICKR CLIMB", "DD:EE:FF:00:11:22", -62)
                yield DeviceItem("Wahoo CADENCE", "33:44:55:66:77:88", -78)
            with Horizontal(id="buttons"):
                yield Button("Refresh", id="refresh-btn")
                yield Button("Close", id="close-btn")
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount."""
        # Get all device items
        self.device_items = list(self.query(DeviceItem))

        # Focus first device
        if self.device_items:
            self.current_index = 0
            self.device_items[self.current_index].focus()

        # Update status after a moment to simulate scanning
        self.set_timer(1.0, self.update_scan_status)

    def update_scan_status(self) -> None:
        """Update the scanning status."""
        status = self.query_one("#status", Static)
        status.update(f"Found {len(self.device_items)} devices")

    def action_navigate_up(self) -> None:
        """Navigate to the previous device."""
        if self.device_items and self.current_index > 0:
            self.current_index -= 1
            self.device_items[self.current_index].focus()

    def action_navigate_down(self) -> None:
        """Navigate to the next device."""
        if self.device_items and self.current_index < len(self.device_items) - 1:
            self.current_index += 1
            self.device_items[self.current_index].focus()

    def action_toggle_connection(self) -> None:
        """Toggle connection for the focused device."""
        if not self.device_items or not (0 <= self.current_index < len(self.device_items)):
            return

        device = self.device_items[self.current_index]

        # Toggle connection state
        device.is_connected = not device.is_connected
        device.refresh()

        # Update status
        status = self.query_one("#status", Static)
        if device.is_connected:
            status.update(f"Connected to {device.device_name}")
        else:
            status.update(f"Disconnected from {device.device_name}")

    def action_refresh(self) -> None:
        """Refresh device list."""
        status = self.query_one("#status", Static)
        status.update("Scanning for devices...")
        self.set_timer(1.0, self.update_scan_status)

    def action_close_modal(self) -> None:
        """Close the devices screen."""
        self.dismiss()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "refresh-btn":
            self.action_refresh()
        elif event.button.id == "close-btn":
            self.action_close_modal()
