import flet as ft
import math
import numpy as np
from design_system import ThemeColors, Spacing, BorderRadius, Typography


class TrackVisualization(ft.Container):
    def __init__(self, track_points, width=500, height=400):
        self.track_points = track_points
        self.vehicle_pos = None
        self.stops = []
        self.trail_points = []
        self.width = width
        self.height = height

        self.canvas = ft.canvas.Canvas()
        self.paint_track()

        super().__init__(
            content=self.canvas,
            width=width,
            height=height,
            bgcolor=ThemeColors.BG_TERTIARY,
            border_radius=BorderRadius.MEDIUM,
            border=ft.border.all(1, ThemeColors.BORDER),
            padding=Spacing.MD,
        )

    def paint_track(self):
        if not self.track_points or len(self.track_points) < 2:
            return

        points = self.track_points
        xs = points[:, 0]
        ys = points[:, 1]

        min_x, max_x = xs.min(), xs.max()
        min_y, max_y = ys.min(), ys.max()

        margin = 20
        self.x_scale = (self.width - 2 * margin) / (max_x - min_x) if max_x != min_x else 1
        self.y_scale = (self.height - 2 * margin) / (max_y - min_y) if max_y != min_y else 1
        self.x_offset = margin - min_x * self.x_scale
        self.y_offset = margin - min_y * self.y_scale

        self.min_x = min_x
        self.min_y = min_y

        for i in range(len(points) - 1):
            x1 = points[i][0] * self.x_scale + self.x_offset
            y1 = points[i][1] * self.y_scale + self.y_offset
            x2 = points[i + 1][0] * self.x_scale + self.x_offset
            y2 = points[i + 1][1] * self.y_scale + self.y_offset

            self.canvas.stroke_color = ThemeColors.BORDER_LIGHT
            self.canvas.stroke_width = 2
            self.canvas.line(x1, y1, x2, y2)

        start_x = points[0][0] * self.x_scale + self.x_offset
        start_y = points[0][1] * self.y_scale + self.y_offset
        self.canvas.fill_color = ThemeColors.ACCENT_SUCCESS
        self.canvas.fill_rect(start_x - 5, start_y - 5, 10, 10)

    def update_vehicle_position(self, x, y, state=""):
        if not hasattr(self, "x_scale"):
            return

        self.vehicle_pos = (x, y)
        canvas_x = x * self.x_scale + self.x_offset
        canvas_y = y * self.y_scale + self.y_offset

        if len(self.trail_points) > 0:
            prev_x, prev_y = self.trail_points[-1]
            if "Brake" in state or "Stop" in state:
                color = ThemeColors.ACCENT_ERROR
            elif "Throttle" in state or "Launch" in state:
                color = ThemeColors.ACCENT_SUCCESS
            else:
                color = ThemeColors.CHART_LINE_1

            self.canvas.stroke_color = color
            self.canvas.stroke_width = 3
            self.canvas.line(prev_x, prev_y, canvas_x, canvas_y)

        self.trail_points.append((canvas_x, canvas_y))

        if len(self.trail_points) > 1000:
            self.trail_points = self.trail_points[-1000:]

        self.canvas.fill_color = ThemeColors.ACCENT_INFO
        self.canvas.fill_circle(canvas_x, canvas_y, 4)

    def update_stops(self, stop_positions):
        if not hasattr(self, "x_scale"):
            return

        self.stops = []
        for stop_x, stop_y in stop_positions:
            canvas_x = stop_x * self.x_scale + self.x_offset
            canvas_y = stop_y * self.y_scale + self.y_offset
            self.stops.append((canvas_x, canvas_y))

            self.canvas.stroke_color = ThemeColors.ACCENT_WARNING
            self.canvas.stroke_width = 2
            self.canvas.draw_line(
                ft.Paint(stroke_width=2, color=ThemeColors.ACCENT_WARNING)
            )
            self.canvas.fill_color = ThemeColors.ACCENT_WARNING
            self.canvas.fill_circle(canvas_x, canvas_y, 6)

    def clear_trail(self):
        self.trail_points = []
        self.paint_track()


