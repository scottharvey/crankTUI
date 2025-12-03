"""Main application entry point."""

import argparse

from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Header, Label, Static

from cranktui.config import get_last_device
from cranktui.routes.route import Route
from cranktui.routes.route_loader import create_demo_routes, load_all_routes
from cranktui.screens.riding import RidingScreen
from cranktui.screens.route_select import RouteSelectScreen
from cranktui.state.state import get_state

# Global debug flag
DEBUG_MODE = False


class ConfirmBackScreen(ModalScreen[bool]):
    """Modal dialog to confirm going back to route selection."""

    BINDINGS = [
        ("left", "navigate_left", "Left"),
        ("right", "navigate_right", "Right"),
    ]

    CSS = """
    ConfirmBackScreen {
        align: center middle;
    }

    #dialog {
        width: 50;
        height: 9;
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
        border: round $surface;
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
            with Horizontal(id="buttons"):
                yield Button("Yes", id="yes")
                yield Button("No", id="no")

    def action_navigate_left(self) -> None:
        """Navigate to Yes button."""
        self.query_one("#yes", Button).focus()

    def action_navigate_right(self) -> None:
        """Navigate to No button."""
        self.query_one("#no", Button).focus()

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
        self.state = get_state()

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        # Empty main screen - we always show screens on top
        yield Static("")

    def on_mount(self) -> None:
        """Handle app mount - show route selection."""
        # Ensure demo routes exist
        create_demo_routes()

        # Try to auto-reconnect to last device
        self.run_worker(self.auto_reconnect_device())

        # Load routes and show selection screen
        routes = load_all_routes()

        if routes:
            self.push_screen(RouteSelectScreen(routes), self.on_route_selected)
        else:
            self.notify("No routes found. Add route JSON files to ~/.local/share/cranktui/routes/")

    async def auto_reconnect_device(self) -> None:
        """Try to reconnect to the last connected device."""
        from cranktui.ble.client import BLEClient

        address, name = get_last_device()
        if not address or not name:
            return

        try:
            ble_client = BLEClient()
            success, error = await ble_client.connect(address, name)

            if success:
                await self.state.update_ble_client(ble_client)

                # Start data stream with state updater callback
                data_started = await ble_client.start_data_stream(self._handle_trainer_data)
                if data_started:
                    self.notify(f"Reconnected to {name}")
                else:
                    self.notify(f"Reconnected to {name} (data stream failed)")
            else:
                # Silently fail - user can manually connect if needed
                pass
        except Exception:
            # Silently fail - user can manually connect if needed
            pass

    def _handle_trainer_data(self, data: dict) -> None:
        """Handle incoming trainer data from BLE.

        Args:
            data: Dictionary with power_w, cadence_rpm, speed_kmh, distance_m
        """
        # Update global state asynchronously
        self.run_worker(self._update_state(data))

    async def _update_state(self, data: dict) -> None:
        """Update global state with trainer data.

        Args:
            data: Dictionary with power_w, cadence_rpm, speed_kmh, distance_m
        """
        await self.state.update_metrics(
            power_w=data['power_w'],
            cadence_rpm=data['cadence_rpm'],
            speed_kmh=data['speed_kmh'],
            mode="LIVE"
        )

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
    global DEBUG_MODE

    parser = argparse.ArgumentParser(description="crankTUI - Terminal trainer controller")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging to cranktui-debug.log")
    args = parser.parse_args()

    DEBUG_MODE = args.debug

    if DEBUG_MODE:
        # Clear the debug log at startup
        with open("cranktui-debug.log", "w") as f:
            f.write("=== crankTUI Debug Log ===\n")

    app = CrankTUI()
    app.run()


if __name__ == "__main__":
    main()
