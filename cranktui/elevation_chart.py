"""Elevation chart visualization using braille characters."""

from textual.widget import Widget
from rich.segment import Segment
from rich.style import Style


class ElevationChart(Widget):
    """Widget that renders an elevation profile using braille characters."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Static sample elevation data (representing a hilly route)
        self.elevations = [
            100, 105, 110, 120, 135, 150, 160, 165, 170, 172, 170, 165, 155,
            140, 125, 115, 110, 108, 105, 103, 102, 100, 98, 95, 93, 92, 90,
            88, 87, 85, 84, 85, 88, 92, 98, 105, 115, 125, 140, 155, 170, 180,
            185, 188, 190, 189, 186, 180, 172, 165, 155, 145, 135, 125, 115,
            110, 108, 107, 106, 105, 104, 103, 102, 101, 100,
        ]

    def render_line(self, y: int) -> list[Segment]:
        """Render a single line of the elevation chart."""
        width = self.size.width
        height = self.size.height

        if width == 0 or height == 0:
            return []

        # Map elevation data to available width
        elevations = self._resample_to_width(width)

        # Normalize elevations to fit height
        min_elev = min(elevations)
        max_elev = max(elevations)
        elev_range = max_elev - min_elev

        if elev_range == 0:
            elev_range = 1

        # Calculate which elevations should be filled at this y position
        # (y=0 is top of widget, so we need to invert)
        threshold = max_elev - (y / height) * elev_range

        segments = []
        for elev in elevations:
            if elev >= threshold:
                segments.append(Segment("█", Style(color="green")))
            else:
                segments.append(Segment(" "))

        return segments

    def _resample_to_width(self, width: int) -> list[float]:
        """Resample elevation data to fit the given width."""
        if len(self.elevations) <= width:
            # Pad with last value if needed
            return self.elevations + [self.elevations[-1]] * (width - len(self.elevations))

        # Downsample by taking evenly spaced points
        indices = [int(i * len(self.elevations) / width) for i in range(width)]
        return [self.elevations[i] for i in indices]

    def render(self):
        """Render the elevation chart."""
        return self.render_line
