import flet as ft
import json
import os
from typing import Optional
import backend_wrapper as backend
import threading
import base64
import io

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

# Re-introduce a lock to prevent concurrent writes that overwrite config
config_file_lock = threading.Lock()

# Constants for view names
VIEW_SIMULATION = "simulation"
VIEW_PARAMETERS = "parameters"
VIEW_GA = "ga_settings"

# FIXED COLOR SCHEME: Define a professional color palette
COLOR_PRIMARY = "#00FF00"  # Bright Green for main accents/sliders
COLOR_BG_DEEP = "#0D1117"  # Main deep slate background
COLOR_CARD_DARK = "#161B22"  # Subtle background for cards/containers
COLOR_DIVIDER = "#3A404C"  # Soft, complementary blue-grey divider
COLOR_TEXT_PRIMARY = ft.Colors.WHITE
COLOR_TEXT_SECONDARY = ft.Colors.GREY_500
COLOR_INPUT_BG = "#1F242C"  # Background for input fields

# New Colors for Buttons and Glow Effect
COLOR_BUTTON_GREEN = "#00E000"  # Slightly subdued green for button background
COLOR_GLOW_GREEN = "#00FFC0"  # Bright, neon green for glow
COLOR_DANGER_RED = ft.Colors.RED_700  # Strong red for Stop button background
COLOR_GLOW_RED = ft.Colors.RED_ACCENT_400  # Bright red for Stop glow


