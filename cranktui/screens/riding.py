"""Riding screen for active training session."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from cranktui.routes.route import Route
from cranktui.screens.devices import DevicesScreen
from cranktui.simulation.simulator import DemoSimulator
from cranktui.widgets.elevation_chart import ElevationChart
from cranktui.widgets.stats_panel import StatsPanel


class RidingScreen(Screen):
    """Main riding screen with elevation profile and stats."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "request_back", "Back"),
        ("d", "show_devices", "Devices"),
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
        """Handle mount - start simulation."""
        await self.simulator.start()

    async def on_unmount(self) -> None:
        """Handle unmount - stop simulation."""
        await self.simulator.stop()

    def action_request_back(self) -> None:
        """Request to go back - will trigger confirmation in main app."""
        self.dismiss()

    def action_show_devices(self) -> None:
        """Show the devices screen."""
        self.app.push_screen(DevicesScreen())
