import flet as ft

class ThemeColors:
    BG_PRIMARY = "#0F1117"
    BG_SECONDARY = "#161B22"
    BG_TERTIARY = "#21262D"

    PRIMARY = "#58A6FF"
    PRIMARY_DARK = "#1F6FEB"

    ACCENT_SUCCESS = "#3FB950"
    ACCENT_WARNING = "#D29922"
    ACCENT_ERROR = "#F85149"
    ACCENT_INFO = "#79C0FF"

    TEXT_PRIMARY = "#C9D1D9"
    TEXT_SECONDARY = "#8B949E"
    TEXT_TERTIARY = "#6E7681"

    BORDER = "#30363D"
    BORDER_LIGHT = "#444C56"

    CHART_LINE_1 = "#58A6FF"
    CHART_LINE_2 = "#3FB950"
    CHART_LINE_3 = "#D29922"
    CHART_FILL = "rgba(88, 166, 255, 0.1)"


class Spacing:
    XS = 4
    SM = 8
    MD = 12
    LG = 16
    XL = 24
    XXL = 32


class BorderRadius:
    SMALL = 6
    MEDIUM = 8
    LARGE = 12


class Typography:
    FONT_FAMILY = "Segoe UI"

    @staticmethod
    def heading_1(text, color=ThemeColors.TEXT_PRIMARY):
        return ft.Text(
            text,
            size=28,
            weight=ft.FontWeight.W_700,
            color=color,
            font_family=Typography.FONT_FAMILY,
        )

    @staticmethod
    def heading_2(text, color=ThemeColors.TEXT_PRIMARY):
        return ft.Text(
            text,
            size=22,
            weight=ft.FontWeight.W_600,
            color=color,
            font_family=Typography.FONT_FAMILY,
        )

    @staticmethod
    def heading_3(text, color=ThemeColors.TEXT_PRIMARY):
        return ft.Text(
            text,
            size=18,
            weight=ft.FontWeight.W_600,
            color=color,
            font_family=Typography.FONT_FAMILY,
        )

    @staticmethod
    def body_large(text, color=ThemeColors.TEXT_PRIMARY):
        return ft.Text(
            text,
            size=14,
            weight=ft.FontWeight.W_400,
            color=color,
            font_family=Typography.FONT_FAMILY,
        )

    @staticmethod
    def body(text, color=ThemeColors.TEXT_PRIMARY):
        return ft.Text(
            text,
            size=13,
            weight=ft.FontWeight.W_400,
            color=color,
            font_family=Typography.FONT_FAMILY,
        )

    @staticmethod
    def body_small(text, color=ThemeColors.TEXT_SECONDARY):
        return ft.Text(
            text,
            size=12,
            weight=ft.FontWeight.W_400,
            color=color,
            font_family=Typography.FONT_FAMILY,
        )

    @staticmethod
    def label(text, color=ThemeColors.TEXT_SECONDARY):
        return ft.Text(
            text,
            size=11,
            weight=ft.FontWeight.W_600,
            color=color,
            font_family=Typography.FONT_FAMILY,
        )


class Card(ft.Container):
    def __init__(self, content, padding=Spacing.LG, **kwargs):
        super().__init__(
            content=content,
            padding=padding,
            bgcolor=ThemeColors.BG_SECONDARY,
            border_radius=BorderRadius.MEDIUM,
            border=ft.border.all(1, ThemeColors.BORDER),
            **kwargs
        )


class Button:
    @staticmethod
    def primary(text, on_click=None, icon=None, width=None):
        return ft.ElevatedButton(
            text=text,
            on_click=on_click,
            icon=icon,
            width=width,
            bgcolor=ThemeColors.PRIMARY,
            color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                padding=Spacing.MD,
                shape=ft.RoundedRectangleBorder(radius=BorderRadius.MEDIUM),
            ),
        )

    @staticmethod
    def secondary(text, on_click=None, icon=None, width=None):
        return ft.OutlinedButton(
            text=text,
            on_click=on_click,
            icon=icon,
            width=width,
            style=ft.ButtonStyle(
                padding=Spacing.MD,
                shape=ft.RoundedRectangleBorder(radius=BorderRadius.MEDIUM),
                side=ft.BorderSide(1, ThemeColors.BORDER_LIGHT),
            ),
        )

    @staticmethod
    def danger(text, on_click=None, icon=None, width=None):
        return ft.ElevatedButton(
            text=text,
            on_click=on_click,
            icon=icon,
            width=width,
            bgcolor=ThemeColors.ACCENT_ERROR,
            color=ft.Colors.WHITE,
            style=ft.ButtonStyle(
                padding=Spacing.MD,
                shape=ft.RoundedRectangleBorder(radius=BorderRadius.MEDIUM),
            ),
        )

    @staticmethod
    def icon_button(icon, on_click=None, tooltip=None, size=24):
        return ft.IconButton(
            icon=icon,
            on_click=on_click,
            icon_size=size,
            icon_color=ThemeColors.TEXT_SECONDARY,
            tooltip=tooltip,
        )


