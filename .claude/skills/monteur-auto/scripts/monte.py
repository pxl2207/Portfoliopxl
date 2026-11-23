#!/usr/bin/env python3
"""Chef d'orchestre — monte une vidéo de A à Z avec les 4 outils.

  yt-dlp  (les yeux)     : si on donne un lien au lieu d'un fichier
  Whisper (les oreilles) : transcription mot par mot
  FFmpeg  (les ciseaux)  : coupes des blancs / hésitations / prises ratées, étalonnage, son
  HyperFrames (le monteur): sous-titres dynamiques, punchs, cartes, zooms, sons -> MP4 final

Deux phases (pour que Claude puisse relire et affiner le plan entre les deux) :
  monte.py prep   <video|url> [--work DIR]          -> DIR/plan.json (+ transcript, cuts, cut.mp4)
  monte.py render [--work DIR] [--music f.mp3]      -> DIR/<nom>_monte.mp4 + planche de contrôle
  monte.py all    <video|url> [...]                 -> les deux d'un coup, sans pause

Options : --style chemin/style.json (défaut : style/style.json du skill)
          --model small|medium|large-v3 (Whisper)   --lang fr
          --quality draft|looks|delivery (rendu)    --no-render
"""
import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
PY = [sys.executable, "-I"]


def log(msg):
    print(f"\033[1;33m▶ {msg}\033[0m", file=sys.stderr, flush=True)


def run(cmd, **kw):
    t = time.time()
    subprocess.run(cmd, check=True, **kw)
    return time.time() - t


def ensure_tools():
    missing = [t for t in ("ffmpeg", "ffprobe", "hyperframes", "yt-dlp") if not shutil.which(t)]
    try:
        import faster_whisper  # noqa: F401
    except Exception:
        missing.append("faster-whisper")
    if missing:
        log(f"outils manquants {missing} -> installation (setup.sh)")
        run(["bash", os.path.join(HERE, "setup.sh")])


def fetch(src, work):
    if src.startswith(("http://", "https://")):
        log("yt-dlp : téléchargement de la vidéo")
        os.makedirs(work, exist_ok=True)
        run(["yt-dlp", "-f", "bv*[height<=1920]+ba/b", "--merge-output-format", "mp4",
             "-o", os.path.join(work, "source.%(ext)s"), src])
        return sorted(glob.glob(os.path.join(work, "source.*")))[0]
    return os.path.abspath(src)


def default_work(src):
    if src.startswith(("http://", "https://")):
        return os.path.abspath("montage_" + time.strftime("%Y%m%d_%H%M%S"))
    base = os.path.splitext(os.path.abspath(src))[0]
    return base + "_montage"


def prep(a):
    ensure_tools()
    work = os.path.abspath(a.work or default_work(a.src))
    os.makedirs(work, exist_ok=True)
    src = fetch(a.src, work)
    st = json.load(open(a.style))
    meta = {"source": src, "style": os.path.abspath(a.style),
            "name": os.path.splitext(os.path.basename(src))[0]}
    json.dump(meta, open(os.path.join(work, "meta.json"), "w"), indent=1, ensure_ascii=False)

    log("Whisper : transcription mot par mot")
    cmd = PY + [os.path.join(HERE, "transcribe.py"), src, os.path.join(work, "words.json"), "--model", a.model]
    if a.lang:
        cmd += ["--lang", a.lang]
    run(cmd)

    log("Plan de coupe : blancs, hésitations, mots ratés")
    c = st.get("cuts", {})
    run(PY + [os.path.join(HERE, "plan_cuts.py"), src, os.path.join(work, "words.json"),
              os.path.join(work, "cuts.json"),
              "--max-pause", str(c.get("max_pause", 0.45)), "--keep-pause", str(c.get("keep_pause", 0.14)),
              "--pad-before", str(c.get("pad_before", 0.07)), "--pad-after", str(c.get("pad_after", 0.09))])

    log("FFmpeg : coupes + étalonnage + son -14 LUFS")
    run(PY + [os.path.join(HERE, "cut.py"), src, os.path.join(work, "cuts.json"),
              os.path.join(work, "cut.mp4"), "--style", a.style])

    log("Réalisation : sous-titres, punchs, cartes, caméra, sons")
    run(PY + [os.path.join(HERE, "plan_edit.py"), os.path.join(work, "cuts.json"), a.style,
              os.path.join(work, "plan.json")])
    log("Placement : sous-titres et punchs jamais sur le visage")
    run(PY + [os.path.join(HERE, "layout.py"), os.path.join(work, "cut.mp4"), os.path.join(work, "plan.json"),
              a.style])
    print(work)
    return work


