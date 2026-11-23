#!/usr/bin/env python3
"""Placement anti-visage : détecte où est le visage dans la vidéo montée et place
sous-titres et punchs EN DESSOUS (sur le buste) quand le visage descend bas dans le cadre.

Usage: layout.py <cut.mp4> <plan.json> <style.json>   -> écrit plan["layout"]
"""
import json
import subprocess
import sys

import numpy as np


def face_bottom(video, H=1920, W=1080, n=24):
    try:
        import cv2
        casc = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    except Exception as e:  # pas d'OpenCV : on garde la mise en page du style
        print(f"[layout] détection visage indisponible ({e})", file=sys.stderr)
        return None
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                "csv=p=0", video], capture_output=True, text=True).stdout or 0)
    bots = []
    for t in np.linspace(dur * 0.03, dur * 0.97, n):
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", video, "-frames:v", "1",
                              "-vf", f"scale={W // 2}:{H // 2}", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                             capture_output=True).stdout
        if len(raw) != (W // 2) * (H // 2):
            continue
        g = np.frombuffer(raw, np.uint8).reshape(H // 2, W // 2)
        f = casc.detectMultiScale(g, 1.1, 5, minSize=(W // 8, W // 8))
        if len(f):
            x, y, w, h = max(f, key=lambda b: b[2] * b[3])
            bots.append((y + h * 1.18) * 2)  # le menton est sous la boîte détectée
    if len(bots) < 3:
        return None
    return float(np.percentile(bots, 85))


def main():
    video, plan_p, style_p = sys.argv[1:4]
    plan = json.load(open(plan_p))
    st = json.load(open(style_p))
    H = st["canvas"]["h"]
    C, P = st["captions"], st["punch"]
    fb = face_bottom(video, H, st["canvas"]["w"])
    lay = {"face_bottom": fb, "cap_bottom": C["y_bottom"], "punch_y": P["y_center"]}
    if fb:
        cap_h = int(C["size"] * C["emph_scale"] * 2.1)          # place pour 2 lignes
        if C["y_bottom"] - cap_h < fb + 30:                      # le sous-titre toucherait le visage
            lay["cap_bottom"] = int(min(H - 300, fb + 40 + cap_h))
        punch_h = int(P["serif_size"] * 2.2)
        if P["y_center"] - punch_h / 2 < fb + 20:
            lay["punch_y"] = int(min(H - 300 - punch_h / 2, fb + 40 + punch_h / 2))
    plan["layout"] = lay
    json.dump(plan, open(plan_p, "w"), ensure_ascii=False, indent=1)
    print(f"[layout] bas du visage ≈ {fb and round(fb)} px -> sous-titres bas {lay['cap_bottom']} px, "
          f"punchs centrés {lay['punch_y']} px", file=sys.stderr)


if __name__ == "__main__":
    main()
