#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
unit_dir="${HOME}/.config/systemd/user"

if [[ ! -x "${repo_dir}/_env/bin/python" ]]; then
  python3 -m venv "${repo_dir}/_env"
fi

"${repo_dir}/_env/bin/python" -m pip install -r "${repo_dir}/requirements.txt"

mkdir -p "${unit_dir}"
sed "s|@REPO_DIR@|${repo_dir}|g" \
  "${repo_dir}/systemd/himawari-wallpaper.service.in" \
  > "${unit_dir}/himawari-wallpaper.service"
cp "${repo_dir}/systemd/himawari-wallpaper.timer" "${unit_dir}/himawari-wallpaper.timer"

systemctl --user daemon-reload
systemctl --user enable --now himawari-wallpaper.timer
systemctl --user start himawari-wallpaper.service

echo "Installed and started himawari-wallpaper.timer"
