import flet as ft
import json
import os
import threading
from typing import Callable

import backend_wrapper as backend
from design_system import (
    ThemeColors,
    Spacing,
    BorderRadius,
    Typography,
    Card,
    Button,
    StatCard,
    InputField,
    SliderField,
    SectionHeader,
    ProgressIndicator,
)
from visualization import TrackVisualization, TelemetryChart, MetricRow, StatusBadge
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


class SimulatorPageNew:
    def __init__(self, on_page_ready: Callable = None):
        self.on_page_ready = on_page_ready
        self.simulation_running = False
        self.ga_running = False
        self.telemetry_history = {"time": [], "velocity": [], "power": []}

    def build(self):
        track_vis = TrackVisualization(np.array([[0, 0], [100, 0], [100, 100], [0, 100]]), width=420, height=380)

        vel_chart = TelemetryChart("Vehicle Speed (km/h)", "Speed", ThemeColors.CHART_LINE_1, "km/h")
        power_chart = TelemetryChart("Power Output (kW)", "Power", ThemeColors.CHART_LINE_2, "kW")

        status_badge = StatusBadge("Ready", "success")
        progress_bar = ft.ProgressBar(value=0, color=ThemeColors.PRIMARY, bgcolor=ThemeColors.BG_TERTIARY, height=6)

        lap_stat = StatCard("Current Lap", "1/4", icon=ft.Icons.TRACK_CHANGES, color=ThemeColors.PRIMARY)
        speed_stat = StatCard("Speed", "0", "km/h", icon=ft.Icons.SPEED, color=ThemeColors.ACCENT_SUCCESS)
        energy_stat = StatCard("Energy Used", "0", "kWh", icon=ft.Icons.FLASH_ON, color=ThemeColors.ACCENT_WARNING)

        telemetry_panel = ft.Column(
            [
                MetricRow("Current Lap", "1/4", "", "Lap Time", "0:00"),
                MetricRow("Speed", "0 km/h", "", "Avg Speed", "0 km/h"),
                MetricRow("Power", "0 kW", "", "State", "Ready"),
                MetricRow("Distance", "0 m", "", "Stops", "0/2"),
            ],
            spacing=Spacing.MD,
        )

        def on_start_simulation(e):
            self.simulation_running = True
            status_badge.content = StatusBadge("Running...", "info").content
            self.page.update()

        def on_stop_simulation(e):
            self.simulation_running = False
            backend.stop_current_process()
            status_badge.content = StatusBadge("Stopped", "warning").content
            self.page.update()

        def on_start_ga(e):
            self.ga_running = True
            status_badge.content = StatusBadge("GA Running...", "info").content
            self.page.update()

        buttons_row = ft.Row(
            [
                Button.primary("Run Simulation", on_click=on_start_simulation, icon=ft.Icons.PLAY_ARROW),
                Button.primary("Run GA → Sim", on_click=on_start_ga, icon=ft.Icons.DOUBLE_ARROW),
                Button.danger("Stop", on_click=on_stop_simulation, icon=ft.Icons.STOP),
            ],
            spacing=Spacing.MD,
            wrap=True,
        )

        status_info = Card(
            ft.Column(
                [
                    ft.Row(
                        [
                            status_badge,
                            ft.Container(expand=True),
                            Typography.body_small("Progress", ThemeColors.TEXT_SECONDARY),
                        ],
                        spacing=Spacing.MD,
                    ),
                    progress_bar,
                    buttons_row,
                ],
                spacing=Spacing.MD,
            )
        )

        charts_column = ft.Column(
            [
                vel_chart,
                power_chart,
            ],
            spacing=Spacing.MD,
            expand=True,
        )

        visualization_row = ft.Row(
            [
                ft.Column(
                    [
                        Card(track_vis),
                        ft.Column(
                            [speed_stat, energy_stat],
                            spacing=Spacing.MD,
                        ),
                    ],
                    spacing=Spacing.MD,
                    width=480,
                ),
                ft.Column(
                    [
                        Card(telemetry_panel, padding=Spacing.MD),
                        charts_column,
                    ],
                    spacing=Spacing.MD,
                    expand=True,
                ),
            ],
            spacing=Spacing.LG,
            expand=True,
        )

        return ft.Column(
            [
                SectionHeader("Live Simulator", "Monitor your EV in real-time"),
                visualization_row,
                status_info,
            ],
            spacing=Spacing.LG,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )


