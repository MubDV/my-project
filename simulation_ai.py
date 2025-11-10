import numpy as np
import pandas as pd
import math
import random
import json
import os
import time

# GA config
DEFAULT_TRACK_CSV = r"sem_apme_2025-track_coordinates.csv"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_POLICY_FILE = os.path.join(BASE_DIR, "best_straight_policy.json")

# Population & evolution only for GA
GA_POPULATION_SIZE = 36
GA_GENERATIONS = 40
GA_CROSSOVER_RATE = 0.9
GA_MUTATION_RATE = 0.12
GA_ELITE_COUNT = 2

# throttle fraction, pulse fraction limits
GENE_MIN_THROTTLE = 0.30
GENE_MAX_THROTTLE = 1.00
GENE_MIN_PULSE_FRAC = 0.05
GENE_MAX_PULSE_FRAC = 0.95

# Load configuration from JSON

CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
with open(CONFIG_PATH, "r") as f:
    cfg = json.load(f)

# Simulation time step used by the GA evaluator (seconds)
SIM_EVAL_TIME_STEP = cfg["ga_time_step_seconds"]

# Physics safety
VELOCITY_FLOOR_FOR_POWER = 1.0  # m/s used when converting power -> force to avoid huge forces


default_car_mass_kg = cfg["car_mass_kg"]
default_drag_coefficient = cfg["drag_coefficient"]
default_rolling_resistance_coefficient = cfg["rolling_resistance_coefficient"]
default_frontal_area_m2 = cfg["car_frontal_area_m2"]
default_air_density = cfg["air_density_kgpm3"]
default_gravity = cfg["gravity_mps2"]

default_motor_max_power_watts = cfg["motor_max_power_watts"]
default_motor_max_drive_force_newton = cfg["motor_max_drive_force_newton"]
default_drivetrain_efficiency = cfg["drivetrain_efficiency"]
default_max_brake_force_newton = cfg["brake_max_force_newton"]

TARGET_AVG_LOWER_KMH = cfg["target_average_speed_lower_kmh"]
TARGET_AVG_UPPER_KMH = cfg["target_average_speed_upper_kmh"]
TARGET_AVG_LOWER_MPS = TARGET_AVG_LOWER_KMH / 3.6
TARGET_AVG_UPPER_MPS = TARGET_AVG_UPPER_KMH / 3.6


DEFAULT_LAUNCH_SPEED_MPS = cfg["launch_phase_speed_mps"]
DEFAULT_BRAKE_SAFETY_SPEED_MPS = cfg["safe_corner_speed_kmh"] / 3.6
DEFAULT_TOTAL_LAPS = cfg["total_laps_to_simulate"]
DEFAULT_STOP_AFTER_LAPS = cfg["stop_after_finish"]

# calculation functions
def deg2rad(deg): return deg * math.pi / 180.0
def unit_vector(v):
    n = np.linalg.norm(v)
    return v / n if n != 0 else np.array([0.0, 0.0])

# Resistive forces
def aerodynamic_drag_force(speed_mps, air_density, drag_coefficient, frontal_area):
    return 0.5 * air_density * drag_coefficient * frontal_area * (speed_mps ** 2)

def rolling_resistance_force(mass_kg, gravity, rolling_resistance_coeff):
    return mass_kg * gravity * rolling_resistance_coeff


