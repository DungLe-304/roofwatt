"""Official Catppuccin colours shared by custom UI surfaces and the map.

Native Streamlit equivalents live in .streamlit/config.toml.
https://github.com/catppuccin/palette
"""
FONT = "CaskaydiaCove Nerd Font Mono"
LATTE = {
    "base": "#eff1f5",
    "mantle": "#e6e9ef",
    "crust": "#dce0e8",
    "text": "#4c4f69",
    "subtext": "#5c5f77",
    "border": "#9ca0b0",
    "surface": "#ccd0da",
    "mauve": "#8839ef",
    "blue": "#1e66f5",
    "peach": "#fe640b",
    "red": "#d20f39",
    "yellow": "#df8e1d",
    "green": "#40a02b"
}
MOCHA = {
    "base": "#1e1e2e",
    "mantle": "#181825",
    "crust": "#11111b",
    "text": "#cdd6f4",
    "subtext": "#bac2de",
    "border": "#6c7086",
    "surface": "#45475a",
    "mauve": "#cba6f7",
    "blue": "#89b4fa",
    "peach": "#fab387",
    "red": "#f38ba8",
    "yellow": "#f9e2af",
    "green": "#a6e3a1"
}


def palette(dark: bool = False) -> dict:
    return MOCHA if dark else LATTE


def rgb(hex_color: str) -> list[int]:
    return [int(hex_color[i:i + 2], 16) for i in (1, 3, 5)]