class StatCard(ft.Container):
    def __init__(self, label, value, unit="", icon=None, color=ThemeColors.PRIMARY):
        content_elements = []

        if icon:
            content_elements.append(
                ft.Row(
                    [
                        ft.Icon(icon, size=20, color=color),
                        Typography.body_small(label, ThemeColors.TEXT_SECONDARY),
                    ],
                    spacing=Spacing.SM,
                )
            )
        else:
            content_elements.append(
                Typography.body_small(label, ThemeColors.TEXT_SECONDARY)
            )

        content_elements.append(
            ft.Row(
                [
                    Typography.heading_2(str(value), color),
                    Typography.body(unit, ThemeColors.TEXT_SECONDARY) if unit else ft.Container(),
                ],
                spacing=Spacing.SM,
                vertical_alignment=ft.CrossAxisAlignment.BASELINE,
            )
        )

        super().__init__(
            content=ft.Column(content_elements, spacing=Spacing.SM),
            padding=Spacing.LG,
            bgcolor=ThemeColors.BG_SECONDARY,
            border_radius=BorderRadius.MEDIUM,
            border=ft.border.all(1, ThemeColors.BORDER),
        )


class InputField(ft.TextField):
    def __init__(self, label, value="", **kwargs):
        super().__init__(
            label=label,
            value=str(value),
            bgcolor=ThemeColors.BG_TERTIARY,
            border_color=ThemeColors.BORDER,
            focused_border_color=ThemeColors.PRIMARY,
            color=ThemeColors.TEXT_PRIMARY,
            label_style=ft.TextStyle(color=ThemeColors.TEXT_SECONDARY),
            text_style=ft.TextStyle(size=13, color=ThemeColors.TEXT_PRIMARY),
            **kwargs
        )


class SliderField(ft.Container):
    def __init__(self, label, min_val, max_val, value, on_change=None, divisions=None, suffix=""):
        self.slider = ft.Slider(
            min=min_val,
            max=max_val,
            value=value,
            divisions=divisions,
            on_change=on_change,
            active_color=ThemeColors.PRIMARY,
            inactive_color=ThemeColors.BG_TERTIARY,
            expand=True,
        )

        self.value_text = Typography.body(str(value) + suffix)

        def update_value(e):
            self.value_text.value = str(round(e.control.value, 3)) + suffix
            if on_change:
                on_change(e)

        self.slider.on_change = update_value

        super().__init__(
            content=ft.Column(
                [
                    Typography.body_small(label, ThemeColors.TEXT_SECONDARY),
                    ft.Row(
                        [self.slider, self.value_text],
                        spacing=Spacing.MD,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=Spacing.SM,
            ),
            padding=ft.padding.symmetric(vertical=Spacing.MD, horizontal=Spacing.LG),
            bgcolor=ThemeColors.BG_SECONDARY,
            border_radius=BorderRadius.MEDIUM,
            border=ft.border.all(1, ThemeColors.BORDER),
        )


class SectionHeader(ft.Container):
    def __init__(self, title, subtitle=""):
        elements = [Typography.heading_2(title)]
        if subtitle:
            elements.append(Typography.body_small(subtitle, ThemeColors.TEXT_SECONDARY))

        super().__init__(
            content=ft.Column(elements, spacing=Spacing.SM),
            padding=ft.padding.symmetric(horizontal=Spacing.LG, vertical=Spacing.MD),
        )


class ProgressIndicator(ft.Container):
    def __init__(self, label, value, max_value, color=ThemeColors.PRIMARY):
        self.progress_bar = ft.ProgressBar(
            value=value / max_value if max_value > 0 else 0,
            color=color,
            bgcolor=ThemeColors.BG_TERTIARY,
            height=8,
        )

        super().__init__(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            Typography.body_small(label),
                            Typography.body_small(f"{value}/{max_value}"),
                        ],
                        spacing=Spacing.MD,
                    ),
                    self.progress_bar,
                ],
                spacing=Spacing.SM,
            ),
            padding=Spacing.LG,
            bgcolor=ThemeColors.BG_SECONDARY,
            border_radius=BorderRadius.MEDIUM,
            border=ft.border.all(1, ThemeColors.BORDER),
        )

    def update(self, value, max_value):
        self.progress_bar.value = value / max_value if max_value > 0 else 0


class LoadingSpinner(ft.Container):
    def __init__(self, message="Loading..."):
        super().__init__(
            content=ft.Column(
                [
                    ft.ProgressRing(color=ThemeColors.PRIMARY, size=40),
                    Typography.body_small(message, ThemeColors.TEXT_SECONDARY),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=Spacing.MD,
            ),
            alignment=ft.alignment.center,
        )
