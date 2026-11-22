#!/usr/bin/env python3
"""Analyse de vidéos de référence (fichiers ou liens) pour apprendre un style.

Pour chaque référence : téléchargement (yt-dlp si lien), planches 1 image/s, rythme de coupe
(détection de plans), débit de parole (Whisper), loudness, palette dominante.
Écrit <out>/rapport.md + <out>/<ref>/planche_XX.jpg que Claude regarde ensuite pour mettre à jour
style/mes-regles.md et style/style.json.

Usage: analyze_ref.py <out_dir> <video|url> [<video|url> ...] [--model small]
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def fetch(src, d):
    if src.startswith(("http://", "https://")):
        sh(["yt-dlp", "-f", "bv*[height<=1920]+ba/b", "--merge-output-format", "mp4",
            "-o", os.path.join(d, "ref.%(ext)s"), src], check=True)
        return sorted(glob.glob(os.path.join(d, "ref.*")))[0]
    return os.path.abspath(src)


def probe(v):
    r = json.loads(sh(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", v]).stdout)
    vs = next(s for s in r["streams"] if s["codec_type"] == "video")
    return float(r["format"]["duration"]), int(vs["width"]), int(vs["height"])


def scenes(v):
    r = sh(["ffmpeg", "-v", "info", "-i", v, "-vf", "select='gt(scene,0.32)',showinfo", "-an", "-f", "null", "-"])
    return [float(m) for m in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def palette(v, dur):
    pts = np.linspace(0.1 * dur, 0.9 * dur, 8)
    px = []
    for t in pts:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", v, "-frames:v", "1",
                              "-vf", "scale=48:85", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                             capture_output=True).stdout
        if raw:
            px.append(np.frombuffer(raw, np.uint8).reshape(-1, 3))
    a = np.concatenate(px).astype(float)
    q = (a // 32).astype(int)
    keys, counts = np.unique(q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2], return_counts=True)
    top = keys[np.argsort(-counts)][:6]
    cols = []
    for k in top:
        m = (q[:, 0] * 64 + q[:, 1] * 8 + q[:, 2]) == k
        c = a[m].mean(0)
        cols.append("#%02X%02X%02X" % tuple(int(x) for x in c))
    luma = float((a @ [0.299, 0.587, 0.114]).mean())
    sat = float((a.max(1) - a.min(1)).mean())
    return cols, luma, sat


def loud(v):
    r = sh(["ffmpeg", "-v", "info", "-i", v, "-af", "ebur128", "-f", "null", "-"]).stderr
    s = r[r.rfind("Summary:"):]
    m = re.search(r"I:\s+(-?[\d.]+) LUFS", s)
    return float(m.group(1)) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("refs", nargs="+")
    ap.add_argument("--model", default="small")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    md = ["# Analyse des références\n"]
    for i, src in enumerate(a.refs):
        d = os.path.join(a.out, f"ref{i + 1}")
        os.makedirs(d, exist_ok=True)
        v = fetch(src, d)
        dur, w, h = probe(v)
        sc = scenes(v)
        shots = np.diff([0] + sc + [dur])
        frames = os.path.join(d, "f_%04d.jpg")
        sh(["ffmpeg", "-v", "error", "-y", "-i", v, "-vf",
            "fps=1,scale=240:-2,drawtext=text='%{pts\\:hms}':x=4:y=4:fontsize=14:fontcolor=yellow:box=1:boxcolor=black@0.5",
            frames])
        sh(["ffmpeg", "-v", "error", "-y", "-i", os.path.join(d, "f_%04d.jpg"), "-vf", "tile=10x2",
            os.path.join(d, "planche_%02d.jpg")])
        for f in glob.glob(os.path.join(d, "f_*.jpg")):
            os.remove(f)
        wj = os.path.join(d, "words.json")
        subprocess.run([sys.executable, "-I", os.path.join(HERE, "transcribe.py"), v, wj, "--model", a.model],
                       check=True)
        words = json.load(open(wj))
        nw = len(words["words"])
        cols, luma, sat = palette(v, dur)
        L = loud(v)
        md += [f"## Réf {i + 1} — {os.path.basename(src)}",
               f"- Format : {w}x{h}, {dur:.1f} s, langue {words['lang']}",
               f"- Plans : {len(shots)} (durée moyenne {shots.mean():.2f} s, médiane {np.median(shots):.2f} s)"
               f" → {60 * len(shots) / dur:.0f} changements de plan / minute",
               f"- Débit : {60 * nw / dur:.0f} mots / minute",
               f"- Loudness : {L} LUFS" if L is not None else "- Loudness : ?",
               f"- Image : luminosité moyenne {luma:.0f}/255, saturation {sat:.0f}",
               f"- Palette dominante : {' '.join(cols)}",
               f"- Planches (1 image/s) : {', '.join(sorted(os.path.basename(p) for p in glob.glob(os.path.join(d, 'planche_*.jpg'))))} dans `{d}`",
               "- Transcription : " + " ".join(x["text"] for x in words["words"])[:1200], ""]
    md += ["## À faire par Claude",
           "Regarder chaque planche (police, taille et position des sous-titres, couleurs, mot clé mis en avant, "
           "punchs plein écran, B-roll, cartes, transitions), puis mettre à jour `style/mes-regles.md` et "
           "`style/style.json`. S'inspirer, ne pas copier."]
    open(os.path.join(a.out, "rapport.md"), "w").write("\n".join(md))
    print(os.path.join(a.out, "rapport.md"))


if __name__ == "__main__":
    main()
