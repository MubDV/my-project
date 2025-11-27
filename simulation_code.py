import json
import math
import os
import random
import numpy as np
import pandas as pd
import time

import matplotlib as plt
plt.use('TkAgg')
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# === Live export settings ===
TELEMETRY_PATH = "telemetry.json"

# Initialize telemetry (reset for each run)
with open(TELEMETRY_PATH, "w") as f:
    json.dump({"time": [], "velocity": [], "power": []}, f)

# ==================== RUN SETTINGS ====================
TRACK_FILE_PATH = r"sem_apme_2025-track_coordinates.csv"
POLICY_SAVE_FILE = "best_straight_policy.json"

# ==================== VEHICLE & SIM SETTINGS (Loaded from config.json) ====================
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
with open(CONFIG_PATH, "r") as f:
    cfg = json.load(f)

# Vehicle physics
car_mass_kg = cfg["car_mass_kg"]
drag_coefficient = cfg["drag_coefficient"]
rolling_resistance_coefficient = cfg["rolling_resistance_coefficient"]
car_frontal_area_m2 = cfg["car_frontal_area_m2"]
air_density_kgpm3 = cfg["air_density_kgpm3"]
gravity_mps2 = cfg["gravity_mps2"]

motor_max_power_watts = cfg["motor_max_power_watts"]
motor_max_drive_force_newton = cfg["motor_max_drive_force_newton"]
drivetrain_efficiency = cfg["drivetrain_efficiency"]
brake_max_force_newton = cfg["brake_max_force_newton"]

# Speed targets
target_average_speed_lower_kmh = cfg["target_average_speed_lower_kmh"]
target_average_speed_upper_kmh = cfg["target_average_speed_upper_kmh"]
target_average_speed_lower_mps = target_average_speed_lower_kmh / 3.6
target_average_speed_upper_mps = target_average_speed_upper_kmh / 3.6
safe_corner_speed_mps = cfg["safe_corner_speed_kmh"] / 3.6
maximum_vehicle_speed_mps = cfg["maximum_vehicle_speed_kmh"] / 3.6
launch_phase_speed_mps = cfg["launch_phase_speed_mps"]

# Simulation physics
simulation_time_step_seconds = cfg["simulation_time_step_seconds"]
animation_refresh_interval_ms = cfg["animation_refresh_interval_ms"]

# Lap control
total_laps_to_simulate = cfg["total_laps_to_simulate"]
stop_after_finish = cfg["stop_after_finish"]

# ====================car point colours===========================
COLOR_ACCEL = "lime"
COLOR_COAST = "#9999ff"
COLOR_BRAKE = "red"

# ================ STOP CONFIG (added) =======================
# choosing a random location inside two sectors each lap.
STOPS_PER_LAP = cfg["stops_per_lap"]
N_SECTORS = 3
BRAKE_DISTANCE = 40.0        # meters before stop to begin heavy braking (tunable)
STOP_HOLD_TIME = cfg["stop_timer"]        # seconds to remain stopped
STOP_TOLERANCE = 1.0         # meters considered "at stop"

# =================calculation functions===========================
def degrees_to_radians(deg): return deg * math.pi / 180.0

def unit_vector(vector):
    length = np.linalg.norm(vector)
    return vector / length if length != 0 else np.array([0.0, 0.0])

def aerodynamic_drag(speed_mps):
    return 0.5 * air_density_kgpm3 * drag_coefficient * car_frontal_area_m2 * (speed_mps ** 2)

def rolling_resistance(mass_kg):
    return mass_kg * gravity_mps2 * rolling_resistance_coefficient

# ================LOAD AND PROCESS TRACK DATA==================
track_data = pd.read_csv(TRACK_FILE_PATH, sep="\t")
latitudes = track_data["latitude"].values
longitudes = track_data["longitude"].values

average_latitude_radians = np.mean(latitudes) * math.pi / 180.0
earth_radius_m = 6371000.0

track_x_positions = np.array(
    [earth_radius_m * degrees_to_radians(lon - longitudes[0]) * math.cos(average_latitude_radians) for lon in
     longitudes])
track_y_positions = np.array([earth_radius_m * degrees_to_radians(lat - latitudes[0]) for lat in latitudes])

track_points = np.vstack([track_x_positions, track_y_positions]).T
track_segment_vectors = np.diff(track_points, axis=0)
track_segment_vectors = np.vstack([track_segment_vectors, track_points[0] - track_points[-1]])