# ---------------------------
# Helper: labeled text field
# ---------------------------
def labeled_text_field(page, label, value, suffix="", config_key: Optional[str] = None):
    label_text = ft.Text(label, color=COLOR_TEXT_PRIMARY, size=12, width=200)

    # Convert value to string based on type (non-boolean)
    if isinstance(value, float):
        # Format floats to 4 decimal places, stripping unnecessary zeros
        initial_value_str = f"{value:.4f}{suffix}".rstrip('0').rstrip('.')
    else:
        initial_value_str = f"{value}{suffix}"

    value_field = ft.TextField(
        value=initial_value_str,
        width=150,
        text_align=ft.TextAlign.RIGHT,
        border_color=COLOR_DIVIDER,
        color=COLOR_TEXT_PRIMARY,
        bgcolor=COLOR_INPUT_BG,
        content_padding=ft.padding.only(left=6, right=6),
        text_style=ft.TextStyle(size=12)
        
    )

    def _read_config_safe():
        """Read config file, return dict (never None)."""
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _atomic_write_config(cfg):
        """Write cfg atomically to CONFIG_PATH using temp file + os.replace."""
        tmp_path = CONFIG_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_PATH)

    def save_to_config(v):
        if not config_key:
            return

        txt_clean = str(v).replace(suffix, "").strip()
        # Determine numeric type if possible
        new_v = None
        try:
            if txt_clean.lower() in ("true", "false"):
                new_v = txt_clean.lower() == "true"
            elif "." in txt_clean or "e" in txt_clean.lower():
                new_v = float(txt_clean)
            else:
                # attempt int, fallback to float if necessary
                new_v = int(txt_clean)
        except ValueError:
            try:
                new_v = float(txt_clean)
            except ValueError:
                # Not a number — store raw string only if the existing key wasn't numeric
                new_v = txt_clean

        # Atomic read/modify/write under lock to avoid overwriting config from other threads
        with config_file_lock:
            cfg = _read_config_safe()
            cfg[config_key] = new_v
            try:
                _atomic_write_config(cfg)
            except Exception as e:
                # Silently ignore write failure but log to console for debugging
                print(f"Error writing config: {e}")

    def on_field_submit(e):
        save_to_config(e.control.value)

        txt = e.control.value.replace(suffix, "").strip()
        try:
            v = float(txt)
            # If it's an integer-like float and input didn't contain '.' or 'e', display as int
            if v == int(v) and "." not in txt and "e" not in txt.lower():
                value_field.value = f"{int(round(v))}{suffix}"
            else:
                value_field.value = f"{v:.4f}{suffix}".rstrip('0').rstrip('.')
        except ValueError:
            # keep user's input unchanged if parsing fails
            pass
        page.update()

    value_field.on_submit = on_field_submit
    value_field.on_blur = on_field_submit

    row = ft.Container(
        content=ft.Row(
            [label_text, value_field],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
        padding=ft.padding.symmetric(vertical=8, horizontal=10),
        margin=ft.margin.only(bottom=2),
        bgcolor=COLOR_CARD_DARK,
        border_radius=ft.border_radius.all(4),
        border=ft.border.all(1, COLOR_DIVIDER)
    )
    return row


# ---------------------------
# Helper: labeled toggle switch
# ---------------------------
def labeled_switch(page, label, value, config_key: Optional[str] = None):
    label_text = ft.Text(label, color=COLOR_TEXT_PRIMARY, size=12, width=200)

    switch_control = ft.Switch(value=bool(value), active_color=COLOR_PRIMARY)

    def _read_config_safe():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _atomic_write_config(cfg):
        tmp_path = CONFIG_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_PATH)

    def save_to_config(v):
        if not config_key:
            return

        with config_file_lock:
            cfg = _read_config_safe()
            cfg[config_key] = bool(v)
            try:
                _atomic_write_config(cfg)
            except Exception as e:
                print(f"Error writing config: {e}")

    def on_switch_change(e):
        save_to_config(e.control.value)
        page.update()

    switch_control.on_change = on_switch_change

    row = ft.Container(
        content=ft.Row(
            [label_text, switch_control],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
        padding=ft.padding.symmetric(vertical=8, horizontal=10),
        margin=ft.margin.only(bottom=2),
        bgcolor=COLOR_CARD_DARK,
        border_radius=ft.border_radius.all(4),
        border=ft.border.all(1, COLOR_DIVIDER)
    )
    return row


# ---------------------------
# Helper: labeled slider row
# ---------------------------
def labeled_slider(page, label, minv, maxv, value, divisions=None, suffix="", fmt="{:.3f}",
                   config_key: Optional[str] = None):
    label_text = ft.Text(label, color=COLOR_TEXT_PRIMARY, size=12, width=170)
    initial_value = float(value)
    # Detect integer format by checking fmt string containing no decimal spec
    if "{:.0f}" in fmt or fmt.endswith(".0f}"):
        initial_value_str = f"{int(round(initial_value))}{suffix}"
    else:
        initial_value_str = fmt.format(initial_value) + suffix

    value_field = ft.TextField(
        value=initial_value_str,
        width=100,
        text_align=ft.TextAlign.RIGHT,
        border_color=COLOR_DIVIDER,
        color=COLOR_TEXT_PRIMARY,
        bgcolor=COLOR_INPUT_BG,
        content_padding=ft.padding.only(left=6, right=6),
        text_style=ft.TextStyle(size=12)
    )
    slider = ft.Slider(
        min=minv,
        max=maxv,
        divisions=divisions,
        value=initial_value,
        expand=True,
        active_color=COLOR_PRIMARY,
        inactive_color="#404040",
    )

    def _read_config_safe():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _atomic_write_config(cfg):
        tmp_path = CONFIG_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, CONFIG_PATH)

    def save_to_config(v):
        if not config_key:
            return
        try:
            val = float(v)
        except Exception:
            return

        with config_file_lock:
            cfg = _read_config_safe()
            # preserve integerness if fmt requests integer
            if "{:.0f}" in fmt or fmt.endswith(".0f}"):
                cfg[config_key] = int(round(val))
            else:
                cfg[config_key] = val
            try:
                _atomic_write_config(cfg)
            except Exception as e:
                print(f"Error writing config: {e}")

    def on_slider_change(e):
        v = e.control.value
        if "{:.0f}" in fmt or fmt.endswith(".0f}"):
            value_field.value = f"{int(round(v))}{suffix}"
        else:
            value_field.value = fmt.format(v) + suffix
        save_to_config(v)
        page.update()

    def on_field_submit(e):
        txt = e.control.value.replace(suffix, "").strip()
        try:
            v = float(txt)
            v = max(minv, min(maxv, v))
            slider.value = v
            if "{:.0f}" in fmt or fmt.endswith(".0f}"):
                value_field.value = f"{int(round(v))}{suffix}"
            else:
                value_field.value = fmt.format(v) + suffix
            save_to_config(v)
            page.update()
        except Exception:
            pass

    slider.on_change = on_slider_change
    value_field.on_submit = on_field_submit
    value_field.on_blur = on_field_submit

    row = ft.Container(
        content=ft.Row(
            [label_text, slider, value_field],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
        padding=ft.padding.symmetric(vertical=8, horizontal=10),
        margin=ft.margin.only(bottom=2),
        bgcolor=COLOR_CARD_DARK,
        border_radius=ft.border_radius.all(4),
        border=ft.border.all(1, COLOR_DIVIDER)
    )
    return row, slider, value_field


# ---------------------------
# Chart Pop-out Modal Logic
# ---------------------------
def open_chart_dialog(page, chart_title: str, chart_data_series: list):
    """
    Creates and shows a modal dialog with a larger version of the clicked chart.
    """

    min_y_val = 0
    max_y_val = 100
    all_points = []
    if chart_data_series:
        for series in chart_data_series:
            if series.data_points:
                all_points.extend([dp.y for dp in series.data_points])

    if all_points:
        min_y_val = min(all_points) * 0.9
        max_y_val = max(all_points) * 1.1

    expanded_chart = ft.LineChart(
        data_series=chart_data_series,
        expand=True,
        min_y=min_y_val,
        max_y=max_y_val,
        tooltip_bgcolor=ft.Colors.BLACK,
        chart_title=ft.Text(chart_title, size=24, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY,
                            text_align=ft.TextAlign.CENTER)
    )

    def close_dialog():
        page.dialog.open = False
        page.update()

    close_button = ft.ElevatedButton("Close", on_click=lambda e: close_dialog(), bgcolor=COLOR_PRIMARY)

    chart_container = ft.Container(
        content=ft.Column(
            [
                expanded_chart,
                ft.Container(height=10),
                ft.Row([close_button], alignment=ft.MainAxisAlignment.END),
            ],
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH
        ),
        padding=20,
        bgcolor=COLOR_BG_DEEP,
        border_radius=10,
        width=800,
        height=600,
    )

    dialog = ft.AlertDialog(
        modal=True,
        content=chart_container,
        content_padding=0,
        bgcolor=COLOR_BG_DEEP,
    )

    page.dialog = dialog
    dialog.open = True
    page.update()


# ---------------------------
# Main app
# ---------------------------
def main(page: ft.Page):
    page.title = "EV SIM - Envision Console"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = COLOR_BG_DEEP
    page.window_width = 1200
    page.window_height = 720
    page.scroll = False
    page.padding = 0

    # --- UI Components defined globally/before use ---

    right_velocity_chart = ft.LineChart(
        data_series=[],
        height=250,
        tooltip_bgcolor=ft.Colors.BLACK,
        expand=True
    )
    right_power_chart = ft.LineChart(
        data_series=[],
        height=250,
        tooltip_bgcolor=ft.Colors.BLACK,
        expand=True
    )

    def on_velocity_chart_click(e):
        open_chart_dialog(page, "Final Vehicle Speed (km/h) vs. Time (s)", right_velocity_chart.data_series)

    def on_power_chart_click(e):
        open_chart_dialog(page, "Final Power Consumption (kW) vs. Time (s)", right_power_chart.data_series)

    velocity_container = ft.Container(
        content=right_velocity_chart,
        bgcolor=COLOR_CARD_DARK,
        padding=12,
        border_radius=ft.border_radius.all(8),
        expand=True,
        on_click=on_velocity_chart_click,
        tooltip="Click to view full-size chart"
    )

    power_container = ft.Container(
        content=right_power_chart,
        bgcolor=COLOR_CARD_DARK,
        padding=12,
        border_radius=ft.border_radius.all(8),
        expand=True,
        on_click=on_power_chart_click,
        tooltip="Click to view full-size chart"
    )

    chart_row = ft.Row(
        [
            ft.Column([
                ft.Text("Speed vs. Time", size=14, color=ft.Colors.GREY_300),
                velocity_container
            ], expand=True, spacing=5),
            ft.Column([
                ft.Text("Power vs. Time (kW)", size=14, color=ft.Colors.GREY_300),
                power_container
            ], expand=True, spacing=5),
        ],
        spacing=15,
        expand=True,
    )

    # ---------- Simulation View (History + Charts) ----------

    history_list_view = ft.ListView(expand=True, spacing=5, auto_scroll=False)

    chart_column = ft.Column(
        [
            ft.Text("Final Telemetry Plots", size=18, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
            ft.Text("Select a run from the history list or run a new simulation.", color=COLOR_TEXT_SECONDARY, size=12),
            ft.Container(height=10),
            chart_row,
        ],
        expand=True,
        alignment=ft.MainAxisAlignment.START,
    )

    simulation_view = ft.Container(
        content=ft.Row(
            [
                # Column for the History List
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text("Simulation History", size=16, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
                            ft.Divider(color=COLOR_DIVIDER),
                            history_list_view
                        ],
                        spacing=5
                    ),
                    width=300,
                    padding=10,
                    bgcolor=COLOR_CARD_DARK,
                    border_radius=ft.border_radius.all(8),
                    border=ft.border.all(1, COLOR_DIVIDER)
                ),
                ft.VerticalDivider(width=1, color="transparent"),
                # Column for the charts
                chart_column
            ],
            expand=True,
            vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            spacing=15
        ),
        expand=True
    )

    # --- Helper: Populate Charts ---
    def populate_charts_from_data(telemetry_data):
        if telemetry_data and telemetry_data.get("time"):
            try:
                power_kw = [p / 1000.0 for p in telemetry_data["power"]]

                vel_series = [
                    ft.LineChartData(
                        data_points=[ft.LineChartDataPoint(x, y) for x, y in
                                     zip(telemetry_data["time"], telemetry_data["velocity"])],
                        color=COLOR_PRIMARY,
                        stroke_width=2.5,
                    )
                ]
                pow_series = [
                    ft.LineChartData(
                        data_points=[ft.LineChartDataPoint(x, y) for x, y in
                                     zip(telemetry_data["time"], power_kw)],
                        color=ft.Colors.ORANGE,
                        stroke_width=2.5,
                    )
                ]
                right_velocity_chart.data_series = vel_series
                right_power_chart.data_series = pow_series

                max_v = max(telemetry_data["velocity"]) * 1.1 if telemetry_data["velocity"] else 50
                max_p = max(power_kw) * 1.1 if power_kw else 10
                max_t = max(telemetry_data["time"]) if telemetry_data["time"] else 100

                right_velocity_chart.min_y = 0
                right_velocity_chart.max_y = max_v
                right_velocity_chart.min_x = 0
                right_velocity_chart.max_x = max_t

                right_power_chart.min_y = 0
                right_power_chart.max_y = max_p
                right_power_chart.min_x = 0
                right_power_chart.max_x = max_t

            except Exception as e:
                print(f"Error populating charts: {e}")
                right_velocity_chart.data_series = []
                right_power_chart.data_series = []
        else:
            right_velocity_chart.data_series = []
            right_power_chart.data_series = []
        page.update()

    # --- Helper: Load History List ---
    def load_history():
        history_list_view.controls.clear()
        try:
            sim_data = backend.load_all_simulations()
        except Exception as e:
            history_list_view.controls.append(ft.Text(f"Error loading history: {e}", color=ft.Colors.RED))
            page.update()
            return

        def create_run_click_handler(run_data):
            def on_run_click(e):
                # Highlight the selected run
                for ctrl in history_list_view.controls:
                    if isinstance(ctrl, ft.Container):
                        # Reset all to default
                        ctrl.bgcolor = COLOR_CARD_DARK
                        ctrl.border = ft.border.all(1, COLOR_DIVIDER)

                # Set selected item to highlighted style
                e.control.bgcolor = ft.Colors.with_opacity(0.15, COLOR_PRIMARY)
                e.control.border = ft.border.all(1, COLOR_PRIMARY)

                # Update charts
                populate_charts_from_data(run_data["summary"])

            return on_run_click

        history_list_view.controls.append(
            ft.Text("RECENT UNSAVED RUNS", weight=ft.FontWeight.BOLD, size=11, color=COLOR_TEXT_SECONDARY))
        history_list_view.controls.append(ft.Divider(height=5, color=COLOR_DIVIDER))

        # Helper to create a history item
        def create_history_item(run):
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text(run["name"], size=13, weight=ft.FontWeight.W_600, color=COLOR_TEXT_PRIMARY),
                        ft.Text(run["timestamp"], size=11, color=ft.Colors.GREY_400),
                    ],
                    spacing=2
                ),
                padding=8,
                margin=ft.margin.only(bottom=5),
                border_radius=5,
                bgcolor=COLOR_CARD_DARK,  # Default background
                border=ft.border.all(1, COLOR_DIVIDER),  # Default border
                on_click=create_run_click_handler(run),
                hover_color=ft.Colors.WHITE10
            )

        for run in sim_data.get("history", []):
            history_list_view.controls.append(create_history_item(run))

        if sim_data.get("saved"):
            history_list_view.controls.append(ft.Container(height=10))  # Spacer
            history_list_view.controls.append(
                ft.Text("SAVED BEST POLICIES", weight=ft.FontWeight.BOLD, size=11, color=COLOR_TEXT_SECONDARY))
            history_list_view.controls.append(ft.Divider(height=5, color=COLOR_DIVIDER))
            for run in sim_data.get("saved", []):
                history_list_view.controls.append(create_history_item(run))

        if not sim_data.get("history") and not sim_data.get("saved"):
            history_list_view.controls.append(ft.Text("No simulations run yet.", italic=True, color=ft.Colors.GREY_600))

        page.update()

    # ---------- Sidebar (History/Console) ----------
    sidebar_visible = True
    console_box = ft.Column([], spacing=4, expand=True, auto_scroll=True)
    sidebar_column = ft.Column(
        [
            # === LOGO REPLACING TEXT ===
            ft.Row([
                ft.Image(
                    src="Team-Envision-Logo.webp",
                    height=30,
                    width=170,  # Adjusted width for horizontal logo look
                    fit=ft.ImageFit.CONTAIN
                ),
                ft.Container(expand=True)  # Ensure it aligns left
            ], vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
            # =======================
            ft.Divider(color=COLOR_DIVIDER, height=20),
            ft.Text("Debug Console", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
            ft.Container(
                content=console_box,
                expand=True,
                padding=5,
                bgcolor="#000000",
                border_radius=4
            )
        ],
        spacing=6,
        expand=True,
        scroll=ft.ScrollMode.AUTO,
    )
    sidebar_container = ft.Container(
        content=sidebar_column,
        width=200,  # Reduced width from 250 to 200
        bgcolor="#12161D",  # Distinct dark slate background
        border_radius=ft.border_radius.only(top_right=8, bottom_right=8),
        padding=ft.padding.symmetric(vertical=12, horizontal=12),
        alignment=ft.alignment.top_left,
    )

    def toggle_sidebar(e):
        nonlocal sidebar_visible
        sidebar_visible = not sidebar_visible
        sidebar_container.visible = sidebar_visible
        page.update()

    # ---------- Status & Progress ----------
    status_text = ft.Text("Ready to simulate", size=12, color=ft.Colors.GREY_400)
    progress = ft.ProgressBar(width=300, bgcolor="#222222", color=COLOR_PRIMARY, value=0)

    # Helper function to update the glow shadow color opacity
    def update_glow(container, is_disabled, glow_color):
        if container and container.shadow:
            opacity = 0.7 if not is_disabled else 0.1
            # Assuming the shadow is a list of BoxShadows
            container.shadow[0].color = ft.Colors.with_opacity(opacity, glow_color)

    def append_console(msg: str):
        MAX_LINES = 200
        console_box.controls.append(ft.Text(msg, size=11, color="#DDDDDD", selectable=True))
        if len(console_box.controls) > MAX_LINES:
            console_box.controls[:] = console_box.controls[-MAX_LINES:]
        console_box.scroll_to(offset=-1, duration=100)
        page.update()

    def backend_callback(msg, prog, done):
        # Flet handles thread safety by allowing page.update() to be called from a background thread.

        if isinstance(msg, dict):
            return

        status_text.value = msg
        if prog > 0:
            progress.value = prog

        append_console(msg)

        if "Simulation complete" in msg or "Final telemetry data saved" in msg:
            try:
                tele = backend.load_final_telemetry()
                populate_charts_from_data(tele)
                load_history()
            except Exception as e:
                append_console(f"Error loading final telemetry: {e}")

        if done:
            start_button.disabled = False
            start_ga_button.disabled = False
            run_both_button.disabled = False
            stop_button.disabled = True
            progress.value = 0
            status_text.value = "Process finished. Ready."

        # --- GLOW UPDATE LOGIC ---
        update_glow(start_button_container, start_button.disabled, COLOR_GLOW_GREEN)
        update_glow(start_ga_button_container, start_ga_button.disabled, COLOR_GLOW_GREEN)
        update_glow(run_both_button_container, run_both_button.disabled, COLOR_GLOW_GREEN)
        update_glow(stop_button_container, stop_button.disabled, COLOR_GLOW_RED)

        page.update()

    # --- Parameter setup (Code is the same here) ---
    config_values = backend.load_config()

    # 1. Physical Parameters
    param_rows_physical = [
        labeled_slider(page, "Mass (kg)", 100, 2000, config_values.get("car_mass_kg", 120), divisions=190, fmt="{:.0f}",
                       config_key="car_mass_kg")[0],
        labeled_slider(page, "Frontal Area (m²)", 0.1, 5, config_values.get("car_frontal_area_m2", 0.8), divisions=49,
                       fmt="{:.3f}", config_key="car_frontal_area_m2")[0],
        labeled_slider(page, "Drag Coefficient (Cd)", 0.05, 0.6, config_values.get("drag_coefficient", 0.22),
                       divisions=55, fmt="{:.3f}", config_key="drag_coefficient")[0],
        labeled_slider(page, "Rolling Resistance Coeff.", 0.005, 0.1,
                       config_values.get("rolling_resistance_coefficient", 0.02), divisions=95, fmt="{:.4f}",
                       config_key="rolling_resistance_coefficient")[0],
    ]

    # 2. Drivetrain & Constraints
    param_rows_drivetrain = [
        labeled_slider(page, "Motor Max Power (W)", 100, 300000, config_values.get("motor_max_power_watts", 900),
                       divisions=300, fmt="{:.0f}", config_key="motor_max_power_watts")[0],
        labeled_slider(page, "Motor Max Drive Force (N)", 50, 500,
                       config_values.get("motor_max_drive_force_newton", 92), divisions=450, fmt="{:.0f}",
                       config_key="motor_max_drive_force_newton")[0],
        labeled_slider(page, "Brake Max Force (N)", 100, 1000, config_values.get("brake_max_force_newton", 400),
                       divisions=900, fmt="{:.0f}", config_key="brake_max_force_newton")[0],
        labeled_slider(page, "Drivetrain Efficiency", 0.5, 1.0, config_values.get("drivetrain_efficiency", 0.78),
                       divisions=50, fmt="{:.3f}", config_key="drivetrain_efficiency")[0],
        labeled_slider(page, "Wheel Radius (m)", 0.05, 0.6, config_values.get("wheel_radius_m", 0.2), divisions=55,
                       fmt="{:.3f}", config_key="wheel_radius_m")[0],
        labeled_slider(page, "Gear Ratio", 1, 10, config_values.get("gear_ratio", 9), divisions=9, fmt="{:.0f}",
                       config_key="gear_ratio")[0],
    ]

    # 3. Objective & Limits
    param_rows_limits = [
        labeled_slider(page, "Max Vehicle Speed (km/h)", 20, 100, config_values.get("maximum_vehicle_speed_kmh", 32),
                       divisions=80, fmt="{:.0f}", config_key="maximum_vehicle_speed_kmh")[0],
        labeled_text_field(page, "Target Avg Speed - Lower (km/h)",
                           config_values.get("target_average_speed_lower_kmh", 24.0),
                           config_key="target_average_speed_lower_kmh"),
        labeled_text_field(page, "Target Avg Speed - Upper (km/h)",
                           config_values.get("target_average_speed_upper_kmh", 27.0),
                           config_key="target_average_speed_upper_kmh"),
        labeled_text_field(page, "Launch Phase Speed (m/s)", config_values.get("launch_phase_speed_mps", 1.5),
                           config_key="launch_phase_speed_mps"),
        labeled_text_field(page, "Safe Corner Speed (km/h)", config_values.get("safe_corner_speed_kmh", 99.0),
                           config_key="safe_corner_speed_kmh"),
        labeled_text_field(page, "Lap Time Limit (min)", config_values.get("lap_time_limit_minutes", 30),
                           config_key="lap_time_limit_minutes"),
        labeled_text_field(page, "Total Laps to Simulate", config_values.get("total_laps_to_simulate", 4),
                           config_key="total_laps_to_simulate"),
    ]

    # 4. Simulation Constants/Timing
    param_rows_constants = [
        labeled_text_field(page, "Gravity (m/s²)", config_values.get("gravity_mps2", 9.81), config_key="gravity_mps2"),
        labeled_text_field(page, "Air Density (kg/m³)", config_values.get("air_density_kgpm3", 1.225),
                           config_key="air_density_kgpm3"),
        labeled_text_field(page, "Simulation Time Step (s)", config_values.get("simulation_time_step_seconds", 0.9),
                           config_key="simulation_time_step_seconds"),
        labeled_text_field(page, "Animation Refresh Interval (ms)",
                           config_values.get("animation_refresh_interval_ms", 1),
                           config_key="animation_refresh_interval_ms"),
        labeled_switch(page, "Stop animation after finish", config_values.get("stop_after_finish", True),
                       config_key="stop_after_finish"),
    ]

    def create_card(title, rows):
        return ft.Card(
            ft.Container(
                ft.Column(
                    [
                        ft.Text(title, size=16, weight=ft.FontWeight.BOLD, color=COLOR_PRIMARY),
                        ft.Divider(height=10, color=COLOR_DIVIDER)
                    ] + rows,
                    spacing=0
                ),
                padding=15
            ),
            margin=ft.margin.only(bottom=15),
            color=COLOR_CARD_DARK
        )

    parameters_column = ft.Column(
        [
            ft.Text("Vehicle & Environment Parameters", size=18, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
            ft.Text("Modify vehicle properties and simulation constants.", color=COLOR_TEXT_SECONDARY, size=12),
            ft.Divider(height=10, color=COLOR_DIVIDER),

            create_card("1. Physical Properties", param_rows_physical),
            create_card("2. Drivetrain & Constraints", param_rows_drivetrain),
            create_card("3. Objective & Simulation Limits", param_rows_limits),
            create_card("4. Constants & Timing", param_rows_constants),
        ],
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # ---------- GA settings tab ----------
    ga_rows = [
        labeled_slider(page, "Generations", 10, 200, config_values.get("ga_generations", 40), divisions=190,
                       fmt="{:.0f}", config_key="ga_generations")[0],
        labeled_slider(page, "Population Size", 10, 500, config_values.get("ga_population_size", 36), divisions=490,
                       fmt="{:.0f}", config_key="ga_population_size")[0],
        labeled_slider(page, "Mutation Rate", 0.001, 0.5, config_values.get("ga_mutation_rate", 0.12), divisions=500,
                       fmt="{:.3f}", config_key="ga_mutation_rate")[0],
        labeled_slider(page, "Crossover Rate", 0.1, 1.0, config_values.get("ga_crossover_rate", 0.9), divisions=90,
                       fmt="{:.2f}", config_key="ga_crossover_rate")[0],
        labeled_slider(page, "Elite Count", 0, 10, config_values.get("ga_elite_count", 2), divisions=10, fmt="{:.0f}",
                       config_key="ga_elite_count")[0],
        labeled_text_field(page, "GA Time Step (s)", config_values.get("ga_time_step_seconds", 0.2),
                           config_key="ga_time_step_seconds")
    ]

    ga_column = ft.Column(
        [
            ft.Text("Genetic Algorithm Settings", size=18, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
            ft.Text("Configure population size, mutation, and evaluation timing.", color=COLOR_TEXT_SECONDARY, size=12),
            ft.Divider(height=10, color=COLOR_DIVIDER),

            create_card("GA Optimization Core Settings", ga_rows)
        ],
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # ---------- Custom Tab Selectors ----------
    current_view = VIEW_SIMULATION

    main_content = ft.Container(
        content=ft.Container(simulation_view, padding=15),
        expand=True,
        padding=ft.padding.only(top=10, bottom=10),
        border_radius=ft.border_radius.all(8),
        border=ft.border.all(1, COLOR_DIVIDER)
    )

    tab_sim_ref = ft.Ref[ft.Container]()
    tab_params_ref = ft.Ref[ft.Container]()
    tab_ga_ref = ft.Ref[ft.Container]()

    def change_view(new_view):
        nonlocal current_view
        current_view = new_view

        if current_view == VIEW_SIMULATION:
            content_column = simulation_view
        elif current_view == VIEW_PARAMETERS:
            content_column = parameters_column
        else:
            content_column = ga_column

        main_content.content = ft.Container(content_column, padding=15)

        for tab_ref, view_key in [
            (tab_sim_ref, VIEW_SIMULATION),
            (tab_params_ref, VIEW_PARAMETERS),
            (tab_ga_ref, VIEW_GA)
        ]:
            is_selected = (view_key == current_view)
            tab_container = tab_ref.current
            if not tab_container: continue

            tab_container.border = ft.border.only(
                bottom=ft.BorderSide(3, COLOR_PRIMARY if is_selected else ft.Colors.TRANSPARENT)
            )
            tab_container.content.controls[0].color = COLOR_TEXT_PRIMARY if is_selected else COLOR_TEXT_SECONDARY

        page.update()

    def create_tab_selector(label, view_key, ref):
        text_control = ft.Text(label, size=14, weight=ft.FontWeight.W_500, color=COLOR_TEXT_SECONDARY)
        return ft.Container(
            ref=ref,
            content=ft.Row(
                [text_control],
                alignment=ft.MainAxisAlignment.CENTER
            ),
            padding=ft.padding.symmetric(vertical=12, horizontal=20),
            on_click=lambda e: change_view(view_key),
            data=view_key,
        )

    tab_sim = create_tab_selector("Simulation & Results", VIEW_SIMULATION, tab_sim_ref)
    tab_params = create_tab_selector("Vehicle Parameters", VIEW_PARAMETERS, tab_params_ref)
    tab_ga = create_tab_selector("GA Optimization Settings", VIEW_GA, tab_ga_ref)

    # --- Button Logic (Threaded) ---

    def on_run_both(e):
        start_button.disabled = True
        start_ga_button.disabled = True
        run_both_button.disabled = True
        stop_button.disabled = False
        progress.value = None
        status_text.value = "Starting GA..."

        # GLOW UPDATE
        update_glow(start_button_container, True, COLOR_GLOW_GREEN)
        update_glow(start_ga_button_container, True, COLOR_GLOW_GREEN)
        update_glow(run_both_button_container, True, COLOR_GLOW_GREEN)
        update_glow(stop_button_container, False, COLOR_GLOW_RED)

        page.update()
        threading.Thread(target=backend.run_both_async, args=(backend_callback,), daemon=True).start()

    def on_run_ga(e):
        start_button.disabled = True
        start_ga_button.disabled = True
        run_both_button.disabled = True
        stop_button.disabled = False
        progress.value = None
        status_text.value = "Starting GA optimization..."

        # GLOW UPDATE
        update_glow(start_button_container, True, COLOR_GLOW_GREEN)
        update_glow(start_ga_button_container, True, COLOR_GLOW_GREEN)
        update_glow(run_both_button_container, True, COLOR_GLOW_GREEN)
        update_glow(stop_button_container, False, COLOR_GLOW_RED)

        page.update()
        threading.Thread(target=backend.run_ga_async, args=(backend_callback,), daemon=True).start()

    def on_run_sim(e):
        start_button.disabled = True
        start_ga_button.disabled = True
        run_both_button.disabled = True
        stop_button.disabled = False
        progress.value = None
        status_text.value = "Starting simulation..."

        # GLOW UPDATE
        update_glow(start_button_container, True, COLOR_GLOW_GREEN)
        update_glow(start_ga_button_container, True, COLOR_GLOW_GREEN)
        update_glow(run_both_button_container, True, COLOR_GLOW_GREEN)
        update_glow(stop_button_container, False, COLOR_GLOW_RED)

        page.update()
        threading.Thread(target=backend.run_simulation_async, args=(backend_callback,), daemon=True).start()

    def on_stop(e):
        append_console("Attempting to stop process...")
        stopped = backend.stop_current_process()
        append_console("Stop requested." if stopped else "No process was running.")
        stop_button.disabled = True

        # GLOW UPDATE
        update_glow(stop_button_container, True, COLOR_GLOW_RED)

        page.update()

    # Use vibrant Colors for buttons to stand out against the dark background.
    button_style_green = ft.ButtonStyle(padding=12, shape=ft.RoundedRectangleBorder(radius=6),
                                        color=ft.Colors.BLACK)  # Black text on bright green
    button_style_red = ft.ButtonStyle(padding=12, shape=ft.RoundedRectangleBorder(radius=6),
                                      color=ft.Colors.WHITE)  # White text on red

    # Helper to wrap the button in a container with a glowing shadow
    def create_glow_container(button_control, glow_color):
        return ft.Container(
            content=button_control,
            # Apply glow effect using BoxShadow
            shadow=[
                ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=15,
                    # Initial opacity will be set later in main()
                    color=ft.Colors.with_opacity(0.1, glow_color),
                    offset=ft.Offset(0, 0),
                    blur_style=ft.ShadowBlurStyle.OUTER,
                )
            ],
            border_radius=6,
        )

    # 1. Define the actual ElevatedButtons (Controls)
    start_button = ft.ElevatedButton("Run Simulation",
                                     icon=ft.Icons.PLAY_ARROW_ROUNDED,
                                     bgcolor=COLOR_BUTTON_GREEN,
                                     on_click=on_run_sim, style=button_style_green)

    start_ga_button = ft.ElevatedButton("Run GA Optimization",
                                        icon=ft.Icons.INSIGHTS_ROUNDED,
                                        bgcolor=COLOR_BUTTON_GREEN,
                                        on_click=on_run_ga, style=button_style_green)

    run_both_button = ft.ElevatedButton("GA → Simulation",
                                        icon=ft.Icons.DOUBLE_ARROW_ROUNDED,
                                        bgcolor=COLOR_BUTTON_GREEN,
                                        on_click=on_run_both, style=button_style_green)

    stop_button = ft.ElevatedButton("Stop Process",
                                    icon=ft.Icons.STOP_ROUNDED,
                                    bgcolor=COLOR_DANGER_RED,
                                    on_click=on_stop, disabled=True,
                                    style=button_style_red)

    # 2. Define the Containers with Glow (Wrappers)
    start_button_container = create_glow_container(start_button, COLOR_GLOW_GREEN)
    start_ga_button_container = create_glow_container(start_ga_button, COLOR_GLOW_GREEN)
    run_both_button_container = create_glow_container(run_both_button, COLOR_GLOW_GREEN)
    stop_button_container = create_glow_container(stop_button, COLOR_GLOW_RED)

    # 3. Control Bar uses the new Containers
    control_bar = ft.Container(
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [start_button_container, start_ga_button_container, run_both_button_container,
                         stop_button_container],
                        spacing=15,
                        alignment=ft.MainAxisAlignment.START,
                        wrap=True
                    ),
                    padding=ft.padding.only(bottom=5)
                ),
                ft.Divider(height=1, color=COLOR_DIVIDER),
                ft.Row([ft.Text("Status:", size=12, color=COLOR_TEXT_SECONDARY),
                        status_text,
                        progress],
                       spacing=10,
                       vertical_alignment=ft.CrossAxisAlignment.CENTER,
                       alignment=ft.MainAxisAlignment.START),
            ],
            spacing=8,
        ),
        margin=ft.margin.only(top=10, bottom=10),
        padding=ft.padding.symmetric(vertical=10, horizontal=15),
        bgcolor=COLOR_CARD_DARK,
        border_radius=ft.border_radius.all(8),
        border=ft.border.all(1, COLOR_DIVIDER)
    )

    # --- HEADER/TITLE/TOGGLE ---

    # 1. Title Row (now just title and toggle)
    title_row = ft.Row([
        ft.Text("Simulator Dashboard", size=20, weight=ft.FontWeight.BOLD, color=COLOR_TEXT_PRIMARY),
        ft.Container(expand=True),  # Spacer to push next elements to the right
        # Console Retractor Button remains here
        ft.IconButton(icon=ft.Icons.MENU_ROUNDED, icon_size=20, on_click=toggle_sidebar,
                      icon_color=COLOR_TEXT_SECONDARY, tooltip="Toggle Debug Console"),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    # 2. Tabs Row
    tabs_row = ft.Row(
        [tab_sim, tab_params, tab_ga],
        spacing=0,
        alignment=ft.MainAxisAlignment.START,
    )

    main_area = ft.Container(
        content=ft.Column([
            ft.Container(
                content=title_row,
                padding=ft.padding.only(top=10, bottom=10)
            ),
            # Divider setup for "stop short" effect:
            ft.Row([
                # Divider constrained to the width of the tabs
                ft.Container(
                    content=ft.Divider(height=1, color=COLOR_DIVIDER, thickness=1),
                    width=600,  # A fixed width that covers the tabs (adjust as needed if needed)
                ),
                ft.Container(expand=True)  # Fills the rest of the horizontal space
            ], spacing=0),

            tabs_row,
            ft.Divider(height=1, color=COLOR_DIVIDER, thickness=1),  # Divider below tabs
            control_bar,
            main_content
        ],
            expand=True,
            spacing=0),
        expand=True,
        padding=ft.padding.only(left=20, right=20, top=10),
        bgcolor=COLOR_BG_DEEP,
    )

    left_divider = ft.VerticalDivider(width=1, color="transparent")

    # ---------- Layout ----------
    layout = ft.Row(
        [sidebar_container, left_divider, main_area],
        expand=True,
        spacing=0,
        vertical_alignment=ft.CrossAxisAlignment.STRETCH,
    )

    # ---------- Initialize the view ----------
    page.add(layout)

    update_glow(start_button_container, start_button.disabled, COLOR_GLOW_GREEN)
    update_glow(start_ga_button_container, start_ga_button.disabled, COLOR_GLOW_GREEN)
    update_glow(run_both_button_container, run_both_button.disabled, COLOR_GLOW_GREEN)
    update_glow(stop_button_container, stop_button.disabled, COLOR_GLOW_RED)

    change_view(VIEW_SIMULATION)
    load_history()


# Run app
if __name__ == "__main__":
    ft.app(target=main)
