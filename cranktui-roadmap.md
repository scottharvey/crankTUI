# crankTUI – Implementation Roadmap

A Python terminal application for controlling a Wahoo KICKR SNAP trainer, visualizing elevation profiles, and racing against ghosts from previous rides.

---

## Project Overview

**crankTUI** is a fun side project that turns your terminal into a cycling trainer controller. It connects to your KICKR SNAP via Bluetooth, shows you a beautiful braille-rendered elevation profile, displays live stats, and lets you race against your previous rides.

Think Zwift, but in your terminal, and way simpler.

### Key Features

- 🚴 **BLE Connection** – Direct Bluetooth connection to KICKR SNAP
- 📊 **Live Metrics** – Speed, power, cadence, heart rate, distance, grade
- 🏔️ **Elevation Visualization** – Filled braille charts showing route profile
- 👻 **Ghost Racing** – Race against your previous rides
- 💾 **Ride Logging** – All rides saved to CSV for analysis
- 🎮 **Two Control Modes** – ERG mode (set power) or SIM mode (route-based resistance)
- 🔧 **Calibration** – Built-in spindown calibration screen

### Tech Stack

- **Language:** Python 3.11+
- **TUI Framework:** Textual (terminal UI)
- **Bluetooth:** Bleak (BLE library)
- **Protocol:** FTMS (Fitness Machine Service)
- **Async:** asyncio for concurrent operations

### Route Format

Routes are simple JSON files:

```json
{
  "name": "ChiangMai_HillLoop",
  "description": "Rolling hills north of the city",
  "distance_km": 24.6,
  "points": [
    {"distance_m": 0, "elevation_m": 320},
    {"distance_m": 500, "elevation_m": 335},
    {"distance_m": 1000, "elevation_m": 358}
  ]
}
```

Store routes in `~/.local/share/cranktui/routes/`

---

## Implementation Philosophy

**Every step produces a working, runnable app.**

You should be able to run `cranktui` after each step and see meaningful progress. We build incrementally, adding features one at a time.

---

## Step-by-Step Implementation

### Step 0: Bootstrap the Project

**Goal:** Get a minimal Textual app running.

**Libraries:**
- `textual` (0.85.0+)

**What to Build:**
- Create Python package structure
- Add `pyproject.toml` with dependencies and entry point
- Create minimal Textual `App` that shows "Hello crankTUI"
- Add quit keybinding (`q`)

**Test:**
```bash
pip install -e .
cranktui
```

**Result:** A simple terminal window with text and a footer showing keybindings. Press `q` to quit.

---

### Step 1: Route Selection Screen

**Goal:** Display a list of available routes and let user select one.

**Libraries:**
- `textual` (already added)

**What to Build:**
- Create `routes/route.py` with Route data model
- Create `routes/route_loader.py` to scan and load JSON routes from disk
- Create `tui/screens/route_select.py` with a Textual screen showing:
  - List of available routes
  - Route name, description, distance
  - Arrow keys to navigate, Enter to select
- Wire route selection into main app

**Test:**
```bash
cranktui
```

**Result:** Terminal shows a menu of available routes. Navigate with arrows, press Enter to select (just prints selection for now).

---

### Step 2: Basic Riding Screen Layout

**Goal:** Create the main riding screen with placeholder panels.

**Libraries:**
- `textual`

**What to Build:**
- Create `tui/screens/riding.py` with main layout:
  - Header showing route name
  - Elevation profile panel (empty box for now)
  - Stats panel (placeholder text)
  - Footer with keybindings
- After route selection, transition to riding screen
- Add keybindings: `q` to quit, `Esc` to go back

**Test:**
```bash
cranktui
```

**Result:** Select a route, see the riding screen with labeled boxes. No data yet, just layout.

---

### Step 3: Static Elevation Chart

**Goal:** Render a braille elevation chart from route data.

**Libraries:**
- `textual`

**What to Build:**
- Create `routes/resample.py` to normalize route points to even spacing
- Create `tui/widgets/elevation_chart.py` widget that:
  - Takes a Route object
  - Resamples to fit terminal width
  - Renders filled braille chart from elevation data
  - Shows distance markers
- Add elevation chart to riding screen

**Test:**
```bash
cranktui
```

**Result:** Select a route and see a beautiful static braille elevation profile filling the terminal.

---

### Step 4: Shared State Container

**Goal:** Create a central state object to hold all live metrics.

**Libraries:**
- None (pure Python)

**What to Build:**
- Create `state/state.py` with:
  - Data class for metrics: speed, power, cadence, distance, time, grade, etc.
  - Thread-safe getters/setters using `asyncio.Lock`
  - Initial values all zero