segment_lengths = np.linalg.norm(track_segment_vectors, axis=1)

segment_directions = np.array([unit_vector(v) for v in track_segment_vectors])

segment_distance_markers = np.concatenate([[0.0], np.cumsum(segment_lengths)])
total_track_length_m = segment_distance_markers[-1]

# =================DETECT CORNERS (CURVATURE METHOD)==============
corner_detection_window_segments = 8
corner_angle_threshold_degrees = 9.0

segment_curvature_degrees = np.zeros(len(segment_directions))
for i in range(len(segment_directions)):
    prev_index = (i - corner_detection_window_segments) % len(segment_directions)
    next_index = (i + corner_detection_window_segments) % len(segment_directions)
    vec_before = segment_directions[prev_index]
    vec_after = segment_directions[next_index]
    dot_product = np.clip(np.dot(vec_before, vec_after), -1.0, 1.0)
    segment_curvature_degrees[i] = math.degrees(math.acos(dot_product))

is_corner_segment = segment_curvature_degrees > corner_angle_threshold_degrees

# record corner lengths for debugging
corner_sections = []
segment_index = 0
while segment_index < len(is_corner_segment):
    if is_corner_segment[segment_index]:
        corner_start = segment_index
        while segment_index < len(is_corner_segment) and is_corner_segment[segment_index]:
            segment_index += 1
        corner_end = segment_index - 1
        start_distance = segment_distance_markers[corner_start]
        end_distance = segment_distance_markers[corner_end + 1] if (corner_end + 1) < len(
            segment_distance_markers) else total_track_length_m
        corner_length = end_distance - start_distance
        if corner_length > 0:
            corner_sections.append({
                "start_segment": corner_start,
                "end_segment": corner_end,
                "start_distance": start_distance,
                "end_distance": end_distance,
                "length": corner_length,
                "diameter": corner_length / math.pi
            })
    else:
        segment_index += 1

# output corner sections for debugging
for i, sec in enumerate(corner_sections):
    print(
        f" Corner {i}: Segments {sec['start_segment']} to {sec['end_segment']}, Length: {sec['length']:.1f} m, Diameter: {sec['diameter']:.1f} m")
    
# =================STRAIGHT SECTION DETECTION============================
straight_sections = []
segment_to_straight_map = -1 * np.ones(len(segment_lengths), dtype=int)

segment_index = 0
while segment_index < len(is_corner_segment):
    if not is_corner_segment[segment_index]:
        straight_start = segment_index
        while segment_index < len(is_corner_segment) and not is_corner_segment[segment_index]:
            segment_index += 1
        straight_end = segment_index - 1
        start_distance = segment_distance_markers[straight_start]
        end_distance = segment_distance_markers[straight_end + 1] if (straight_end + 1) < len(
            segment_distance_markers) else total_track_length_m
        straight_length = end_distance - start_distance
        if straight_length > 0:
            straight_sections.append({
                "start_segment": straight_start,
                "end_segment": straight_end,
                "start_distance": start_distance,
                "end_distance": end_distance,
                "length": straight_length
            })
    else:
        segment_index += 1

for i, section in enumerate(straight_sections):
    for seg in range(section["start_segment"], section["end_segment"] + 1):
        segment_to_straight_map[seg] = i

print(f"Track length = {total_track_length_m:.1f} m, straights detected: {len(straight_sections)}")

# print straight sections
for i, sec in enumerate(straight_sections):
    print(
        f" Straight {i}: Segments {sec['start_segment']} to {sec['end_segment']}, Length: {sec['length']:.1f} m")

# straight section coords for debugging
for i, sec in enumerate(straight_sections):
    start_x, start_y = track_points[sec['start_segment']]
    end_x, end_y = track_points[(sec['end_segment'] + 1) % len(track_points)]
    print(f" Straight {i} coords: Start ({start_x:.1f}, {start_y:.1f}), End ({end_x:.1f}, {end_y:.1f})")

# =====================LOAD OR GENERATE POLICY====================

print("Loading policy from best_straight_policy.json...")
best_policy = None
if os.path.exists(POLICY_SAVE_FILE):
    try:
        with open(POLICY_SAVE_FILE, "r") as f:
            best_policy = json.load(f).get("policy", None)
    except Exception as e:
        print(f"Warning: Could not load policy file. {e}")