class ParametersPageNew:
    def __init__(self):
        self.config = self._load_config()

    def build(self):
        physical_props = ft.Column(
            [
                SliderField("Mass (kg)", 100, 2000, self.config.get("car_mass_kg", 120)),
                SliderField("Frontal Area (m²)", 0.1, 5, self.config.get("car_frontal_area_m2", 0.8)),
                SliderField("Drag Coefficient", 0.05, 0.6, self.config.get("drag_coefficient", 0.22)),
                SliderField("Rolling Resistance", 0.005, 0.1, self.config.get("rolling_resistance_coefficient", 0.02)),
                SliderField("Wheel Radius (m)", 0.05, 0.6, self.config.get("wheel_radius_m", 0.2)),
                SliderField("Gear Ratio", 1, 10, self.config.get("gear_ratio", 9)),
            ],
            spacing=Spacing.MD,
        )

        drivetrain_props = ft.Column(
            [
                SliderField("Motor Max Power (W)", 100, 300000, self.config.get("motor_max_power_watts", 900)),
                SliderField("Max Drive Force (N)", 50, 500, self.config.get("motor_max_drive_force_newton", 92)),
                SliderField("Max Brake Force (N)", 100, 1000, self.config.get("brake_max_force_newton", 400)),
                SliderField("Drivetrain Efficiency", 0.5, 1.0, self.config.get("drivetrain_efficiency", 0.78)),
            ],
            spacing=Spacing.MD,
        )

        objective_props = ft.Column(
            [
                SliderField("Max Vehicle Speed (km/h)", 20, 100, self.config.get("maximum_vehicle_speed_kmh", 32)),
                SliderField("Target Avg Speed - Lower (km/h)", 15, 35, self.config.get("target_average_speed_lower_kmh", 24)),
                SliderField("Target Avg Speed - Upper (km/h)", 15, 35, self.config.get("target_average_speed_upper_kmh", 27)),
                SliderField("Safe Corner Speed (km/h)", 20, 100, self.config.get("safe_corner_speed_kmh", 99)),
            ],
            spacing=Spacing.MD,
        )

        return ft.Column(
            [
                SectionHeader("Vehicle Parameters", "Configure your EV's physical properties"),
                Card(
                    ft.Column(
                        [
                            Typography.heading_3("Physical Properties", ThemeColors.PRIMARY),
                            ft.Divider(color=ThemeColors.BORDER, height=Spacing.LG),
                            physical_props,
                        ],
                        spacing=Spacing.MD,
                    )
                ),
                Card(
                    ft.Column(
                        [
                            Typography.heading_3("Drivetrain & Constraints", ThemeColors.PRIMARY),
                            ft.Divider(color=ThemeColors.BORDER, height=Spacing.LG),
                            drivetrain_props,
                        ],
                        spacing=Spacing.MD,
                    )
                ),
                Card(
                    ft.Column(
                        [
                            Typography.heading_3("Objectives & Limits", ThemeColors.PRIMARY),
                            ft.Divider(color=ThemeColors.BORDER, height=Spacing.LG),
                            objective_props,
                        ],
                        spacing=Spacing.MD,
                    )
                ),
            ],
            spacing=Spacing.LG,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}


