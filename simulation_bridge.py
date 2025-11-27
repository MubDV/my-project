import json
import os
import threading
import time
from typing import Callable, Optional
from dataclasses import dataclass, asdict
import numpy as np
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
TRACK_FILE_PATH = os.path.join(BASE_DIR, "sem_apme_2025-track_coordinates.csv")


@dataclass
class TelemetryFrame:
    timestamp: float
    distance: float
    speed_mps: float
    speed_kmh: float
    power_kw: float
    energy_wh: float
    state: str
    lap: int
    position: tuple


@dataclass
class SimulationResult:
    total_time: float
    total_distance: float
    total_energy: float
    avg_speed: float
    final_lap: int
    telemetry: list


class TrackLoader:
    def __init__(self, csv_path=TRACK_FILE_PATH):
        self.csv_path = csv_path
        self.track_data = None
        self.track_points = None
        self.load_track()

    def load_track(self):
        try:
            df = pd.read_csv(self.csv_path, sep="\t")
            latitudes = df["latitude"].values
            longitudes = df["longitude"].values

            mean_lat_rad = np.mean(latitudes) * np.pi / 180.0
            R = 6371000.0

            xs, ys = [], []
            lat0, lon0 = latitudes[0], longitudes[0]

            for la, lo in zip(latitudes, longitudes):
                xs.append(R * np.radians(lo - lon0) * np.cos(mean_lat_rad))
                ys.append(R * np.radians(la - lat0))

            self.track_points = np.vstack([xs, ys]).T
            self.track_data = {
                "latitudes": latitudes,
                "longitudes": longitudes,
                "xs": xs,
                "ys": ys,
                "total_length": np.sum(np.linalg.norm(np.diff(self.track_points, axis=0), axis=1)),
            }
        except Exception as e:
            print(f"Error loading track: {e}")
            self.track_points = np.array([[0, 0], [100, 0], [100, 100], [0, 100]])
            self.track_data = {"total_length": 400}

    def get_position_from_distance(self, distance_meters):
        if self.track_points is None or len(self.track_points) < 2:
            return 0, 0

        segment_lengths = np.linalg.norm(np.diff(self.track_points, axis=0), axis=1)
        cumulative_distances = np.concatenate([[0.0], np.cumsum(segment_lengths)])
        total_track_length = cumulative_distances[-1]

        local_distance = distance_meters % total_track_length
        segment_index = np.searchsorted(cumulative_distances, local_distance, side="right") - 1
        segment_index = min(segment_index, len(segment_lengths) - 1)

        segment_start_distance = cumulative_distances[segment_index]
        segment_length = segment_lengths[segment_index] if segment_lengths[segment_index] > 0 else 1e-9
        segment_fraction = (local_distance - segment_start_distance) / segment_length

        x_position = self.track_points[segment_index][0] + (self.track_points[(segment_index + 1) % len(self.track_points)][0] - self.track_points[segment_index][0]) * segment_fraction
        y_position = self.track_points[segment_index][1] + (self.track_points[(segment_index + 1) % len(self.track_points)][1] - self.track_points[segment_index][1]) * segment_fraction

        return x_position, y_position


class SimulationBridge:
    def __init__(self, on_telemetry_frame: Optional[Callable] = None, on_simulation_end: Optional[Callable] = None):
        self.on_telemetry_frame = on_telemetry_frame
        self.on_simulation_end = on_simulation_end
        self.track_loader = TrackLoader()
        self.running = False
        self.paused = False

    def run_simulation_async(self, callback: Optional[Callable] = None):
        thread = threading.Thread(target=self._run_simulation_worker, args=(callback,), daemon=True)
        thread.start()

    def _run_simulation_worker(self, callback: Optional[Callable] = None):
        try:
            config = self._load_config()

            distance_m = 0.0
            speed_mps = 0.0
            energy_used_wh = 0.0
            elapsed_time_s = 0.0
            lap_counter = 0

            telemetry_data = []

            car_mass_kg = config["car_mass_kg"]
            motor_max_power_watts = config["motor_max_power_watts"]
            simulation_time_step = config["simulation_time_step_seconds"]
            total_laps = config["total_laps_to_simulate"]

            self.running = True

            for step in range(int(total_laps * self.track_loader.track_data["total_length"] / (speed_mps * simulation_time_step + 1))):
                if not self.running:
                    break

                x, y = self.track_loader.get_position_from_distance(distance_m)
                lap_counter = int(distance_m // self.track_loader.track_data["total_length"])

                if lap_counter >= total_laps:
                    break

                state = "Coasting"
                power_draw_watts = 0

                frame = TelemetryFrame(
                    timestamp=elapsed_time_s,
                    distance=distance_m,
                    speed_mps=speed_mps,
                    speed_kmh=speed_mps * 3.6,
                    power_kw=power_draw_watts / 1000.0,
                    energy_wh=energy_used_wh,
                    state=state,
                    lap=lap_counter + 1,
                    position=(x, y),
                )

                telemetry_data.append(frame)

                if self.on_telemetry_frame:
                    self.on_telemetry_frame(frame)

                if callback:
                    callback(f"Step {step}: Lap {lap_counter + 1}/{total_laps}", step / (total_laps * 100))

                time.sleep(0.01)

                distance_m += speed_mps * simulation_time_step
                elapsed_time_s += simulation_time_step
                speed_mps = min(speed_mps + 0.1, 10)

            result = SimulationResult(
                total_time=elapsed_time_s,
                total_distance=distance_m,
                total_energy=energy_used_wh,
                avg_speed=distance_m / elapsed_time_s * 3.6 if elapsed_time_s > 0 else 0,
                final_lap=lap_counter,
                telemetry=telemetry_data,
            )

            if self.on_simulation_end:
                self.on_simulation_end(result)

        except Exception as e:
            print(f"Simulation error: {e}")
        finally:
            self.running = False

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}

    def stop_simulation(self):
        self.running = False
        self.paused = False

    def pause_simulation(self):
        self.paused = True

    def resume_simulation(self):
        self.paused = False
