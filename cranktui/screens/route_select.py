"""Route selection screen."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from cranktui.routes.route import Route
from cranktui.screens.devices import DevicesScreen
from cranktui.screens.settings import SettingsScreen
from cranktui.state.state import get_state


class RouteItem(Static):
    """A widget for displaying a single route."""

    def __init__(self, route: Route, **kwargs):
        super().__init__(**kwargs)
        self.route = route
        self.can_focus = True

    def render(self) -> str:
        """Render the route information."""
        return f"{self.route.name}\n{self.route.description}\n{self.route.distance_km} km"


class RouteSelectScreen(Screen):
    """Screen for selecting a route."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "app.pop_screen", "Back"),
        ("up", "navigate_up", "Up"),
        ("down", "navigate_down", "Down"),
        ("enter", "select_route", "Select"),
        ("d", "show_devices", "Devices"),
        ("s", "show_settings", "Settings"),
    ]

    CSS = """
    RouteSelectScreen {
        layout: vertical;
    }

    #main-container {
        width: 100%;
        height: 1fr;
    }

    #routes-panel {
        width: 70%;
        height: 100%;
        border: round white;
        margin: 1;
    }

    #routes-panel-title {
        text-style: bold;
        text-align: center;
        border-bottom: solid white;
        padding: 1;
        margin: 0 1 1 1;
    }

    #routes-scroll {
        width: 100%;
        height: 1fr;
        padding: 0 1;
    }

    #devices-panel {
        width: 30%;
        height: 100%;
        border: round white;
        margin: 1;
    }

    #devices-panel-title {
        text-style: bold;
        text-align: center;
        border-bottom: solid white;
        padding: 1;
        margin: 0 1 1 1;
    }

    #device-status {
        color: $text-muted;
        padding: 1;
        text-align: center;
        height: auto;
    }

    RouteItem {
        height: auto;
        padding: 1 2;
        margin-bottom: 1;
        border: solid $surface;
    }

    RouteItem:focus {
        border: round white;
        background: $surface;
    }

    RouteItem > .route-name {
        text-style: bold;
    }

    RouteItem > .route-description {
        color: $text-muted;
    }

    RouteItem > .route-distance {
        color: $text-muted;
    }
    """

    def __init__(self, routes: list[Route], **kwargs):
        super().__init__(**kwargs)
        self.routes = routes
        self.route_items: list[RouteItem] = []
        self.current_index = 0
        self.state = get_state()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        with Horizontal(id="main-container"):
            with Vertical(id="routes-panel"):
                yield Static("Routes", id="routes-panel-title")
                with VerticalScroll(id="routes-scroll"):
                    for route in self.routes:
                        item = RouteItem(route)
                        self.route_items.append(item)
                        yield item
            with Vertical(id="devices-panel"):
                yield Static("Devices", id="devices-panel-title")
                yield Static("", id="device-status")
        yield Footer()

    def on_mount(self) -> None:
        """Focus first route when mounted."""
        if self.route_items:
            self.current_index = 0
            self.route_items[self.current_index].focus()

        # Update device status
        self.set_interval(1.0, self.update_device_status)
        self.update_device_status()

    async def update_device_status(self) -> None:
        """Update the device status display."""
        ble_client = await self.state.get_ble_client()
        status_widget = self.query_one("#device-status", Static)

        if ble_client and ble_client.is_connected:
            device_name = ble_client.device_name or "Unknown"
            status_widget.update(f"✓ {device_name} Connected\n\n\nPress d to manage")
        else:
            status_widget.update("No devices connected\n\n\nPress d to connect")

    def action_navigate_up(self) -> None:
        """Navigate to the previous route."""
        if self.route_items and self.current_index > 0:
            self.current_index -= 1
            self.route_items[self.current_index].focus()

    def action_navigate_down(self) -> None:
        """Navigate to the next route."""
        if self.route_items and self.current_index < len(self.route_items) - 1:
            self.current_index += 1
            self.route_items[self.current_index].focus()

    def action_select_route(self) -> None:
        """Select the currently focused route."""
        if self.route_items and 0 <= self.current_index < len(self.route_items):
            self.dismiss(self.route_items[self.current_index].route)

    def action_show_devices(self) -> None:
        """Show the devices screen."""
        self.app.push_screen(DevicesScreen())

    def action_show_settings(self) -> None:
        """Show the settings screen."""
        self.app.push_screen(SettingsScreen())
