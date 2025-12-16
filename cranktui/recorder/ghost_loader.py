"""Ghost ride loader for racing against previous rides."""

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GhostDataPoint:
    """Single data point from a ghost ride."""
    elapsed_time_s: float
    distance_m: float


class GhostRide:
    """Represents a previous ride that can be used as a ghost."""

    def __init__(self, filepath: Path, data_points: list[GhostDataPoint]):
        """Initialize ghost ride.

        Args:
            filepath: Path to the CSV file
            data_points: List of time/distance data points
        """
        self.filepath = filepath
        self.data_points = data_points
        # Sort by elapsed time to ensure proper ordering
        self.data_points.sort(key=lambda p: p.elapsed_time_s)

    @property
    def total_time(self) -> float:
        """Get total ride time in seconds."""
        if not self.data_points:
            return 0.0
        return self.data_points[-1].elapsed_time_s

    @property
    def total_distance(self) -> float:
        """Get total distance in meters."""
        if not self.data_points:
            return 0.0
        return self.data_points[-1].distance_m

    def get_distance_at_time(self, elapsed_time_s: float) -> float:
        """Get ghost's distance at a specific elapsed time using linear interpolation.

        Args:
            elapsed_time_s: Time in seconds since ride start

        Returns:
            Distance in meters at that time
        """
        if not self.data_points:
            return 0.0

        # Before ride starts
        if elapsed_time_s <= 0:
            return 0.0

        # After ride ends - return final distance
        if elapsed_time_s >= self.data_points[-1].elapsed_time_s:
            return self.data_points[-1].distance_m

        # Find the two points to interpolate between
        for i in range(len(self.data_points) - 1):
            p1 = self.data_points[i]
            p2 = self.data_points[i + 1]

            if p1.elapsed_time_s <= elapsed_time_s <= p2.elapsed_time_s:
                # Linear interpolation
                time_diff = p2.elapsed_time_s - p1.elapsed_time_s
                if time_diff == 0:
                    return p1.distance_m

                ratio = (elapsed_time_s - p1.elapsed_time_s) / time_diff
                distance = p1.distance_m + ratio * (p2.distance_m - p1.distance_m)
                return distance

        # Shouldn't get here, but return last distance as fallback
        return self.data_points[-1].distance_m


def load_ghost_ride(csv_path: Path) -> GhostRide | None:
    """Load a ghost ride from a CSV file.

    Args:
        csv_path: Path to the CSV file

    Returns:
        GhostRide object or None if loading failed
    """
    try:
        data_points = []

        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    elapsed_time_s = float(row['elapsed_time_s'])
                    distance_m = float(row['distance_m'])
                    data_points.append(GhostDataPoint(elapsed_time_s, distance_m))
                except (KeyError, ValueError):
                    # Skip invalid rows
                    continue

        if not data_points:
            return None

        return GhostRide(csv_path, data_points)

    except Exception:
        return None


def load_all_ghosts(route_name: str) -> list[tuple[Path, GhostRide]]:
    """Load all valid ghost rides for a route, sorted by fastest first.

    Args:
        route_name: Name of the route (used in CSV filename)

    Returns:
        List of (filepath, GhostRide) tuples, sorted by total_time ascending (fastest first)
    """
    rides_dir = Path.home() / ".local" / "share" / "cranktui" / "rides"

    if not rides_dir.exists():
        return []

    # Sanitize route name to match filename format
    safe_route_name = "".join(c if c.isalnum() or c in (' ', '-', '_') else '_' for c in route_name)
    safe_route_name = safe_route_name.replace(' ', '_')

    # Find all CSV files for this route
    pattern = f"*_{safe_route_name}.csv"
    matching_files = list(rides_dir.glob(pattern))

    if not matching_files:
        return []

    # Load all valid rides
    # Only consider rides with at least 5 seconds of data and some distance traveled
    valid_ghosts = []

    for csv_path in matching_files:
        ghost = load_ghost_ride(csv_path)
        if ghost and ghost.total_time > 5.0 and ghost.total_distance > 10.0:
            valid_ghosts.append((csv_path, ghost))

    # Sort by total_time (fastest first)
    valid_ghosts.sort(key=lambda x: x[1].total_time)

    return valid_ghosts


def find_fastest_ghost(route_name: str) -> GhostRide | None:
    """Find the fastest previous ride for a given route.

    Args:
        route_name: Name of the route (used in CSV filename)

    Returns:
        GhostRide object of the fastest ride, or None if no rides found
    """
    all_ghosts = load_all_ghosts(route_name)
    if not all_ghosts:
        return None

    # Return the fastest (first in sorted list)
    return all_ghosts[0][1]
