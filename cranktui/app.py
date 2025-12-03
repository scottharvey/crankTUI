"""Main application entry point."""

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Header, Label, Static

from cranktui.elevation_chart import ElevationChart
from cranktui.routes.route import Route
from cranktui.routes.route_loader import create_demo_routes, load_all_routes
from cranktui.screens.route_select import RouteSelectScreen


class ConfirmBackScreen(ModalScreen[bool]):
    """Modal dialog to confirm going back to route selection."""

    CSS = """
    ConfirmBackScreen {
        align: center middle;
    }

    #dialog {
        width: 50;
        height: 11;
        border: round white;
        background: $surface;
        padding: 1 2;
    }

    #question {
        width: 100%;
        height: auto;
        content-align: center middle;
        margin-bottom: 1;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }

    Button.-primary {
        background: transparent;
        border: round white;
        color: white;
    }

    Button.-primary:hover {
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        """Create dialog widgets."""
        with Container(id="dialog"):
            yield Label("Return to route selection?", id="question")
            with Container(id="buttons"):
                yield Button("Yes", variant="primary", id="yes")
                yield Button("No", variant="default", id="no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "yes":
            self.dismiss(True)
        else:
            self.dismiss(False)


class StatusPanel(Static):
    """Widget to display current status information."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "Status"

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("Mode: DEMO")
        yield Static("Power: 0W")
        yield Static("Speed: 0 km/h")
        yield Static("Cadence: 0 rpm")


class CrankTUI(App):
    """A Textual app for KICKR trainer control."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "confirm_back", "Back"),
    ]

    CSS = """
    Screen {
        layout: vertical;
    }

    #main-container {
        layout: horizontal;
        height: 1fr;
    }

    #viz-panel {
        width: 2fr;
        border: round white;
        content-align: center middle;
    }

    #status-panel {
        width: 1fr;
        border: round white;
        padding: 1;
    }

    StatusPanel Static {
        margin: 1 0;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_route: Route | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with Container(id="main-container"):
            yield ElevationChart(id="viz-panel")
            yield StatusPanel(id="status-panel")

    def on_mount(self) -> None:
        """Handle app mount - show route selection."""
        # Ensure demo routes exist
        create_demo_routes()

        # Load routes and show selection screen
        routes = load_all_routes()

        if routes:
            self.push_screen(RouteSelectScreen(routes), self.on_route_selected)
        else:
            self.notify("No routes found. Add route JSON files to ~/.local/share/cranktui/routes/")

    def on_route_selected(self, route: Route | None) -> None:
        """Handle route selection."""
        if route:
            self.selected_route = route
            self.notify(f"Selected route: {route.name}")

    def action_confirm_back(self) -> None:
        """Show confirmation dialog before going back to route selection."""
        # Only show dialog if we have a selected route
        if self.selected_route:
            self.push_screen(ConfirmBackScreen(), self.handle_confirm_back)

    def handle_confirm_back(self, confirmed: bool) -> None:
        """Handle the confirmation result."""
        if confirmed:
            # Clear selected route
            self.selected_route = None

            # Load routes and show selection screen
            routes = load_all_routes()
            if routes:
                self.push_screen(RouteSelectScreen(routes), self.on_route_selected)


def main():
    """Run the application."""
    app = CrankTUI()
    app.run()


if __name__ == "__main__":
    main()
