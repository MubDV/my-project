import json
import math
import os
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


# =================calculation fucntions===========================
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

print(f"Track length ≈ {total_track_length_m:.1f} m, straights detected: {len(straight_sections)}")

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


# ============MAIN CONTROL STRATEGY================
def control_strategy(current_distance, current_speed, current_time):
    avg_speed = current_distance / current_time if current_time > 0 else 0.0
    current_segment = np.searchsorted(segment_distance_markers, current_distance % total_track_length_m,
                                      side='right') - 1
    current_segment = min(current_segment, len(segment_lengths) - 1)

    drag_force = aerodynamic_drag(current_speed)
    rolling_force = rolling_resistance(car_mass_kg)
    total_resistive_force = drag_force + rolling_force

    drive_force = 0.0
    brake_force = 0.0
    state = "Coast"

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

    # Removed: hud = ax_map.text(0.02, 0.98, "", transform=ax_map.transAxes, va='top', bbox=...)

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
    ax_vel.set_title("Speed vs Time (Last 120s)")  # Updated title
    ax_vel.set_ylabel("Speed (km/h)")
    ax_vel.grid(True)
    ax_vel.legend(loc="lower right", fontsize=8)  # Smaller legend font

    line_pow, = ax_pow.plot([], [], label="Power (kW)", color='lime')
    ax_pow.set_title("Power vs Time")
    ax_pow.set_ylabel("Power (kW)")
    ax_pow.set_xlabel("Time (s)")
    ax_pow.grid(True)
    ax_pow.legend(loc="upper right", fontsize=8)  # Smaller legend font

    # Hide the x-axis tick labels for the top chart
    plt.setp(ax_vel.get_xticklabels(), visible=False)

    # Global limit trackers for charts
    max_time = 0.0
    max_speed = 0.0
    max_power = 0.0


    # This is the FuncAnimation update function
    def update_frame(frame):
        global distance_m, speed_mps, energy_used_wh, elapsed_time_s, lap_counter, max_time, max_speed, max_power

        # --- 1. Physics Step ---
        drive_force, brake_force, resistive_force, state, avg_speed = control_strategy(distance_m, speed_mps,
                                                                                       elapsed_time_s)

        net_force = (drive_force * drivetrain_efficiency) - resistive_force - brake_force
        acceleration = net_force / car_mass_kg
        new_speed = np.clip(speed_mps + acceleration * simulation_time_step_seconds, 0.0, maximum_vehicle_speed_mps)
        average_speed_step = 0.5 * (speed_mps + new_speed)

        distance_m += average_speed_step * simulation_time_step_seconds
        elapsed_time_s += simulation_time_step_seconds
        speed_mps = new_speed

        power_draw_watts = max(0.0, min(drive_force * speed_mps, motor_max_power_watts))
        energy_used_wh += (power_draw_watts * simulation_time_step_seconds) / 3600.0

        lap_counter = int(distance_m // total_track_length_m)
        x, y, _ = get_position_from_distance(distance_m)

        # Append telemetry data
        telemetry_time.append(elapsed_time_s)
        telemetry_speed.append(speed_mps * 3.6)
        telemetry_avg_speed.append(avg_speed * 3.6)
        telemetry_power.append(power_draw_watts)
        telemetry_state.append(state)

        # --- 2. Map Update ---
        car_dot.set_data([x], [y])

        if "Brake" in state:
            trail_color = COLOR_BRAKE
        elif "Throttle" in state or "Launch" in state:
            trail_color = COLOR_ACCEL
        else:
            trail_color = COLOR_COAST

        # Draw trail segment
        if frame > 0 and len(telemetry_time) > 1:
            prev_x, prev_y = get_position_from_distance(distance_m - average_speed_step * simulation_time_step_seconds)[
                             :2]
            ax_map.plot([prev_x, x], [prev_y, y], color=trail_color, linewidth=4.8, alpha=0.25, zorder=4)

        # --- 3. HUD Update (Now uses fig.suptitle) ---
        if segment_to_straight_map[np.searchsorted(segment_distance_markers, distance_m % total_track_length_m,
                                                   side='right') - 1] != -1 and "Throttle" in state and power_draw_watts < 1.0:
            state = "Straight Coasting | S" + state.split("S")[-1]
        if state == "Corner Braking" and brake_force < 1.0:
            state = "Corner Coasting"

        car_dot.set_color(
            COLOR_BRAKE if "Brake" in state else COLOR_ACCEL if "Throttle" in state or "Launch" in state else COLOR_COAST)

        hud.set_text(
            f"**Lap {lap_counter + 1}/{total_laps_to_simulate}** | **Time:** {elapsed_time_s:.1f} s | **Energy:** {energy_used_wh / 1000:.2f} kWh\n"
            f"**Speed:** {speed_mps * 3.6:.1f} km/h (Avg: {avg_speed * 3.6:.1f} km/h) | **Power:** {power_draw_watts / 1000:.1f} kW | **State:** {state}"
        )

        # --- 4. Live Charts Update ---
        line_vel.set_data(telemetry_time, telemetry_speed)
        line_avg.set_data(telemetry_time, telemetry_avg_speed)
        line_pow.set_data(telemetry_time, np.array(telemetry_power) / 1000.0)

        # Dynamic axis resizing
        if elapsed_time_s > max_time:
            max_time = elapsed_time_s
            # Show last 120s or start to end, plus 5% padding
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
            print(f"Lap Time per lap: {elapsed_time_s / lap_counter:.2f} s")
            print(f"Efficiency: {(energy_used_wh / 1000) / (distance_m / 1000):.2f} kWh/km")

            # Save final telemetry data for the Flet UI
            with open(TELEMETRY_PATH, "w") as f:
                json.dump({
                    "time": telemetry_time,
                    "velocity": telemetry_speed,
                    "power": telemetry_power
                }, f)
            print("Final telemetry data saved to telemetry.json.")

            # Close the Matplotlib window gracefully
            plt.close(fig)

        return car_dot, line_vel, line_avg, line_pow  # Return all animated elements (Note: hud update is outside of blit elements)


    # Start the animation loop
    print("Starting visual simulation in new window...")
    ani = FuncAnimation(fig, update_frame, interval=animation_refresh_interval_ms, blit=False)
    plt.show()

else:
    print("No straights detected. Skipping animation.")

print("simulation_code.py finished.")