- Create `tui/widgets/stats_panel.py` widget that:
  - Reads from state
  - Displays metrics in a nice table/grid
  - Updates periodically (use Textual's reactive system)
- Add stats panel to riding screen

**Test:**
```bash
cranktui
```

**Result:** Riding screen shows stats panel with all zeros. Everything is static but the structure is there.

---

### Step 5: Fake Simulation Loop

**Goal:** Make stats come alive with simulated data.

**Libraries:**
- `asyncio`

**What to Build:**
- Create `simulation/simulator.py` with:
  - Async task that runs every 0.5 seconds
  - Updates state with fake data: incrementing time/distance, oscillating power/speed
  - Calculates current grade from route based on fake distance
- Start simulation task when entering riding screen
- Stats panel auto-updates as state changes

**Test:**
```bash
cranktui
```

**Result:** Stats panel shows changing numbers. Distance increases, power oscillates, grade updates based on route position.

---

### Step 6: Rider Position Marker

**Goal:** Show rider position moving across elevation chart.

**Libraries:**
- `textual`

**What to Build:**
- Extend `elevation_chart.py` to:
  - Read current distance from state
  - Calculate X position on chart
  - Draw `▲` marker above the elevation line at current position
  - Update on a timer (10-20 FPS)
- Optionally add a fake ghost marker `◆` slightly ahead

**Test:**
```bash
cranktui
```

**Result:** Watch the `▲` marker move across the elevation chart as fake distance increases.

---

### Step 7: BLE Discovery and Connection

**Goal:** Connect to KICKR SNAP via Bluetooth.

**Libraries:**
- `bleak` (add to dependencies)

**What to Build:**
- Create `ble/client.py` with:
  - Async function to scan for devices matching "KICKR"
  - Connect to first matching device
  - Discover FTMS service and characteristics
  - Print device info when connected
- Add a "Connecting..." screen or modal before riding screen
- Handle connection errors gracefully

**Test:**
```bash
cranktui
```

**Result:** App scans for and connects to your KICKR SNAP. Shows "Connected to KICKR SNAP" message.

**Note:** You'll need your trainer powered on and in pairing mode.

---

### Step 8: Parse BLE Data

**Goal:** Receive and parse live trainer data.

**Libraries:**
- `bleak`

**What to Build:**
- Create `ble/ftms_parser.py` with:
  - Function to parse "Indoor Bike Data" characteristic (0x2AD2)
  - Extract speed, cadence, power, distance from byte array
  - Handle optional fields based on flags
- In `ble/client.py`:
  - Subscribe to Indoor Bike Data notifications
  - Parse each notification
  - Log parsed data to console for debugging

**Test:**
```bash
cranktui
```

**Result:** Start pedaling on your trainer. Console shows live power, cadence, speed values updating.

---

### Step 9: Feed Real Data to State

**Goal:** Replace fake simulation with real trainer data.

**Libraries:**
- None (integration work)

**What to Build:**
- Wire BLE data into state updates:
  - Each notification updates state with real power, cadence, speed
  - Remove fake oscillating data
  - Keep distance calculation (integrate speed over time)
- Add mode toggle to switch between "Demo" (fake data) and "Live" (BLE data)

**Test:**
```bash
cranktui
```

**Result:** Stats panel shows real power/cadence/speed from your trainer as you pedal. Distance increases based on your actual speed.

---

### Step 10: Physics-Based Distance

**Goal:** Calculate distance from power instead of trainer speed.

**Libraries:**
- None (just math)

**What to Build:**
- Create `simulation/physics.py` with:
  - Function: `power_to_speed(power_w, grade_pct, mass_kg)` using physics
  - Accounts for gravity, rolling resistance, air resistance
  - Returns virtual speed in m/s
- Update simulator to use calculated speed instead of trainer-reported speed
- Add config for rider mass (default 75kg)

**Test:**
```bash
cranktui
```

**Result:** Distance calculation is more consistent. On steep climbs, you slow down realistically even at constant power.

---

### Step 11: Calibration Screen

**Goal:** Add spindown calibration for the trainer.

**Libraries:**
- `textual`, `bleak`

**What to Build:**
- Create `ble/control_point.py` with:
  - Function to send "Request Spindown" command (FTMS Control Point)
  - Parse spindown result
- Create `tui/screens/calibration.py` with:
  - Instructions to spin up to 35+ km/h
  - "Start Calibration" button
  - Show calibration progress
  - Display result and save timestamp
- Add calibration option to main menu
- Remind user if last calibration >7 days ago

**Test:**
```bash
cranktui
```

**Result:** Select calibration, pedal hard to 35km/h, coast, get calibration result.

---

<!-- ### Step 12: ERG Mode Control

**Goal:** Manually set target power from keyboard.

**Libraries:**
- `bleak`

**What to Build:**
- Extend `ble/control_point.py` with:
  - Function to send "Set Target Power" command
- Add keybindings to riding screen:
  - `[1-5]` for ERG presets (150W, 200W, 250W, 300W, 350W)
  - `[` and `]` to adjust power ±10W
- Show current ERG target in stats panel
- Display "ERG Mode" indicator

**Test:**
```bash
cranktui
```

**Result:** Press `3` to set 250W target. Trainer resistance increases. Press `]` to bump to 260W. -->

---

### Step 13: SIM Mode (Grade-Based Resistance)

**Goal:** Automatically adjust resistance based on route grade.

**Libraries:**
- `bleak`

**What to Build:**
- Create `simulation/smoothing.py` with:
  - Moving average filter for grade (50m window)
  - Rate limiter for max grade change per second
- Extend `ble/control_point.py` with:
  - Function to send "Set Indoor Bike Simulation Parameters"
  - Include grade, rolling resistance, wind resistance
- Add mode toggle: `[e]` for ERG, `[s]` for SIM
- In SIM mode, update resistance every 2 seconds based on smoothed grade

**Test:**
```bash
cranktui
```

**Result:** Press `s` for SIM mode. As you ride up a hill on the route, resistance increases automatically.

---

### Step 14: Ride Logging

**Goal:** Save all ride data to CSV files.

**Libraries:**
- None (use Python `csv` module)

**What to Build:**
- Create `recorder/ride_logger.py` with:
  - Start new CSV file when ride begins: `~/.local/share/cranktui/rides/YYYY-MM-DD_HHMMSS_routename.csv`
  - Append row every second with: timestamp, distance, power, cadence, speed, grade
  - Close file when ride ends
- Add `[space]` keybinding to start/stop recording
- Show recording indicator in stats panel

**Test:**
```bash
cranktui
```

**Result:** Press space to start, ride for a bit, press space to stop. Check CSV file with all your data.

---

### Step 15: Basic Ghost Support

**Goal:** Race against your best previous ride.

**Libraries:**
- None

**What to Build:**
- Create `recorder/ghost_loader.py` with:
  - Function to find all previous rides for current route
  - Load CSV and build distance-vs-time lookup
  - Find your fastest ride (shortest time to complete)
- Create `tui/widgets/ghost_panel.py` with:
  - Show time delta: "Ghost +15s" or "Ghost -8s"
  - Show distance delta
- Add ghost `◆` marker to elevation chart

**Test:**
```bash
cranktui
```

**Result:** On your second ride of the same route, see your ghost marker on the chart. Try to catch it!

---

### Step 16: Polish and Safety Features

**Goal:** Add quality-of-life features and safety.

**Libraries:**
- None

**What to Build:**
- Add pause/resume: `[p]` key
- Add emergency stop: `[space]` drops resistance to minimum immediately
- Add connection lost handling: try to reconnect automatically
- Add session summary screen after ride:
  - Total distance, time, average power, elevation gain
  - Did you beat the ghost?
- Add power graph (small sparkline) in stats panel

**Test:**
```bash
cranktui
```

**Result:** Polished app with safety features, better UX, and post-ride summary.

---

## Optional Future Enhancements

Once the core is working, consider:

- **Multi-ghost racing** – Show multiple previous rides
- **FIT file export** – Export rides for Strava/TrainingPeaks
- **Custom workouts** – Define interval workouts
- **ANT+ support** – Alternative to BLE
- **Power zones** – Visual indicators for training zones
- **Route creation tool** – Built-in tool to create JSON routes
- **GPX import** – Convert GPX files to JSON within the app

---

## Development Tips

### Testing Without a Trainer

Keep the "Demo Mode" from Step 5. Add a `--demo` flag to run without BLE:

```bash
cranktui --demo
```

Use keyboard to simulate power changes for testing.

### BLE Permissions on Linux

You may need to run with proper permissions:

```bash
sudo setcap 'cap_net_raw,cap_net_admin+eip' $(which python3)
```

Or add your user to the `bluetooth` group.

### Project Structure

Stick to the structure from the original plan. Keep concerns separated:

- `ble/` – All Bluetooth logic
- `routes/` – Route data and processing
- `simulation/` – Physics and resistance control
- `tui/` – All Textual UI code
- `recorder/` – Logging and ghost management
- `state/` – Shared state container

### Git Commits

Commit after each step! Makes it easy to roll back if something breaks.

### Async Best Practices

- Don't block the event loop
- Use `asyncio.create_task()` for background tasks
- Always cancel tasks on cleanup
- Use `asyncio.Lock` for shared state

### Performance

- Update stats panel at 2-5 Hz (not every BLE notification)
- Update elevation chart at 10-20 Hz max
- Don't recalculate route data every frame

---

## Running the App

Once installed:

```bash
# Normal mode (requires trainer)
cranktui

# Demo mode (fake data)
cranktui --demo

# Select specific route
cranktui --route flat_5k
```

---

## Conclusion

This roadmap gives you a clear path from zero to a working trainer app. Each step builds on the previous one, and you always have something runnable.

Take your time, have fun, and enjoy the ride! 🚴

Remember: this is a **fun side project** – don't stress about making it perfect. Get it working, iterate, and enjoy coding while your friends are out riding real bikes. 😄
