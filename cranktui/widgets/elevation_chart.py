"""Elevation chart widget for route visualization."""

from rich.console import RenderableType
from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from cranktui.routes.resample import resample_route, get_elevation_range
from cranktui.routes.route import Route
from cranktui.state.state import get_state


class ElevationChart(Widget):
    """Widget that renders an elevation profile using braille characters.

    Displays two views:
    - Main view: Scrolling detailed view centered on rider (~500m window)
    - Minimap: Small overview of entire route in bottom-right corner
    """

    # Braille characters for different top edge patterns
    FULL_BLOCK = "⣿"          # Full block for filled areas
    SLOPE_UP = "⣠"            # Up-slope: right side higher (dots 4,5,6,7,8)
    SLOPE_DOWN = "⣷"          # Down-slope: full except top-right missing (all except dots 5,6,7)
    SLOPE_FLAT = "⣀"          # Flat top: bottom row (dots 4,8)

    # Reactive property for current distance
    current_distance_m: reactive[float] = reactive(0.0)

    def __init__(self, route: Route | None = None, **kwargs):
        super().__init__(**kwargs)
        self.route = route
        self.state = get_state()
        self.window_size_m = 500.0  # Show 500m window (250m ahead, 250m behind)

    def on_mount(self) -> None:
        """Handle mount - start update timer."""
        self.set_interval(0.05, self.update_position)  # Update at 20 FPS

    async def update_position(self) -> None:
        """Fetch current distance from state."""
        metrics = await self.state.get_metrics()
        self.current_distance_m = metrics.distance_m

    def render(self) -> RenderableType:
        """Render the elevation chart with main view and minimap."""
        width = self.size.width
        height = self.size.height

        if width == 0 or height == 0:
            return Text("")

        if not self.route or not self.route.points:
            return Text("No route data", style="dim")

        # Minimap dimensions (bottom-right corner)
        minimap_width = min(20, width // 4)
        minimap_height = min(8, height // 4)

        # Main view area (leave space for minimap)
        main_width = width
        main_height = height - 1  # Reserve bottom line for distance markers

        # Render main scrolling view
        main_view = self._render_main_view(main_width, main_height)

        # Render minimap overlay
        minimap = self._render_minimap(minimap_width, minimap_height)

        # Combine views: overlay minimap on bottom-right of main view
        result = self._overlay_minimap(main_view, minimap, width, height, minimap_width, minimap_height)

        return result

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

    def _render_main_view(self, width: int, height: int) -> list[str]:
        """Render the main scrolling elevation view.

        Returns:
            List of strings, one per row
        """
        if not self.route:
            return [""] * height

        total_distance_m = self.route.distance_km * 1000

        # Calculate window bounds (centered on rider)
        center_distance = self.current_distance_m
        window_start = max(0, center_distance - self.window_size_m / 2)
        window_end = min(total_distance_m, center_distance + self.window_size_m / 2)

        # Get route points in this window
        window_points = [
            p for p in self.route.points
            if window_start <= p.distance_m <= window_end
        ]

        if len(window_points) < 2:
            return ["No data in window"] + [""] * (height - 1)

        # Resample to fit width
        # Create a temporary route object for the window
        from cranktui.routes.route import Route, RoutePoint
        window_route = Route(
            name="window",
            description="",
            distance_km=(window_end - window_start) / 1000,
            points=window_points
        )

        resampled_points = resample_route(window_route, width)

        # Get elevation range for this window
        min_elev, max_elev = get_elevation_range(resampled_points)
        elev_range = max_elev - min_elev

        if elev_range == 0:
            elev_range = 1

        # Calculate realistic vertical scale
        chart_height = height
        meters_per_row = elev_range / (chart_height * 0.5)
        meters_per_row = max(2.0, meters_per_row)

        # Normalize heights
        normalized_heights = []
        for point in resampled_points:
            height_in_rows = (point.elevation_m - min_elev) / meters_per_row
            normalized = int(height_in_rows)
            normalized = min(normalized, chart_height - 1)
            normalized_heights.append(normalized)

        # Calculate rider position in window
        if window_end > window_start:
            rider_progress = (center_distance - window_start) / (window_end - window_start)
            rider_x = int(rider_progress * (width - 1))
        else:
            rider_x = width // 2

        # Build the chart rows
        rows = []
        for y in range(chart_height):
            row = []
            for x, h in enumerate(normalized_heights):
                row_from_bottom = chart_height - y - 1

                is_rider_column = (x == rider_x)
                style = "green" if is_rider_column else "white"

                if row_from_bottom < h:
                    row.append(self.FULL_BLOCK)
                elif row_from_bottom == h:
                    prev_h = normalized_heights[x - 1] if x > 0 else h
                    next_h = normalized_heights[x + 1] if x < len(normalized_heights) - 1 else h

                    if prev_h > h:
                        row.append(self.SLOPE_DOWN)
                    elif next_h > h:
                        row.append(self.SLOPE_UP)
                    else:
                        row.append(self.SLOPE_FLAT)
                else:
                    row.append(" ")

            rows.append("".join(row))

        return rows

    def _render_minimap(self, width: int, height: int) -> list[str]:
        """Render the minimap showing full route.

        Returns:
            List of strings, one per row
        """
        if not self.route or width < 5 or height < 3:
            return [""] * height

        # Resample entire route to minimap width
        resampled_points = resample_route(self.route, width)

        # Get full route elevation range
        min_elev, max_elev = get_elevation_range(resampled_points)
        elev_range = max_elev - min_elev

        if elev_range == 0:
            elev_range = 1

        # Normalize to minimap height
        chart_height = height - 1  # Reserve one line for label

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

        # Build minimap rows
        rows = []
        for y in range(chart_height):
            row = []
            for x, h in enumerate(normalized_heights):
                row_from_bottom = chart_height - y - 1

                is_rider_column = (x == rider_x)

                if row_from_bottom <= h:
                    # Use different character for rider position
                    if is_rider_column:
                        row.append("▲")
                    else:
                        row.append("⣿")
                else:
                    row.append(" ")

            rows.append("".join(row))

        # Add label
        rows.append(" MINIMAP")

        return rows

    def _overlay_minimap(self, main_view: list[str], minimap: list[str],
                        total_width: int, total_height: int,
                        minimap_width: int, minimap_height: int) -> Text:
        """Overlay minimap on bottom-right of main view.

        Args:
            main_view: List of main view rows
            minimap: List of minimap rows
            total_width: Total chart width
            total_height: Total chart height
            minimap_width: Minimap width
            minimap_height: Minimap height

        Returns:
            Combined Text with minimap overlaid
        """
        result = Text()

        # Position minimap in bottom-right
        minimap_start_row = total_height - minimap_height - 1
        minimap_start_col = total_width - minimap_width - 1

        for row_idx in range(total_height - 1):  # -1 for distance markers
            if row_idx < len(main_view):
                main_row = main_view[row_idx]
            else:
                main_row = " " * total_width

            # Check if we need to overlay minimap on this row
            if minimap_start_row <= row_idx < minimap_start_row + minimap_height:
                minimap_row_idx = row_idx - minimap_start_row
                if minimap_row_idx < len(minimap):
                    minimap_row = minimap[minimap_row_idx]

                    # Combine: use main view up to minimap position, then minimap
                    combined = main_row[:minimap_start_col] + minimap_row
                    # Pad if needed
                    if len(combined) < total_width:
                        combined += " " * (total_width - len(combined))
                    result.append(combined[:total_width])
                else:
                    result.append(main_row)
            else:
                result.append(main_row)

            result.append("\n")

        # Add distance markers for main view
        # Show window bounds
        window_start_km = max(0, (self.current_distance_m - self.window_size_m / 2)) / 1000
        window_end_km = min(self.route.distance_km, (self.current_distance_m + self.window_size_m / 2) / 1000)

        distance_line = self._create_window_distance_markers(total_width, window_start_km, window_end_km)
        result.append(distance_line, style="white")

        return result

    def _create_window_distance_markers(self, width: int, start_km: float, end_km: float) -> str:
        """Create distance markers showing the current window bounds."""
        if width < 10:
            return ""

        start = f"{start_km:.1f}"
        middle = f"{(start_km + end_km) / 2:.1f}"
        end = f"{end_km:.1f}km"

        # Calculate spacing
        middle_pos = width // 2 - len(middle) // 2
        end_pos = width - len(end)

        # Build the marker line
        line = [" "] * width

        # Place markers
        for i, char in enumerate(start):
            if i < width:
                line[i] = char

        for i, char in enumerate(middle):
            pos = middle_pos + i
            if 0 <= pos < width:
                line[pos] = char

        for i, char in enumerate(end):
            pos = end_pos + i
            if 0 <= pos < width:
                line[pos] = char

        return "".join(line)
