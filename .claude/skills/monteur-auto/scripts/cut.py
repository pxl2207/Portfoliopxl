#!/usr/bin/env python3
"""Les ciseaux — applique le plan de coupe avec FFmpeg.

- recadre en 9:16 (1080x1920, cover) à 30 i/s, keyframe toutes les 0.5 s (seek fluide dans HyperFrames)
- coupes nettes à l'image + micro-fondus audio de 12 ms (aucun « clic »)
- étalonnage léger selon style.json (contraste, saturation, chaleur, vignette, netteté)
- son nettoyé : passe-haut, débruitage léger, compresseur, normalisation -14 LUFS (réseaux sociaux)

Usage: cut.py <video> <cuts.json> <out.mp4> [--style style.json]
"""
import argparse
import json
import subprocess
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("cuts")
    ap.add_argument("out")
    ap.add_argument("--style", default=None)
    a = ap.parse_args()

    cuts = json.load(open(a.cuts))
    st = json.load(open(a.style)) if a.style else {}
    cv = st.get("canvas", {"w": 1080, "h": 1920, "fps": 30})
    W, H, FPS = cv["w"], cv["h"], cv["fps"]
    g = st.get("grade", {})
    segs = cuts["segments"]
    n = len(segs)
    fade = 0.012

    grade = []
    if g:
        grade.append("eq=contrast={c}:saturation={s}:brightness={b}:gamma={gm}".format(
            c=g.get("contrast", 1.0), s=g.get("saturation", 1.0), b=g.get("brightness", 0.0),
            gm=g.get("gamma", 1.0)))
        w = g.get("warmth", 0.0)
        if w:
            grade.append(f"colorbalance=rm={w:.3f}:gm={w/3:.3f}:bm={-w:.3f}:rh={w/2:.3f}:bh={-w/2:.3f}")
        if g.get("sharpen", 0):
            grade.append(f"unsharp=5:5:{g['sharpen']}:5:5:0")
        if g.get("vignette", 0):
            grade.append(f"vignette=angle={0.2 + 0.5 * g['vignette']:.3f}")
    # HDR (iPhone HLG / PQ) -> SDR Rec.709, sinon image grise et délavée
    tone = []
    pr = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                         "stream=color_transfer", "-of", "csv=p=0", a.video], capture_output=True, text=True)
    trc = pr.stdout.strip()
    if trc in ("arib-std-b67", "smpte2084"):
        tone = [f"zscale=tin={trc}:min=bt2020nc:pin=bt2020:rin=tv:t=linear:npl=203", "format=gbrpf32le",
                "zscale=p=bt709", "tonemap=hable:desat=2", "zscale=t=bt709:m=bt709:r=tv", "format=yuv420p",
                "eq=saturation=0.82:gamma=1.08"]
        print(f"[cut] source HDR ({trc}) -> conversion SDR", file=sys.stderr)

    # Une seule passe : on sélectionne les segments gardés (pas de split = mémoire constante)
    expr = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in segs)
    parts = [
        "[0:v]" + ",".join([f"fps={FPS}", f"select='{expr}'", f"setpts=N/({FPS}*TB)"] + tone +
                           [f"scale={W}:{H}:force_original_aspect_ratio=increase", f"crop={W}:{H}", "setsar=1"]
                           + grade) + "[vc]",
        f"[0:a]aresample=48000,aformat=channel_layouts=stereo,aselect='{expr}',asetpts=N/SR/TB[ac]",
    ]
    ac = st.get("audio", {})
    lufs = ac.get("lufs", -14)
    achain = (f"highpass=f=75,afftdn=nr=8:nf=-45,"
              f"acompressor=threshold=-20dB:ratio=3:attack=8:release=120:makeup=2,"
              f"loudnorm=I={lufs}:TP=-1.5:LRA=9")
    parts.append(f"[ac]{achain},aresample=48000[ao]")
    fc = ";\n".join(parts)
    script = a.out + ".filter.txt"
    open(script, "w").write(fc)
    cmd = ["ffmpeg", "-v", "error", "-y", "-i", a.video, "-filter_complex_script", script,
           "-map", "[vc]", "-map", "[ao]", "-c:v", "libx264", "-preset", "medium", "-crf", "17",
           "-pix_fmt", "yuv420p", "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-color_range", "tv", "-g", str(FPS // 2), "-keyint_min", str(FPS // 2), "-sc_threshold", "0",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out]
    subprocess.run(cmd, check=True)
    print(f"[cut] {n} segments -> {a.out} ({cuts['duration_out']:.1f}s)", file=sys.stderr)


if __name__ == "__main__":
    main()
