#!/usr/bin/env python3
"""Le monteur — génère le projet HyperFrames à partir de plan.json.

projet/
  index.html                  racine 1080x1920 : vidéo montée + caméra (zooms) + sons
  compositions/captions.html  sous-titres dynamiques mot par mot
  compositions/fx.html        punchs typographiques, cartes plein écran, cartes motion design
  assets/cut.mp4, assets/fonts/*, assets/sfx/*

Usage: build_hf.py <plan.json> <cut.mp4> <style.json> <project_dir> [--music music.mp3]
"""
import argparse
import html
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)

ICONS = {
    "play": '<rect x="6" y="12" width="52" height="40" rx="8"/><path d="M27 24l12 8-12 8z" fill="currentColor"/>',
    "scissors": '<circle cx="16" cy="18" r="8"/><circle cx="16" cy="46" r="8"/><path d="M22 23l34 25M22 41l34-25"/>',
    "wave": '<path d="M8 32v0M18 24v16M28 14v36M38 22v20M48 28v8M56 31v2"/>',
    "eye": '<path d="M4 32s10-16 28-16 28 16 28 16-10 16-28 16S4 32 4 32z"/><circle cx="32" cy="32" r="7" fill="currentColor"/>',
    "check": '<circle cx="32" cy="32" r="24"/><path d="M21 33l8 8 15-17"/>',
    "star": '<path d="M32 8l7 15 16 2-12 11 3 16-14-8-14 8 3-16L9 25l16-2z"/>',
    "bolt": '<path d="M36 6L14 36h16l-4 22 24-32H34z"/>',
    "euro": '<path d="M46 16a20 20 0 1 0 0 32M12 28h26M12 36h26"/>',
    "clock": '<circle cx="32" cy="32" r="24"/><path d="M32 18v15l10 6"/>',
}


def esc(t):
    return html.escape(t, quote=True)


def font_faces(prefix="assets/fonts/"):
    return f"""
@font-face {{ font-family: 'Inter Tight'; font-weight: 600; src: url('{prefix}inter-tight-latin-600-normal.woff2') format('woff2'); }}
@font-face {{ font-family: 'Inter Tight'; font-weight: 800; src: url('{prefix}inter-tight-latin-800-normal.woff2') format('woff2'); }}
@font-face {{ font-family: 'Inter Tight'; font-weight: 900; src: url('{prefix}inter-tight-latin-900-normal.woff2') format('woff2'); }}
@font-face {{ font-family: 'Instrument Serif'; font-style: italic; font-weight: 400; src: url('{prefix}instrument-serif-latin-400-italic.woff2') format('woff2'); }}
@font-face {{ font-family: 'Instrument Serif'; font-style: normal; font-weight: 400; src: url('{prefix}instrument-serif-latin-400-normal.woff2') format('woff2'); }}
@font-face {{ font-family: 'JetBrains Mono'; font-weight: 400; src: url('{prefix}jetbrains-mono-latin-400-normal.woff2') format('woff2'); }}
"""


