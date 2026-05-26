#!/usr/bin/env python3
"""Download the latest Himawari-8 image and set it as the GNOME wallpaper."""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime
from pathlib import Path

from PIL import Image


BASE_URL = "https://himawari8-dl.nict.go.jp/himawari8/img/D531106"
LATEST_URL = f"{BASE_URL}/latest.json"
USER_AGENT = "himawari-wallpaper/1.0"
XRANDR_SCREEN_RE = re.compile(r"\bcurrent\s+(\d+)\s+x\s+(\d+),")


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_image(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        data = response.read()
    return Image.open(io.BytesIO(data)).convert("RGB")


def tile_url(capture_time: datetime, divisions: int, tile_size: int, x: int, y: int) -> str:
    return (
        f"{BASE_URL}/{divisions}d/{tile_size}/"
        f"{capture_time:%Y/%m/%d/%H%M%S}_{x}_{y}.png"
    )


def build_satellite_image(divisions: int, tile_size: int) -> tuple[Image.Image, str]:
    latest = fetch_json(LATEST_URL)
    capture_time = datetime.strptime(latest["date"], "%Y-%m-%d %H:%M:%S")

    satellite = Image.new("RGB", (divisions * tile_size, divisions * tile_size))
    for y in range(divisions):
        for x in range(divisions):
            tile = fetch_image(tile_url(capture_time, divisions, tile_size, x, y))
            satellite.paste(tile, (x * tile_size, y * tile_size))

    return satellite, latest["date"]


def detect_canvas_size() -> tuple[int, int]:
    output = subprocess.run(
        ["xrandr", "--current"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout

    match = XRANDR_SCREEN_RE.search(output)
    if not match:
        raise RuntimeError("Could not detect screen size from xrandr output")

    return int(match.group(1)), int(match.group(2))


def parse_canvas_size(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d+)x(\d+)", value)
    if not match:
        raise argparse.ArgumentTypeError("Canvas size must look like WIDTHxHEIGHT")

    width, height = int(match.group(1)), int(match.group(2))
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("Canvas width and height must be positive")

    return width, height


def compose_wallpaper(
    satellite: Image.Image,
    canvas_size: tuple[int, int],
    image_scale: float,
    max_canvas_fraction: float,
) -> Image.Image:
    canvas_width, canvas_height = canvas_size
    canvas = Image.new("RGB", canvas_size, "black")

    target_size = int(round(min(satellite.width, satellite.height) * image_scale))
    max_size = int(round(min(canvas_width, canvas_height) * max_canvas_fraction))
    target_size = max(1, min(target_size, max_size))

    resized = satellite.resize((target_size, target_size), Image.Resampling.LANCZOS)
    paste_at = (
        (canvas_width - resized.width) // 2,
        (canvas_height - resized.height) // 2,
    )
    canvas.paste(resized, paste_at)
    return canvas


def atomic_save(image: Image.Image, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=output.parent,
        prefix=f".{output.name}.",
        suffix=".png",
        delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)

    try:
        image.save(temp_path, "PNG")
        temp_path.replace(output)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def set_gnome_wallpaper(output: Path) -> None:
    uri = output.resolve().as_uri()
    commands = [
        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri", uri],
        ["gsettings", "set", "org.gnome.desktop.background", "picture-uri-dark", uri],
        ["gsettings", "set", "org.gnome.desktop.background", "picture-options", "centered"],
        ["gsettings", "set", "org.gnome.desktop.background", "primary-color", "#000000"],
        ["gsettings", "set", "org.gnome.desktop.background", "secondary-color", "#000000"],
    ]
    for command in commands:
        subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download the latest Himawari-8 full-disk image and set it as the Ubuntu wallpaper."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path.home() / ".local/share/himawari-wallpaper/himawari_latest.png",
        help="Where to save the stitched wallpaper PNG.",
    )
    parser.add_argument(
        "--divisions",
        type=int,
        default=4,
        choices=(1, 2, 4, 8, 16, 20),
        help="Tile grid size. 4 creates a 2200x2200 image; larger values download more data.",
    )
    parser.add_argument(
        "--tile-size",
        type=int,
        default=550,
        help="Tile size used by the NICT image service.",
    )
    parser.add_argument(
        "--download-only",
        action="store_true",
        help="Save the image but do not change GNOME wallpaper settings.",
    )
    parser.add_argument(
        "--canvas-size",
        type=parse_canvas_size,
        help="Wallpaper canvas size, such as 2560x1440. Defaults to xrandr's current screen size.",
    )
    parser.add_argument(
        "--image-scale",
        type=float,
        default=0.8,
        help="Satellite image size relative to the downloaded square before canvas fitting.",
    )
    parser.add_argument(
        "--max-canvas-fraction",
        type=float,
        default=0.8,
        help="Maximum satellite size as a fraction of the shorter canvas side.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    try:
        if args.image_scale <= 0:
            raise ValueError("--image-scale must be greater than 0")
        if not 0 < args.max_canvas_fraction <= 1:
            raise ValueError("--max-canvas-fraction must be greater than 0 and at most 1")

        satellite, capture_date = build_satellite_image(args.divisions, args.tile_size)
        canvas_size = args.canvas_size or detect_canvas_size()
        wallpaper = compose_wallpaper(
            satellite,
            canvas_size,
            args.image_scale,
            args.max_canvas_fraction,
        )
        atomic_save(wallpaper, args.output)
        if not args.download_only:
            set_gnome_wallpaper(args.output)
    except Exception as exc:
        print(f"himawari-wallpaper: {exc}", file=sys.stderr)
        return 1

    print(f"Saved Himawari image from {capture_date} to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