if best_policy is None:
    best_policy = [(0.7, 0.4) for _ in range(len(straight_sections))]
    print("Using default fallback throttle policy.")

# ==================SIMULATION STATE VARIABLES===================
distance_m = 0.0
speed_mps = 0.0
energy_used_wh = 0.0
elapsed_time_s = 0.0
lap_counter = 0

telemetry_time, telemetry_speed, telemetry_avg_speed, telemetry_power, telemetry_state = [], [], [], [], []

# ================== STOP STATE (per-lap) ======================
sector_len_cache = total_track_length_m / float(N_SECTORS)

def generate_two_random_stops_for_lap():
    sector_len = total_track_length_m / float(N_SECTORS)
    sectors = random.sample(range(N_SECTORS), STOPS_PER_LAP)
    stops = []
    for sec in sectors:
        start = sec * sector_len
        end = start + sector_len
        margin = min(5.0, sector_len * 0.05)
        s_pos = random.uniform(start + margin, end - margin)
        s_pos = s_pos % total_track_length_m
        stops.append(s_pos)
    stops = sorted(stops)
    return stops

# global_state['lap_stop_positions'] = generate_two_random_stops_for_lap()
# global_state['next_stop_idx'] = 0
# print("Initial lap stops (m):", global_state['lap_stop_positions'])

lap_stops = generate_two_random_stops_for_lap()
next_stop_idx = 0
in_stop_hold = False
stop_hold_start_time = 0.0

print("Initial lap stops (m):", lap_stops)

# Convert distance along track X,Y coordinate
def get_position_from_distance(distance_meters, clamp_to_track=False):
    if clamp_to_track and stop_after_finish and distance_meters >= total_laps_to_simulate * total_track_length_m:
        local_distance = total_track_length_m
    else:
        local_distance = distance_meters % total_track_length_m

    segment_index = np.searchsorted(segment_distance_markers, local_distance, side='right') - 1
    segment_index = min(segment_index, len(segment_lengths) - 1)

    segment_start_distance = segment_distance_markers[segment_index]
    segment_length = segment_lengths[segment_index] if segment_lengths[segment_index] > 0 else 1e-9
    segment_fraction = (local_distance - segment_start_distance) / segment_length

    x_position = track_points[segment_index][0] + segment_directions[segment_index][
        0] * segment_length * segment_fraction
    y_position = track_points[segment_index][1] + segment_directions[segment_index][
        1] * segment_length * segment_fraction
    return x_position, y_position, segment_index

# Helper: compute minimum braking force (positive) required to bring current_speed to zero over distance d
def required_brake_force_for_stop(current_speed, distance_to_stop):
    # Using v^2 = 2 * a * d  => a = v^2 / (2 d)  (a positive = magnitude of deceleration)
    if distance_to_stop <= 1e-6:
        return brake_max_force_newton
    decel_required = (current_speed ** 2) / (2.0 * distance_to_stop)
    force_needed = car_mass_kg * decel_required
    return min(force_needed, brake_max_force_newton)