def render(a, work=None):
    work = os.path.abspath(work or a.work)
    meta = json.load(open(os.path.join(work, "meta.json")))
    style = a.style if a.style_given else meta["style"]
    proj = os.path.join(work, "projet")
    if os.path.isdir(proj):
        shutil.rmtree(proj)
    log("HyperFrames : construction du projet")
    cmd = PY + [os.path.join(HERE, "build_hf.py"), os.path.join(work, "plan.json"),
                os.path.join(work, "cut.mp4"), style, proj]
    if a.music:
        cmd += ["--music", os.path.abspath(a.music)]
    run(cmd)

    log("HyperFrames : vérification (lint + runtime + mise en page)")
    rep = os.path.join(work, "check.json")
    with open(rep, "w") as fh:
        # vidéo HEVC / HDR : HyperFrames doit d'abord en faire une copie lisible par le navigateur (sans limite)
        subprocess.run(["hyperframes", "check", "--prepare-media"], cwd=proj,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["hyperframes", "check", "--json"], cwd=proj, stdout=fh, stderr=subprocess.DEVNULL)
    try:
        chk = json.load(open(rep))
        errs = [f for k in ("lint", "runtime", "layout") for f in chk.get(k, {}).get("findings", [])
                if f.get("severity") == "error"]
        warns = [f for k in ("lint", "runtime", "layout") for f in chk.get(k, {}).get("findings", [])
                 if f.get("severity") == "warning"]
        log(f"check : {len(errs)} erreur(s), {len(warns)} avertissement(s)")
        for f in errs + warns[:8]:
            print(f"   - [{f.get('severity')}] {f.get('code')}: {f.get('message', '')[:160]}", file=sys.stderr)
        if errs:
            print("Des erreurs bloquantes : voir check.json", file=sys.stderr)
            sys.exit(2)
    except Exception as e:  # le check est un garde-fou, pas un bloqueur
        print(f"   (check illisible : {e})", file=sys.stderr)

    if a.no_render:
        print(proj)
        return
    out = os.path.join(work, f"{meta['name']}_monte.mp4")
    log("HyperFrames : rendu MP4 1080x1920")
    dt = run(["hyperframes", "render", "-o", out, "-q", a.quality, "--quiet"], cwd=proj)
    log(f"rendu en {dt:.0f}s -> {out}")

    # planche de contrôle pour la relecture visuelle
    sheet = os.path.join(work, "controle.jpg")
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                "csv=p=0", out], capture_output=True, text=True).stdout.strip() or 0)
    n = 12
    tiles = []
    for k in range(n):
        t = dur * (k + 0.5) / n
        fp = os.path.join(work, f".ctl_{k:02d}.jpg")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.2f}", "-i", out, "-frames:v", "1", "-vf",
                        f"scale=270:-1,drawtext=text='{int(t // 60)}\\:{t % 60:04.1f}':x=6:y=6:fontsize=16:"
                        f"fontcolor=yellow:box=1:boxcolor=black@0.5", fp])
        tiles.append(fp)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(work, ".ctl_%02d.jpg"), "-vf", "tile=6x2",
                    "-frames:v", "1", sheet])
    for fp in tiles:
        if os.path.exists(fp):
            os.remove(fp)
    r = subprocess.run(["ffmpeg", "-v", "info", "-i", out, "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True).stderr
    summ = r[r.rfind("Summary:"):]
    lufs = next((l.split(":")[1].strip() for l in summ.splitlines() if l.strip().startswith("I:")), "?")
    peak = next((l.split(":")[1].strip() for l in summ.splitlines() if l.strip().startswith("Peak:")), "?")
    cuts = json.load(open(os.path.join(work, "cuts.json")))
    plan = json.load(open(os.path.join(work, "plan.json")))
    rapport = {
        "video": out, "planche": sheet,
        "duree_brute": cuts["duration_in"], "duree_montee": cuts["duration_out"],
        "coupes": len(cuts["cut_points"]), "retraits": len(cuts["removed"]),
        "sous_titres": len(plan["captions"]), "punchs": len(plan["punches"]),
        "plein_ecran": len(plan["fullscreens"]), "cartes": len(plan.get("cards", [])),
        "sons": len(plan["sfx"]), "loudness": lufs, "true_peak": peak, "rendu_s": round(dt),
    }
    # Version lisible partout (H.264 SDR) : beaucoup de lecteurs (Android, Chrome, aperçus) ne lisent pas le HEVC HDR
    trc = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=color_transfer",
                          "-of", "csv=p=0", out], capture_output=True, text=True).stdout.strip().split(",")[0].strip()
    if trc in ("arib-std-b67", "smpte2084"):
        compat = os.path.join(work, f"{meta['name']}_monte_compatible.mp4")
        log("Export H.264 lisible partout (conversion HDR -> SDR la plus neutre possible)")
        run(["ffmpeg", "-v", "error", "-y", "-i", out, "-vf",
             "zscale=t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,tonemap=mobius:desat=0,"
             "zscale=t=bt709:m=bt709:r=tv,format=yuv420p",
             "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-maxrate", "3M", "-bufsize", "6M",
             "-profile:v", "high", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
             "-color_range", "tv", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", compat])
        rapport["video_compatible"] = compat
    json.dump(rapport, open(os.path.join(work, "rapport.json"), "w"), indent=1, ensure_ascii=False)
    print(json.dumps(rapport, indent=1, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["prep", "render", "all"])
    ap.add_argument("src", nargs="?")
    ap.add_argument("--work")
    ap.add_argument("--style", default=os.path.join(SKILL, "style", "style.json"))
    ap.add_argument("--model", default=os.environ.get("MONTEUR_WHISPER", "medium"))
    ap.add_argument("--lang", default=None)
    ap.add_argument("--music", default=None)
    ap.add_argument("--quality", default="looks")
    ap.add_argument("--no-render", action="store_true")
    a = ap.parse_args()
    a.style_given = "--style" in sys.argv
    a.style = os.path.abspath(a.style)
    if a.phase in ("prep", "all") and not a.src:
        ap.error("donne une vidéo (fichier ou lien)")
    if a.phase == "render" and not a.work:
        ap.error("--work DIR requis (le dossier créé par prep)")
    if a.phase == "prep":
        prep(a)
    elif a.phase == "render":
        render(a)
    else:
        render(a, prep(a))


if __name__ == "__main__":
    main()
