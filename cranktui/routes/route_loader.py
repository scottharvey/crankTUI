"""Route loading from JSON files."""

import json
from pathlib import Path

from cranktui.routes.route import Route, RoutePoint


def get_routes_directory() -> Path:
    """Get the directory where routes are stored."""
    routes_dir = Path.home() / ".local" / "share" / "cranktui" / "routes"
    routes_dir.mkdir(parents=True, exist_ok=True)
    return routes_dir


def load_route_from_file(filepath: Path) -> Route:
    """Load a single route from a JSON file."""
    with open(filepath, "r") as f:
        data = json.load(f)

    points = [
        RoutePoint(distance_m=p["distance_m"], elevation_m=p["elevation_m"])
        for p in data["points"]
    ]

    return Route(
        name=data["name"],
        description=data["description"],
        distance_km=data["distance_km"],
        points=points,
    )


def load_all_routes() -> list[Route]:
    """Load all routes from the routes directory."""
    routes_dir = get_routes_directory()
    routes = []

    for filepath in sorted(routes_dir.glob("*.json")):
        try:
            route = load_route_from_file(filepath)
            routes.append(route)
        except (json.JSONDecodeError, KeyError, FileNotFoundError) as e:
            print(f"Warning: Failed to load route from {filepath}: {e}")
            continue

    # Sort routes by name for consistent ordering
    routes.sort(key=lambda r: r.name)
    return routes


def create_demo_routes():
    """Create demo routes if no routes exist."""
    routes_dir = get_routes_directory()

    # Check if any routes exist
    if list(routes_dir.glob("*.json")):
        return

    # Create a demo hilly route
    demo_route = {
        "name": "Demo Hills",
        "description": "A sample hilly route for testing",
        "distance_km": 10.0,
        "points": [
            {"distance_m": 0, "elevation_m": 100},
            {"distance_m": 1000, "elevation_m": 150},
            {"distance_m": 2000, "elevation_m": 180},
            {"distance_m": 3000, "elevation_m": 170},
            {"distance_m": 4000, "elevation_m": 140},
            {"distance_m": 5000, "elevation_m": 90},
            {"distance_m": 6000, "elevation_m": 85},
            {"distance_m": 7000, "elevation_m": 120},
            {"distance_m": 8000, "elevation_m": 160},
            {"distance_m": 9000, "elevation_m": 190},
            {"distance_m": 10000, "elevation_m": 180},
        ]
    }

    demo_flat = {
        "name": "Flat Road",
        "description": "Easy flat route for recovery",
        "distance_km": 5.0,
        "points": [
            {"distance_m": 0, "elevation_m": 100},
            {"distance_m": 1000, "elevation_m": 102},
            {"distance_m": 2000, "elevation_m": 101},
            {"distance_m": 3000, "elevation_m": 103},
            {"distance_m": 4000, "elevation_m": 100},
            {"distance_m": 5000, "elevation_m": 102},
        ]
    }

    # Write demo routes
    with open(routes_dir / "demo_hills.json", "w") as f:
        json.dump(demo_route, f, indent=2)

    with open(routes_dir / "flat_road.json", "w") as f:
        json.dump(demo_flat, f, indent=2)
