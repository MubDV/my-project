import flet as ft
import json
import os
import threading
import time
from typing import Optional

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
    LoadingSpinner,
)
from visualization import TrackVisualization, TelemetryChart, MetricRow, StatusBadge

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

config_file_lock = threading.Lock()


class AppState:
    def __init__(self):
        self.current_page = "dashboard"
        self.simulation_running = False
        self.ga_running = False
        self.current_telemetry = None
        self.simulation_history = []


class SimulatorPage:
    def __init__(self, app_state: AppState, page: ft.Page):
        self.app_state = app_state
        self.page = page
        self.simulation_data = {
            "time": [],
            "velocity": [],
            "power": [],
            "state": [],
        }

    def build(self):
        track_vis = TrackVisualization(np.array([[0, 0], [100, 0], [100, 100], [0, 100]]), width=400, height=350)
        vel_chart = TelemetryChart("Speed (km/h)", "Speed", ThemeColors.CHART_LINE_1, "km/h", width=None)
        power_chart = TelemetryChart("Power (kW)", "Power", ThemeColors.CHART_LINE_2, "kW", width=None)

        status_text = Typography.body("Ready to simulate", ThemeColors.TEXT_SECONDARY)
        progress_bar = ft.ProgressBar(value=0, color=ThemeColors.PRIMARY, bgcolor=ThemeColors.BG_TERTIARY)

        lap_stat = StatCard("Current Lap", "1", "", ft.Icons.TRACK_CHANGES, ThemeColors.PRIMARY)
        speed_stat = StatCard("Speed", "0", "km/h", ft.Icons.SPEED, ThemeColors.ACCENT_SUCCESS)
        energy_stat = StatCard("Energy Used", "0", "kWh", ft.Icons.FLASH_ON, ThemeColors.ACCENT_WARNING)

        telemetry_panel = ft.Column(
            [
                MetricRow("Lap", "1/4", "", "Speed", "0 km/h"),
                MetricRow("Avg Speed", "0 km/h", "", "Distance", "0 m"),
                MetricRow("Power", "0 kW", "", "Energy", "0 kWh"),
                MetricRow("State", "Ready", "", "Stops", "0/2"),
            ],
            spacing=Spacing.MD,
        )

        def on_start_simulation(e):
            self.app_state.simulation_running = True

        def on_stop_simulation(e):
            self.app_state.simulation_running = False

        def on_start_ga(e):
            self.app_state.ga_running = True

        buttons_row = ft.Row(
            [
                Button.primary("Run Simulation", on_click=on_start_simulation, icon=ft.Icons.PLAY_ARROW),
                Button.primary("Run GA", on_click=on_start_ga, icon=ft.Icons.INSIGHTS),
                Button.danger("Stop", on_click=on_stop_simulation, icon=ft.Icons.STOP),
            ],
            spacing=Spacing.MD,
            wrap=True,
        )

        return ft.Column(
            [
                SectionHeader("Live Simulator", "Monitor your EV in real-time"),
                ft.Row(
                    [
                        ft.Column(
                            [
                                Card(track_vis),
                                ft.Column(
                                    [
                                        speed_stat,
                                        energy_stat,
                                    ],
                                    spacing=Spacing.MD,
                                ),
                            ],
                            spacing=Spacing.MD,
                            width=450,
                        ),
                        ft.Column(
                            [
                                Card(telemetry_panel, padding=Spacing.MD),
                                vel_chart,
                                power_chart,
                            ],
                            spacing=Spacing.MD,
                            expand=True,
                        ),
                    ],
                    spacing=Spacing.LG,
                    expand=True,
                ),
                Card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    status_text,
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
                ),
            ],
            spacing=Spacing.LG,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )


