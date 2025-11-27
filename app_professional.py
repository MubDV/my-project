import flet as ft
import json
import os
import threading
from typing import Optional

import backend_wrapper as backend
from design_system import ThemeColors, Spacing, BorderRadius, Typography, Button
from pages import SimulatorPageNew, ParametersPageNew, GAControlPageNew, DashboardPageNew

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")


class AppState:
    def __init__(self):
        self.current_page = "dashboard"
        self.simulation_running = False
        self.ga_running = False


class ProfessionalEVSimApp:
    def __init__(self):
        self.app_state = AppState()
        self.page = None
        self.main_content = None
        self.nav_buttons = {}

    def build_header(self):
        header = ft.Container(
            content=ft.Row(
                [
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.ELECTRIC_CAR, size=28, color=ThemeColors.PRIMARY),
                            Typography.heading_1("EV SIM Pro", color=ThemeColors.PRIMARY),
                        ],
                        spacing=Spacing.MD,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Container(expand=True),
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.CHECK_CIRCLE, size=20, color=ThemeColors.ACCENT_SUCCESS),
                            Typography.body_small("System Ready", ThemeColors.ACCENT_SUCCESS),
                        ],
                        spacing=Spacing.SM,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=Spacing.LG,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=Spacing.LG, vertical=Spacing.MD),
            bgcolor=ThemeColors.BG_SECONDARY,
            border_bottom=ft.border.only(bottom=ft.BorderSide(1, ThemeColors.BORDER)),
        )
        return header

    def build_navigation(self):
        nav_items = [
            ("dashboard", ft.Icons.HOME, "Dashboard"),
            ("simulator", ft.Icons.PLAY_CIRCLE_OUTLINED, "Simulator"),
            ("parameters", ft.Icons.TUNE, "Parameters"),
            ("ga", ft.Icons.AUTO_AWESOME, "GA Optimizer"),
        ]

        def create_nav_button(page_key, icon, label):
            def on_nav(e):
                self.navigate_to_page(page_key)

            self.nav_buttons[page_key] = ft.Container(
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
            return self.nav_buttons[page_key]

        nav_column = ft.Column(
            [create_nav_button(pk, ic, lb) for pk, ic, lb in nav_items],
            spacing=Spacing.SM,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Container(height=Spacing.LG),
                    ft.Row(
                        [
                            ft.Icon(ft.Icons.ELECTRIC_CAR, size=32, color=ThemeColors.PRIMARY),
                        ],
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                    Typography.heading_2("EV SIM", color=ThemeColors.PRIMARY),
                    ft.Divider(color=ThemeColors.BORDER, height=Spacing.LG),
                    nav_column,
                    ft.Container(expand=True),
                    ft.Divider(color=ThemeColors.BORDER, height=Spacing.LG),
                    ft.Container(
                        content=Typography.body_small("© 2025 Team Envision", color=ThemeColors.TEXT_TERTIARY),
                        alignment=ft.alignment.center,
                    ),
                ],
                spacing=Spacing.MD,
                alignment=ft.MainAxisAlignment.START,
            ),
            width=220,
            bgcolor=ThemeColors.BG_SECONDARY,
            padding=Spacing.LG,
            border_radius=BorderRadius.LARGE,
        )

    def update_nav_active(self, page_key):
        for key, btn in self.nav_buttons.items():
            if key == page_key:
                btn.bgcolor = ThemeColors.BG_TERTIARY
                btn.border = ft.border.all(1, ThemeColors.PRIMARY)
            else:
                btn.bgcolor = ThemeColors.BG_SECONDARY
                btn.border = ft.border.all(1, ThemeColors.BG_SECONDARY)

    def navigate_to_page(self, page_key):
        self.app_state.current_page = page_key
        self.update_nav_active(page_key)

        if page_key == "dashboard":
            page_obj = DashboardPageNew()
        elif page_key == "simulator":
            page_obj = SimulatorPageNew()
        elif page_key == "parameters":
            page_obj = ParametersPageNew()
        elif page_key == "ga":
            page_obj = GAControlPageNew()
        else:
            page_obj = DashboardPageNew()

        content = page_obj.build()
        self.main_content.content = content
        self.page.update()

    def run(self, page: ft.Page):
        self.page = page
        page.title = "EV SIM - Professional Edition"
        page.theme_mode = ft.ThemeMode.DARK
        page.bgcolor = ThemeColors.BG_PRIMARY
        page.window_width = 1500
        page.window_height = 950
        page.padding = 0
        page.window_min_width = 1200
        page.window_min_height = 700

        header = self.build_header()
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


def main(page: ft.Page):
    app = ProfessionalEVSimApp()
    app.run(page)


if __name__ == "__main__":
    ft.app(target=main)
