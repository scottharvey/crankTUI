"""Main application entry point."""

from textual.app import App, ComposeResult
from textual.widgets import Static


class CrankTUI(App):
    """A Textual app for KICKR trainer control."""

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Static("Hello, crankTUI!")


def main():
    """Run the application."""
    app = CrankTUI()
    app.run()


if __name__ == "__main__":
    main()