def captions_html(plan, st, W, H, D):
    C, col = st["captions"], st["colors"]
    bottom = H - C["y_bottom"]
    groups = []
    for c in plan["captions"]:
        spans = []
        for j, w in enumerate(c["words"]):
            cls = "w emph" if w["emph"] else "w"
            spans.append(f'<span class="{cls}" data-s="{w["start"]}">{esc(w["text"])}</span>')
        groups.append(f'    <div class="cap" id="{c["id"]}" data-s="{c["start"]}" data-e="{c["end"]}">'
                      + " ".join(spans) + "</div>")
    dim = 0.38 if C.get("upcoming_dim", True) else 0.0
    return f"""<template>
  <style>
{font_faces()}
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    .cap {{
      position: absolute; left: 0; right: 0; bottom: {bottom}px;
      padding: 0 {int((W - C['max_width']) / 2)}px; text-align: center;
      font-family: 'Inter Tight', sans-serif; font-weight: {st['fonts']['sans_weight']};
      font-size: {C['size']}px; line-height: 1.08; letter-spacing: -0.025em; color: {col['text']};
      visibility: hidden; opacity: 0; overflow: visible;
      text-shadow: 0 3px 18px {col['shadow']}, 0 1px 3px rgba(0,0,0,.35);
    }}
    .w {{ display: inline-block; margin: 0 0.06em; }}
    .w.emph {{
      font-family: 'Instrument Serif', serif; font-style: italic; font-weight: 400;
      font-size: {C['emph_scale']:.2f}em; letter-spacing: -0.01em; color: {col['accent']};
      line-height: 0.9;
    }}
  </style>
  <div id="root" data-composition-id="captions" data-width="{W}" data-height="{H}" data-layout-allow-overlap data-layout-allow-safe-zone>
{chr(10).join(groups)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    const DIM = {dim};
    document.querySelectorAll('#root .cap').forEach((cap) => {{
      const s = +cap.dataset.s, e = +cap.dataset.e;
      tl.set(cap, {{ visibility: 'visible', opacity: 1 }}, s);
      cap.querySelectorAll('.w').forEach((w) => {{
        const ws = Math.max(s, +w.dataset.s);
        if (w.classList.contains('emph')) {{
          tl.fromTo(w, {{ opacity: DIM, scale: 0.82, y: 10, filter: 'blur(6px)' }},
            {{ opacity: 1, scale: 1, y: 0, filter: 'blur(0px)', duration: 0.24, ease: 'back.out(2.2)' }}, ws);
        }} else {{
          tl.fromTo(w, {{ opacity: DIM, y: 12 }},
            {{ opacity: 1, y: 0, duration: 0.14, ease: 'power3.out' }}, ws);
        }}
      }});
      tl.to(cap, {{ opacity: 0, duration: 0.09, ease: 'power2.in' }}, Math.max(s, e - 0.09));
      tl.set(cap, {{ opacity: 0, visibility: 'hidden' }}, e);
    }});
    window.__timelines['captions'] = tl;
  </script>
</template>
"""


