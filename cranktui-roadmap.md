# crankTUI – Remaining Tasks

A Python terminal application for controlling a Wahoo KICKR SNAP trainer, visualizing elevation profiles, and racing against ghosts from previous rides.

---

## Completed Features ✅

- Route selection with multiple demo routes
- Scrolling elevation chart with 3x vertical exaggeration
- Minimap showing full route overview
- BLE connection to KICKR SNAP
- Real-time metrics display (power, cadence, speed, grade)
- Physics-based speed calculation from power
- Settings for rider/bike weight
- Start/finish line markers
- Click-to-select routes
- Demo mode with adjustable speed

---

## Remaining Tasks

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

---

### Step 17: AI Route Generation

**Goal:** Generate custom routes using AI from natural language descriptions.

**Libraries:**
- `httpx` or `openai` (for API calls)

**What to Build:**
- Create `routes/ai_generator.py` with:
  - Function to call OpenRouter API (using Claude Haiku or GPT-4o-mini)
  - Structured prompt that outputs route JSON
  - Response validation and sanitization
  - Error handling for API failures
- Create `tui/screens/ai_route_generator.py` modal with:
  - Text input for route description
  - "Generate" button
  - Loading indicator during generation
  - Preview of generated elevation chart
  - "Save" and "Cancel" buttons
- Add keybinding to route selection screen: `[a]` for AI Generate
- Add API key configuration:
  - Environment variable: `OPENROUTER_API_KEY`
  - Or add to settings screen
- Save generated routes to `~/.local/share/cranktui/routes/`

**Example Prompts:**
- "70km ride where the first half is gentle hills and the last half is big mountains"
- "Flat 40km time trial course"
- "15km with 4 steep climbs for interval training"
- "Rolling hills, 25km, never more than 5% grade"

**Cost:** ~$0.001-0.01 per route generation (very cheap)

**Test:**
```bash
export OPENROUTER_API_KEY="your-key"
cranktui
```

**Result:** Press `a` on route selection, enter description like "30km with gradually increasing difficulty", get a custom-generated route in 1-2 seconds. Preview it, save it, ride it!

---

## Optional Future Enhancements

Once the core is working, consider:

- **Multi-ghost racing** – Show multiple previous rides
- **FIT file export** – Export rides for Strava/TrainingPeaks
- **Custom workouts** – Define interval workouts
- **ANT+ support** – Alternative to BLE
- **Power zones** – Visual indicators for training zones
- **Route creation tool** – Built-in manual tool to create JSON routes
- **GPX import** – Convert GPX files to JSON within the app
- **AI route variations** – "Make this route harder/longer/hillier"

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
