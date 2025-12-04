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

        # Reserve bottom line for distance markers
        chart_height = height - 1

        # Define viewport window: 500m behind, 4500m ahead
        VIEWPORT_BEHIND_M = 500
        VIEWPORT_AHEAD_M = 4500
        VIEWPORT_TOTAL_M = VIEWPORT_BEHIND_M + VIEWPORT_AHEAD_M

        # Calculate window bounds
        window_start_m = self.current_distance_m - VIEWPORT_BEHIND_M
        window_end_m = self.current_distance_m + VIEWPORT_AHEAD_M

        # Get route points within window (with padding at start/end)
        visible_points = self._get_visible_points(window_start_m, window_end_m)

        # Resample visible points to fit width
        resampled_points = self._resample_points(visible_points, width)

        # Safety check: if resampling failed, return empty
        if not resampled_points:
            return Text("No data in viewport", style="dim")

        # Get elevation range for visible window
        min_elev, max_elev = get_elevation_range(resampled_points)
        elev_range = max_elev - min_elev

        if elev_range == 0:
            elev_range = 1

        # Calculate vertical scale with exaggeration for visibility
        # Use 3x vertical exaggeration to make grades clearly visible
        # This makes a 5% grade look like ~15% visually, which is much more readable
        # while still maintaining proportional representation of the terrain

        VERTICAL_EXAGGERATION = 3.0

        meters_per_char_horizontal = VIEWPORT_TOTAL_M / width if width > 0 else 50
        # Use 3x exaggeration: divide by 3 to make vertical features 3x larger
        meters_per_row = meters_per_char_horizontal / VERTICAL_EXAGGERATION

        # Calculate how many rows the elevation range would occupy
        rows_needed = int(elev_range / meters_per_row) + 1

        # If it still doesn't fit in available height, scale it down proportionally
        if rows_needed > chart_height:
            meters_per_row = elev_range / chart_height

        # Normalize heights using realistic scale
        normalized_heights = []
        for point in resampled_points:
            # Calculate height in rows from the minimum elevation
            height_in_rows = int((point.elevation_m - min_elev) / meters_per_row)
            # Clamp to chart height
            height_in_rows = min(height_in_rows, chart_height - 1)
            normalized_heights.append(height_in_rows)

        # Calculate rider position (always at 10% from left edge in scrolling view)
        rider_x = int(width * (VIEWPORT_BEHIND_M / VIEWPORT_TOTAL_M))

        # Calculate start line position (first point of actual route)
        route_start_m = self.route.points[0].distance_m if self.route.points else 0
        start_x = None
        if window_start_m <= route_start_m <= window_end_m:
            # Start line is visible in this window
            progress_in_window = (route_start_m - window_start_m) / VIEWPORT_TOTAL_M
            start_x = int(progress_in_window * width)
            start_x = max(0, min(start_x, width - 1))

        # Calculate finish line position (last point of actual route)
        route_end_m = self.route.points[-1].distance_m if self.route.points else 0
        finish_x = None
        if window_start_m <= route_end_m <= window_end_m:
            # Finish line is visible in this window
            progress_in_window = (route_end_m - window_start_m) / VIEWPORT_TOTAL_M
            finish_x = int(progress_in_window * width)
            finish_x = max(0, min(finish_x, width - 1))

        # Build the chart from top to bottom using Rich Text for styling
        chart_text = Text()

        for y in range(chart_height):
            for x, h in enumerate(normalized_heights):
                # Calculate which row this is from bottom
                row_from_bottom = chart_height - y - 1

                # Determine styling based on special columns
                is_rider_column = (rider_x is not None and x == rider_x)
                is_start_column = (start_x is not None and x == start_x)
                is_finish_column = (finish_x is not None and x == finish_x)

                if is_finish_column:
                    style = "red"
                elif is_rider_column:
                    style = "green"
                elif is_start_column:
                    style = "dark_green"
                else:
                    style = "white"

                # Bottom row is always filled as baseline/ground
                if row_from_bottom == 0:
                    chart_text.append(self.FULL_BLOCK, style=style)
                # Check if this position should be filled
                elif row_from_bottom < h:
                    # Below the top - always use full block
                    chart_text.append(self.FULL_BLOCK, style=style)
                elif row_from_bottom == h:
                    # This is the top row - use slope-aware character
                    # Check previous column to see if we're coming from higher
                    prev_h = normalized_heights[x - 1] if x > 0 else h
                    # Check next column to see where we're going
                    next_h = normalized_heights[x + 1] if x < len(normalized_heights) - 1 else h

                    if prev_h > h:
                        # Coming down from previous column - use down-slope
                        chart_text.append(self.SLOPE_DOWN, style=style)
                    elif next_h > h:
                        # Next column is higher - upward slope
                        chart_text.append(self.SLOPE_UP, style=style)
                    else:
                        # Flat or going down to next
                        chart_text.append(self.SLOPE_FLAT, style=style)
                else:
                    # Above the elevation - empty
                    chart_text.append(" ")

            # Add newline after each row (except the last)
            if y < chart_height - 1:
                chart_text.append("\n")

        # Add distance markers at the bottom (show visible window range)
        chart_text.append("\n")
        distance_line = self._create_distance_markers(width, window_start_m / 1000, window_end_m / 1000)
        chart_text.append(distance_line, style="white")

        return chart_text

    def _get_visible_points(self, window_start_m: float, window_end_m: float) -> list:
        """Get route points within the visible window, with padding at edges.

        Args:
            window_start_m: Start of visible window in meters
            window_end_m: End of visible window in meters

        Returns:
            List of RoutePoint objects for the visible window
        """
        from cranktui.routes.route import RoutePoint

        visible_points = []
        route_start_m = self.route.points[0].distance_m if self.route.points else 0
        route_end_m = self.route.points[-1].distance_m if self.route.points else 0

        # Add padding before route start if needed
        if window_start_m < route_start_m:
            # Add flat ground padding
            start_elevation = self.route.points[0].elevation_m if self.route.points else 0
            # Add point at window start
            visible_points.append(RoutePoint(distance_m=window_start_m, elevation_m=start_elevation))
            # Add point just before route starts
            if window_end_m >= route_start_m:
                visible_points.append(RoutePoint(distance_m=route_start_m - 0.1, elevation_m=start_elevation))

        # Add actual route points within window
        # Also include points just outside the window for proper interpolation
        for i, point in enumerate(self.route.points):
            if window_start_m <= point.distance_m <= window_end_m:
                visible_points.append(point)
            elif point.distance_m < window_start_m:
                # Keep track of the last point before window (for interpolation)
                if not visible_points or visible_points[-1].distance_m < point.distance_m:
                    if visible_points and visible_points[-1].distance_m < window_start_m:
                        visible_points.pop()
                    visible_points.append(point)
            elif point.distance_m > window_end_m:
                # Add first point after window (for interpolation) and stop
                visible_points.append(point)
                break

        # Add padding after route end if needed
        if window_end_m > route_end_m:
            # Add flat ground padding
            end_elevation = self.route.points[-1].elevation_m if self.route.points else 0
            # Add point just after route ends
            if window_start_m <= route_end_m:
                visible_points.append(RoutePoint(distance_m=route_end_m + 0.1, elevation_m=end_elevation))
            # Add point at window end
            visible_points.append(RoutePoint(distance_m=window_end_m, elevation_m=end_elevation))

        return visible_points

    def _resample_points(self, points: list, target_width: int) -> list:
        """Resample points to target width.

        Args:
            points: List of RoutePoint objects
            target_width: Number of samples desired

        Returns:
            List of resampled RoutePoint objects
        """
        from cranktui.routes.route import RoutePoint

        if not points:
            return []

        if len(points) == 1:
            # If only one point, duplicate it to fill width
            return [points[0]] * target_width

        start_distance = points[0].distance_m
        end_distance = points[-1].distance_m
        total_distance = end_distance - start_distance

        if total_distance == 0:
            # All points at same distance, return duplicates
            return [points[0]] * target_width

        # Create evenly spaced samples
        resampled = []
        for i in range(target_width):
            # Calculate distance for this sample
            fraction = i / (target_width - 1) if target_width > 1 else 0
            sample_distance = start_distance + (fraction * total_distance)

            # Find surrounding points and interpolate elevation
            elevation = self._interpolate_elevation(points, sample_distance)
            resampled.append(RoutePoint(distance_m=sample_distance, elevation_m=elevation))

        return resampled

    def _interpolate_elevation(self, points: list, distance_m: float) -> float:
        """Interpolate elevation at a given distance.

        Args:
            points: List of RoutePoint objects
            distance_m: Distance to interpolate at

        Returns:
            Interpolated elevation in meters
        """
        if not points:
            return 0.0

        # Before first point
        if distance_m <= points[0].distance_m:
            return points[0].elevation_m

        # After last point
        if distance_m >= points[-1].distance_m:
            return points[-1].elevation_m

        # Find surrounding points
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]

            if p1.distance_m <= distance_m <= p2.distance_m:
                # Linear interpolation
                if p2.distance_m == p1.distance_m:
                    return p1.elevation_m
                ratio = (distance_m - p1.distance_m) / (p2.distance_m - p1.distance_m)
                return p1.elevation_m + ratio * (p2.elevation_m - p1.elevation_m)

        return points[-1].elevation_m

    def _create_distance_markers(self, width: int, start_km: float, end_km: float) -> str:
        """Create distance markers for the bottom of the chart.

        Args:
            width: Chart width in characters
            start_km: Start distance in km
            end_km: End distance in km
        """
        if width < 10:
            return ""

        # Show markers at start, middle, and end of visible window
        start = f"{start_km:.1f}" if start_km >= 0 else "0.0"
        middle = f"{(start_km + end_km) / 2:.1f}"
        end = f"{end_km:.1f}km"

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