def load_track_meta(csv_path=DEFAULT_TRACK_CSV,
                    corner_window=8,
                    corner_angle_threshold_deg=9.0):
    df = pd.read_csv(csv_path, sep="\t")
    latitudes = df["latitude"].values
    longitudes = df["longitude"].values

    mean_lat_rad = np.mean(latitudes) * math.pi / 180.0
    R = 6371000.0
    xs, ys = [], []
    lat0, lon0 = latitudes[0], longitudes[0]
    for la, lo in zip(latitudes, longitudes):
        xs.append(R * deg2rad(lo - lon0) * math.cos(mean_lat_rad))
        ys.append(R * deg2rad(la - lat0))

    x_track = np.array(xs); y_track = np.array(ys)
    track_points = np.vstack([x_track, y_track]).T
    segment_vectors = np.diff(track_points, axis=0)
    segment_vectors = np.vstack([segment_vectors, track_points[0] - track_points[-1]])
    segment_lengths = np.linalg.norm(segment_vectors, axis=1)
    segment_directions = np.array([unit_vector(v) for v in segment_vectors])
    cumulative_distances = np.concatenate([[0.0], np.cumsum(segment_lengths)])
    total_track_length = cumulative_distances[-1]

    # curvature based corner detection
    curvature_deg = np.zeros(len(segment_directions))
    for i in range(len(segment_directions)):
        prev_i = (i - corner_window) % len(segment_directions)
        next_i = (i + corner_window) % len(segment_directions)
        v_before = segment_directions[prev_i]; v_after = segment_directions[next_i]
        dot = np.clip(np.dot(v_before, v_after), -1.0, 1.0)
        curvature_deg[i] = math.degrees(math.acos(dot))
    is_corner_segment = curvature_deg > corner_angle_threshold_deg

    # assemble straights list (start/end indices and s positions)
    straights = []
    i = 0
    while i < len(is_corner_segment):
        if not is_corner_segment[i]:
            start = i
            while i < len(is_corner_segment) and not is_corner_segment[i]:
                i += 1
            end = i - 1
            s_start = cumulative_distances[start]
            s_end = cumulative_distances[end+1] if (end+1) < len(cumulative_distances) else total_track_length
            length = s_end - s_start
            if length > 0:
                straights.append({
                    "start_segment": start,
                    "end_segment": end,
                    "start_distance": s_start,
                    "end_distance": s_end,
                    "length": length
                })
        else:
            i += 1

    seg_to_straight = -1 * np.ones(len(segment_lengths), dtype=int)
    for si, s in enumerate(straights):
        for seg_idx in range(s["start_segment"], s["end_segment"]+1):
            seg_to_straight[seg_idx] = si

    meta = {
        "track_points": track_points,
        "segment_vectors": segment_vectors,
        "segment_lengths": segment_lengths,
        "segment_directions": segment_directions,
        "cumulative_distances": cumulative_distances,
        "total_track_length": total_track_length,
        "is_corner_segment": is_corner_segment,
        "straights": straights,
        "seg_to_straight": seg_to_straight
    }
    return meta

# strategy functions
def random_policy(num_straights):
    pol = []
    for _ in range(num_straights):
        t = random.uniform(GENE_MIN_THROTTLE, GENE_MAX_THROTTLE)
        p = random.uniform(GENE_MIN_PULSE_FRAC, GENE_MAX_PULSE_FRAC)
        pol.append((t, p))
    return pol

def policy_to_vector(policy):
    flat = []
    for throttle, pulse in policy:
        flat.append(throttle); flat.append(pulse)
    return np.array(flat, dtype=float)

def vector_to_policy(vec):
    lst = []
    for i in range(0, len(vec), 2):
        t = float(np.clip(vec[i], GENE_MIN_THROTTLE, GENE_MAX_THROTTLE))
        p = float(np.clip(vec[i+1], GENE_MIN_PULSE_FRAC, GENE_MAX_PULSE_FRAC))
        lst.append((t, p))
    return lst