def fx_html(plan, st, W, H, D):
    P, col, Fn = st["punch"], st["colors"], st["fonts"]
    items = []
    for p in plan["punches"]:
        lines = []
        for k, ln in enumerate(p["lines"]):
            cls = "serif" if ln["style"] == "serif" else "sans"
            lines.append(f'<div class="ln"><span class="{cls}">{esc(ln["text"])}</span></div>')
        items.append(f'    <div class="punch" id="{p["id"]}" data-s="{p["start"]}" data-e="{p["end"]}">'
                     + "".join(lines) + "</div>")
    for f in plan["fullscreens"]:
        ctx = f'<div class="fctx">{esc(f["ctx"])}</div>' if f.get("ctx") else ""
        items.append(f'    <div class="full" id="{f["id"]}" data-s="{f["start"]}" data-e="{f["end"]}">'
                     f'<div class="fin"><div class="fbig">{esc(f["big"])}</div>{ctx}</div></div>')
    for c in plan.get("cards", []):
        icon = ICONS.get(c.get("icon", "none"), "")
        svg = (f'<svg class="cic" viewBox="0 0 64 64" fill="none" stroke="currentColor" stroke-width="4" '
               f'stroke-linecap="round" stroke-linejoin="round">{icon}</svg>') if icon else ""
        pill = f'<div class="cpill">{esc(c["pill"])}</div>' if c.get("pill") else ""
        pos = "top" if c.get("position", "bottom") == "top" else "bottom"
        items.append(f'    <div class="card {pos}" id="{c["id"]}" data-s="{c["start"]}" data-e="{c["end"]}">'
                     f'<div class="cin">{svg}<div class="clab">{esc(c.get("label", ""))}</div>'
                     f'<div class="ctit">{esc(c.get("title", ""))}</div>{pill}</div></div>')
    yc = P["y_center"]
    return f"""<template>
  <style>
{font_faces()}
    #root {{ position: absolute; inset: 0; pointer-events: none; }}
    .punch {{
      position: absolute; left: 0; right: 0; top: {yc}px; transform: translateY(-50%);
      text-align: center; visibility: hidden; padding: 0 70px;
    }}
    .punch .ln {{ display: block; clip-path: inset(-30% -30% 0 -30%); line-height: 0.98; }}
    .punch .ln > span {{ display: inline-block; }}
    .punch .sans {{
      font-family: 'Inter Tight', sans-serif; font-weight: {Fn['heavy_weight']}; font-size: {P['size']}px;
      letter-spacing: -0.05em; word-spacing: 0.1em; color: {col['text']};
      text-shadow: 0 6px 34px rgba(0,0,0,.42);
    }}
    .punch .serif {{
      font-family: 'Instrument Serif', serif; font-style: italic; font-size: {P['serif_size']}px;
      letter-spacing: -0.02em; color: {col['accent']}; padding: 0 0.08em;
      text-shadow: 0 6px 34px rgba(0,0,0,.35);
    }}
    .full {{
      position: absolute; inset: 0; visibility: hidden;
      background: radial-gradient(ellipse 75% 60% at 50% 45%, {col['paper']} 0%, {col['paper']} 45%, #DCD8D0 100%);
    }}
    .fin {{ position: absolute; left: 0; right: 0; top: 760px; text-align: center; padding: 0 60px; }}
    .fbig {{
      font-family: 'Inter Tight', sans-serif; font-weight: 900; font-size: 176px; letter-spacing: -0.06em;
      color: {col['ink']}; line-height: 0.95; white-space: nowrap;
    }}
    .fctx {{
      font-family: 'Instrument Serif', serif; font-style: italic; font-size: 86px; color: {col['accent']};
      margin-top: 18px; line-height: 1;
    }}
    .card {{ position: absolute; left: 60px; right: 60px; visibility: hidden; }}
    .card.top {{ top: 300px; }}
    .card.bottom {{ bottom: {H - st['captions']['y_bottom']}px; }}
    .cin {{
      background: #FFFFFF; border-radius: 40px; padding: 44px 52px 48px;
      box-shadow: 0 24px 60px rgba(0,0,0,.22), 0 2px 6px rgba(0,0,0,.08);
    }}
    .cic {{ width: 92px; height: 92px; color: {col['accent']}; display: block; margin-bottom: 22px; }}
    .clab {{ font-family: 'JetBrains Mono', monospace; font-size: 38px; color: #6B6B6B; letter-spacing: 0.02em; }}
    .ctit {{ font-family: 'Inter Tight', sans-serif; font-weight: 900; font-size: 92px; letter-spacing: -0.05em;
            color: {col['ink']}; line-height: 1; margin-top: 6px; }}
    .cpill {{ display: inline-block; margin-top: 22px; background: {col['pill']}; color: #fff; border-radius: 999px;
             padding: 12px 30px; font-family: 'Inter Tight', sans-serif; font-weight: 800; font-size: 40px;
             letter-spacing: -0.03em; box-shadow: 0 10px 24px rgba(31,157,87,.35); }}
  </style>
  <div id="root" data-composition-id="fx" data-width="{W}" data-height="{H}" data-layout-allow-overlap data-layout-allow-safe-zone>
{chr(10).join(items)}
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    const hide = (el, e, d) => {{
      tl.to(el, {{ opacity: 0, duration: d, ease: 'power2.in' }}, Math.max(0, e - d));
      tl.set(el, {{ opacity: 0, visibility: 'hidden' }}, e);
    }};
    document.querySelectorAll('#root .punch').forEach((el) => {{
      const s = +el.dataset.s, e = +el.dataset.e;
      tl.set(el, {{ visibility: 'visible', opacity: 1 }}, s);
      el.querySelectorAll('.ln > span').forEach((sp, i) => {{
        tl.fromTo(sp, {{ yPercent: 105, filter: 'blur(10px)', opacity: 0 }},
          {{ yPercent: 0, filter: 'blur(0px)', opacity: 1, duration: 0.34, ease: 'expo.out' }}, s + i * 0.09);
      }});
      tl.to(el.querySelectorAll('.ln > span'), {{ y: -26, filter: 'blur(6px)', duration: 0.18, ease: 'power2.in' }}, Math.max(s, e - 0.18));
      hide(el, e, 0.18);
    }});
    document.querySelectorAll('#root .full').forEach((el) => {{
      const s = +el.dataset.s, e = +el.dataset.e;
      tl.set(el, {{ visibility: 'visible' }}, s);
      tl.fromTo(el, {{ opacity: 0 }}, {{ opacity: 1, duration: 0.1, ease: 'none' }}, s);
      tl.fromTo(el.querySelector('.fbig'), {{ scale: 1.18, filter: 'blur(14px)', opacity: 0 }},
        {{ scale: 1, filter: 'blur(0px)', opacity: 1, duration: 0.42, ease: 'expo.out' }}, s + 0.04);
      const c = el.querySelector('.fctx');
      if (c) tl.fromTo(c, {{ y: 30, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.35, ease: 'power3.out' }}, s + 0.22);
      hide(el, e, 0.14);
    }});
    document.querySelectorAll('#root .card').forEach((el) => {{
      const s = +el.dataset.s, e = +el.dataset.e;
      tl.set(el, {{ visibility: 'visible', opacity: 1 }}, s);
      const cin = el.querySelector('.cin');
      tl.fromTo(cin, {{ y: 90, scale: 0.94, opacity: 0 }}, {{ y: 0, scale: 1, opacity: 1, duration: 0.5, ease: 'expo.out' }}, s);
      const kids = el.querySelectorAll('.cic, .clab, .ctit, .cpill');
      tl.fromTo(kids, {{ y: 18, opacity: 0 }}, {{ y: 0, opacity: 1, duration: 0.3, stagger: 0.06, ease: 'power3.out' }}, s + 0.12);
      tl.to(cin, {{ y: 40, opacity: 0, duration: 0.3, ease: 'power2.in' }}, Math.max(s, e - 0.3));
      tl.set(el, {{ visibility: 'hidden' }}, e);
    }});
    window.__timelines['fx'] = tl;
  </script>
</template>
"""


