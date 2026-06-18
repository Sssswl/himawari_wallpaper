# Himawari Wallpaper

Downloads the latest Himawari-8 full-disk image from NICT, stitches the image tiles, places it on a black desktop-sized canvas, and sets it as the Ubuntu GNOME wallpaper.

## Install

```bash
./install.sh
```

The installer uses the workspace venv at `_env`, creating it if needed. It installs `Pillow`, writes user systemd units for the folder where the project currently lives, enables the timer, and runs the wallpaper update once.

## Timer

The timer runs every 15 minutes:

```bash
systemctl --user status himawari-wallpaper.timer
systemctl --user status himawari-wallpaper.service
```

## Manual Run

```bash
_env/bin/python himawari_wallpaper.py
```

The wallpaper image is saved to:

```text
~/.local/share/himawari-wallpaper/himawari_latest.png
```

By default the script detects the current desktop size with `xrandr`, centers the satellite image, and caps it at 70% of the shorter screen dimension. You can override that:

```bash
_env/bin/python himawari_wallpaper.py --canvas-size 2560x1440 --image-scale 0.7 --max-canvas-fraction 0.7
```
