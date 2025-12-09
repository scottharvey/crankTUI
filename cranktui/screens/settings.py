"""Settings screen for user profile and preferences."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Input, Label, Static

from cranktui.config import get_bike_weight_kg, get_rider_weight_kg, set_bike_weight_kg, set_rider_weight_kg


class SettingsScreen(ModalScreen[None]):
    """Modal screen for user settings and profile."""

    BINDINGS = [
        ("escape", "close_modal", "Close"),
        ("enter", "save_settings", "Save"),
        ("left", "navigate_left", "Left"),
        ("right", "navigate_right", "Right"),
    ]

    CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-dialog {
        width: 60;
        height: auto;
        border: round white;
        background: $background 60%;
        padding: 1 2;
    }

    #header {
        width: 100%;
        height: auto;
        content-align: center middle;
        padding-bottom: 1;
        border-bottom: solid white;
        text-style: bold;
    }

    #settings-content {
        width: 100%;
        height: auto;
        padding: 2 1;
    }

    .setting-row {
        width: 100%;
        height: auto;
        margin-bottom: 1;
    }

    .setting-label {
        width: 100%;
        height: auto;
        margin-bottom: 0;
    }

    .setting-input {
        width: 100%;
        height: 3;
        border: round $surface;
    }

    .setting-input:focus {
        border: round white;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
        padding-top: 1;
        border-top: solid white;
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

    #status-message {
        width: 100%;
        height: auto;
        content-align: center middle;
        padding: 1;
        color: green;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rider_weight = get_rider_weight_kg()
        self.bike_weight = get_bike_weight_kg()

    def compose(self) -> ComposeResult:
        """Create dialog widgets."""
        with Container(id="settings-dialog"):
            yield Label("Settings", id="header")
            with Vertical(id="settings-content"):
                with Vertical(classes="setting-row"):
                    yield Label("Rider Weight (kg)", classes="setting-label")
                    yield Input(
                        value=str(self.rider_weight),
                        placeholder="75.0",
                        id="rider-weight-input",
                        classes="setting-input"
                    )
                with Vertical(classes="setting-row"):
                    yield Label("Bike Weight (kg)", classes="setting-label")
                    yield Input(
                        value=str(self.bike_weight),
                        placeholder="10.0",
                        id="bike-weight-input",
                        classes="setting-input"
                    )
            yield Static("", id="status-message")
            with Horizontal(id="buttons"):
                yield Button("Save", id="save-btn")
                yield Button("Cancel", id="cancel-btn")
        yield Footer()

    def on_mount(self) -> None:
        """Focus first input when mounted."""
        self.query_one("#rider-weight-input", Input).focus()

    def action_save_settings(self) -> None:
        """Save settings when Enter is pressed."""
        self.save_settings()

    def action_close_modal(self) -> None:
        """Close the settings screen without saving."""
        self.dismiss()

    def action_navigate_left(self) -> None:
        """Navigate to Save button (left side)."""
        self.query_one("#save-btn", Button).focus()

    def action_navigate_right(self) -> None:
        """Navigate to Cancel button (right side)."""
        self.query_one("#cancel-btn", Button).focus()

    def save_settings(self) -> None:
        """Validate and save settings."""
        rider_input = self.query_one("#rider-weight-input", Input)
        bike_input = self.query_one("#bike-weight-input", Input)
        status_message = self.query_one("#status-message", Static)

        try:
            # Parse and validate rider weight
            rider_weight = float(rider_input.value)
            if rider_weight <= 0 or rider_weight > 300:
                status_message.update("Rider weight must be between 0 and 300 kg")
                status_message.styles.color = "red"
                return

            # Parse and validate bike weight
            bike_weight = float(bike_input.value)
            if bike_weight <= 0 or bike_weight > 50:
                status_message.update("Bike weight must be between 0 and 50 kg")
                status_message.styles.color = "red"
                return

            # Save settings
            set_rider_weight_kg(rider_weight)
            set_bike_weight_kg(bike_weight)

            # Dismiss immediately (no success message needed)
            self.dismiss()

        except ValueError:
            status_message.update("Please enter valid numbers")
            status_message.styles.color = "red"

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "save-btn":
            self.save_settings()
        elif event.button.id == "cancel-btn":
            self.dismiss()
