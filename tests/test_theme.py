"""Keep native widgets and custom surfaces on the same theme in both modes."""
from pathlib import Path
import tomllib

from ui.palette import FONT, LATTE, MOCHA


def test_native_theme_matches_custom_surfaces_and_bundled_fonts():
    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / ".streamlit/config.toml").read_text())
    theme = config["theme"]
    assert "base" not in theme  # retain native system/light/dark switching
    assert config["server"]["enableStaticServing"]
    assert theme["font"] == theme["headingFont"] == theme["codeFont"] == FONT
    assert theme["baseRadius"] == theme["buttonRadius"] == "none"
    for mode, colors in (("light", LATTE), ("dark", MOCHA)):
        native = theme[mode]
        for key, token in (("backgroundColor", "base"), ("secondaryBackgroundColor", "mantle"),
                           ("textColor", "text"), ("borderColor", "border"), ("primaryColor", "mauve")):
            assert native[key] == colors[token]
        assert native["sidebar"]["baseRadius"] == native["sidebar"]["buttonRadius"] == "none"
    for font in theme["fontFaces"]:
        assert font["family"] == FONT
        assert (root / font["url"].removeprefix("app/")).is_file()
