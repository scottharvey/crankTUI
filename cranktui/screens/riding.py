"""Riding screen for active training session."""

import asyncio
import time

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.screen import Screen, ModalScreen
from textual.widgets import Button, Footer, Header, Label, Static

from cranktui.recorder.ride_logger import RideLogger
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
        background: $background 60%;
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
Ride Control
  SPACE       Start ride / Pause ride
  ESC         Go Back
  d           Open Devices Screen
  h           Show this help

Mode Control (while riding)
  m           Toggle Mode (SIM → LIVE → DEMO)
              SIM:  Automatic grade-following (default)
              LIVE: Manual control with trainer
              DEMO: Simulated ride data

SIM Mode Resistance Scaling
  ↑           Increase resistance +10%
  ↓           Decrease resistance -10%
              Range: 30% to 200%

Manual Resistance (LIVE mode)
  1, 2, 3     Resistance level (Low/Med/High)
  e           ERG mode - constant 200W
  6           Flat (0% gradient)
  7           Gentle climb (3%)
  8           Medium climb (7%)
  9           Steep climb (12%)
"""


class PauseRideModal(ModalScreen[str]):
    """Modal dialog shown when ride is paused."""

    BINDINGS = [
        ("escape", "resume", "Resume"),
    ]

    CSS = """
    PauseRideModal {
        align: center middle;
    }

    #dialog {
        width: 60;
        height: 13;
        border: round white;
        background: $background 60%;
        padding: 1 2;
    }

    #question {
        width: 100%;
        height: auto;
        content-align: center middle;
        margin-bottom: 1;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
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
        """Create dialog widgets."""
        with Container(id="dialog"):
            yield Label("Ride Paused", id="question")
            with Horizontal(id="buttons"):
                yield Button("Continue", id="continue")
                yield Button("Save & Exit", id="save")
                yield Button("Exit (No Save)", id="discard")

    def on_mount(self) -> None:
        """Focus the Continue button by default."""
        self.query_one("#continue", Button).focus()

    def action_resume(self) -> None:
        """Resume riding (escape key)."""
        self.dismiss("continue")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "continue":
            self.dismiss("continue")
        elif event.button.id == "save":
            self.dismiss("save")
        elif event.button.id == "discard":
            self.dismiss("discard")