def camera_js(plan, st):
    """Zooms sur le wrapper #cam (jamais sur la vidéo elle-même)."""
    out = []
    sets = [c for c in plan["camera"] if c.get("set")]
    drifts = [c for c in plan["camera"] if "from_t" in c]
    pushes = [c for c in plan["camera"] if "push" in c]
    zmax = st["zoom"]["max"]
    for c in sets:
        out.append(f"tl.set(cam, {{ scale: {min(c['scale'], zmax)} }}, {c['t']});")
    for c in drifts:
        d = max(0.05, c["t"] - c["from_t"])
        base = next((s["scale"] for s in sets if abs(s["t"] - c["from_t"]) < 1e-3), 1.0)
        out.append(f"tl.fromTo(cam, {{ scale: {base} }}, {{ scale: {min(c['scale'], zmax)}, duration: {d:.3f}, "
                   f"ease: 'none', immediateRender: false }}, {c['from_t']});")
    for c in pushes:
        if c["push"] and c["push"] != 1.0:
            dur = max(0.2, c["until"] - c["t"])
            out.append(f"tl.fromTo(push, {{ scale: 1 }}, {{ scale: {c['push']:.3f}, duration: {min(0.45, dur):.3f}, "
                       f"ease: 'power3.out', immediateRender: false }}, {c['t']});")
            out.append(f"tl.to(push, {{ scale: 1, duration: 0.25, ease: 'power2.inOut' }}, {c['until']:.3f});")
    return "\n      ".join(out)