# ============MAIN CONTROL STRATEGY================
def control_strategy(current_distance, current_speed, current_time):
    """
    Returns: drive_force, brake_force, total_resistive_force, state, avg_speed
    STOP-GO override uses lap_stops and calculates required braking force to reach the stop point.
    """
    global lap_stops, next_stop_idx, in_stop_hold, stop_hold_start_time

    avg_speed = current_distance / current_time if current_time > 0 else 0.0

    # Resistive forces based on instantaneous speed/state
    drag_force = aerodynamic_drag(current_speed)
    rolling_force = rolling_resistance(car_mass_kg)
    total_resistive_force = drag_force + rolling_force

    # Start with defaults
    drive_force = 0.0
    brake_force = 0.0
    state = "Coast"

    # ---- STOP-GO OVERRIDE ----
    if next_stop_idx < len(lap_stops):
        # distance along current lap [0..L)
        s_mod = current_distance % total_track_length_m
        target_stop_s = lap_stops[next_stop_idx]

        # forward distance to stop (wrap-aware)
        dist_to_stop = (target_stop_s - s_mod) % total_track_length_m

        # If we're currently holding at a stop, enforce hold (prevent drive)
        if in_stop_hold:
            # If car is essentially stopped, hold timer controls release
            if current_speed < 0.1:
                if (current_time - stop_hold_start_time) >= STOP_HOLD_TIME:
                    # release and advance to next stop
                    in_stop_hold = False
                    next_stop_idx += 1
                    # After release, resume low throttle to exit
                    return 0.0, 0.0, total_resistive_force, "Stop Hold Released", avg_speed
                else:
                    # keep brakes slightly applied to prevent creep
                    return 0.0, brake_max_force_newton * 0.3, total_resistive_force, "Stop Hold", avg_speed
            else:
                # if we somehow have speed while in hold, apply strong braking
                return 0.0, brake_max_force_newton, total_resistive_force, "Stop Hold - Braking", avg_speed

        # If approaching stop within BRAKE_DISTANCE, compute braking plan
        if dist_to_stop <= BRAKE_DISTANCE:
            # If already extremely close (tolerance) and almost stopped -> start hold
            if dist_to_stop <= STOP_TOLERANCE or current_speed < 0.5:
                # instruct caller to settle to zero speed; set strong brake. The update_frame will snap when crossing.
                # Begin hold timer when speed is near zero; control_strategy returns high brake so simulation brakes quickly.
                if current_speed < 0.5:
                    # Start hold (the update_frame snap will actually set speed to zero and set stop_hold_start_time)
                    in_stop_hold = True
                    stop_hold_start_time = current_time
                    return 0.0, brake_max_force_newton, total_resistive_force, "Stop | Start Hold", avg_speed
                else:
                    # strong braking to settle speed before the stop
                    brk = min(brake_max_force_newton, (current_speed ** 2) * car_mass_kg / max(1e-6, 2.0 * max(dist_to_stop, 1e-6)))
                    brk = max(0.0, min(brk, brake_max_force_newton))
                    return 0.0, brk, total_resistive_force, "Stop | Strong Braking", avg_speed
            else:
                # compute minimum braking force needed to decelerate to zero exactly at stop
                required_brake = required_brake_force_for_stop(current_speed, dist_to_stop)
                # Add a small safety margin but do not exceed brake capacity
                brake_force = min(brake_max_force_newton, required_brake * 1.05)
                # Optionally allow a small drive if brake_force is tiny (but here we prefer brake-only)
                state = "Approach Stop | Braking"
                return 0.0, brake_force, total_resistive_force, state, avg_speed

    # ---- end STOP-GO OVERRIDE ----

    # Normal driving logic when not stopping
    current_segment = np.searchsorted(segment_distance_markers, current_distance % total_track_length_m,
                                      side='right') - 1
    current_segment = min(current_segment, len(segment_lengths) - 1)

    base_lookahead_distance = 50.0
    dynamic_lookahead_distance = base_lookahead_distance * np.clip(current_speed / 25.0, 0.8, 3.0)
    future_segment = np.searchsorted(segment_distance_markers,
                                     (current_distance + dynamic_lookahead_distance) % total_track_length_m,
                                     side='right') - 1
    approaching_corner = is_corner_segment[future_segment]

    if current_speed < launch_phase_speed_mps:
        drive_force = motor_max_drive_force_newton
        if current_speed > 0.5:
            drive_force = min(drive_force, (motor_max_power_watts * drivetrain_efficiency) / current_speed)
        return drive_force, 0.0, total_resistive_force, "Launch", avg_speed

    straight_index = int(segment_to_straight_map[current_segment])
    if straight_index >= 0:
        throttle_ratio, pulse_fraction = best_policy[straight_index]
        straight = straight_sections[straight_index]
        s_mod = current_distance % total_track_length_m
        start_s = straight["start_distance"] % total_track_length_m
        end_s = straight["end_distance"] % total_track_length_m

        if start_s <= end_s:
            progress_along_straight = (s_mod - start_s) / max(1e-9, (end_s - start_s))
        else:
            progress_along_straight = (total_track_length_m - start_s + s_mod) / max(1e-9, (
                        total_track_length_m - start_s + end_s))

        if approaching_corner and current_speed > safe_corner_speed_mps * 0.9:
            brake_force = min(brake_max_force_newton, (current_speed - safe_corner_speed_mps * 0.9) * 35.0)
            drive_force = 0.0
            state = "Pre-Brake"
        else:
            desired_power = throttle_ratio * motor_max_power_watts
            available_force = (desired_power * drivetrain_efficiency) / max(current_speed, 1.0)
            drive_force = min(motor_max_drive_force_newton,
                              available_force) if progress_along_straight <= pulse_fraction else 0.0
            state = f"Throttle {throttle_ratio * 100:.0f}% | S{straight_index}"
    else:
        if current_speed > safe_corner_speed_mps:
            brake_force = min(brake_max_force_newton, (current_speed - safe_corner_speed_mps) * 45.0)
            state = "Corner Braking"
        else:
            state = "Corner Coasting"

    if current_speed >= maximum_vehicle_speed_mps:
        drive_force = 0.0
        state = "Speed Limited"

    if avg_speed > target_average_speed_upper_mps:
        drive_force *= 0.6
    elif avg_speed < target_average_speed_lower_mps:
        drive_force *= 1.1

    return drive_force, brake_force, total_resistive_force, state, avg_speed

