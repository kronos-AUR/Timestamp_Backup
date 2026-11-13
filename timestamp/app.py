#!/usr/bin/env python3
"""
Timestamp - Graphical user interface entry point.

This module launches the backup GUI.
"""

import os
import sys
from pathlib import Path

# Import the initialization module to set paths
from timestamp import CONFIG_DIR, RUNTIME_DIR, ICONS_DIR, ensure_directories

# Ensure directories exist
ensure_directories()

# Set the project directory for the backup module
import backup.config
backup.config._project_root = CONFIG_DIR

# Import webview and the API
import webview
from timestamp.gui.api import BackupAPI


def _generate_icon():
    """Generate runtime icons from the SVG."""
    svg_path = ICONS_DIR / "timestamp-backup.svg"
    out_dir = RUNTIME_DIR
    png_path = out_dir / "icon.png"
    ico_path = out_dir / "icon.ico"

    if ico_path.exists() and png_path.exists():
        return ico_path, png_path
    if not svg_path.exists():
        # Try with installation path
        svg_path = Path("/usr/share/icons/hicolor/scalable/apps/timestamp-backup.svg")
        if not svg_path.exists():
            return None, None

    try:
        import re
        import xml.etree.ElementTree as ET
        from PIL import Image, ImageDraw

        tree = ET.parse(str(svg_path))
        root = tree.getroot()
        SVG = "{http://www.w3.org/2000/svg}"

        SIZE = 512
        canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))

        def hex_to_rgba(color, opacity=1.0):
            if not color or color == "none":
                return None
            c = color.lstrip("#")
            r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
            return (r, g, b, int(opacity * 255))

        def parse_path(d):
            """Parse SVG path commands M/H/V/L/Z (no curves) -> list of (x,y)."""
            tokens = re.findall(r"[MmHhVvLlZz]|[-+]?\d*\.?\d+", d)
            pts, cx, cy, sx, sy = [], 0.0, 0.0, 0.0, 0.0
            cmd, i = None, 0
            while i < len(tokens):
                t = tokens[i]
                if re.fullmatch(r"[MmHhVvLlZz]", t):
                    cmd = t; i += 1; continue
                if cmd == "M":
                    cx, cy = float(tokens[i]), float(tokens[i+1]); sx, sy = cx, cy
                    pts.append((cx, cy)); i += 2; cmd = "L"
                elif cmd == "m":
                    cx += float(tokens[i]); cy += float(tokens[i+1]); sx, sy = cx, cy
                    pts.append((cx, cy)); i += 2; cmd = "l"
                elif cmd == "L":
                    cx, cy = float(tokens[i]), float(tokens[i+1])
                    pts.append((cx, cy)); i += 2
                elif cmd == "l":
                    cx += float(tokens[i]); cy += float(tokens[i+1])
                    pts.append((cx, cy)); i += 2
                elif cmd == "H":
                    cx = float(tokens[i]); pts.append((cx, cy)); i += 1
                elif cmd == "h":
                    cx += float(tokens[i]); pts.append((cx, cy)); i += 1
                elif cmd == "V":
                    cy = float(tokens[i]); pts.append((cx, cy)); i += 1
                elif cmd == "v":
                    cy += float(tokens[i]); pts.append((cx, cy)); i += 1
                elif cmd in ("Z", "z"):
                    cx, cy = sx, sy; i += 1
                else:
                    i += 1
            return pts

        for elem in root.iter():
            tag = elem.tag.replace(SVG, "")
            fill_str  = elem.get("fill", "").strip()
            fill_op   = float(elem.get("fill-opacity", "1"))
            stroke_str = elem.get("stroke", "").strip()
            stroke_w   = float(elem.get("stroke-width", "1"))

            if tag == "rect":
                x = float(elem.get("x", 0)); y = float(elem.get("y", 0))
                w = float(elem.get("width", 0)); h = float(elem.get("height", 0))
                rx = float(elem.get("rx", 0) or 0)
                color = hex_to_rgba(fill_str, fill_op)
                if color:
                    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
                    draw = ImageDraw.Draw(layer)
                    if rx > 0:
                        draw.rounded_rectangle([x, y, x + w, y + h], radius=rx, fill=color)
                    else:
                        draw.rectangle([x, y, x + w, y + h], fill=color)
                    canvas = Image.alpha_composite(canvas, layer)

            elif tag == "circle":
                cx = float(elem.get("cx", 0)); cy = float(elem.get("cy", 0))
                r  = float(elem.get("r", 0))
                bbox = [cx - r, cy - r, cx + r, cy + r]
                fill_color   = hex_to_rgba(fill_str, fill_op) if fill_str not in ("", "none") else None
                stroke_color = hex_to_rgba(stroke_str) if stroke_str not in ("", "none") else None
                if fill_color:
                    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
                    ImageDraw.Draw(layer).ellipse(bbox, fill=fill_color)
                    canvas = Image.alpha_composite(canvas, layer)
                if stroke_color:
                    layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
                    ImageDraw.Draw(layer).ellipse(bbox, outline=stroke_color, width=int(stroke_w))
                    canvas = Image.alpha_composite(canvas, layer)

            elif tag == "path":
                pts = parse_path(elem.get("d", ""))
                if len(pts) >= 3:
                    fill_color   = hex_to_rgba(fill_str, fill_op) if fill_str != "none" else None
                    stroke_color = hex_to_rgba(stroke_str) if stroke_str not in ("", "none") else None
                    if fill_color:
                        layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
                        ImageDraw.Draw(layer).polygon(pts, fill=fill_color)
                        canvas = Image.alpha_composite(canvas, layer)
                    if stroke_color:
                        layer = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
                        d2 = ImageDraw.Draw(layer)
                        closed = pts + [pts[0]]
                        for j in range(len(closed) - 1):
                            d2.line([closed[j], closed[j+1]], fill=stroke_color, width=int(stroke_w))
                        canvas = Image.alpha_composite(canvas, layer)

        out_dir.mkdir(exist_ok=True)
        canvas.save(str(png_path))

        # Resize from the 512px canvas to each target size.
        ico_sizes = [(16,16),(20,20),(24,24),(32,32),(40,40),(48,48),(64,64),(96,96),(128,128),(256,256)]
        canvas.save(str(ico_path), format="ICO", sizes=ico_sizes)

        return ico_path, png_path
    except Exception as e:
        print(f"[icon] Generation skipped: {e}")
        return None, None


