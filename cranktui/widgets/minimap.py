"""Minimap widget showing full route overview."""

from rich.console import RenderableType
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from cranktui.routes.resample import resample_route, get_elevation_range
from cranktui.routes.route import Route
from cranktui.state.state import get_state


class MinimapWidget(Widget):
    """Widget that shows compressed overview of entire route."""

    FULL_BLOCK = "⣿"

    # Reactive property for current distance
    current_distance_m: reactive[float] = reactive(0.0)

    def __init__(self, route: Route | None = None, **kwargs):
        super().__init__(**kwargs)
        self.route = route
        self.state = get_state()

    def on_mount(self) -> None:
        """Handle mount - start update timer."""
        self.set_interval(0.1, self.update_position)  # Update at 10 FPS

    async def update_position(self) -> None:
        """Fetch current distance from state."""
        metrics = await self.state.get_metrics()
        self.current_distance_m = metrics.distance_m

    def render(self) -> RenderableType:
        """Render the minimap."""
        width = self.size.width
        height = self.size.height

        if width == 0 or height == 0:
            return Text("")

        if not self.route or not self.route.points:
            return Text("No route data", style="dim")

        # Reserve bottom line for distance markers
        chart_height = height - 1

        # Resample entire route to fit width
        resampled_points = resample_route(self.route, width)

        # Get full route elevation range
        min_elev, max_elev = get_elevation_range(resampled_points)
        elev_range = max_elev - min_elev

        if elev_range == 0:
            elev_range = 1

        # Normalize to chart height (use full height for minimap)
        normalized_heights = []
        for point in resampled_points:
            normalized = int(((point.elevation_m - min_elev) / elev_range) * chart_height)
            normalized = min(normalized, chart_height - 1)
            normalized_heights.append(normalized)

        # Calculate rider position on minimap
        total_distance_m = self.route.distance_km * 1000
        if total_distance_m > 0:
            progress = self.current_distance_m / total_distance_m
            progress = max(0.0, min(1.0, progress))
            rider_x = int(progress * (width - 1))
        else:
            rider_x = 0

        # Calculate start line position (first column of route)
        route_start_distance_m = self.route.points[0].distance_m if self.route.points else 0
        if total_distance_m > 0:
            start_progress = route_start_distance_m / total_distance_m
            start_x = int(start_progress * (width - 1))
        else:
            start_x = 0

        # Calculate finish line position (actual end of route, not padded end)
        # The route ends at route.distance_km * 1000, which should be at the last actual route point
        route_end_distance_m = self.route.points[-1].distance_m if self.route.points else 0
        if total_distance_m > 0:
            finish_progress = route_end_distance_m / total_distance_m
            finish_x = int(finish_progress * (width - 1))
        else:
            finish_x = width - 1

        # Build the chart from top to bottom using Rich Text for styling
        chart_text = Text()

        for y in range(chart_height):
            for x, h in enumerate(normalized_heights):
                # Calculate which row this is from bottom
                row_from_bottom = chart_height - y - 1

                # Determine styling based on special columns
                is_rider_column = (x == rider_x)
                is_start_column = (x == start_x)
                is_finish_column = (x == finish_x)

                if is_finish_column:
                    style = "red"
                elif is_rider_column:
                    style = "green"
                elif is_start_column:
                    style = "dark_green"
                else:
                    style = "white"

                # Check if this position should be filled
                if row_from_bottom <= h:
                    # Use green color for rider's column
                    chart_text.append(self.FULL_BLOCK, style=style)
                else:
                    # Above the elevation - empty
                    chart_text.append(" ")

            # Add newline after each row
            if y < chart_height - 1:
                chart_text.append("\n")

        # Add distance markers at the bottom
        chart_text.append("\n")
        distance_line = self._create_distance_markers(width, self.route.distance_km)
        chart_text.append(distance_line, style="white dim")

        return chart_text

    def _create_distance_markers(self, width: int, total_distance_km: float) -> str:
        """Create distance markers for the bottom of the chart."""
        if width < 10:
            return ""

        # Show markers at start, middle, and end
        start = "0"
        middle = f"{total_distance_km / 2:.1f}"
        end = f"{total_distance_km:.1f}km"

        # Calculate spacing
        middle_pos = width // 2 - len(middle) // 2
        end_pos = width - len(end)

        # Build the marker line
        line = [" "] * width

        # Place start marker
        for i, char in enumerate(start):
            if i < width:
                line[i] = char

        # Place middle marker
        for i, char in enumerate(middle):
            pos = middle_pos + i
            if 0 <= pos < width:
                line[pos] = char

        # Place end marker
        for i, char in enumerate(end):
            pos = end_pos + i
            if 0 <= pos < width:
                line[pos] = char

        return "".join(line)