class ParametersPage:
    def __init__(self, page: ft.Page):
        self.page = page

    def build(self):
        config = self._load_config()

        physical_props = ft.Column(
            [
                SliderField("Mass (kg)", 100, 2000, config.get("car_mass_kg", 120)),
                SliderField("Frontal Area (m²)", 0.1, 5, config.get("car_frontal_area_m2", 0.8)),
                SliderField("Drag Coefficient", 0.05, 0.6, config.get("drag_coefficient", 0.22)),
                SliderField("Rolling Resistance", 0.005, 0.1, config.get("rolling_resistance_coefficient", 0.02)),
            ],
            spacing=Spacing.MD,
        )

        drivetrain_props = ft.Column(
            [
                SliderField("Motor Max Power (W)", 100, 300000, config.get("motor_max_power_watts", 900)),
                SliderField("Max Drive Force (N)", 50, 500, config.get("motor_max_drive_force_newton", 92)),
                SliderField("Max Brake Force (N)", 100, 1000, config.get("brake_max_force_newton", 400)),
                SliderField("Drivetrain Efficiency", 0.5, 1.0, config.get("drivetrain_efficiency", 0.78)),
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
                            physical_props,
                        ],
                        spacing=Spacing.LG,
                    )
                ),
                Card(
                    ft.Column(
                        [
                            Typography.heading_3("Drivetrain & Constraints", ThemeColors.PRIMARY),
                            drivetrain_props,
                        ],
                        spacing=Spacing.LG,
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


class GAControlPage:
    def __init__(self, page: ft.Page):
        self.page = page

    def build(self):
        config = self._load_config()

        ga_settings = ft.Column(
            [
                SliderField("Generations", 10, 200, config.get("ga_generations", 40)),
                SliderField("Population Size", 10, 500, config.get("ga_population_size", 36)),
                SliderField("Mutation Rate", 0.001, 0.5, config.get("ga_mutation_rate", 0.12)),
                SliderField("Crossover Rate", 0.1, 1.0, config.get("ga_crossover_rate", 0.9)),
            ],
            spacing=Spacing.MD,
        )

        progress = ProgressIndicator("Generation Progress", 0, 40, ThemeColors.ACCENT_SUCCESS)

        return ft.Column(
            [
                SectionHeader("Genetic Algorithm", "Optimize your driving policy"),
                Card(
                    ft.Column(
                        [
                            Typography.heading_3("GA Configuration", ThemeColors.PRIMARY),
                            ga_settings,
                        ],
                        spacing=Spacing.LG,
                    )
                ),
                Card(progress),
                Card(
                    ft.Row(
                        [
                            Button.primary("Start Optimization", icon=ft.Icons.PLAY_ARROW),
                            Button.secondary("View Results", icon=ft.Icons.ASSESSMENT),
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


class DashboardPage:
    def __init__(self, app_state: AppState, page: ft.Page):
        self.app_state = app_state
        self.page = page

    def build(self):
        recent_runs = ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                Typography.body("Last Run"),
                                Typography.heading_3("28.5 km/h", ThemeColors.PRIMARY),
                                Typography.body_small("2.5 kWh used"),
                            ]
                        ),
                        ft.Column(
                            [
                                Typography.body("Best Efficiency"),
                                Typography.heading_3("0.089", ThemeColors.ACCENT_SUCCESS),
                                Typography.body_small("kWh/km"),
                            ]
                        ),
                    ],
                    spacing=Spacing.LG,
                ),
            ],
            spacing=Spacing.MD,
        )

        quick_actions = ft.Row(
            [
                ft.Column(
                    [
                        ft.Icon(ft.Icons.PLAY_ARROW, size=32, color=ThemeColors.PRIMARY),
                        Typography.body_small("Run Simulation"),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=Spacing.SM,
                ),
                ft.Column(
                    [
                        ft.Icon(ft.Icons.INSIGHTS, size=32, color=ThemeColors.ACCENT_SUCCESS),
                        Typography.body_small("Run GA"),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=Spacing.SM,
                ),
                ft.Column(
                    [
                        ft.Icon(ft.Icons.SETTINGS, size=32, color=ThemeColors.ACCENT_WARNING),
                        Typography.body_small("Configure"),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=Spacing.SM,
                ),
            ],
            spacing=Spacing.LG,
        )

        return ft.Column(
            [
                SectionHeader("Welcome Back", "Your EV Simulation Dashboard"),
                Card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    StatCard("Simulations Run", "12", icon=ft.Icons.ASSESSMENT, color=ThemeColors.PRIMARY),
                                    StatCard("GA Optimizations", "3", icon=ft.Icons.AUTO_AWESOME, color=ThemeColors.ACCENT_SUCCESS),
                                    StatCard("Best Speed", "29.2", "km/h", icon=ft.Icons.SPEED, color=ThemeColors.ACCENT_WARNING),
                                ],
                                spacing=Spacing.MD,
                            ),
                        ]
                    )
                ),
                Card(
                    ft.Column(
                        [Typography.heading_3("Quick Actions"), quick_actions],
                        spacing=Spacing.LG,
                    )
                ),
                Card(
                    ft.Column(
                        [
                            Typography.heading_3("Recent Simulations"),
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


class MainApp:
    def __init__(self):
        self.app_state = AppState()
        self.page = None

    def build_navigation(self):
        nav_items = [
            ("dashboard", ft.Icons.HOME, "Dashboard"),
            ("simulator", ft.Icons.PLAY_CIRCLE, "Simulator"),
            ("parameters", ft.Icons.TUNE, "Parameters"),
            ("ga", ft.Icons.AUTO_AWESOME, "GA Optimizer"),
        ]

        def create_nav_button(page_key, icon, label):
            def on_nav(e):
                self.app_state.current_page = page_key
                self.navigate_to_page(page_key)

            return ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(icon, size=20, color=ThemeColors.TEXT_SECONDARY),
                        Typography.body(label),
                    ],
                    spacing=Spacing.MD,
                ),
                padding=ft.padding.symmetric(horizontal=Spacing.LG, vertical=Spacing.MD),
                on_click=on_nav,
                hover_color=ThemeColors.BG_TERTIARY,
                border_radius=BorderRadius.MEDIUM,
            )

        nav_column = ft.Column(
            [create_nav_button(pk, ic, lb) for pk, ic, lb in nav_items],
            spacing=Spacing.SM,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Icon(ft.Icons.ELECTRIC_CAR, size=32, color=ThemeColors.PRIMARY),
                    Typography.heading_2("EV SIM"),
                    ft.Divider(color=ThemeColors.BORDER, height=Spacing.LG),
                    nav_column,
                ],
                spacing=Spacing.LG,
                alignment=ft.MainAxisAlignment.START,
            ),
            width=200,
            bgcolor=ThemeColors.BG_SECONDARY,
            padding=Spacing.LG,
            border_radius=BorderRadius.LARGE,
        )

    def navigate_to_page(self, page_key):
        content_area = self.page.clean()

        if page_key == "dashboard":
            page = DashboardPage(self.app_state, self.page)
        elif page_key == "simulator":
            page = SimulatorPage(self.app_state, self.page)
        elif page_key == "parameters":
            page = ParametersPage(self.page)
        elif page_key == "ga":
            page = GAControlPage(self.page)
        else:
            page = DashboardPage(self.app_state, self.page)

        content = page.build()
        self.page.add(content)
        self.page.update()

    def run(self, page: ft.Page):
        self.page = page
        page.title = "EV SIM - Professional Edition"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = ThemeColors.BG_PRIMARY
        page.window_width = 1400
        page.window_height = 900
        page.padding = 0

        header = ft.Container(
            content=ft.Row(
                [
                    Typography.heading_1("EV SIM Pro"),
                    ft.Container(expand=True),
                    Typography.body_small("Status: Ready", ThemeColors.ACCENT_SUCCESS),
                ],
                spacing=Spacing.LG,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=Spacing.LG, vertical=Spacing.MD),
            bgcolor=ThemeColors.BG_SECONDARY,
            border_bottom=ft.border.only(bottom=ft.BorderSide(1, ThemeColors.BORDER)),
        )

        navigation = self.build_navigation()

        self.main_content = ft.Container(
            expand=True,
            padding=Spacing.LG,
            content=ft.Column(),
        )

        body = ft.Row(
            [
                navigation,
                ft.VerticalDivider(width=1, color=ThemeColors.BORDER),
                self.main_content,
            ],
            expand=True,
            spacing=0,
        )

        page.add(
            ft.Column(
                [header, body],
                expand=True,
                spacing=0,
            )
        )

        self.navigate_to_page("dashboard")


import numpy as np


def main(page: ft.Page):
    app = MainApp()
    app.run(page)


if __name__ == "__main__":
    ft.app(target=main)
