"""Main application entry point."""

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Button, Header, Label, Static

from cranktui.routes.route import Route
from cranktui.routes.route_loader import create_demo_routes, load_all_routes
from cranktui.screens.riding import RidingScreen
from cranktui.screens.route_select import RouteSelectScreen


class ConfirmBackScreen(ModalScreen[bool]):
    """Modal dialog to confirm going back to route selection."""

    BINDINGS = [
        ("up", "navigate_buttons", "Navigate"),
        ("down", "navigate_buttons", "Navigate"),
        ("left", "navigate_buttons", "Navigate"),
        ("right", "navigate_buttons", "Navigate"),
    ]

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
        background: transparent;
        border: none;
        color: white;
    }

    Button:focus {
        border: round white;
    }
    """

    def compose(self) -> ComposeResult:
        """Create dialog widgets."""
        with Container(id="dialog"):
            yield Label("Return to route selection?", id="question")
            with Container(id="buttons"):
                yield Button("Yes", id="yes")
                yield Button("No", id="no")

    def action_navigate_buttons(self) -> None:
        """Toggle focus between buttons."""
        buttons = self.query(Button)
        if len(buttons) == 2:
            # Get currently focused button
            if self.query_one("#yes", Button).has_focus:
                self.query_one("#no", Button).focus()
            else:
                self.query_one("#yes", Button).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "yes":
            self.dismiss(True)
        else:
            self.dismiss(False)


class CrankTUI(App):
    """A Textual app for KICKR trainer control."""

    BINDINGS = [
        ("q", "quit", "Quit"),
    ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_route: Route | None = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        # Empty main screen - we always show screens on top
        yield Static("")

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
            # Show the riding screen
            self.push_screen(RidingScreen(route), self.on_riding_complete)

    def on_riding_complete(self, result) -> None:
        """Handle when riding screen is dismissed."""
        # Show confirmation dialog
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
        else:
            # Return to riding screen
            if self.selected_route:
                self.push_screen(RidingScreen(self.selected_route), self.on_riding_complete)


def main():
    """Run the application."""
    app = CrankTUI()
    app.run()


if __name__ == "__main__":
    main()
