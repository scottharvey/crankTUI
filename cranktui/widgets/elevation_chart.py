"""Elevation chart widget for route visualization."""

from rich.console import RenderableType
from rich.text import Text
from textual.widget import Widget

from cranktui.routes.resample import resample_route, get_elevation_range
from cranktui.routes.route import Route


class ElevationChart(Widget):
    """Widget that renders an elevation profile using braille characters."""

    # Braille patterns using 2x4 dot matrix (left and right columns)
    # Unicode braille: U+2800 base + bit pattern
    # Bits: 0=top-left, 1=mid-left, 2=low-left, 3=bottom-left,
    #       4=top-right, 5=mid-right, 6=low-right, 7=bottom-right

    def __init__(self, route: Route | None = None, **kwargs):
        super().__init__(**kwargs)
        self.route = route

    def _get_braille(self, dots: list[bool]) -> str:
        """Convert 8 dots to braille character.

        Args:
            dots: List of 8 booleans representing braille dots:
                  [0,1,2,3,4,5,6,7] where each index corresponds to the bit position
        """
        value = 0x2800
        for i, dot in enumerate(dots):
            if dot:
                value += (1 << i)
        return chr(value)

    def render(self) -> RenderableType:
        """Render the elevation chart."""
        width = self.size.width
        height = self.size.height

        if width == 0 or height == 0:
            return Text("")

        if not self.route or not self.route.points:
            return Text("No route data", style="dim")

        # Resample route to fit width (each char has 2 horizontal pixels)
        resampled_points = resample_route(self.route, width * 2)

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
            pixel_h = ((point.elevation_m - min_elev) / elev_range) * pixel_height
            normalized_heights.append(pixel_h)

        # Create a 2D grid for the filled area
        grid = [[False] * (width * 2) for _ in range(chart_height * 4)]

        # Draw the elevation profile by filling below the line
        for x in range(len(normalized_heights)):
            h = normalized_heights[x]
            # Fill from bottom (0) up to the elevation height
            for y in range(int(h) + 1):
                if y < len(grid):
                    grid[y][x] = True

        # Convert grid to braille characters
        lines = []
        for char_row in range(chart_height):
            line = ""
            for char_col in range(width):
                # Each braille character represents 2x4 pixels
                dots = [False] * 8

                # Map pixels to braille dots
                # Left column (dots 0,1,2,3) and right column (dots 4,5,6,7)
                for dot_row in range(4):
                    pixel_y = (chart_height - char_row - 1) * 4 + dot_row

                    # Left column
                    pixel_x_left = char_col * 2
                    if pixel_x_left < len(grid[0]) and pixel_y < len(grid):
                        dots[dot_row] = grid[pixel_y][pixel_x_left]

                    # Right column
                    pixel_x_right = char_col * 2 + 1
                    if pixel_x_right < len(grid[0]) and pixel_y < len(grid):
                        dots[dot_row + 4] = grid[pixel_y][pixel_x_right]

                line += self._get_braille(dots)

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
