"""Riding screen for active training session."""

import asyncio

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen, ModalScreen
from textual.widgets import Button, Footer, Header, Label, Static

from cranktui.routes.route import Route
from cranktui.screens.devices import DevicesScreen
from cranktui.simulation.simulator import DemoSimulator
from cranktui.state.state import get_state
from cranktui.widgets.elevation_chart import ElevationChart
from cranktui.widgets.minimap import MinimapWidget
from cranktui.widgets.stats_panel import StatsPanel


class HelpModal(ModalScreen):
    """Modal screen showing keyboard shortcuts."""

    BINDINGS = [
        ("escape", "dismiss", "Close"),
        ("h", "dismiss", "Close"),
    ]

    CSS = """
    HelpModal {
        align: center middle;
    }

    #help-dialog {
        width: 40%;
        height: auto;
        max-height: 90%;
        border: round white;
        background: $surface;
        padding: 1;
    }

    #header {
        width: 100%;
        height: auto;
        content-align: center middle;
        padding-bottom: 1;
        border-bottom: solid white;
    }

    #help-content {
        width: 100%;
        height: auto;
        padding: 1 2;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1;
    }

    Button {
        margin: 0 1;
        background: transparent;
        border: round $surface;
        color: white;
    }

    Button:focus {
        border: round white;
    }
    """

    def compose(self) -> ComposeResult:
        """Create the help dialog."""
        with Container(id="help-dialog"):
            yield Label("Keyboard Shortcuts", id="header")
            yield Static(self._build_help_text(), id="help-content")
            with Horizontal(id="buttons"):
                yield Button("Close", id="close-btn")
        yield Footer()

    def on_button_pressed(self, event) -> None:
        """Handle button press."""
        self.dismiss()

    def _build_help_text(self) -> str:
        """Build the help text content."""
        return """
Navigation
  ESC         Go Back
  d           Open Devices Screen
  h           Show this help

Mode Control
  m           Toggle Mode (DEMO → LIVE → SIM)
              DEMO: Simulated ride data
              LIVE: Manual control with trainer
              SIM:  Automatic grade-following

Manual Resistance (LIVE mode)
  1, 2, 3     Resistance level (Low/Med/High)
  e           ERG mode - constant 200W
  6           Flat (0% gradient)
  7           Gentle climb (3%)
  8           Medium climb (7%)
  9           Steep climb (12%)
"""


