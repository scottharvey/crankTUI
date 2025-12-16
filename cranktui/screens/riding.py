"""Riding screen for active training session."""

import asyncio
import time
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical, VerticalScroll
from textual.screen import Screen, ModalScreen
from textual.widgets import Button, Footer, Header, Label, Static

from cranktui.recorder.ghost_loader import find_fastest_ghost, load_all_ghosts, load_ghost_ride, GhostRide
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
        background: transparent;
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
  g           Select Ghost Rider (before ride starts)
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


def parse_ride_datetime(filepath: Path) -> str:
    """Extract formatted date/time from ride filename.

    Example: '2025-12-16_162415_Alpine_Challenge.csv' → '2025-12-16 16:24'
    """
    filename = filepath.stem  # Remove .csv
    datetime_str = filename[:15]  # 'YYYY-MM-DD_HHMM'
    date_part = datetime_str[:10]  # 'YYYY-MM-DD'
    time_part = datetime_str[11:13] + ":" + datetime_str[13:15]  # 'HH:MM'
    return f"{date_part} {time_part}"


class GhostItem(Static, can_focus=True):
    """Widget representing a single ghost ride option."""

    def __init__(self, filepath: Path | None, ghost_ride: GhostRide | None, date_str: str, is_current: bool):
        super().__init__()
        self.filepath = filepath  # None for "No Ghost" option
        self.ghost_ride = ghost_ride  # None for "No Ghost" option
        self.date_str = date_str
        self.is_current = is_current

    def render(self) -> str:
        if self.ghost_ride is None:
            # "No Ghost" option
            marker = "→" if self.is_current else " "
            return f"{marker} No Ghost"

        # Format: "→ 2025-12-16 16:24 | 5.2km | 12:34"
        total_km = self.ghost_ride.total_distance / 1000
        mins = int(self.ghost_ride.total_time // 60)
        secs = int(self.ghost_ride.total_time % 60)

        marker = "→" if self.is_current else " "
        return f"{marker} {self.date_str} | {total_km:.1f}km | {mins:02d}:{secs:02d}"


class GhostModal(ModalScreen[str | None]):
    """Modal dialog for selecting a ghost ride.

    Returns:
        None if cancelled (no change)
        "NO_GHOST" if "No Ghost" was explicitly selected
        str(filepath) if a ghost was selected
    """

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
    ]

    CSS = """
    GhostModal {
        align: center middle;
        background: transparent;
    }

    #ghost-dialog {
        width: 60;
        height: 25;
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

    #ghost-list {
        width: 100%;
        height: 1fr;
        padding: 1;
    }

    GhostItem {
        margin: 0;
        padding: 0 1;
        background: transparent;
        border: round $surface;
    }

    GhostItem:focus {
        border: round white;
    }

    #help-text {
        width: 100%;
        height: auto;
        content-align: center middle;
        padding: 1;
        color: $text-muted;
    }

    #buttons {
        width: 100%;
        height: auto;
        align: center middle;
        padding: 1;
        border-top: solid white;
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

    def __init__(self, route_name: str, current_ghost: GhostRide | None):
        super().__init__()
        self.route_name = route_name
        self.current_ghost = current_ghost
        self.ghost_items: list[GhostItem] = []
        self.current_index = 0

    def compose(self) -> ComposeResult:
        """Create the ghost selection dialog."""
        with Container(id="ghost-dialog"):
            yield Label("Select Ghost Rider", id="header")
            with VerticalScroll(id="ghost-list"):
                pass  # Items will be added in on_mount
            yield Static("Press 'd' to delete | ↑↓ to navigate | Enter to select", id="help-text")
            with Horizontal(id="buttons"):
                yield Button("Select", id="select-btn")
                yield Button("Cancel", id="cancel-btn")
        yield Footer()

    async def on_mount(self) -> None:
        """Load ghosts and populate the list."""
        ghost_list = self.query_one("#ghost-list", VerticalScroll)

        # Load all ghosts for this route
        all_ghosts = load_all_ghosts(self.route_name)

        # Add "No Ghost" option first
        no_ghost_item = GhostItem(None, None, "", self.current_ghost is None)
        await ghost_list.mount(no_ghost_item)
        self.ghost_items.append(no_ghost_item)

        # Add all ghost rides
        for filepath, ghost_ride in all_ghosts:
            date_str = parse_ride_datetime(filepath)
            is_current = (self.current_ghost is not None and
                         self.current_ghost.filepath == filepath)
            ghost_item = GhostItem(filepath, ghost_ride, date_str, is_current)
            await ghost_list.mount(ghost_item)
            self.ghost_items.append(ghost_item)

        # Focus the current selection or first item
        if self.current_ghost is not None:
            # Find the index of current ghost
            for i, item in enumerate(self.ghost_items):
                if item.is_current:
                    self.current_index = i
                    break

        # Set focus after everything is mounted
        if self.ghost_items:
            self.call_after_refresh(self._set_initial_focus)

    def _set_initial_focus(self) -> None:
        """Set initial focus to the current selection."""
        if self.ghost_items and self.current_index < len(self.ghost_items):
            self.ghost_items[self.current_index].focus()

    def on_key(self, event) -> None:
        """Handle key presses."""
        if event.key == "up":
            self._navigate_up()
            event.prevent_default()
        elif event.key == "down":
            self._navigate_down()
            event.prevent_default()
        elif event.key == "enter":
            self._select()
            event.prevent_default()
        elif event.key == "d":
            self.run_worker(self._delete())
            event.prevent_default()

    def _navigate_up(self) -> None:
        """Navigate to previous ghost."""
        if not self.ghost_items:
            return

        self.current_index = (self.current_index - 1) % len(self.ghost_items)
        self.ghost_items[self.current_index].focus()

    def _navigate_down(self) -> None:
        """Navigate to next ghost."""
        if not self.ghost_items:
            return

        self.current_index = (self.current_index + 1) % len(self.ghost_items)
        self.ghost_items[self.current_index].focus()

    def _select(self) -> None:
        """Select the focused ghost."""
        if not self.ghost_items:
            self.dismiss(None)
            return

        selected_item = self.ghost_items[self.current_index]

        if selected_item.filepath is None:
            # "No Ghost" option selected
            self.dismiss("NO_GHOST")
        else:
            # Actual ghost selected
            self.dismiss(str(selected_item.filepath))

    def action_cancel(self) -> None:
        """Cancel without changing selection."""
        self.dismiss(None)

    async def _delete(self) -> None:
        """Delete the focused ghost ride."""
        if not self.ghost_items or self.current_index >= len(self.ghost_items):
            return

        selected_item = self.ghost_items[self.current_index]

        # Can't delete "No Ghost" option
        if selected_item.filepath is None:
            return

        # Delete the CSV file
        try:
            selected_item.filepath.unlink()
        except Exception:
            return

        # Remove from UI
        await selected_item.remove()
        self.ghost_items.remove(selected_item)

        # Adjust index if needed
        if self.current_index >= len(self.ghost_items):
            self.current_index = max(0, len(self.ghost_items) - 1)

        # Focus next item
        if self.ghost_items:
            self.ghost_items[self.current_index].focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press."""
        if event.button.id == "select-btn":
            self._select()
        elif event.button.id == "cancel-btn":
            self.action_cancel()


