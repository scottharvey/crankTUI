"""Physics-based calculations for cycling speed and power."""

import math


# Physical constants
GRAVITY = 9.81  # m/s²
AIR_DENSITY = 1.225  # kg/m³ at sea level, 15°C
ROLLING_RESISTANCE = 0.004  # Typical for road bike on smooth asphalt
DRAG_COEFFICIENT_AREA = 0.3  # m² - CdA for road position


def power_to_speed(power_w: float, grade_pct: float, total_mass_kg: float) -> float:
    """Calculate speed from power output using physics.

    Uses iterative solver to find speed that satisfies the power equation:
    Power = (gravity + rolling + air resistance) forces × speed

    Args:
        power_w: Power output in watts
        grade_pct: Grade as percentage (5% = 5.0)
        total_mass_kg: Combined rider + bike mass in kg

    Returns:
        Speed in m/s
    """
    if power_w <= 0:
        return 0.0

    # Convert grade percentage to decimal slope
    grade = grade_pct / 100.0

    # Initial guess for speed (m/s)
    speed = 5.0  # Start with ~18 km/h

    # Newton's method to solve: power = force × speed
    # We need to find speed where: power_w = total_force(speed) × speed
    for _ in range(20):  # Max 20 iterations
        # Calculate forces at current speed
        force_gravity = total_mass_kg * GRAVITY * grade
        force_rolling = ROLLING_RESISTANCE * total_mass_kg * GRAVITY
        force_air = 0.5 * DRAG_COEFFICIENT_AREA * AIR_DENSITY * speed * speed

        total_force = force_gravity + force_rolling + force_air

        # Power equation: P = F × v
        power_calculated = total_force * speed

        # Error in power
        power_error = power_calculated - power_w

        # If close enough, we're done
        if abs(power_error) < 0.1:
            break

        # Derivative of power with respect to speed
        # dP/dv = F + v × dF/dv
        # dF/dv = d(0.5 × Cd × A × rho × v²)/dv = Cd × A × rho × v
        dforce_dspeed = AIR_DENSITY * DRAG_COEFFICIENT_AREA * speed
        dpower_dspeed = total_force + speed * dforce_dspeed

        # Newton's method update
        if abs(dpower_dspeed) > 0.01:
            speed = speed - power_error / dpower_dspeed

        # Clamp speed to reasonable range
        speed = max(0.1, min(speed, 30.0))  # 0.36 to 108 km/h

    return max(0.0, speed)


def power_to_speed_kmh(power_w: float, grade_pct: float, total_mass_kg: float) -> float:
    """Calculate speed from power output in km/h.

    Args:
        power_w: Power output in watts
        grade_pct: Grade as percentage (5% = 5.0)
        total_mass_kg: Combined rider + bike mass in kg

    Returns:
        Speed in km/h
    """
    speed_ms = power_to_speed(power_w, grade_pct, total_mass_kg)
    return speed_ms * 3.6


def speed_sanity_check(speed_kmh: float, power_w: float) -> float:
    """Apply sanity check to speed calculation.

    Ensures speed is within reasonable bounds for given power.

    Args:
        speed_kmh: Calculated speed in km/h
        power_w: Power output in watts

    Returns:
        Adjusted speed in km/h
    """
    # Absolute limits
    if speed_kmh < 0:
        return 0.0
    if speed_kmh > 80:  # ~80 km/h max for indoor trainer
        return 80.0

    # Power-based sanity checks
    if power_w < 50 and speed_kmh > 20:
        # Very low power shouldn't give high speed
        return 20.0
    if power_w > 500 and speed_kmh < 20:
        # Very high power shouldn't give low speed on reasonable grade
        return 20.0

    return speed_kmh
