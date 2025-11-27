# Quick Start - Run EV SIM Professional

## Standard Run

```bash
python3 app_professional.py
```

## With Different Python Path

```bash
/usr/bin/python3 app_professional.py
```

## Testing (No GUI)

To verify all modules load correctly without opening the GUI:

```bash
python3 -c "
import design_system
import visualization
import pages
import app_professional
print('All modules loaded successfully!')
"
```

## What Happens When You Run

1. **App Window Opens** with professional dark theme
2. **Dashboard Page Displays** with stats and quick actions
3. **Sidebar Navigation** allows switching between pages
4. **Ready to Use**:
   - Configure vehicle in Parameters tab
   - Run simulations in Simulator tab
   - Optimize with GA in GA Optimizer tab

## Stopping the App

- Click window close button (X)
- Press `Ctrl+C` in terminal
- Close window through OS

## Output Files Created

When you run simulations, these files are updated:
- `telemetry.json` - Current run data
- `sim_storage.json` - History of all runs
- `best_straight_policy.json` - GA best policy
- `config.json` - Current configuration (updated by UI)

## Environment Variables

None required. App uses relative paths for all files.

## Performance Tips

- **First Launch**: May take 2-3 seconds to start
- **During Simulation**: Keep charts visible for live updates
- **Long Runs**: Can take several minutes depending on settings

## Logs

Console output shows:
- Status updates during simulation
- GA generation progress
- Any error messages

Check the console if anything seems wrong!
