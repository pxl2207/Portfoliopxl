#!/usr/bin/env bash
# Installe (ou vérifie) les 4 outils du monteur. Idempotent : relançable sans risque.
#   FFmpeg (les ciseaux) · Whisper/faster-whisper (les oreilles) · yt-dlp (les yeux) · HyperFrames (le monteur)
set -euo pipefail
export HF_HUB_DISABLE_XET=1
HF_VERSION="${HYPERFRAMES_VERSION:-0.9.81}"
WHISPER_MODEL="${MONTEUR_WHISPER:-small}"

say() { printf '\033[1;36m[setup]\033[0m %s\n' "$*"; }

# 1. FFmpeg
if ! command -v ffmpeg >/dev/null 2>&1; then
  say "FFmpeg absent -> installation"
  if command -v apt-get >/dev/null 2>&1; then (sudo -n true 2>/dev/null && SUDO=sudo || SUDO=""); $SUDO apt-get update -qq && $SUDO apt-get install -y -qq ffmpeg
  elif command -v brew >/dev/null 2>&1; then brew install ffmpeg
  else say "Installe FFmpeg à la main : https://ffmpeg.org/download.html"; exit 1; fi
fi
say "FFmpeg      : $(ffmpeg -version | head -1 | cut -d' ' -f1-3)"

# 2. Whisper (faster-whisper) + 3. yt-dlp
PIP="python3 -m pip"
$PIP install -q -U yt-dlp faster-whisper numpy 2>/dev/null || $PIP install -q -U --break-system-packages yt-dlp faster-whisper numpy
say "yt-dlp      : $(yt-dlp --version)"
python3 -I -c "import faster_whisper; print('[setup] Whisper     : faster-whisper', faster_whisper.__version__)"

# 4. HyperFrames (CLI + ses skills pour Claude Code)
if ! command -v hyperframes >/dev/null 2>&1 || [ "$(hyperframes --version 2>/dev/null | grep -o '[0-9.]*' | head -1)" != "$HF_VERSION" ]; then
  npm install -g "hyperframes@${HF_VERSION}" >/dev/null 2>&1
fi
say "HyperFrames : $(hyperframes --version 2>/dev/null | head -1)"
if [ ! -d "$HOME/.claude/skills/hyperframes" ]; then
  say "installation des skills HyperFrames pour Claude Code"
  hyperframes skills >/dev/null 2>&1 || say "(skills HyperFrames non installés : optionnels)"
fi

# Modèle Whisper en cache (évite d'attendre au premier montage)
python3 -I - <<PY
import os
os.environ["HF_HUB_DISABLE_XET"] = "1"
from faster_whisper.utils import download_model
p = download_model("${WHISPER_MODEL}")
print("[setup] Modèle      : ${WHISPER_MODEL} ->", p)
PY
say "Tout est prêt."
