"""Main application entry point."""

from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Static


class StatusPanel(Static):
    """Widget to display current status information."""

    def __init__(self):
        super().__init__()
        self.border_title = "Status"

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static("Mode: DEMO")
        yield Static("Power: 0W")
        yield Static("Speed: 0 km/h")
        yield Static("Cadence: 0 rpm")


class CrankTUI(App):
    """A Textual app for KICKR trainer control."""

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
        border: solid green;
        content-align: center middle;
    }

    #status-panel {
        width: 1fr;
        border: solid blue;
        padding: 1;
    }

    StatusPanel Static {
        margin: 1 0;
    }
    """

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        with Container(id="main-container"):
            yield Static("[Visualization will go here]", id="viz-panel")
            yield StatusPanel(id="status-panel")


def main():
    """Run the application."""
    app = CrankTUI()
    app.run()


if __name__ == "__main__":
    main()