class GAControlPageNew:
    def __init__(self):
        self.config = self._load_config()
        self.ga_progress = ProgressIndicator("Generation Progress", 0, 40, ThemeColors.ACCENT_SUCCESS)

    def build(self):
        ga_settings = ft.Column(
            [
                SliderField("Generations", 10, 200, self.config.get("ga_generations", 40)),
                SliderField("Population Size", 10, 500, self.config.get("ga_population_size", 36)),
                SliderField("Mutation Rate", 0.001, 0.5, self.config.get("ga_mutation_rate", 0.12)),
                SliderField("Crossover Rate", 0.1, 1.0, self.config.get("ga_crossover_rate", 0.9)),
                SliderField("Elite Count", 0, 10, self.config.get("ga_elite_count", 2)),
                SliderField("GA Time Step (s)", 0.1, 1.0, self.config.get("ga_time_step_seconds", 0.2)),
            ],
            spacing=Spacing.MD,
        )

        stats_row = ft.Row(
            [
                StatCard("Best Fitness", "0.85", icon=ft.Icons.TRENDING_UP, color=ThemeColors.ACCENT_SUCCESS),
                StatCard("Current Gen", "0/40", icon=ft.Icons.ASSESSMENT, color=ThemeColors.PRIMARY),
                StatCard("Population", "36", icon=ft.Icons.GROUPS, color=ThemeColors.ACCENT_INFO),
            ],
            spacing=Spacing.MD,
        )

        def on_start_ga(e):
            pass

        def on_view_results(e):
            pass

        buttons_row = ft.Row(
            [
                Button.primary("Start Optimization", on_click=on_start_ga, icon=ft.Icons.PLAY_ARROW, width=300),
                Button.secondary("View Results", on_click=on_view_results, icon=ft.Icons.ASSESSMENT, width=300),
            ],
            spacing=Spacing.MD,
            wrap=True,
        )

        return ft.Column(
            [
                SectionHeader("Genetic Algorithm Optimizer", "Optimize your driving policy"),
                Card(
                    ft.Column(
                        [
                            Typography.heading_3("GA Configuration", ThemeColors.PRIMARY),
                            ft.Divider(color=ThemeColors.BORDER, height=Spacing.LG),
                            ga_settings,
                        ],
                        spacing=Spacing.MD,
                    )
                ),
                Card(stats_row),
                Card(self.ga_progress),
                Card(buttons_row),
            ],
            spacing=Spacing.LG,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

    def _load_config(self):
        try:
            with open(CONFIG_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}


class DashboardPageNew:
    def build(self):
        stats = ft.Row(
            [
                StatCard("Simulations Run", "12", icon=ft.Icons.ASSESSMENT, color=ThemeColors.PRIMARY),
                StatCard("GA Optimizations", "3", icon=ft.Icons.AUTO_AWESOME, color=ThemeColors.ACCENT_SUCCESS),
                StatCard("Best Efficiency", "0.089", "kWh/km", icon=ft.Icons.SPEED, color=ThemeColors.ACCENT_WARNING),
            ],
            spacing=Spacing.MD,
            wrap=True,
        )

        recent_runs = ft.Column(
            [
                Card(
                    ft.Row(
                        [
                            ft.Column(
                                [
                                    Typography.body_small("Last Run", ThemeColors.TEXT_SECONDARY),
                                    Typography.heading_2("28.5 km/h", ThemeColors.PRIMARY),
                                    Typography.body_small("2.5 kWh", ThemeColors.TEXT_SECONDARY),
                                ]
                            ),
                            ft.Container(expand=True),
                            ft.Column(
                                [
                                    ft.Icon(ft.Icons.CHECK_CIRCLE, size=32, color=ThemeColors.ACCENT_SUCCESS),
                                    Typography.body_small("Completed", ThemeColors.ACCENT_SUCCESS),
                                ]
                            ),
                        ],
                        spacing=Spacing.LG,
                    )
                ),
            ],
            spacing=Spacing.MD,
        )

        quick_actions = ft.Row(
            [
                Card(
                    ft.Column(
                        [
                            ft.Icon(ft.Icons.PLAY_ARROW, size=32, color=ThemeColors.PRIMARY),
                            Typography.body_small("Run Simulation"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=Spacing.SM,
                    ),
                    width=150,
                ),
                Card(
                    ft.Column(
                        [
                            ft.Icon(ft.Icons.INSIGHTS, size=32, color=ThemeColors.ACCENT_SUCCESS),
                            Typography.body_small("Run GA"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=Spacing.SM,
                    ),
                    width=150,
                ),
                Card(
                    ft.Column(
                        [
                            ft.Icon(ft.Icons.SETTINGS, size=32, color=ThemeColors.ACCENT_WARNING),
                            Typography.body_small("Configure"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=Spacing.SM,
                    ),
                    width=150,
                ),
                Card(
                    ft.Column(
                        [
                            ft.Icon(ft.Icons.ASSESSMENT, size=32, color=ThemeColors.CHART_LINE_1),
                            Typography.body_small("Results"),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=Spacing.SM,
                    ),
                    width=150,
                ),
            ],
            spacing=Spacing.MD,
            wrap=True,
        )

        return ft.Column(
            [
                SectionHeader("Dashboard", "Your EV Simulation Hub"),
                Card(stats),
                Card(
                    ft.Column(
                        [
                            Typography.heading_3("Quick Actions"),
                            quick_actions,
                        ],
                        spacing=Spacing.LG,
                    )
                ),
                Card(
                    ft.Column(
                        [
                            Typography.heading_3("Recent Activity"),
                            recent_runs,
                        ],
                        spacing=Spacing.LG,
                    )
                ),
            ],
            spacing=Spacing.LG,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
