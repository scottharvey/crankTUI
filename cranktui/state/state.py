"""Shared state container for live metrics."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RideMetrics:
    """Live ride metrics."""

    # Current values
    speed_kmh: float = 0.0
    power_w: float = 0.0
    cadence_rpm: float = 0.0
    heart_rate_bpm: float = 0.0
    distance_m: float = 0.0
    elapsed_time_s: float = 0.0
    grade_pct: float = 0.0

    # Session info
    start_time: datetime | None = None
    is_recording: bool = False
    mode: str = "DEMO"  # "DEMO", "LIVE", "ERG", or "SIM"


class RideState:
    """Thread-safe container for ride state."""

    def __init__(self):
        self._metrics = RideMetrics()
        self._lock = asyncio.Lock()

    async def get_metrics(self) -> RideMetrics:
        """Get a copy of current metrics."""
        async with self._lock:
            # Return a copy to avoid race conditions
            return RideMetrics(
                speed_kmh=self._metrics.speed_kmh,
                power_w=self._metrics.power_w,
                cadence_rpm=self._metrics.cadence_rpm,
                heart_rate_bpm=self._metrics.heart_rate_bpm,
                distance_m=self._metrics.distance_m,
                elapsed_time_s=self._metrics.elapsed_time_s,
                grade_pct=self._metrics.grade_pct,
                start_time=self._metrics.start_time,
                is_recording=self._metrics.is_recording,
                mode=self._metrics.mode,
            )

    async def update_metrics(self, **kwargs) -> None:
        """Update one or more metrics.

        Args:
            **kwargs: Metric name and value pairs to update
        """
        async with self._lock:
            for key, value in kwargs.items():
                if hasattr(self._metrics, key):
                    setattr(self._metrics, key, value)

    async def reset(self) -> None:
        """Reset all metrics to initial state."""
        async with self._lock:
            self._metrics = RideMetrics()


# Global state instance
_global_state: RideState | None = None


def get_state() -> RideState:
    """Get the global ride state instance."""
    global _global_state
    if _global_state is None:
        _global_state = RideState()
    return _global_state
