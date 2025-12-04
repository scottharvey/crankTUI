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
from cranktui.widgets.minimap import MinimapWidget
from cranktui.widgets.stats_panel import StatsPanel


class RidingScreen(Screen):
    """Main riding screen with elevation profile and stats."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "request_back", "Back"),
        ("d", "show_devices", "Devices"),
        ("m", "toggle_mode", "Toggle Mode"),
        ("1", "test_resistance_low", "Test: Low Resistance"),
        ("2", "test_resistance_med", "Test: Med Resistance"),
        ("3", "test_resistance_high", "Test: High Resistance"),
        ("e", "test_erg_mode", "Test: ERG 200W"),
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
        layout: vertical;
    }

    #route-info {
        height: auto;
        border: round white;
        padding: 1;
        margin-bottom: 1;
    }

    StatsPanel {
        height: auto;
        border: round white;
        padding: 1;
        margin-bottom: 1;
    }

    #minimap-panel {
        height: 10;
        border: round white;
        padding: 1;
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
                yield MinimapWidget(route=self.route, id="minimap-panel")
        yield Footer()

    async def on_mount(self) -> None:
        """Handle mount - start simulation only if in demo mode."""
        from datetime import datetime
        from cranktui.app import DEMO_MODE

        ble_client = await self.state.get_ble_client()

        # Set start time for the ride
        await self.state.update_metrics(start_time=datetime.now())

        # Start demo simulator if --demo flag was passed OR no BLE device connected
        if DEMO_MODE or not ble_client or not ble_client.is_connected:
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
        from cranktui.app import DEMO_MODE

        # Can't toggle if --demo flag was passed
        if DEMO_MODE:
            self.notify("Started with --demo flag, cannot switch to LIVE mode")
            return

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
                self.notify("No device connected - cannot switch to LIVE mode")
        else:
            # Switch back to DEMO mode
            await self.state.update_metrics(mode="DEMO")
            await self.simulator.start()
            self.notify("Switched to DEMO mode")

    def action_test_resistance_low(self) -> None:
        """Test setting low resistance (20%)."""
        self.run_worker(self._test_resistance(20))

    def action_test_resistance_med(self) -> None:
        """Test setting medium resistance (50%)."""
        self.run_worker(self._test_resistance(50))

    def action_test_resistance_high(self) -> None:
        """Test setting high resistance (80%)."""
        self.run_worker(self._test_resistance(80))

    def action_test_erg_mode(self) -> None:
        """Test setting ERG mode to 200W."""
        self.run_worker(self._test_erg(200))

    async def _test_resistance(self, level: int) -> None:
        """Test resistance command."""
        ble_client = await self.state.get_ble_client()
        if not ble_client or not ble_client.is_connected:
            self.notify("No device connected")
            return

        self.notify(f"Testing: Set resistance to {level}% (check debug log)")
        success = await ble_client.set_resistance_level(level)
        if success:
            self.notify(f"Command sent! Did resistance change?")
        else:
            self.notify(f"Command failed")

    async def _test_erg(self, power: int) -> None:
        """Test ERG mode command."""
        ble_client = await self.state.get_ble_client()
        if not ble_client or not ble_client.is_connected:
            self.notify("No device connected")
            return

        self.notify(f"Testing: ERG mode {power}W (check debug log)")
        success = await ble_client.set_erg_mode(power)
        if success:
            self.notify(f"Command sent! Did trainer respond?")
        else:
            self.notify(f"Command failed")