# Background color of the window by theme. Applied before page rendering:
# without it, the window opens in dark then switches, which produces a
# visible flash with the light theme.
_THEME_BG = {
    "dark":    "#14171C",
    "monokai": "#272822",
    "amber":   "#EDEDF0",
    "flexoki": "#100F0F",
}


def _select_qt_binding() -> None:
    """Force qtpy to use PyQt6."""
    if os.environ.get("QT_API"):
        return
    try:
        import importlib.util
        if importlib.util.find_spec("PyQt6") is not None:
            os.environ["QT_API"] = "pyqt6"
    except Exception:
        pass


def _configure_qtwebengine() -> None:
    """Necessary QtWebEngine settings on some Linux distributions."""
    if os.name == "nt":
        return

    # Kali is often used as root; the Chromium sandbox refuses to start
    # and the window remains blank.
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        flags = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        if "--no-sandbox" not in flags:
            os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = (flags + " --no-sandbox").strip()

    # Under Wayland, QtWebEngine goes through XWayland
    if not os.environ.get("QT_QPA_PLATFORM") and os.environ.get("WAYLAND_DISPLAY") \
            and os.environ.get("DISPLAY"):
        os.environ["QT_QPA_PLATFORM"] = "xcb"


def _gui_backends() -> list:
    """pywebview backends to try, in order."""
    forced = os.environ.get("TIMESTAMP_GUI")
    if forced:
        return [forced]
    return ["qt"] if os.name == "nt" else ["qt", "gtk"]


def main():
    _generate_icon()
    _select_qt_binding()
    _configure_qtwebengine()

    api = BackupAPI()
    index = Path(__file__).resolve().parent / "gui" / "assets" / "index.html"

    try:
        from backup.config import get_theme
        theme = get_theme()
    except Exception:
        theme = "flexoki"

    # Theme is injected into the template
    html = index.read_text(encoding="utf-8").replace("__THEME__", theme, 1)

    webview.create_window(
        title="Timestamp",
        html=html,
        js_api=api,
        width=960,
        height=660,
        min_size=(720, 520),
        background_color=_THEME_BG.get(theme, "#14171C"),
    )
    debug = "--debug" in sys.argv
    storage = str(RUNTIME_DIR / "webview_data")

    backends = _gui_backends()
    last_error = None
    for backend in backends:
        try:
            webview.start(debug=debug, gui=backend, storage_path=storage)
            return
        except Exception as e:
            last_error = e
            print(f"[gui] Backend '{backend}' unavailable: {e}")

    print(
        "No usable display engine.\n"
        "  Linux (Debian/Kali/Ubuntu) : sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine\n"
        "  Linux (Arch/CachyOS)       : sudo pacman -S python-pyqt6 python-pyqt6-webengine\n"
        "  Windows                    : Install PyQt6",
        file=sys.stderr,
    )
    raise SystemExit(1 if last_error else 0)


if __name__ == "__main__":
    main()
