"""Riding screen for active training session."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from cranktui.routes.route import Route
from cranktui.screens.devices import DevicesScreen
from cranktui.simulation.simulator import DemoSimulator
from cranktui.state.state import get_state
from cranktui.widgets.elevation_chart import ElevationChart
from cranktui.widgets.stats_panel import StatsPanel


class RidingScreen(Screen):
    """Main riding screen with elevation profile and stats."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "request_back", "Back"),
        ("d", "show_devices", "Devices"),
        ("m", "toggle_mode", "Toggle Mode"),
    ]

    CSS = """
    RidingScreen {
        layout: vertical;
    }

    #main-container {
        layout: horizontal;
        height: 1fr;
    }

    #elevation-panel {
        width: 2fr;
        border: round white;
        padding: 1;
    }

    #stats-panel {
        width: 1fr;
        border: round white;
        padding: 1;
    }

    #route-info {
        margin-bottom: 1;
        padding-bottom: 1;
        border-bottom: solid white;
    }
    """

    def __init__(self, route: Route, **kwargs):
        super().__init__(**kwargs)
        self.route = route
        self.simulator = DemoSimulator(route)
        self.state = get_state()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=True)
        with Container(id="main-container"):
            yield ElevationChart(route=self.route, id="elevation-panel")
            with Container(id="stats-panel"):
                yield Static(
                    f"{self.route.name}\n{self.route.distance_km} km",
                    id="route-info"
                )
                yield StatsPanel()
        yield Footer()

    async def on_mount(self) -> None:
        """Handle mount - start simulation only if no BLE connection."""
        from datetime import datetime

        ble_client = await self.state.get_ble_client()

        # Set start time for the ride
        await self.state.update_metrics(start_time=datetime.now())

        # Only start demo simulator if no BLE device connected
        if not ble_client or not ble_client.is_connected:
            await self.state.update_metrics(mode="DEMO")
            await self.simulator.start()
        else:
            await self.state.update_metrics(mode="LIVE")

    async def on_unmount(self) -> None:
        """Handle unmount - stop simulation and reset state."""
        await self.simulator.stop()
        # Reset state for next ride (but keep BLE client)
        ble_client = await self.state.get_ble_client()
        await self.state.reset()
        await self.state.update_ble_client(ble_client)

    def action_request_back(self) -> None:
        """Request to go back - will trigger confirmation in main app."""
        self.dismiss()

    def action_show_devices(self) -> None:
        """Show the devices screen."""
        self.app.push_screen(DevicesScreen())

    def action_toggle_mode(self) -> None:
        """Toggle between Demo and Live modes."""
        self.run_worker(self._toggle_mode())

    async def _toggle_mode(self) -> None:
        """Async toggle mode implementation."""
        metrics = await self.state.get_metrics()
        ble_client = await self.state.get_ble_client()

        if metrics.mode == "DEMO":
            # Try to switch to LIVE mode
            if ble_client and ble_client.is_connected:
                # Stop demo simulator
                await self.simulator.stop()
                await self.state.update_metrics(mode="LIVE")
                self.notify("Switched to LIVE mode")
            else:
                self.notify("No device connected - staying in DEMO mode")
        else:
            # Switch back to DEMO mode
            await self.state.update_metrics(mode="DEMO")
            await self.simulator.start()
            self.notify("Switched to DEMO mode")
