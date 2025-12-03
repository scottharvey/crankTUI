"""Route resampling utilities."""

from cranktui.routes.route import Route, RoutePoint


def resample_route(route: Route, num_points: int) -> list[RoutePoint]:
    """
    Resample a route to have a specific number of evenly-spaced points.

    Args:
        route: The route to resample
        num_points: The desired number of points

    Returns:
        List of resampled route points with even distance spacing
    """
    if not route.points or num_points < 2:
        return route.points

    total_distance = route.total_distance_m
    distance_step = total_distance / (num_points - 1)

    resampled = []
    for i in range(num_points):
        distance_m = i * distance_step
        elevation_m = route.get_elevation_at_distance(distance_m)
        resampled.append(RoutePoint(distance_m=distance_m, elevation_m=elevation_m))

    return resampled


def get_elevation_range(points: list[RoutePoint]) -> tuple[float, float]:
    """
    Get the minimum and maximum elevation from a list of points.

    Args:
        points: List of route points

    Returns:
        Tuple of (min_elevation, max_elevation)
    """
    if not points:
        return (0.0, 0.0)

    elevations = [p.elevation_m for p in points]
    return (min(elevations), max(elevations))