def simulate_policy(policy, meta,
                    car_mass_kg=default_car_mass_kg,
                    drag_coefficient=default_drag_coefficient,
                    rolling_res_coeff=default_rolling_resistance_coefficient,
                    frontal_area_m2=default_frontal_area_m2,
                    air_density=default_air_density,
                    gravity=default_gravity,
                    motor_max_power_watts=default_motor_max_power_watts,
                    motor_max_force_newton=default_motor_max_drive_force_newton,
                    drivetrain_eff=default_drivetrain_efficiency,
                    max_brake_newton=default_max_brake_force_newton,
                    brake_safety_speed_mps=DEFAULT_BRAKE_SAFETY_SPEED_MPS,
                    launch_speed_mps=DEFAULT_LAUNCH_SPEED_MPS,
                    total_laps=DEFAULT_TOTAL_LAPS,
                    stop_after_laps=DEFAULT_STOP_AFTER_LAPS,
                    dt=SIM_EVAL_TIME_STEP):

    seg_lengths = meta["segment_lengths"]
    cum_dist = meta["cumulative_distances"]
    track_len = meta["total_track_length"]
    is_corner = meta["is_corner_segment"]
    straights = meta["straights"]
    seg_to_straight = meta["seg_to_straight"]

    distance = 0.0
    velocity = 0.0
    energy_wh = 0.0
    time_sim = 0.0
    lap_count = 0

    # if no straights: run simple coast policy
    if len(straights) == 0:
        # simple run (coast all the way) and exit quickly
        return 0.0, 0.0, 0.0

    while True:
        # Locate current segment on track
        s_mod = distance % track_len
        seg_idx = np.searchsorted(cum_dist, s_mod, side='right') - 1
        seg_idx = min(seg_idx, len(seg_lengths) - 1)
        in_corner = is_corner[seg_idx]

        # Initialize forces for this step
        drive_force = 0.0
        brake_force = 0.0

        # Launch assist: full torque until launch speed reached

        if velocity < launch_speed_mps:
            drive_force = motor_max_force_newton

        else:
            # Identify which straight the car is currently on
            straight_idx = int(seg_to_straight[seg_idx])
            if straight_idx >= 0:
                straight = straights[straight_idx]
                s_start = straight["start_distance"] % track_len
                s_end = straight["end_distance"] % track_len

                # Fractional progress along this straight
                if s_start <= s_end:
                    frac = (s_mod - s_start) / max(1e-9, (s_end - s_start))
                else:
                    # wrap-around straight (start finish line)
                    if s_mod >= s_start:
                        frac = (s_mod - s_start) / max(1e-9, (track_len - s_start + s_end))
                    else:
                        frac = (track_len - s_start + s_mod) / max(1e-9, (track_len - s_start + s_end))

                # Extract throttle and pulse fraction for current straight
                throttle_frac, pulse_frac = policy[straight_idx]

                # Desired motor-side power (W)
                desired_motor_power_w = throttle_frac * motor_max_power_watts

                # Convert motor power to available force
                vel_for_calc = max(velocity, VELOCITY_FLOOR_FOR_POWER)
                wheel_force_from_power = (desired_motor_power_w * drivetrain_eff) / vel_for_calc

                # Apply pulse modulation: active throttle only for part of straight
                drive_force = min(motor_max_force_newton, wheel_force_from_power) if frac <= pulse_frac else 0.0

            else:
                # Corner segment: apply safety braking if too fast
                if velocity > brake_safety_speed_mps:
                    brake_force = min(max_brake_newton, (velocity - brake_safety_speed_mps) * 20.0)
                drive_force = 0.0

        # calculate resistive forces (drag + rolling)
        drag_force = aerodynamic_drag_force(velocity, air_density, drag_coefficient, frontal_area_m2)
        roll_force = rolling_resistance_force(car_mass_kg, gravity, rolling_res_coeff)
        resist_force = drag_force + roll_force

        #power cap on drive force
        #
        if velocity > 0.2:
            power_limited_force = (motor_max_power_watts * drivetrain_eff) / max(velocity, 0.2)
            drive_force = min(drive_force, power_limited_force)


        # drive_force: forward, resistive and brake: oppose
        net_force = (drive_force * drivetrain_eff) - resist_force - brake_force
        accel = net_force / car_mass_kg
        new_velocity = max(0.0, velocity + accel * dt)

        # Optional: hard physical speed cap (200 km/h)
        MAX_SPEED_MPS = 200.0 / 3.6
        if new_velocity > MAX_SPEED_MPS:
            new_velocity = MAX_SPEED_MPS

        v_avg = 0.5 * (velocity + new_velocity)
        distance += v_avg * dt
        time_sim += dt
        velocity = new_velocity


        wheel_power_w = drive_force * new_velocity
        motor_power_w = wheel_power_w / drivetrain_eff if drivetrain_eff > 1e-6 else wheel_power_w
        motor_power_w = max(0.0, min(motor_power_w, motor_max_power_watts))
        energy_wh += (motor_power_w * dt) / 3600.0


        lap_count = int(distance // track_len)
        if stop_after_laps and lap_count >= total_laps:
            break
        if time_sim > 60 * 60 * 2:  # emergency stop (2 hrs sim time)
            break


    avg_speed = distance / time_sim if time_sim > 0 else 0.0
    return energy_wh, avg_speed, time_sim


def fitness_of_policy(policy, meta):
    # Simulate given policy to get results to compare
    energy_wh, avg_speed_mps, sim_time = simulate_policy(policy, meta)


    target_laps = DEFAULT_TOTAL_LAPS
    target_total_time_s = cfg["lap_time_limit_minutes"] * 60

    allowed_time_s = (target_total_time_s / 4.0) * target_laps

    # Time penalty if simulation exceeds the limit
    time_penalty = 1.0
    if sim_time > allowed_time_s:
        excess_fraction = (sim_time - allowed_time_s) / allowed_time_s
        time_penalty += excess_fraction * 10.0  # harsh penalty


    penalty = 1.0
    if avg_speed_mps < TARGET_AVG_LOWER_MPS:
        penalty += (TARGET_AVG_LOWER_MPS - avg_speed_mps) / (TARGET_AVG_LOWER_MPS + 1e-9) * 5.0
    elif avg_speed_mps > TARGET_AVG_UPPER_MPS:
        penalty += (avg_speed_mps - TARGET_AVG_UPPER_MPS) / (TARGET_AVG_UPPER_MPS + 1e-9) * 5.0


    cost = energy_wh * penalty * time_penalty
    fitness = 1.0 / (1.0 + cost)

    return fitness, cost, energy_wh, avg_speed_mps


# GA operators (vector-based)
def one_point_crossover_vec(a, b):
    if len(a) <= 2:
        return a.copy(), b.copy()
    pt = random.randint(2, len(a)-2)
    child_a = np.concatenate([a[:pt], b[pt:]])
    child_b = np.concatenate([b[:pt], a[pt:]])
    return child_a, child_b

def mutate_vector(vec, mutation_rate=GA_MUTATION_RATE):
    for i in range(len(vec)):
        if random.random() < mutation_rate:
            if i % 2 == 0:
                vec[i] = np.clip(vec[i] + random.gauss(0, 0.08), GENE_MIN_THROTTLE, GENE_MAX_THROTTLE)
            else:
                vec[i] = np.clip(vec[i] + random.gauss(0, 0.08), GENE_MIN_PULSE_FRAC, GENE_MAX_PULSE_FRAC)


def run_ga(save_file=DEFAULT_POLICY_FILE, csv_path=DEFAULT_TRACK_CSV,
           population_size=GA_POPULATION_SIZE, generations=GA_GENERATIONS):
    meta = load_track_meta(csv_path)
    n_straights = len(meta["straights"])
    if n_straights == 0:
        print("No straights detected — GA aborted.")
        return None

    vec_len = n_straights * 2
    # initialize population (vectors)
    population = []
    for _ in range(population_size):
        v = []
        for _ in range(n_straights):
            v.append(random.uniform(GENE_MIN_THROTTLE, GENE_MAX_THROTTLE))
            v.append(random.uniform(GENE_MIN_PULSE_FRAC, GENE_MAX_PULSE_FRAC))
        population.append(np.array(v, dtype=float))

    best_solution = None
    best_cost = float('inf')
    start_time = time.time()

    for gen in range(generations):
        scored = []
        for individual in population:
            policy = vector_to_policy(individual)
            fit, cost, energy_wh, avg_spd = fitness_of_policy(policy, meta)
            scored.append((fit, cost, energy_wh, avg_spd, individual))
        # sort descending by fitness
        scored.sort(key=lambda x: x[0], reverse=True)
        gen_best = scored[0]
        if gen_best[1] < best_cost:
            best_cost = gen_best[1]
            best_solution = gen_best[4].copy()
        print(f"GA Gen {gen+1}/{generations}  bestCost {gen_best[1]:.3f}  energy {gen_best[2]:.3f} Wh  avg {gen_best[3]*3.6:.2f} km/h")

        # create new generation (elitism + tournament selection)
        new_pop = [scored[i][4].copy() for i in range(min(GA_ELITE_COUNT, len(scored)))]
        while len(new_pop) < population_size:
            def tournament_select():
                a = random.choice(scored); b = random.choice(scored)
                return a[4] if a[0] > b[0] else b[4]
            parent_a = tournament_select().copy()
            parent_b = tournament_select().copy()
            if random.random() < GA_CROSSOVER_RATE:
                child_a, child_b = one_point_crossover_vec(parent_a, parent_b)
            else:
                child_a, child_b = parent_a, parent_b
            mutate_vector(child_a); mutate_vector(child_b)
            new_pop.append(child_a)
            if len(new_pop) < population_size:
                new_pop.append(child_b)
        population = new_pop

    if best_solution is None:
        print("GA produced no solution.")
        return None

    best_policy = vector_to_policy(best_solution)
    try:
        with open(save_file, "w") as f:
            json.dump({"policy": best_policy}, f, indent=2)
        print("Saved best policy to", save_file)
    except Exception as e:
        print("Could not save policy:", e)
    print("GA total time: %.1f s" % (time.time() - start_time))
    return best_policy


# Replace lines 340-341 in simulation_ai.py with this:
import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Circuit GA Optimization.")
    parser.add_argument('--run_ga', action='store_true', help='Run the Genetic Algorithm.')
    args = parser.parse_args()

    if args.run_ga:
        # --- This block is new ---
        # The backend_wrapper is calling us.
        # Use the 'cfg' dictionary loaded from config.json at the top of the file.

        # Get parameters from cfg, using the script's globals as a fallback
        generations = cfg.get("ga_generations", GA_GENERATIONS)
        population_size = cfg.get("ga_population_size", GA_POPULATION_SIZE)
        mutation_rate = cfg.get("ga_mutation_rate", GA_MUTATION_RATE)

        # Update the global mutation rate, as 'mutate_vector' reads it directly
        GA_MUTATION_RATE = mutation_rate

        # SIM_EVAL_TIME_STEP is already loaded from cfg at the top of the file.

        print(f"--- GA Started from UI Config ---")
        print(f"Generations: {generations}, Population: {population_size}")
        print(f"Mutation Rate: {mutation_rate}, Sim Time Step: {SIM_EVAL_TIME_STEP}s")

        # Call run_ga() with the parameters loaded from the config file
        run_ga(
            population_size=population_size,
            generations=generations
        )

        print("--- GA run completed ---")
        # --- End of new block ---

    else:
        # Script was run directly without --run_ga, use defaults
        print("--- GA Started Directly (using script defaults) ---")
        run_ga()