class RidingScreen(Screen):
    """Main riding screen with elevation profile and stats."""

    BINDINGS = [
        ("escape", "request_back", "Back"),
        ("d", "show_devices", "Devices"),
        ("m", "toggle_mode", "Mode"),
        ("h", "show_help", "Help"),
        # Hidden bindings - functional but not shown in footer
        Binding("1", "test_resistance_low", "Test: Low Resistance", show=False),
        Binding("2", "test_resistance_med", "Test: Med Resistance", show=False),
        Binding("3", "test_resistance_high", "Test: High Resistance", show=False),
        Binding("e", "test_erg_mode", "Test: ERG 200W", show=False),
        Binding("6", "test_gradient_flat", "Test: Flat (0%)", show=False),
        Binding("7", "test_gradient_gentle", "Test: Gentle (3%)", show=False),
        Binding("8", "test_gradient_medium", "Test: Medium (7%)", show=False),
        Binding("9", "test_gradient_steep", "Test: Steep (12%)", show=False),
    ]

    CSS = """
    RidingScreen {
        layout: vertical;
    }

    #main-container {
        layout: horizontal;
        height: 1fr;
    }

    #elevation-panel {
        width: 2fr;
        border: round white;
        padding: 1;
    }

    #stats-panel {
        width: 1fr;
        layout: vertical;
    }

    #route-info {
        height: auto;
        border: round white;
        padding: 1;
        margin-bottom: 1;
    }

    StatsPanel {
        height: auto;
        border: round white;
        padding: 1;
        margin-bottom: 1;
    }

    #minimap-panel {
        height: 10;
        border: round white;
        padding: 1;
    }
    """

    def __init__(self, route: Route, **kwargs):
        super().__init__(**kwargs)
        self.route = route
        self.simulator = DemoSimulator(route)
        self.state = get_state()
        self.sim_task: asyncio.Task | None = None
        self.last_gradient: float = 0.0  # For smoothing
        self.target_gradient: float = 0.0  # For smoothing

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        yield Header(show_clock=True)
        with Container(id="main-container"):
            yield ElevationChart(route=self.route, id="elevation-panel")
            with Container(id="stats-panel"):
                yield Static(
                    f"{self.route.name}\n{self.route.distance_km} km",
                    id="route-info"
                )
                yield StatsPanel()
                yield MinimapWidget(route=self.route, id="minimap-panel")
        yield Footer()

    async def on_mount(self) -> None:
        """Handle mount - start simulation only if in demo mode."""
        from datetime import datetime
        from cranktui.app import DEMO_MODE

        ble_client = await self.state.get_ble_client()

        # Set start time for the ride
        await self.state.update_metrics(start_time=datetime.now())

        # Start demo simulator if --demo flag was passed OR no BLE device connected
        if DEMO_MODE or not ble_client or not ble_client.is_connected:
            await self.state.update_metrics(mode="DEMO")
            await self.simulator.start()
        else:
            await self.state.update_metrics(mode="LIVE")

    async def on_unmount(self) -> None:
        """Handle unmount - stop simulation and reset state."""
        await self.simulator.stop()
        await self._stop_sim_mode()
        # Reset state for next ride (but keep BLE client)
        ble_client = await self.state.get_ble_client()
        await self.state.reset()
        await self.state.update_ble_client(ble_client)

    def action_request_back(self) -> None:
        """Request to go back - will trigger confirmation in main app."""
        self.dismiss()

    def action_show_devices(self) -> None:
        """Show the devices screen."""
        self.app.push_screen(DevicesScreen())

    def action_show_help(self) -> None:
        """Show the help modal."""
        self.app.push_screen(HelpModal())

    def action_toggle_mode(self) -> None:
        """Toggle between Demo and Live modes."""
        self.run_worker(self._toggle_mode())

    async def _toggle_mode(self) -> None:
        """Async toggle mode implementation.

        Cycles through modes: DEMO → LIVE → SIM → DEMO
        """
        from cranktui.app import DEMO_MODE

        # Can't toggle if --demo flag was passed
        if DEMO_MODE:
            self.notify("Started with --demo flag, cannot toggle modes")
            return

        metrics = await self.state.get_metrics()
        ble_client = await self.state.get_ble_client()

        if metrics.mode == "DEMO":
            # Try to switch to LIVE mode
            if ble_client and ble_client.is_connected:
                # Stop demo simulator
                await self.simulator.stop()
                await self.state.update_metrics(mode="LIVE")
                self.notify("Switched to LIVE mode (manual control)")
            else:
                self.notify("No device connected - cannot switch modes")
        elif metrics.mode == "LIVE":
            # Switch to SIM mode (automatic grade-following)
            if ble_client and ble_client.is_connected:
                await self._start_sim_mode()
                self.notify("Switched to SIM mode (auto grade-following)")
            else:
                self.notify("No device connected")
        elif metrics.mode == "SIM":
            # Switch back to DEMO mode
            await self._stop_sim_mode()
            await self.state.update_metrics(mode="DEMO")
            await self.simulator.start()
            self.notify("Switched to DEMO mode")
        else:
            # Unknown mode, reset to DEMO
            await self._stop_sim_mode()
            await self.state.update_metrics(mode="DEMO")
            await self.simulator.start()
            self.notify("Switched to DEMO mode")

    def action_test_resistance_low(self) -> None:
        """Test setting low resistance (20%)."""
        self.run_worker(self._test_resistance(20))

    def action_test_resistance_med(self) -> None:
        """Test setting medium resistance (50%)."""
        self.run_worker(self._test_resistance(50))

    def action_test_resistance_high(self) -> None:
        """Test setting high resistance (80%)."""
        self.run_worker(self._test_resistance(80))

    def action_test_erg_mode(self) -> None:
        """Test setting ERG mode to 200W."""
        self.run_worker(self._test_erg(200))

    def action_test_gradient_flat(self) -> None:
        """Test setting gradient to flat (0%)."""
        self.run_worker(self._test_gradient(0.0))

    def action_test_gradient_gentle(self) -> None:
        """Test setting gradient to gentle climb (3%)."""
        self.run_worker(self._test_gradient(3.0))

    def action_test_gradient_medium(self) -> None:
        """Test setting gradient to medium climb (7%)."""
        self.run_worker(self._test_gradient(7.0))

    def action_test_gradient_steep(self) -> None:
        """Test setting gradient to steep climb (12%)."""
        self.run_worker(self._test_gradient(12.0))

    async def _test_resistance(self, level: int) -> None:
        """Test resistance command."""
        ble_client = await self.state.get_ble_client()
        if not ble_client or not ble_client.is_connected:
            self.notify("No device connected")
            return

        success = await ble_client.set_resistance_level(level)
        if success:
            self.notify(f"Resistance set to {level}%")
        else:
            self.notify(f"Command failed")

    async def _test_erg(self, power: int) -> None:
        """Test ERG mode command."""
        ble_client = await self.state.get_ble_client()
        if not ble_client or not ble_client.is_connected:
            self.notify("No device connected")
            return

        success = await ble_client.set_erg_mode(power)
        if success:
            self.notify(f"ERG mode: {power}W")
        else:
            self.notify(f"Command failed")

    async def _test_gradient(self, grade_percent: float) -> None:
        """Test gradient/SIM mode command."""
        ble_client = await self.state.get_ble_client()
        if not ble_client or not ble_client.is_connected:
            self.notify("No device connected")
            return

        success = await ble_client.set_gradient(grade_percent)
        if success:
            self.notify(f"Gradient: {grade_percent:.1f}%")
        else:
            self.notify(f"Command failed")

    def _calculate_grade(self, distance_m: float) -> float:
        """Calculate grade percentage at given distance.

        Uses 100m lookahead for realistic grade calculation.

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

    def _smooth_gradient(self, target: float, current: float, max_change: float = 1.0) -> float:
        """Smooth gradient changes to avoid jarring resistance shifts.

        Args:
            target: Target gradient percentage
            current: Current gradient percentage
            max_change: Maximum change per update (default 1% per 2 seconds)

        Returns:
            Smoothed gradient value
        """
        diff = target - current
        if abs(diff) <= max_change:
            return target
        elif diff > 0:
            return current + max_change
        else:
            return current - max_change

    async def _start_sim_mode(self) -> None:
        """Start SIM mode - automatic grade-based resistance control."""
        from cranktui.ble.client import debug_log
        from cranktui.config import get_bike_weight_kg, get_rider_weight_kg

        if self.sim_task is not None:
            return  # Already running

        # Send rider characteristics to trainer for realistic simulation
        ble_client = await self.state.get_ble_client()
        if ble_client and ble_client.is_connected:
            total_weight = get_rider_weight_kg() + get_bike_weight_kg()
            debug_log(f"Starting SIM mode, sending rider characteristics: {total_weight:.1f}kg")
            await ble_client.set_rider_characteristics(total_weight)

        self.last_gradient = 0.0
        self.target_gradient = 0.0
        # Set mode BEFORE starting task to avoid race condition
        await self.state.update_metrics(mode="SIM")
        self.sim_task = asyncio.create_task(self._sim_mode_loop())

    async def _stop_sim_mode(self) -> None:
        """Stop SIM mode background task."""
        if self.sim_task is not None:
            self.sim_task.cancel()
            try:
                await self.sim_task
            except asyncio.CancelledError:
                pass
            self.sim_task = None

    async def _sim_mode_loop(self) -> None:
        """Background task that updates gradient every 2 seconds based on route position."""
        from cranktui.ble.client import debug_log

        try:
            while True:
                # Get current distance from state
                metrics = await self.state.get_metrics()
                distance_m = metrics.distance_m
                speed_kmh = metrics.speed_kmh
                power_w = metrics.power_w

                # Check if mode is still SIM
                if metrics.mode != "SIM":
                    break

                # Calculate grade at current position
                target_grade = self._calculate_grade(distance_m)
                self.target_gradient = target_grade

                # Get elevation data for logging
                current_elevation = self.route.get_elevation_at_distance(distance_m)

                # Smooth the transition
                smoothed_grade = self._smooth_gradient(
                    target=self.target_gradient,
                    current=self.last_gradient,
                    max_change=1.0  # Max 1% change per 2 seconds
                )
                self.last_gradient = smoothed_grade

                # Calculate expected power for comparison
                from cranktui.config import get_bike_weight_kg, get_rider_weight_kg
                total_weight = get_rider_weight_kg() + get_bike_weight_kg()
                speed_ms = speed_kmh / 3.6
                gravity_power = total_weight * 9.8 * (smoothed_grade / 100.0) * speed_ms if speed_ms > 0 else 0

                # Log current state
                debug_log(f"SIM: dist={distance_m:.0f}m, elev={current_elevation:.1f}m, grade_target={target_grade:.2f}%, grade_smooth={smoothed_grade:.2f}%, speed={speed_kmh:.1f}km/h, power={power_w:.0f}W (gravity_only={gravity_power:.0f}W, weight={total_weight:.0f}kg)")

                # Send to trainer
                ble_client = await self.state.get_ble_client()
                if ble_client and ble_client.is_connected:
                    await ble_client.set_gradient(smoothed_grade)
                    # Also update state for display - preserve mode!
                    await self.state.update_metrics(grade_pct=smoothed_grade, mode="SIM")

                # Wait 2 seconds before next update
                await asyncio.sleep(2.0)

        except asyncio.CancelledError:
            pass
