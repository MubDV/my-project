# EV SIM Professional Edition - Migration Guide

## Overview

The new professional frontend completely overhauls the UI/UX while maintaining all physics simulations, GA optimization, and configuration unchanged.

## Key Improvements

### 1. **Modern Design System**
- Professional dark theme with blue accents
- Consistent color palette, typography, and spacing
- Reusable component library
- Smooth transitions and hover effects

### 2. **Unified Interface**
- Single-window application (no matplotlib pop-outs)
- Integrated dashboard, simulator, parameters, and GA controls
- Navigation-based page system

### 3. **Better Real-Time Visualization**
- Live track visualization with vehicle position and trail
- In-app telemetry charts (no matplotlib)
- Live telemetry metrics panel
- Stop markers on track visualization

### 4. **Organized Information Architecture**
- **Dashboard**: Quick stats, recent activity, quick actions
- **Simulator**: Live vehicle animation, telemetry charts, controls
- **Parameters**: Organized by category (Physical, Drivetrain, Objectives)
- **GA Optimizer**: Configuration, progress tracking, results

## New Files

```
design_system.py      # Color palette, typography, reusable components
visualization.py      # Track visualization, charts, telemetry display
pages.py             # Individual page implementations
app_professional.py  # Main application entry point
simulation_bridge.py # Integration layer for real-time updates
```

## Running the New App

```bash
python3 app_professional.py
```

The app will start with the Dashboard page. Navigate using the sidebar.

## Backward Compatibility

All physics code remains unchanged:
- `simulation_code.py` - Vehicle physics simulation
- `simulation_ai.py` - Genetic Algorithm optimizer
- `backend_wrapper.py` - Process management
- `config.json` - All configuration

The new frontend reads/writes the same config and telemetry files.

## File Structure

### design_system.py
Core design tokens and reusable components:
- `ThemeColors` - Color palette
- `Spacing` - 8px grid system
- `Typography` - Text styles
- `Card` - Reusable card component
- `Button` - Primary, secondary, danger buttons
- `StatCard` - Statistics display
- `SliderField` - Parameter sliders
- `ProgressIndicator` - Progress tracking

### visualization.py
Real-time visualization components:
- `TrackVisualization` - Flet canvas track drawing
- `TelemetryChart` - Live charts (speed, power)
- `MetricRow` - Key metrics display
- `StatusBadge` - Status indicators

### pages.py
Page implementations:
- `DashboardPageNew` - Overview and quick stats
- `SimulatorPageNew` - Live simulator interface
- `ParametersPageNew` - Vehicle configuration
- `GAControlPageNew` - GA optimization controls

### app_professional.py
Main application:
- `ProfessionalEVSimApp` - App controller
- Navigation management
- Page routing
- Header and sidebar

## Customization

### Change Colors
Edit `design_system.py`:
```python
class ThemeColors:
    PRIMARY = "#58A6FF"  # Change this
    ACCENT_SUCCESS = "#3FB950"  # Or this
```

### Add New Pages
1. Create page class in `pages.py`:
```python
class MyPageNew:
    def build(self):
        return ft.Column([...])
```

2. Add to navigation in `app_professional.py`:
```python
nav_items = [
    ("mypage", ft.Icons.SOME_ICON, "My Page"),
    ...
]
```

3. Add handler in `navigate_to_page()`:
```python
elif page_key == "mypage":
    page_obj = MyPageNew()
```

## Integration with Backend

The new UI works with existing backend:

```python
# Run simulation
backend.run_simulation_async(callback)

# Run GA
backend.run_ga_async(callback)

# Load config
config = json.load(open("config.json"))

# Load telemetry
telemetry = json.load(open("telemetry.json"))
```

No changes needed to simulation or GA code.

## Performance Optimization

- Charts render incrementally (don't redraw entire dataset)
- Track visualization caches scaled coordinates
- UI updates batched to reduce Flet redraws
- Background threads handle long operations

## Known Limitations

- Track visualization renders pre-calculated points (not live update)
- Charts cap at 1000 data points to maintain performance
- Animation refresh rate depends on Flet's event loop

## Future Enhancements

- Supabase integration for result persistence
- Export results to CSV/JSON
- Multi-device synchronization
- Advanced result comparison tools
- Real-time collaborative features
