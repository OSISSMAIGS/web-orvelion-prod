#!/usr/bin/env bash
# Build CSS Tailwind STATIS — pengganti Play CDN (kompilator di browser = berat).
#
# Butuh salah satu: bun (bunx) ATAU node (npx). Tidak punya keduanya?
# Unduh binary standalone Tailwind v3 lalu jalankan perintah yang sama:
#   https://github.com/tailwindlabs/tailwindcss/releases
#
# CATATAN TIM: setelah menambah/mengubah kelas Tailwind di templates/ atau
# static/js/, WAJIB jalankan script ini lagi lalu commit static/css/tailwind.css.
set -euo pipefail
cd "$(dirname "$0")/.."

if command -v bunx >/dev/null 2>&1; then
  bunx tailwindcss@3.4.17 -c tailwind.config.js \
    -i static/css/tailwind.src.css -o static/css/tailwind.css --minify
elif command -v npx >/dev/null 2>&1; then
  npx -y tailwindcss@3.4.17 -c tailwind.config.js \
    -i static/css/tailwind.src.css -o static/css/tailwind.css --minify
else
  echo "ERROR: butuh bun atau node (npx), atau pakai binary standalone Tailwind v3." >&2
  exit 1
fi

echo "OK -> static/css/tailwind.css ($(wc -c < static/css/tailwind.css) bytes)"
