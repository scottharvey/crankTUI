"""Elevation chart widget for route visualization."""

from rich.console import RenderableType
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from cranktui.routes.resample import resample_route, get_elevation_range
from cranktui.routes.route import Route
from cranktui.state.state import get_state


class ElevationChart(Widget):
    """Widget that renders an elevation profile using braille characters."""

    # Braille characters for different top edge patterns
    FULL_BLOCK = "⣿"          # Full block for filled areas
    SLOPE_UP = "⣠"            # Up-slope: right side higher (dots 4,5,6,7,8)
    SLOPE_DOWN = "⣷"          # Down-slope: full except top-right missing (all except dots 5,6,7)
    SLOPE_FLAT = "⣀"          # Flat top: bottom row (dots 4,8)
    RIDER_MARKER = "▲"

    # Reactive property for current distance
    current_distance_m: reactive[float] = reactive(0.0)

    def __init__(self, route: Route | None = None, **kwargs):
        super().__init__(**kwargs)
        self.route = route
        self.state = get_state()

    def on_mount(self) -> None:
        """Handle mount - start update timer."""
        self.set_interval(0.05, self.update_position)  # Update at 20 FPS

    async def update_position(self) -> None:
        """Fetch current distance from state."""
        metrics = await self.state.get_metrics()
        self.current_distance_m = metrics.distance_m

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

        # Calculate rider position
        rider_x = self._calculate_rider_position(width)

        # Build the chart from top to bottom
        lines = []
        for y in range(chart_height):
            line = ""
            for x, h in enumerate(normalized_heights):
                # Calculate which row this is from bottom
                row_from_bottom = chart_height - y - 1

                # Check if this position should be filled
                if row_from_bottom < h:
                    # Below the top - always use full block
                    line += self.FULL_BLOCK
                elif row_from_bottom == h:
                    # This is the top row - use slope-aware character
                    # Check previous column to see if we're coming from higher
                    prev_h = normalized_heights[x - 1] if x > 0 else h
                    # Check next column to see where we're going
                    next_h = normalized_heights[x + 1] if x < len(normalized_heights) - 1 else h

                    if prev_h > h:
                        # Coming down from previous column - use down-slope
                        line += self.SLOPE_DOWN
                    elif next_h > h:
                        # Next column is higher - upward slope
                        line += self.SLOPE_UP
                    else:
                        # Flat or going down to next
                        line += self.SLOPE_FLAT
                else:
                    # Above the elevation - empty
                    line += " "

            lines.append(line)

        # Add rider marker above the elevation profile
        if rider_x is not None and 0 <= rider_x < width:
            # Find the top of the elevation at rider position
            rider_height = normalized_heights[rider_x]
            marker_row = chart_height - rider_height - 2  # Place 1 row above the elevation

            if 0 <= marker_row < chart_height:
                # Insert marker into the line
                line = lines[marker_row]
                lines[marker_row] = line[:rider_x] + self.RIDER_MARKER + line[rider_x + 1:]

        # Add distance markers at the bottom
        distance_line = self._create_distance_markers(width, self.route.distance_km)
        lines.append(distance_line)

        # Join all lines with white color
        chart_text = Text("\n".join(lines), style="white")
        return chart_text

    def _calculate_rider_position(self, width: int) -> int | None:
        """Calculate the X position of the rider marker.

        Args:
            width: Chart width in characters

        Returns:
            X position (0 to width-1), or None if not applicable
        """
        if not self.route:
            return None

        total_distance_m = self.route.distance_km * 1000

        if total_distance_m == 0:
            return None

        # Calculate position as fraction of total distance
        progress = self.current_distance_m / total_distance_m

        # Clamp to [0, 1]
        progress = max(0.0, min(1.0, progress))

        # Convert to X position
        x = int(progress * (width - 1))

        return x

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
