# EV SIM Professional - Setup & Usage Guide

## Installation

### 1. Verify Dependencies
```bash
pip install flet numpy pandas matplotlib
```

### 2. Run the Professional App
```bash
python3 app_professional.py
```

## Application Structure

### Dashboard Tab
- **Overview of system status**
- Quick statistics (runs, GA optimizations, efficiency)
- Recent activity feed
- Quick action buttons

### Simulator Tab
- **Live vehicle animation** on track
- Real-time telemetry charts (speed, power)
- Current metrics (lap, speed, energy, state)
- Control buttons (Run, Stop, Run GA)

### Parameters Tab
- **Physical Properties**: Mass, frontal area, drag, rolling resistance
- **Drivetrain**: Motor power, drive force, brake force, efficiency
- **Objectives**: Max speed, target avg speed, corner speed
- All changes saved to `config.json` automatically

### GA Optimizer Tab
- **Configuration**: Generations, population size, mutation rate, crossover
- **Statistics**: Best fitness, current generation, population size
- **Controls**: Start optimization, view results

## Using the Simulator

### 1. Configure Vehicle (Optional)
- Go to **Parameters** tab
- Adjust any settings using sliders
- Changes save automatically

### 2. Run Simulation
- Go to **Simulator** tab
- Click **"Run Simulation"**
- Watch live animation and telemetry
- Use **"Stop"** to halt any time

### 3. View Results
- Results display on **Dashboard** after completion
- Telemetry data saved to `telemetry.json`

## Using GA Optimization

### 1. Configure GA (Optional)
- Go to **GA Optimizer** tab
- Adjust population size, generations, mutation rate
- Settings save automatically

### 2. Run Optimization
- Click **"Start Optimization"**
- Monitor progress in real-time
- Best policy saved to `best_straight_policy.json`

### 3. Run Optimized Simulation
- After GA completes, click **"Run Simulation"**
- Vehicle uses optimized policy from GA

## Advanced Usage

### Running GA → Simulation Pipeline
- Go to **Simulator** tab
- Click **"Run GA → Sim"**
- Runs GA optimization first, then simulation with best policy

### Exporting Results
Results are automatically saved:
- `telemetry.json` - Current run telemetry
- `best_straight_policy.json` - Best GA policy
- `sim_storage.json` - History of all runs

### Custom Track
To use a different track:
1. Create CSV file with columns: `latitude, longitude`
2. Save as `sem_apme_2025-track_coordinates.csv`
3. Restart the app

## Key Features

### Real-Time Visualization
- Vehicle position updates live during simulation
- Trail shows path traveled (color-coded by state)
- Stop markers show required stop locations

### Telemetry Display
- Speed (km/h) and average speed
- Power consumption (kW)
- Energy used (kWh)
- Simulation state (Throttle, Brake, Coast, Stop, etc.)
- Current lap and distance

### Live Charts
- Speed vs Time graph with rolling window
- Power vs Time graph
- Dynamic axis scaling

### Status Indicators
- Green badges: Running successfully
- Yellow badges: Warning states
- Red badges: Errors or stopped
- Progress bars: Simulation/GA progress

## Configuration Reference

Key parameters in `config.json`:

```json
{
  "car_mass_kg": 170,
  "motor_max_power_watts": 540,
  "drag_coefficient": 0.22,
  "target_average_speed_lower_kmh": 24.0,
  "target_average_speed_upper_kmh": 27.0,
  "ga_generations": 40,
  "ga_population_size": 36,
  "ga_mutation_rate": 0.12,
  "total_laps_to_simulate": 1,
  "stops_per_lap": 2
}
```

## Troubleshooting

### App Won't Start
- Check Flet installation: `pip install --upgrade flet`
- Verify Python version: 3.8+
- Check for syntax errors: `python3 -m py_compile app_professional.py`

### Simulation Won't Run
- Verify `config.json` exists and is valid JSON
- Check track file exists: `sem_apme_2025-track_coordinates.csv`
- Look at console output for error messages

### Charts Not Updating
- This is normal for first second (need data points)
- Charts will appear after 2+ data points collected
- Restart simulation if stuck

### Performance Issues
- Reduce chart resolution (fewer data points stored)
- Close other applications
- Increase `simulation_time_step_seconds` in config

## File Reference

| File | Purpose |
|------|---------|
| `app_professional.py` | Main application entry point |
| `design_system.py` | UI components and theme |
| `visualization.py` | Charts and track visualization |
| `pages.py` | Page implementations |
| `simulation_bridge.py` | Simulation integration |
| `backend_wrapper.py` | Process management (unchanged) |
| `simulation_code.py` | Vehicle physics (unchanged) |
| `simulation_ai.py` | GA optimizer (unchanged) |
| `config.json` | Vehicle and simulation parameters |
| `best_straight_policy.json` | Best GA-optimized throttle policy |
| `telemetry.json` | Current run telemetry data |

## Keyboard Shortcuts
- None currently (all via GUI)

## Tips & Tricks

### Faster GA
- Reduce `ga_generations` (e.g., 20 instead of 40)
- Reduce `ga_population_size` (e.g., 20 instead of 36)
- Increase `ga_time_step_seconds` (coarser evaluation)

### More Accurate Simulation
- Decrease `simulation_time_step_seconds` (e.g., 0.5 instead of 5)
- Increases runtime but more precise physics

### Better Track Visualization
- Track is automatically scaled to fit window
- Zoom by adjusting track coordinates in CSV

## Support

For issues or feature requests, check:
1. Console output (error messages)
2. `config.json` validity (use JSON validator)
3. File permissions (read/write to project directory)
