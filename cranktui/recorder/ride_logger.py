"""Ride data logger for saving ride metrics to CSV files."""

import asyncio
import csv
from datetime import datetime
from pathlib import Path
from typing import TextIO

from cranktui.routes.route import Route
from cranktui.state.state import RideState


class RideLogger:
    """Logs ride data to CSV files."""

    def __init__(self, route: Route, state: RideState):
        """Initialize ride logger.

        Args:
            route: The route being ridden
            state: The global ride state
        """
        self.route = route
        self.state = state
        self.csv_file: TextIO | None = None
        self.csv_writer: csv.DictWriter | None = None
        self.log_task: asyncio.Task | None = None
        self.rides_dir = Path.home() / ".local" / "share" / "cranktui" / "rides"
        self.current_filepath: Path | None = None
        self.paused: bool = False

    async def start_recording(self) -> str:
        """Start recording ride data.

        Returns:
            Path to the CSV file being created
        """
        # Create rides directory if it doesn't exist
        self.rides_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename: YYYY-MM-DD_HHMMSS_routename.csv
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        # Sanitize route name for filename
        safe_route_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in self.route.name)
        safe_route_name = safe_route_name.replace(' ', '_')
        filename = f"{timestamp}_{safe_route_name}.csv"
        filepath = self.rides_dir / filename
        self.current_filepath = filepath

        # Open CSV file for writing
        self.csv_file = open(filepath, 'w', newline='')

        # Define CSV columns
        fieldnames = [
            'timestamp',
            'elapsed_time_s',
            'distance_m',
            'speed_kmh',
            'power_w',
            'cadence_rpm',
            'heart_rate_bpm',
            'grade_pct',
            'mode',
            'resistance_scale',
        ]

        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=fieldnames)
        self.csv_writer.writeheader()
        self.csv_file.flush()

        # Update state to recording
        await self.state.update_metrics(is_recording=True)

        # Start background logging task
        self.log_task = asyncio.create_task(self._log_loop())

        return str(filepath)

    async def stop_recording(self) -> None:
        """Stop recording ride data."""
        # Update state
        await self.state.update_metrics(is_recording=False)

        # Cancel background task
        if self.log_task is not None:
            self.log_task.cancel()
            try:
                await self.log_task
            except asyncio.CancelledError:
                pass
            self.log_task = None

        # Close CSV file
        if self.csv_file is not None:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None

    def pause(self) -> None:
        """Pause logging (don't write new data points)."""
        self.paused = True

    def resume(self) -> None:
        """Resume logging."""
        self.paused = False

    def discard_ride(self) -> None:
        """Delete the current ride file.

        Should be called after stop_recording() if user chooses to discard.
        """
        if self.current_filepath and self.current_filepath.exists():
            self.current_filepath.unlink()
            self.current_filepath = None

    async def _log_loop(self) -> None:
        """Background task that logs data every second."""
        try:
            while True:
                await self._log_data_point()
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            # Final log before stopping
            await self._log_data_point()
            raise

    async def _log_data_point(self) -> None:
        """Log a single data point to the CSV file."""
        if self.csv_writer is None or self.csv_file is None:
            return

        # Skip logging if paused
        if self.paused:
            return

        # Get current metrics
        metrics = await self.state.get_metrics()

        # Create data row
        row = {
            'timestamp': datetime.now().isoformat(),
            'elapsed_time_s': metrics.elapsed_time_s,
            'distance_m': metrics.distance_m,
            'speed_kmh': metrics.speed_kmh,
            'power_w': metrics.power_w,
            'cadence_rpm': metrics.cadence_rpm,
            'heart_rate_bpm': metrics.heart_rate_bpm,
            'grade_pct': metrics.grade_pct,
            'mode': metrics.mode,
            'resistance_scale': metrics.resistance_scale,
        }

        # Write row to CSV
        self.csv_writer.writerow(row)
        self.csv_file.flush()
