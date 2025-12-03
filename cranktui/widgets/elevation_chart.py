"""Elevation chart widget for route visualization."""

from rich.console import RenderableType
from rich.text import Text
from textual.widget import Widget

from cranktui.routes.resample import resample_route, get_elevation_range
from cranktui.routes.route import Route


class ElevationChart(Widget):
    """Widget that renders an elevation profile using braille characters."""

    # Full braille block character
    FULL_BLOCK = "⣿"

    def __init__(self, route: Route | None = None, **kwargs):
        super().__init__(**kwargs)
        self.route = route

    def render(self) -> RenderableType:
        """Render the elevation chart."""
        width = self.size.width
        height = self.size.height

        if width == 0 or height == 0:
            return Text("")

        if not self.route or not self.route.points:
            return Text("No route data", style="dim")

        # Resample route to fit width
        resampled_points = resample_route(self.route, width)

        # Get elevation range
        min_elev, max_elev = get_elevation_range(resampled_points)
        elev_range = max_elev - min_elev

        if elev_range == 0:
            elev_range = 1

        # Reserve bottom line for distance markers
        chart_height = height - 1

        # Normalize heights to chart height
        normalized_heights = []
        for point in resampled_points:
            normalized = int(((point.elevation_m - min_elev) / elev_range) * chart_height)
            normalized_heights.append(normalized)

        # Build the chart from top to bottom
        lines = []
        for y in range(chart_height):
            line = ""
            for x, h in enumerate(normalized_heights):
                # Calculate which row this is from bottom
                row_from_bottom = chart_height - y - 1

                # Fill if this row is at or below the elevation
                if row_from_bottom <= h:
                    line += self.FULL_BLOCK
                else:
                    line += " "

            lines.append(line)

        # Add distance markers at the bottom
        distance_line = self._create_distance_markers(width, self.route.distance_km)
        lines.append(distance_line)

        # Join all lines with white color
        chart_text = Text("\n".join(lines), style="white")
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