# ===================ANIMATION AND TELEMETRY===================

if len(straight_sections) > 0:
    fig = plt.figure(figsize=(12, 6))
    gs = fig.add_gridspec(2, 2, hspace=0.3, wspace=0.4, width_ratios=[2, 1])
    ax_map = fig.add_subplot(gs[:, 0])  # Map takes the entire left 2/3 column
    ax_vel = fig.add_subplot(gs[0, 1])  # Velocity chart top right
    ax_pow = fig.add_subplot(gs[1, 1], sharex=ax_vel)  # Power chart bottom right, sharing X-axis with velocity

    hud = fig.suptitle("", fontsize=10, x=0.34, y=0.98, ha='center',
                       bbox=dict(facecolor='white', alpha=0.9, edgecolor='lightgray', boxstyle='round,pad=0.5'))

    # --- Setup Map Plot (Left) ---
    ax_map.plot(track_x_positions, track_y_positions, color='lightgray', linewidth=1.2, zorder=1, label="Track Layout")
    ax_map.plot(track_x_positions[0], track_y_positions[0], marker='s', color='black', markersize=9,
                label="Start/Finish", zorder=6)
    car_dot, = ax_map.plot([], [], 'o', markersize=8, zorder=10, label="Car Position")

    # STOP markers (visual)
    stop_scatter = ax_map.scatter([], [], s=80, marker='x', c='magenta', zorder=8, label='Stops')

    margin = 20
    ax_map.set_xlim(track_x_positions.min() - margin, track_x_positions.max() + margin)
    ax_map.set_ylim(track_y_positions.min() - margin, track_y_positions.max() + margin)
    ax_map.set_xlabel("X Position (m)")
    ax_map.set_ylabel("Y Position (m)")
    ax_map.set_title("Live Vehicle Position")
    ax_map.set_aspect('equal', adjustable='box')  # Ensure the map is square

    # --- Setup Live Charts (Right) ---
    line_vel, = ax_vel.plot([], [], label="Speed (km/h)", color='cyan')
    line_avg, = ax_vel.plot([], [], label="Avg Speed (km/h)", color='orange', linestyle='--')
    ax_vel.set_title("Speed vs Time (Last 120s)")
    ax_vel.set_ylabel("Speed (km/h)")
    ax_vel.grid(True)
    ax_vel.legend(loc="lower right", fontsize=8)

    line_pow, = ax_pow.plot([], [], label="Power (kW)", color='lime')
    ax_pow.set_title("Power vs Time")
    ax_pow.set_ylabel("Power (kW)")
    ax_pow.set_xlabel("Time (s)")
    ax_pow.grid(True)
    ax_pow.legend(loc="upper right", fontsize=8)

    plt.setp(ax_vel.get_xticklabels(), visible=False)

    # Global limit trackers for charts
    max_time = 0.0
    max_speed = 0.0
    max_power = 0.0

    # For lap-based stop regeneration
    last_lap_generated = 0

    # Animation update function
    def update_frame(frame):
        global distance_m, speed_mps, energy_used_wh, elapsed_time_s, lap_counter, max_time, max_speed, max_power
        global lap_stops, next_stop_idx, in_stop_hold, stop_hold_start_time, last_lap_generated

        # --- 1. Physics Step ---
        drive_force, brake_force, resistive_force, state, avg_speed = control_strategy(distance_m, speed_mps,
                                                                                       elapsed_time_s)

        # net force: drive (after drivetrain eff) minus resistances and brake_force
        net_force = (drive_force * drivetrain_efficiency) - resistive_force - brake_force
        acceleration = net_force / car_mass_kg
        new_speed = np.clip(speed_mps + acceleration * simulation_time_step_seconds, 0.0, maximum_vehicle_speed_mps)
        average_speed_step = 0.5 * (speed_mps + new_speed)

        prev_distance = distance_m
        distance_m += average_speed_step * simulation_time_step_seconds
        elapsed_time_s += simulation_time_step_seconds
        speed_mps = new_speed

        # --- STOP CROSSING / SNAP LOGIC ---
        # Check if we crossed the next stop this frame. Use prev and new s_mod (per-lap).
        if next_stop_idx < len(lap_stops):
            s_mod_old = prev_distance % total_track_length_m
            s_mod_new = distance_m % total_track_length_m
            stop_s = lap_stops[next_stop_idx]

            crossed = False
            # Normal (no wrap)
            if s_mod_old <= s_mod_new:
                if (s_mod_old < stop_s <= s_mod_new) or (abs(s_mod_new - stop_s) <= STOP_TOLERANCE and s_mod_old < stop_s):
                    crossed = True
            else:
                # wrapped around the lap boundary this update
                if (s_mod_old < stop_s <= total_track_length_m) or (0.0 <= stop_s <= s_mod_new):
                    crossed = True

            if crossed:
                # Snap to the stop on the same lap as where prev_distance was
                lap_number = int(math.floor(prev_distance / total_track_length_m))
                stop_abs_s = lap_number * total_track_length_m + stop_s

                # If we are past it by a tiny numeric error, clamp
                # Move car to exact stop location and set speed to zero (simulate perfect stop)
                distance_m = stop_abs_s
                speed_mps = 0.0
                in_stop_hold = True
                stop_hold_start_time = elapsed_time_s
                state = "Stopped at Stop Point"
                # Don't advance next_stop_idx here; control_strategy will advance it after hold release
                # (this preserves a single source of truth for advancing).
                print(f"Crossed stop (idx {next_stop_idx}) at absolute {stop_abs_s:.2f} m — snapping to stop and holding.")

        power_draw_watts = max(0.0, min(drive_force * speed_mps, motor_max_power_watts))
        energy_used_wh += (power_draw_watts * simulation_time_step_seconds) / 3600.0

        lap_counter = int(distance_m // total_track_length_m)
        x, y, _ = get_position_from_distance(distance_m)

        # If we've started a new lap (lap_counter increased), regenerate stops for that lap
        if lap_counter > last_lap_generated:
            last_lap_generated = lap_counter
            lap_stops = generate_two_random_stops_for_lap()
            next_stop_idx = 0
            in_stop_hold = False
            stop_hold_start_time = 0.0
            print(f"Lap {lap_counter} started. New stops (m): {lap_stops}")

        # Append telemetry data
        telemetry_time.append(elapsed_time_s)
        telemetry_speed.append(speed_mps * 3.6)
        telemetry_avg_speed.append(avg_speed * 3.6)
        telemetry_power.append(power_draw_watts)
        telemetry_state.append(state)

        # --- 2. Map Update ---
        car_dot.set_data([x], [y])

        if "Braking" in state or "Stop" in state:
            trail_color = COLOR_BRAKE
        elif "Throttle" in state or "Launch" in state:
            trail_color = COLOR_ACCEL
        else:
            trail_color = COLOR_COAST

        # Draw trail segment
        if frame > 0 and len(telemetry_time) > 1:
            prev_x, prev_y = get_position_from_distance(distance_m - average_speed_step * simulation_time_step_seconds)[:2]
            ax_map.plot([prev_x, x], [prev_y, y], color=trail_color, linewidth=4.8, alpha=0.25, zorder=4)

        # Update stop marker visuals (show current lap stops on the map)
        stop_xy = []
        for sp in lap_stops:
            sx, sy, _ = get_position_from_distance(sp)
            stop_xy.append((sx, sy))
        if stop_xy:
            xs_st, ys_st = zip(*stop_xy)
            stop_scatter.set_offsets(np.column_stack((xs_st, ys_st)))
        else:
            stop_scatter.set_offsets(np.empty((0, 2)))

        # --- 3. HUD Update ---
        if segment_to_straight_map[np.searchsorted(segment_distance_markers, distance_m % total_track_length_m,
                                                   side='right') - 1] != -1 and "Throttle" in state and power_draw_watts < 1.0:
            state = "Straight Coasting"
        if state == "Corner Braking" and brake_force < 1.0:
            state = "Corner Coasting"

        car_dot.set_color(
            COLOR_BRAKE if "Brake" in state or "Stop" in state else COLOR_ACCEL if "Throttle" in state or "Launch" in state else COLOR_COAST)

        hud.set_text(
            f"**Lap {lap_counter + 1}/{total_laps_to_simulate}** | **Time:** {elapsed_time_s:.1f} s | **Energy:** {energy_used_wh / 1000:.2f} kWh\n"
            f"**Speed:** {speed_mps * 3.6:.1f} km/h (Avg: {avg_speed * 3.6:.1f} km/h) | **Power:** {power_draw_watts / 1000:.1f} kW | **State:** {state}\n"
            f"Next stop: {next_stop_idx}/{len(lap_stops)}"
        )

        # --- 4. Live Charts Update ---
        line_vel.set_data(telemetry_time, telemetry_speed)
        line_avg.set_data(telemetry_time, telemetry_avg_speed)
        line_pow.set_data(telemetry_time, np.array(telemetry_power) / 1000.0)

        # Dynamic axis resizing
        if elapsed_time_s > max_time:
            max_time = elapsed_time_s
            ax_vel.set_xlim(max(0, max_time - 120), max_time * 1.05)

        current_max_speed = max(telemetry_speed) if telemetry_speed else 0
        current_max_power = max(np.array(telemetry_power) / 1000.0) if telemetry_power else 0
        if current_max_speed > max_speed: max_speed = current_max_speed
        if current_max_power > max_power: max_power = current_max_power

        ax_vel.set_ylim(0, max_speed * 1.1 if max_speed > 0 else 10)
        ax_pow.set_ylim(0, max_power * 1.1 if max_power > 0 else 1)

        # --- 5. Stop Condition ---
        if stop_after_finish and lap_counter >= total_laps_to_simulate:
            ani.event_source.stop()
            print("\n=== Simulation complete ===")
            print(f"Average Speed: {(distance_m / elapsed_time_s) * 3.6:.2f} km/h")
            print(f"Energy Used: {energy_used_wh / 1000:.2f} kWh")
            print(f"Total Time: {elapsed_time_s:.2f} s for {lap_counter} laps")
            if lap_counter > 0:
                print(f"Lap Time per lap: {elapsed_time_s / lap_counter:.2f} s")
            if distance_m > 0:
                print(f"Efficiency: {(energy_used_wh / 1000) / (distance_m / 1000):.2f} kWh/km")

            # Save final telemetry data for the Flet UI
            with open(TELEMETRY_PATH, "w") as f:
                json.dump({
                    "time": telemetry_time,
                    "velocity": telemetry_speed,
                    "power": telemetry_power
                }, f)
            print("Final telemetry data saved to telemetry.json.")

        return car_dot, line_vel, line_avg, line_pow  # Return all animated elements

    # Start the animation loop
    print("Starting visual simulation in new window...")
    ani = FuncAnimation(fig, update_frame, interval=animation_refresh_interval_ms, blit=False)
    plt.show()

    # ===================== STRAIGHT SECTION VISUALIZER =====================

    print("Opening straight section color map...")

    fig2, ax_s = plt.subplots(figsize=(10, 8))

    # Draw full track in light grey
    ax_s.plot(track_x_positions, track_y_positions, color="lightgray", linewidth=1.5, label="Track")

    # Plot each straight with random color
    for i, sec in enumerate(straight_sections):
        color = (random.random(), random.random(), random.random())

        start_idx = sec["start_segment"]
        end_idx = sec["end_segment"]

        # Collect coordinates of this straight
        xs = track_x_positions[start_idx:end_idx+2]  # +2 to include next point
        ys = track_y_positions[start_idx:end_idx+2]

        ax_s.plot(xs, ys, linewidth=3.5, color=color, label=f"Straight {i}")

    ax_s.set_title("Straight Sections (Random Colors)")
    ax_s.set_xlabel("X Position (m)")
    ax_s.set_ylabel("Y Position (m)")
    ax_s.set_aspect('equal', adjustable='box')
    ax_s.grid(True)
    ax_s.legend(fontsize=7)

    plt.show()

else:
    print("No straights detected. Skipping animation.")

print("simulation_code.py finished.")
