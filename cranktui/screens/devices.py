"""Devices screen for BLE device discovery and connection."""

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Label, Static


class DeviceItem(Static):
    """A single device in the list."""

    def __init__(self, name: str, address: str, rssi: int, **kwargs):
        super().__init__(**kwargs)
        self.device_name = name
        self.device_address = address
        self.rssi = rssi

    def render(self) -> str:
        """Render device information."""
        signal_strength = "●●●" if self.rssi > -60 else "●●○" if self.rssi > -75 else "●○○"
        return f"{self.device_name}\n{self.device_address}  Signal: {signal_strength}"


class DevicesScreen(ModalScreen[None]):
    """Modal screen for device discovery and connection."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("r", "refresh", "Refresh"),
    ]

    CSS = """
    DevicesScreen {
        align: center middle;
    }

    #devices-dialog {
        width: 70;
        height: 25;
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

    #connection-info {
        width: 100%;
        height: auto;
        margin-top: 1;
        padding-top: 1;
        border-top: solid white;
    }

    .highlight {
        color: green;
    }
    """

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
            with Container(id="connection-info"):
                yield Static("Status: Not Connected", classes="status-line")
                yield Static("Press [r] to refresh  [Esc] to close", classes="help-text")
        yield Footer()

    def on_mount(self) -> None:
        """Handle mount."""
        # Update status after a moment to simulate scanning
        self.set_timer(1.0, self.update_scan_status)

    def update_scan_status(self) -> None:
        """Update the scanning status."""
        status = self.query_one("#status", Static)
        status.update("Found 3 devices")

    def action_refresh(self) -> None:
        """Refresh device list."""
        status = self.query_one("#status", Static)
        status.update("Scanning for devices...")
        self.set_timer(1.0, self.update_scan_status)

    def action_dismiss(self) -> None:
        """Close the devices screen."""
        self.dismiss()
