"""Elevation chart visualization using braille characters."""

from rich.console import RenderableType
from rich.text import Text
from textual.widget import Widget


class ElevationChart(Widget):
    """Widget that renders an elevation profile using braille characters."""

    # Braille patterns for different fill levels (0-4 dots vertical)
    # Unicode braille patterns use dots 1-8, we use dots on the left column (1,2,3,4)
    BRAILLE_LEVELS = [
        " ",      # 0 dots - empty
        "⠈",      # 1 dot  - top
        "⠘",      # 2 dots - top + middle-top
        "⠸",      # 3 dots - top + middle-top + middle-bottom
        "⣸",      # 4 dots - all dots (filled)
    ]

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

    def render(self) -> RenderableType:
        """Render the elevation chart using braille characters."""
        width = self.size.width
        height = self.size.height

        if width == 0 or height == 0:
            return Text("")

        # Map elevation data to available width
        elevations = self._resample_to_width(width)

        # Normalize elevations to fit height (multiply by 4 for braille resolution)
        min_elev = min(elevations)
        max_elev = max(elevations)
        elev_range = max_elev - min_elev

        if elev_range == 0:
            elev_range = 1

        # Convert elevations to pixel heights (height * 4 for braille resolution)
        pixel_height = height * 4
        normalized_heights = []
        for elev in elevations:
            pixel_h = int(((elev - min_elev) / elev_range) * pixel_height)
            normalized_heights.append(pixel_h)

        # Build the chart from top to bottom
        lines = []
        for y in range(height):
            line = ""
            for x, pixel_h in enumerate(normalized_heights):
                # Calculate which braille level to use for this position
                # Each character row represents 4 vertical pixels
                row_bottom = (height - y - 1) * 4
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

        # Join all lines with white color
        chart_text = Text("\n".join(lines), style="white")
        return chart_text

    def _resample_to_width(self, width: int) -> list[float]:
        """Resample elevation data to fit the given width."""
        if len(self.elevations) <= width:
            # Pad with last value if needed
            return self.elevations + [self.elevations[-1]] * (width - len(self.elevations))

        # Downsample by taking evenly spaced points
        indices = [int(i * len(self.elevations) / width) for i in range(width)]
        return [self.elevations[i] for i in indices]
