"""Stats panel widget for displaying live ride metrics."""

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Static

from cranktui.state.state import RideMetrics, get_state


class StatsPanel(Widget):
    """Widget that displays live ride statistics."""

    # Reactive properties that trigger re-render
    metrics: reactive[RideMetrics | None] = reactive(None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.state = get_state()

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Static(id="stats-content")

    def on_mount(self) -> None:
        """Handle mount - start update timer."""
        self.set_interval(0.2, self.update_stats)  # Update 5 times per second

    async def update_stats(self) -> None:
        """Fetch latest metrics from state and update display."""
        self.metrics = await self.state.get_metrics()

    def watch_metrics(self, metrics: RideMetrics | None) -> None:
        """Called when metrics change - update the display."""
        if metrics is None:
            return

        stats_widget = self.query_one("#stats-content", Static)

        # Format time as MM:SS
        minutes = int(metrics.elapsed_time_s // 60)
        seconds = int(metrics.elapsed_time_s % 60)
        time_str = f"{minutes:02d}:{seconds:02d}"

        # Format distance
        distance_km = metrics.distance_m / 1000
        distance_str = f"{distance_km:.2f} km"

        # Format stats
        content = "\n".join([
            f"Mode: {metrics.mode}",
            "",
            f"Time: {time_str}",
            f"Distance: {distance_str}",
            "",
            f"Speed: {metrics.speed_kmh:.1f} km/h",
            f"Power: {metrics.power_w:.0f} W",
            f"Cadence: {metrics.cadence_rpm:.0f} rpm",
            f"Grade: {metrics.grade_pct:+.1f}%",
        ])

        if metrics.heart_rate_bpm > 0:
            content += f"\nHeart Rate: {metrics.heart_rate_bpm:.0f} bpm"

        if metrics.is_recording:
            content += "\n\n● Recording"

        stats_widget.update(content)
