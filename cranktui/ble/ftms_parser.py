"""FTMS protocol parser for trainer data.

This will be implemented in Step 8, but we create the stub now.
"""


def parse_indoor_bike_data(data: bytes) -> dict:
    """Parse Indoor Bike Data characteristic (0x2AD2).

    Args:
        data: Raw bytes from the characteristic

    Returns:
        Dictionary with parsed values (speed, cadence, power, etc.)
    """
    # Stub implementation for now
    # Will be fully implemented in Step 8
    return {
        "speed_kmh": 0.0,
        "cadence_rpm": 0.0,
        "power_w": 0.0,
        "distance_m": 0.0,
    }
