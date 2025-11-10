# backend_wrapper.py
# Bridge layer that runs your simulation/GA as subprocesses and streams stdout -> callback
import os
import sys
import threading
import subprocess
import json
import time
import signal
import uuid  # For generating unique IDs

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = sys.executable  # use same python interpreter
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
POLICY_PATH = os.path.join(BASE_DIR, "best_straight_policy.json")
# New path for storing history and saved simulations
SIM_STORAGE_PATH = os.path.join(BASE_DIR, "sim_storage.json")

# Global process handle (to support stop)
_current_proc = None
_proc_lock = threading.Lock()


def load_config():
    """Loads the main application configuration."""
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


# Add this function to backend_wrapper.py
def load_final_telemetry():
    """Helper to load the *last run's* telemetry from the live file."""
    # This path must match the one in simulation_code.py
    tele_path = os.path.join(BASE_DIR, "telemetry.json")
    try:
        with open(tele_path, "r") as f:
            return json.load(f)
    except Exception:
        # Return empty data if file not found or corrupt
        return {"time": [], "velocity": [], "power": []}


def save_config(new_data):
    """Saves the main application configuration."""
    with open(CONFIG_PATH, "w") as f:
        json.dump(new_data, f, indent=2)


# --- Simulation Storage Functions (New) ---

def _get_default_storage():
    """Returns the default structure for simulation storage."""
    return {
        "history": [],  # Last 5 unsaved runs
        "saved": []  # User-saved runs
    }


def _load_storage():
    """Loads all simulation data from the storage file."""
    if not os.path.exists(SIM_STORAGE_PATH):
        return _get_default_storage()
    try:
        with open(SIM_STORAGE_PATH, "r") as f:
            return json.load(f)
    except Exception:
        # If file is corrupted, return default
        return _get_default_storage()


def _save_storage(data):
    """Saves all simulation data to the storage file."""
    with open(SIM_STORAGE_PATH, "w") as f:
        json.dump(data, f, indent=2)


def save_simulation_result(result_data, is_saved=False, name=None):
    """
    Saves a simulation result to history (max 5) or to the saved list.
    result_data should contain: {"summary": ..., "policy": ...}
    """
    storage = _load_storage()
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

    entry = {
        "id": str(uuid.uuid4()),
        "name": name if name else f"History Run {timestamp}",
        "timestamp": timestamp,
        "summary": result_data["summary"],
        "policy": result_data["policy"]
    }

    if is_saved:
        storage["saved"].insert(0, entry)  # Add to the top
    else:
        # Add to history, maintain max size of 5
        storage["history"].insert(0, entry)
        storage["history"] = storage["history"][:5]

    _save_storage(storage)
    return entry


def load_all_simulations():
    """Loads all history and saved simulations for the UI."""
    return _load_storage()


# --- Process Streaming and Running ---

def _stream_process(proc, callback):
    """
    Read stdout/stderr lines from proc and forward to callback.
    callback(msg: str, progress: float, done: bool)
    """
    try:
        # use non-blocking line iteration
        for line in proc.stdout:
            if not line:
                continue
            text = line.decode(errors="replace") if isinstance(line, bytes) else str(line)
            text = text.rstrip("\n")

            # Simple progress parsing for GA
            if "GA Gen " in text:
                try:
                    parts = text.split(" ")
                    gen_index = parts.index("Gen")
                    current_gen = int(parts[gen_index + 1].split("/")[0])
                    total_gen = int(parts[gen_index + 1].split("/")[1])
                    progress = current_gen / total_gen * 0.5  # GA is 0.0 to 0.5
                    callback(text, progress, False)
                except:
                    callback(text, 0.0, False)
            else:
                callback(text, 0.0, False)

    except Exception as e:
        callback(f"Streaming error: {e}", 0.0, True)