class PauseRideModal(ModalScreen[str]):
    """Modal dialog shown when ride is paused."""

    BINDINGS = [
        ("escape", "resume", "Resume"),
    ]

    CSS = """
    PauseRideModal {
        align: center middle;
        background: transparent;
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
        ("g", "show_ghosts", "Ghost"),
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
        self.ghost_ride: GhostRide | None = None
        self.ghost_task: asyncio.Task | None = None

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

        # Stop ghost task if running
        if self.ghost_task is not None:
            self.ghost_task.cancel()
            try:
                await self.ghost_task
            except asyncio.CancelledError:
                pass
            self.ghost_task = None

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

    def action_show_ghosts(self) -> None:
        """Show the ghost selection modal."""
        # Only allow before ride starts
        if self.ride_state != "not_started":
            return

        self.app.push_screen(GhostModal(self.route.name, self.ghost_ride), self.handle_ghost_choice)

    def handle_ghost_choice(self, choice: str | None) -> None:
        """Handle ghost selection from modal.

        Args:
            choice: None (cancelled), "NO_GHOST" (clear ghost), or filepath string
        """
        if choice is None:
            # Cancelled - no change
            return
        elif choice == "NO_GHOST":
            # Explicitly cleared ghost
            self.ghost_ride = None
        else:
            # Load the selected ghost
            ghost_path = Path(choice)
            self.ghost_ride = load_ghost_ride(ghost_path)

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

        # Load ghost ride (fastest previous ride for this route)
        self.ghost_ride = find_fastest_ghost(self.route.name)
        if self.ghost_ride:
            debug_log(f"Loaded ghost: {self.ghost_ride.total_time:.1f}s, {self.ghost_ride.total_distance:.0f}m")
            # Start ghost update task
            self.ghost_task = asyncio.create_task(self._update_ghost_loop())
        else:
            debug_log("No ghost ride found for this route")

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

    async def _update_ghost_loop(self) -> None:
        """Background task that updates ghost position based on elapsed time."""
        try:
            while True:
                if not self.ghost_ride:
                    break

                # Get current elapsed time
                metrics = await self.state.get_metrics()
                elapsed_time_s = metrics.elapsed_time_s

                # Get ghost distance at this time
                ghost_distance = self.ghost_ride.get_distance_at_time(elapsed_time_s)

                # Debug: print ghost info every 10 updates (once per second)
                if int(elapsed_time_s * 10) % 10 == 0:
                    from cranktui.ble.client import debug_log
                    debug_log(f"Ghost update: elapsed={elapsed_time_s:.1f}s, ghost_dist={ghost_distance:.1f}m")

                # Update state with ghost distance (for stats panel)
                await self.state.update_metrics(ghost_distance_m=ghost_distance)

                # Update both chart widgets
                elevation_chart = self.query_one("#elevation-panel", ElevationChart)
                minimap = self.query_one("#minimap-panel", MinimapWidget)

                elevation_chart.ghost_distance_m = ghost_distance
                minimap.ghost_distance_m = ghost_distance

                # Update every 0.1 seconds for smooth animation
                await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            pass

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