class RidingScreen(Screen):
    """Main riding screen with elevation profile and stats."""

    BINDINGS = [
        ("escape", "request_back", "Back"),
        ("d", "show_devices", "Devices"),
        ("m", "toggle_mode", "Mode"),
        ("h", "show_help", "Help"),
        ("space", "stop_ride", "Start/Pause"),
        # Hidden bindings - functional but not shown in footer
        Binding("1", "test_resistance_low", "Test: Low Resistance", show=False),
        Binding("2", "test_resistance_med", "Test: Med Resistance", show=False),
        Binding("3", "test_resistance_high", "Test: High Resistance", show=False),
        Binding("e", "test_erg_mode", "Test: ERG 200W", show=False),
        Binding("6", "test_gradient_flat", "Test: Flat (0%)", show=False),
        Binding("7", "test_gradient_gentle", "Test: Gentle (3%)", show=False),
        Binding("8", "test_gradient_medium", "Test: Medium (7%)", show=False),
        Binding("9", "test_gradient_steep", "Test: Steep (12%)", show=False),
        Binding("up", "increase_resistance", "Increase Resistance", show=False),
        Binding("down", "decrease_resistance", "Decrease Resistance", show=False),
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
        self.ride_logger = RideLogger(route, self.state)
        self.ride_state: str = "not_started"  # "not_started", "riding", "paused"

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
        """Handle mount - wait for user to start ride."""
        # Don't start anything yet - wait for user to press space
        pass

    async def on_unmount(self) -> None:
        """Handle unmount - stop simulation and reset state."""
        await self.simulator.stop()
        await self._stop_sim_mode()

        # Stop recording if still active
        metrics = await self.state.get_metrics()
        if metrics.is_recording:
            await self.ride_logger.stop_recording()

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

    def action_stop_ride(self) -> None:
        """Handle space bar - start/pause the ride."""
        if self.ride_state == "not_started":
            # Start the ride
            self.run_worker(self._start_ride())
        elif self.ride_state == "riding":
            # Pause the ride
            self.run_worker(self._pause_ride())

    async def _start_ride(self) -> None:
        """Start the ride and recording."""
        from datetime import datetime
        from cranktui.app import DEMO_MODE
        from cranktui.ble.client import debug_log

        self.ride_state = "riding"

        ble_client = await self.state.get_ble_client()

        # Set start time for the ride
        await self.state.update_metrics(start_time=datetime.now())

        # Start recording
        filepath = await self.ride_logger.start_recording()
        debug_log(f"Started recording ride to: {filepath}")

        # Start demo simulator if --demo flag was passed OR no BLE device connected
        if DEMO_MODE or not ble_client or not ble_client.is_connected:
            await self.state.update_metrics(mode="DEMO")
            await self.simulator.start()
        else:
            # Start in SIM mode by default when connected to trainer
            await self._start_sim_mode()

        self.notify("Ride started!")

    async def _pause_ride(self) -> None:
        """Pause the ride - stop simulator/SIM mode.

        elapsed_time_s automatically stops advancing because we stop
        calling update_metrics() when the simulator/SIM mode is stopped.
        """
        self.ride_state = "paused"

        # Pause logging
        self.ride_logger.pause()

        # Get current mode to know what to pause
        metrics = await self.state.get_metrics()

        # Stop the appropriate background task
        if metrics.mode == "DEMO":
            await self.simulator.stop()
        elif metrics.mode == "SIM":
            await self._stop_sim_mode()

        # Show pause modal
        self.app.push_screen(PauseRideModal(), self.handle_pause_choice)

    async def _resume_ride(self) -> None:
        """Resume the ride - restart simulator/SIM mode."""
        self.ride_state = "riding"

        # Resume logging
        self.ride_logger.resume()

        # Get current mode to know what to resume
        metrics = await self.state.get_metrics()

        # Restart the appropriate background task
        if metrics.mode == "DEMO":
            # Don't reset state - just restart simulation loop from current elapsed time
            self.simulator.running = True
            self.simulator.start_time = time.time() - metrics.elapsed_time_s
            self.simulator.task = asyncio.create_task(self.simulator._simulation_loop())
        elif metrics.mode == "SIM":
            await self._start_sim_mode()

        self.notify("Resumed")

    def handle_pause_choice(self, choice: str) -> None:
        """Handle the pause modal choice.

        Args:
            choice: "continue", "save", or "discard"
        """
        if choice == "continue":
            # Resume riding
            self.run_worker(self._resume_ride())
        elif choice == "save":
            # Save and exit
            self.run_worker(self._finish_ride(save=True))
        elif choice == "discard":
            # Discard and exit
            self.run_worker(self._finish_ride(save=False))

    async def _finish_ride(self, save: bool) -> None:
        """Finish the ride and save or discard.

        Args:
            save: True to save the ride, False to discard
        """
        # Stop recording
        await self.ride_logger.stop_recording()

        if save:
            self.notify("Ride saved!")
        else:
            # Discard the ride file
            self.ride_logger.discard_ride()
            self.notify("Ride discarded")

        # Go back to route selection
        self.dismiss()

    def action_toggle_mode(self) -> None:
        """Toggle between Demo and Live modes."""
        self.run_worker(self._toggle_mode())

    async def _toggle_mode(self) -> None:
        """Async toggle mode implementation.

        Cycles through modes: SIM → LIVE → DEMO → SIM
        """
        from cranktui.app import DEMO_MODE

        # Can't toggle if --demo flag was passed
        if DEMO_MODE:
            self.notify("Started with --demo flag, cannot toggle modes")
            return

        metrics = await self.state.get_metrics()
        ble_client = await self.state.get_ble_client()

        if metrics.mode == "SIM":
            # Switch to LIVE mode (manual control)
            if ble_client and ble_client.is_connected:
                await self._stop_sim_mode()
                await self.state.update_metrics(mode="LIVE")
                self.notify("Switched to LIVE mode (manual control)")
            else:
                self.notify("No device connected")
        elif metrics.mode == "LIVE":
            # Switch to DEMO mode
            await self.state.update_metrics(mode="DEMO")
            await self.simulator.start()
            self.notify("Switched to DEMO mode")
        elif metrics.mode == "DEMO":
            # Try to switch back to SIM mode
            if ble_client and ble_client.is_connected:
                # Stop demo simulator
                await self.simulator.stop()
                await self._start_sim_mode()
                self.notify("Switched to SIM mode (auto grade-following)")
            else:
                self.notify("No device connected - cannot switch modes")
        else:
            # Unknown mode, reset to SIM if connected, otherwise DEMO
            if ble_client and ble_client.is_connected:
                await self._stop_sim_mode()
                await self._start_sim_mode()
                self.notify("Switched to SIM mode (auto grade-following)")
            else:
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

    def action_increase_resistance(self) -> None:
        """Increase resistance scaling by 10%."""
        self.run_worker(self._adjust_resistance_scale(0.1))

    def action_decrease_resistance(self) -> None:
        """Decrease resistance scaling by 10%."""
        self.run_worker(self._adjust_resistance_scale(-0.1))

    async def _adjust_resistance_scale(self, delta: float) -> None:
        """Adjust resistance scaling factor.

        Args:
            delta: Change in scaling factor (e.g., +0.1 or -0.1)
        """
        metrics = await self.state.get_metrics()

        # Only works in SIM mode
        if metrics.mode != "SIM":
            self.notify("Resistance scaling only works in SIM mode")
            return

        # Calculate new scale (clamp between 0.3 and 2.0)
        new_scale = max(0.3, min(2.0, metrics.resistance_scale + delta))

        # Update state
        await self.state.update_metrics(resistance_scale=new_scale)

        # Notify user
        percentage = int(new_scale * 100)
        self.notify(f"Resistance: {percentage}%")

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
                resistance_scale = metrics.resistance_scale

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

                # Apply resistance scaling
                scaled_grade = smoothed_grade * resistance_scale

                # Calculate expected power for comparison
                from cranktui.config import get_bike_weight_kg, get_rider_weight_kg
                total_weight = get_rider_weight_kg() + get_bike_weight_kg()
                speed_ms = speed_kmh / 3.6
                gravity_power = total_weight * 9.8 * (scaled_grade / 100.0) * speed_ms if speed_ms > 0 else 0

                # Log current state
                scale_str = f", scale={int(resistance_scale*100)}%" if resistance_scale != 1.0 else ""
                debug_log(f"SIM: dist={distance_m:.0f}m, elev={current_elevation:.1f}m, grade_target={target_grade:.2f}%, grade_smooth={smoothed_grade:.2f}%{scale_str}, speed={speed_kmh:.1f}km/h, power={power_w:.0f}W (gravity_only={gravity_power:.0f}W, weight={total_weight:.0f}kg)")

                # Send to trainer
                ble_client = await self.state.get_ble_client()
                if ble_client and ble_client.is_connected:
                    await ble_client.set_gradient(scaled_grade)
                    # Also update state for display - preserve mode!
                    await self.state.update_metrics(grade_pct=scaled_grade, mode="SIM")

                # Wait 2 seconds before next update
                await asyncio.sleep(2.0)

        except asyncio.CancelledError:
            pass
