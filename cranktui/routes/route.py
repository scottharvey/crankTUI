"""Route data model."""

from dataclasses import dataclass


@dataclass
class RoutePoint:
    """A single point on a route."""
    distance_m: float
    elevation_m: float


@dataclass
class Route:
    """A cycling route with elevation profile."""
    name: str
    description: str
    distance_km: float
    points: list[RoutePoint]

    @property
    def total_distance_m(self) -> float:
        """Get total distance in meters."""
        return self.distance_km * 1000

    def get_elevation_at_distance(self, distance_m: float) -> float:
        """Get interpolated elevation at a given distance."""
        if not self.points:
            return 0.0

        # Before first point
        if distance_m <= self.points[0].distance_m:
            return self.points[0].elevation_m

        # After last point
        if distance_m >= self.points[-1].distance_m:
            return self.points[-1].elevation_m

        # Find surrounding points and interpolate
        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]

            if p1.distance_m <= distance_m <= p2.distance_m:
                # Linear interpolation
                ratio = (distance_m - p1.distance_m) / (p2.distance_m - p1.distance_m)
                return p1.elevation_m + ratio * (p2.elevation_m - p1.elevation_m)

        return self.points[-1].elevation_m