class TelemetryChart(ft.Container):
    def __init__(self, title, series_label, series_color, y_label, width=None, height=200):
        self.title = title
        self.series_label = series_label
        self.series_color = series_color
        self.y_label = y_label
        self.data_points = []
        self.height = height

        self.canvas = ft.canvas.Canvas()

        super().__init__(
            content=ft.Column(
                [
                    Typography.body(title, ThemeColors.TEXT_PRIMARY),
                    self.canvas,
                ],
                spacing=Spacing.SM,
            ),
            width=width,
            height=height + 40,
            bgcolor=ThemeColors.BG_SECONDARY,
            border_radius=BorderRadius.MEDIUM,
            border=ft.border.all(1, ThemeColors.BORDER),
            padding=Spacing.LG,
        )

    def add_data_point(self, x, y):
        self.data_points.append((x, y))
        self.redraw()

    def redraw(self):
        if len(self.data_points) < 2:
            return

        xs = np.array([p[0] for p in self.data_points])
        ys = np.array([p[1] for p in self.data_points])

        min_x, max_x = 0, max(xs) if len(xs) > 0 else 1
        min_y, max_y = 0, max(ys) * 1.1 if len(ys) > 0 else 1

        margin = 40
        width = self.canvas.width - 2 * margin
        height = self.height - 2 * margin

        self.canvas.stroke_color = ThemeColors.BORDER
        self.canvas.stroke_width = 1

        self.canvas.line(margin, margin, margin, self.height - margin)
        self.canvas.line(margin, self.height - margin, self.canvas.width - margin, self.height - margin)

        x_scale = width / (max_x - min_x) if max_x != min_x else 1
        y_scale = height / (max_y - min_y) if max_y != min_y else 1

        self.canvas.stroke_color = self.series_color
        self.canvas.stroke_width = 2

        for i in range(len(self.data_points) - 1):
            x1 = margin + (xs[i] - min_x) * x_scale
            y1 = self.height - margin - (ys[i] - min_y) * y_scale
            x2 = margin + (xs[i + 1] - min_x) * x_scale
            y2 = self.height - margin - (ys[i + 1] - min_y) * y_scale

            self.canvas.line(x1, y1, x2, y2)

    def clear(self):
        self.data_points = []


class MetricRow(ft.Container):
    def __init__(self, label, value, unit="", secondary_label="", secondary_value="", color=ThemeColors.PRIMARY):
        elements = [
            ft.Row(
                [
                    Typography.body_small(label, ThemeColors.TEXT_SECONDARY),
                    ft.Container(expand=True),
                    ft.Row(
                        [
                            Typography.body(str(value), color),
                            Typography.body_small(unit, ThemeColors.TEXT_SECONDARY),
                        ],
                        spacing=Spacing.XS,
                    ),
                ],
                spacing=Spacing.MD,
            )
        ]

        if secondary_label:
            elements.append(
                ft.Row(
                    [
                        Typography.body_small(secondary_label, ThemeColors.TEXT_SECONDARY),
                        ft.Container(expand=True),
                        ft.Row(
                            [
                                Typography.body(str(secondary_value), color),
                            ],
                            spacing=Spacing.XS,
                        ),
                    ],
                    spacing=Spacing.MD,
                )
            )

        super().__init__(
            content=ft.Column(elements, spacing=Spacing.SM),
            padding=ft.padding.symmetric(vertical=Spacing.MD, horizontal=Spacing.LG),
            bgcolor=ThemeColors.BG_TERTIARY,
            border_radius=BorderRadius.SMALL,
            border=ft.border.all(1, ThemeColors.BORDER),
        )


class StatusBadge(ft.Container):
    def __init__(self, status, status_type="info"):
        if status_type == "success":
            bg_color = ThemeColors.ACCENT_SUCCESS
        elif status_type == "error":
            bg_color = ThemeColors.ACCENT_ERROR
        elif status_type == "warning":
            bg_color = ThemeColors.ACCENT_WARNING
        else:
            bg_color = ThemeColors.PRIMARY

        super().__init__(
            content=Typography.label(status, ft.Colors.WHITE),
            padding=ft.padding.symmetric(horizontal=Spacing.MD, vertical=Spacing.XS),
            bgcolor=bg_color,
            border_radius=BorderRadius.SMALL,
        )
