"""Route selection screen."""

from textual.app import ComposeResult
from textual.containers import Container, VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from cranktui.routes.route import Route


class RouteItem(Static):
    """A widget for displaying a single route."""

    def __init__(self, route: Route, **kwargs):
        super().__init__(**kwargs)
        self.route = route
        self.can_focus = True

    def render(self) -> str:
        """Render the route information."""
        return f"{self.route.name}\n{self.route.description}\n{self.route.distance_km} km"


class RouteSelectScreen(Screen):
    """Screen for selecting a route."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("escape", "app.pop_screen", "Back"),
        ("up", "focus_previous", "Up"),
        ("down", "focus_next", "Down"),
        ("enter", "select_route", "Select"),
    ]

    CSS = """
    RouteSelectScreen {
        layout: vertical;
    }

    #route-container {
        height: 1fr;
        border: round white;
        margin: 1;
        padding: 1;
    }

    RouteItem {
        height: auto;
        padding: 1 2;
        margin-bottom: 1;
        border: solid $surface;
    }

    RouteItem:focus {
        border: solid white;
        background: $surface;
    }

    RouteItem > .route-name {
        text-style: bold;
    }

    RouteItem > .route-description {
        color: $text-muted;
    }

    RouteItem > .route-distance {
        color: $text-muted;
    }
    """

    def __init__(self, routes: list[Route], **kwargs):
        super().__init__(**kwargs)
        self.routes = routes
        self.route_items: list[RouteItem] = []

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header()
        with VerticalScroll(id="route-container"):
            for route in self.routes:
                item = RouteItem(route)
                self.route_items.append(item)
                yield item
        yield Footer()

    def on_mount(self) -> None:
        """Focus first route when mounted."""
        if self.route_items:
            self.route_items[0].focus()

    def action_select_route(self) -> None:
        """Select the currently focused route."""
        focused = self.focused
        if isinstance(focused, RouteItem):
            self.dismiss(focused.route)