def make_sfx_variants(name, var, dst_dir):
    """3 prises par son (pitch 0.93 / 1.0 / 1.08) pour ne jamais répéter exactement le même."""
    src = os.path.join(SKILL, "assets", "sfx", name + ".mp3")
    rate = [1.0, 0.93, 1.08][var % 3]
    out = os.path.join(dst_dir, f"{name}-v{var % 3}.mp3")
    if not os.path.exists(out):
        if rate == 1.0:
            shutil.copy(src, out)
        else:
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", src, "-af",
                            f"asetrate=44100*{rate},aresample=44100", out], check=True)
    return os.path.basename(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("video")
    ap.add_argument("style")
    ap.add_argument("project")
    ap.add_argument("--music", default=None)
    a = ap.parse_args()
    plan = json.load(open(a.plan))
    st = json.load(open(a.style))
    W, H, FPS = st["canvas"]["w"], st["canvas"]["h"], st["canvas"]["fps"]
    D = round(plan["duration"], 3)
    pj = a.project
    for d in ("compositions", "assets/fonts", "assets/sfx", "assets/js"):
        os.makedirs(os.path.join(pj, d), exist_ok=True)
    shutil.copy(a.video, os.path.join(pj, "assets", "cut.mp4"))
    for f in os.listdir(os.path.join(SKILL, "assets", "fonts")):
        shutil.copy(os.path.join(SKILL, "assets", "fonts", f), os.path.join(pj, "assets", "fonts", f))
    shutil.copy(os.path.join(SKILL, "assets", "js", "gsap.min.js"), os.path.join(pj, "assets", "js", "gsap.min.js"))
    name = os.path.basename(os.path.abspath(pj))
    json.dump({"paths": {"blocks": "compositions", "components": "compositions/components", "assets": "assets"},
               "media": {"autoProxy": True}}, open(os.path.join(pj, "hyperframes.json"), "w"), indent=2)
    json.dump({"id": name, "name": name}, open(os.path.join(pj, "meta.json"), "w"), indent=2)
    peaks = json.load(open(os.path.join(SKILL, "assets", "sfx", "peaks.json")))

    open(os.path.join(pj, "compositions", "captions.html"), "w").write(captions_html(plan, st, W, H, D))
    open(os.path.join(pj, "compositions", "fx.html"), "w").write(fx_html(plan, st, W, H, D))

    audios = []
    lane = {}
    for k, s in enumerate(plan["sfx"]):
        fname = make_sfx_variants(s["name"], s.get("var", 0), os.path.join(pj, "assets", "sfx"))
        rate = [1.0, 0.93, 1.08][s.get("var", 0) % 3]
        pk = peaks.get(s["name"], {"peak": 0.0, "dur": 1.0})
        peak = pk["peak"] / rate
        dur = pk["dur"] / rate
        start = s["t"] + 1 / FPS - peak
        mstart = 0.0
        if start < 0:
            mstart, start = -start, 0.0
        dur = min(dur - mstart, D - start)
        if dur <= 0.05:
            continue
        # lanes : une seule piste sauf chevauchement
        tr = 10
        while lane.get(tr, -1) > start:
            tr += 1
        lane[tr] = start + dur
        ms = f' data-media-start="{mstart:.3f}"' if mstart else ""
        audios.append(f'      <audio id="sfx{k}" class="clip" src="assets/sfx/{fname}" data-start="{start:.3f}" '
                      f'data-duration="{dur:.3f}"{ms} data-track-index="{tr}" data-volume="{s["vol"]:.3f}"></audio>')
    if a.music:
        ext = os.path.splitext(a.music)[1]
        shutil.copy(a.music, os.path.join(pj, "assets", "music" + ext))
        audios.append(f'      <audio id="music" class="clip" src="assets/music{ext}" data-start="0" data-duration="{D}" '
                      f'data-track-index="20" data-volume="{st["audio"]["music_volume"]}" data-fade-in="0.6" '
                      f'data-fade-out="1.5"></audio>')

    index = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width={W}, height={H}" />
    <script src="assets/js/gsap.min.js"></script>
    <style>
      html, body {{ margin: 0; background: #000; }}
      #root {{ position: relative; width: {W}px; height: {H}px; overflow: hidden; background: #000; }}
      #cam, #push {{ position: absolute; inset: 0; transform-origin: 50% 36%; }}
      #aroll {{ position: absolute; left: 0; top: 0; width: {W}px; height: {H}px; object-fit: cover; }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="main" data-start="0" data-duration="{D}" data-width="{W}" data-height="{H}" data-fps="{FPS}">
      <div id="cam" data-layout-ignore><div id="push">
        <video id="aroll" class="clip" src="assets/cut.mp4" data-start="0" data-duration="{D}" data-track-index="0"
               playsinline data-has-audio="true"></video>
      </div></div>
      <div id="captions" data-composition-id="captions" data-composition-src="compositions/captions.html"
           data-start="0" data-duration="{D}" data-track-index="1" data-track-kind="captions"
           data-width="{W}" data-height="{H}" style="z-index: 5"></div>
      <div id="fx" data-composition-id="fx" data-composition-src="compositions/fx.html"
           data-start="0" data-duration="{D}" data-track-index="2" data-track-kind="graphics"
           data-width="{W}" data-height="{H}" style="z-index: 6"></div>
{chr(10).join(audios)}
    </div>
    <script>
      const tl = gsap.timeline({{ paused: true }});
      const cam = document.getElementById('cam');
      const push = document.getElementById('push');
      {camera_js(plan, st)}
      tl.set({{}}, {{}}, {D});
      window.__timelines['main'] = tl;
    </script>
  </body>
</html>
"""
    open(os.path.join(pj, "index.html"), "w").write(index)
    print(f"[build] projet HyperFrames -> {pj} ({D:.1f}s, {len(audios)} pistes son)", file=sys.stderr)


if __name__ == "__main__":
    main()
