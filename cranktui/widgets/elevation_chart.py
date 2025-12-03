"""Elevation chart widget for route visualization."""

from rich.console import RenderableType
from rich.text import Text
from textual.widget import Widget

from cranktui.routes.resample import resample_route, get_elevation_range
from cranktui.routes.route import Route


class ElevationChart(Widget):
    """Widget that renders an elevation profile using braille characters."""

    # Braille patterns for different fill levels (0-4 dots vertical)
    BRAILLE_LEVELS = [
        " ",      # 0 dots - empty
        "⠈",      # 1 dot  - top
        "⠘",      # 2 dots - top + middle-top
        "⠸",      # 3 dots - top + middle-top + middle-bottom
        "⣸",      # 4 dots - all dots (filled)
    ]

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

        # Convert elevations to pixel heights (multiply by 4 for braille resolution)
        pixel_height = chart_height * 4
        normalized_heights = []
        for point in resampled_points:
            pixel_h = int(((point.elevation_m - min_elev) / elev_range) * pixel_height)
            normalized_heights.append(pixel_h)

        # Build the chart from top to bottom
        lines = []
        for y in range(chart_height):
            line = ""
            for x, pixel_h in enumerate(normalized_heights):
                # Calculate which braille level to use for this position
                # Each character row represents 4 vertical pixels
                row_bottom = (chart_height - y - 1) * 4
                row_top = row_bottom + 4

                if pixel_h >= row_top:
                    # Fully filled
                    line += self.BRAILLE_LEVELS[4]
                elif pixel_h > row_bottom:
                    # Partially filled
                    dots = pixel_h - row_bottom
                    line += self.BRAILLE_LEVELS[dots]
                else:
                    # Empty
                    line += self.BRAILLE_LEVELS[0]

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