def _run_process_and_stream(cmd, callback, is_sim=False, success_msg="Process finished successfully."):
    """Helper to run a subprocess and stream output."""
    global _current_proc

    with _proc_lock:
        if _current_proc is not None:
            callback("Error: Another process is already running.", 0.0, True)
            return None

        _current_proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=False,
            cwd=BASE_DIR
        )
        proc = _current_proc

    _stream_thread = threading.Thread(target=_stream_process, args=(proc, callback))
    _stream_thread.start()

    # The streaming thread handles progress. Wait for process to finish
    proc.wait()

    # Special handling for simulation result retrieval
    if is_sim:
        try:
            # The simulation script writes its final JSON result to a known file
            result_path = os.path.join(BASE_DIR, "live_stream", "final_result.json")
            with open(result_path, "r") as f:
                sim_result = json.load(f)

            # Save to history automatically (Policy is contained in sim_result)
            save_simulation_result(sim_result, is_saved=False)

            # Final callback with the result data (policy is removed here for cleaner status display)
            del sim_result["policy"]
            callback({"final_result": sim_result["summary"]}, 1.0, True)

        except Exception as e:
            callback(f"Simulation finished, but failed to retrieve results: {e}", 1.0, True)

    else:
        # Standard callback for GA or sequential processes
        if proc.returncode == 0:
            callback(success_msg, 1.0, True)
        else:
            callback(f"Process failed with return code {proc.returncode}.", 1.0, True)

    with _proc_lock:
        if proc == _current_proc:
            _current_proc = None

    return proc


def run_simulation_async(callback=None):
    """Run the simulation code."""
    cmd = [PYTHON, os.path.join(BASE_DIR, "simulation_code.py"), "--run_sim"]
    threading.Thread(target=_run_process_and_stream, args=(cmd, callback, True, "Simulation finished.")).start()


def run_ga_async(callback=None):
    """Run the GA optimization code."""
    cmd = [PYTHON, os.path.join(BASE_DIR, "simulation_ai.py"), "--run_ga"]
    threading.Thread(target=_run_process_and_stream, args=(cmd, callback, False, "GA optimization finished.")).start()


def run_both_async(callback=None):
    """Run GA, wait for it to finish, then run simulation (sequentially)."""

    def seq_worker():
        if callback:
            callback("Starting GA optimization...", 0.0, False)

        # Run GA
        cmd_ga = [PYTHON, os.path.join(BASE_DIR, "simulation_ai.py"), "--run_ga"]
        p1 = _run_process_and_stream(cmd_ga, callback)
        if p1 and p1.returncode != 0:
            callback("GA failed. Stopping sequence.", 1.0, True)
            return

        if callback:
            callback("GA finished. Starting simulation...", 0.5, False)

        # Run Simulation (this will handle saving the result automatically)
        cmd_sim = [PYTHON, os.path.join(BASE_DIR, "simulation_code.py"), "--run_sim"]
        _run_process_and_stream(cmd_sim, callback, is_sim=True, success_msg="Simulation finished.")

    threading.Thread(target=seq_worker).start()


def stop_current_process():
    """Attempts to stop the current running subprocess."""
    global _current_proc

    with _proc_lock:
        if _current_proc is None:
            return False

        try:
            # Use SIGINT (Ctrl+C equivalent) for a clean stop
            os.kill(_current_proc.pid, signal.SIGINT)
            # Give it a moment to stop
            time.sleep(0.5)
            if _current_proc.poll() is None:
                # If still running, force kill
                _current_proc.terminate()
                _current_proc.wait()
            _current_proc = None
            return True
        except Exception:
            return False


# --- Telemetry Streaming (Existing) ---

import glob
import base64

tele_path = os.path.join(BASE_DIR, "live_stream", "telemetry.json")
last_len = 0
last_frame = ""


def stream_telemetry(callback=None):
    """Streams live telemetry data (JSON) and latest frame (PNG)."""
    global last_len, last_frame

    while True:
        try:
            # Read newest telemetry
            if os.path.exists(tele_path):
                with open(tele_path, "r") as f:
                    tele = json.load(f)
                if len(tele["time"]) > last_len:
                    last_len = len(tele["time"])
                    callback({"telemetry": tele}, 0.0, False)
            # Read newest frame
            frames = sorted(glob.glob(os.path.join(BASE_DIR, "live_stream", "frame_*.png")))
            if frames:
                newest = frames[-1]
                if newest != last_frame:
                    last_frame = newest
                    with open(newest, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode("ascii")
                    callback({"frame": b64}, 0.0, False)
        except Exception:
            # Silence errors during streaming, which can be frequent during I/O conflicts
            pass
        time.sleep(0.2)


def start_telemetry_stream(callback):
    """Starts the telemetry streaming thread."""
    threading.Thread(target=stream_telemetry, args=(callback,), daemon=True).start()