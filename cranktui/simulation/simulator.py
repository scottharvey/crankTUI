"""Fake simulation loop for demo mode."""

import asyncio
import math
import time
from datetime import datetime

from cranktui.routes.route import Route
from cranktui.state.state import get_state


class DemoSimulator:
    """Simulates ride data for demo mode."""

    def __init__(self, route: Route):
        self.route = route
        self.state = get_state()
        self.running = False
        self.task: asyncio.Task | None = None
        self.start_time: float | None = None

    async def start(self) -> None:
        """Start the simulation loop."""
        if self.running:
            return

        self.running = True
        self.start_time = time.time()

        # Initialize state
        await self.state.update_metrics(
            mode="DEMO",
            start_time=datetime.now(),
        )

        # Start background task
        self.task = asyncio.create_task(self._simulation_loop())

    async def stop(self) -> None:
        """Stop the simulation loop."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
            self.task = None

    async def _simulation_loop(self) -> None:
        """Main simulation loop - runs every 0.5 seconds."""
        try:
            while self.running:
                await self._update_metrics()
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    async def _update_metrics(self) -> None:
        """Update state with fake data."""
        if self.start_time is None:
            return

        # Calculate elapsed time
        elapsed = time.time() - self.start_time

        # Simulate speed: oscillates between 20-30 km/h
        base_speed = 25.0
        speed_variation = 5.0 * math.sin(elapsed * 0.3)
        speed_kmh = base_speed + speed_variation

        # Simulate power: oscillates between 150-250W
        base_power = 200.0
        power_variation = 50.0 * math.sin(elapsed * 0.5)
        power_w = base_power + power_variation

        # Simulate cadence: oscillates between 70-90 rpm
        base_cadence = 80.0
        cadence_variation = 10.0 * math.sin(elapsed * 0.4)
        cadence_rpm = base_cadence + cadence_variation

        # Calculate distance: integrate speed over time
        # Speed in m/s = km/h / 3.6
        # Distance increase = speed * time_interval
        speed_ms = speed_kmh / 3.6
        distance_increase = speed_ms * 0.5  # 0.5 second interval
        current_metrics = await self.state.get_metrics()
        distance_m = current_metrics.distance_m + distance_increase

        # Prevent distance from exceeding route length
        max_distance_m = self.route.distance_km * 1000
        if distance_m > max_distance_m:
            distance_m = max_distance_m

        # Calculate current grade from route
        grade_pct = self._calculate_grade(distance_m)

        # Update state
        await self.state.update_metrics(
            speed_kmh=speed_kmh,
            power_w=power_w,
            cadence_rpm=cadence_rpm,
            distance_m=distance_m,
            elapsed_time_s=elapsed,
            grade_pct=grade_pct,
        )

    def _calculate_grade(self, distance_m: float) -> float:
        """Calculate grade percentage at given distance.

        Args:
            distance_m: Current distance in meters

        Returns:
            Grade percentage (positive = uphill, negative = downhill)
        """
        if not self.route.points or len(self.route.points) < 2:
            return 0.0

        # Get elevation at current position
        current_elevation = self.route.get_elevation_at_distance(distance_m)

        # Look ahead 100m to calculate grade
        lookahead_distance = distance_m + 100.0
        max_distance = self.route.distance_km * 1000

        if lookahead_distance > max_distance:
            lookahead_distance = max_distance

        lookahead_elevation = self.route.get_elevation_at_distance(lookahead_distance)

        # Calculate grade percentage
        elevation_change = lookahead_elevation - current_elevation
        horizontal_distance = lookahead_distance - distance_m

        if horizontal_distance == 0:
            return 0.0

        grade = (elevation_change / horizontal_distance) * 100.0
        return grade
