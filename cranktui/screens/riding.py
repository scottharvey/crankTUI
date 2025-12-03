"""Riding screen for active training session."""

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from cranktui.routes.route import Route
from cranktui.widgets.elevation_chart import ElevationChart


class RidingScreen(Screen):
    """Main riding screen with elevation profile and stats."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "request_back", "Back"),
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

    .stat-item {
        margin: 1 0;
    }
    """

    def __init__(self, route: Route, **kwargs):
        super().__init__(**kwargs)
        self.route = route

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=True)
        with Container(id="main-container"):
            yield ElevationChart(route=self.route, id="elevation-panel")
            with Container(id="stats-panel"):
                yield Static(f"Route: {self.route.name}", classes="stat-item")
                yield Static(f"Distance: {self.route.distance_km} km", classes="stat-item")
                yield Static("", classes="stat-item")
                yield Static("Mode: DEMO", classes="stat-item")
                yield Static("Power: 0W", classes="stat-item")
                yield Static("Speed: 0 km/h", classes="stat-item")
                yield Static("Cadence: 0 rpm", classes="stat-item")
        yield Footer()

    def action_request_back(self) -> None:
        """Request to go back - will trigger confirmation in main app."""
        self.dismiss()
