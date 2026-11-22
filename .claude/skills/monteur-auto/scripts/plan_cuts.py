#!/usr/bin/env python3
"""Plan de coupe — décide QUOI couper, sans sur-couper.

On coupe uniquement :
  1. les blancs / silences plus longs que --max-pause (0.45 s par défaut), en gardant
     une respiration naturelle (--keep-pause, 0.14 s) ;
  2. les hésitations (« euh », « hum », « bah euh »...) ;
  3. les mots ratés / phrases recommencées (prise ratée puis reprise) ;
  4. les bégaiements de mot (« le le », « je je ») ;
  5. le début et la fin vides, et les hallucinations de Whisper sur le silence.

Les bords de chaque coupe sont recalés sur l'énergie réelle du son (pas seulement sur
les timestamps Whisper) pour ne jamais manger une syllabe.

Usage: plan_cuts.py <video> <words.json> <cuts.json> [--max-pause 0.45] [--keep-pause 0.14]
Sortie : cuts.json = {segments: [[start,end],...], removed: [...], words: [...mots remappés...],
                      duration_in, duration_out}
"""
import argparse
import difflib
import json
import re
import subprocess
import sys
import unicodedata

import numpy as np

FILLERS = {"euh", "heu", "euhh", "euhm", "hum", "hmm", "hm", "mmh", "mh", "mhm", "eh", "ehm",
           "uh", "um", "uhm", "erm", "ah", "bah", "ben", "beh"}
# « bah / ben / ah » ne sont des hésitations que s'ils sont collés à un autre filler ou isolés par
# des pauses ; sinon ils peuvent faire partie du style oral → traités plus bas.
SOFT_FILLERS = {"bah", "ben", "beh", "ah", "eh"}
HALLUCINATIONS = [
    "sous-titres réalisés", "sous-titrage", "amara.org", "merci d'avoir regardé",
    "abonnez-vous", "thanks for watching", "thank you for watching", "sous-titres par",
]
FRAME = 0.01  # 10 ms


def norm(t):
    t = unicodedata.normalize("NFD", t.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9%€$]+", "", t)


def merge_tokens(words):
    """Whisper découpe « c'est » en « c » + « 'est », « là » en « -là » : on recolle."""
    out = []
    for w in words:
        t = w["text"].strip()
        if out and (t[:1] in "'’-" or t in {"%", "€", ".", ",", "?", "!", "…"}
                    or re.match(r"^-[a-zà-ÿ]", t)):
            p = out[-1]
            sep = "" if t[:1] in "'’-" else (" " if t in {"%", "€"} else "")
            p["text"] = (p["text"] + sep + t).replace(" '", "'")
            p["end"] = max(p["end"], w["end"])
            continue
        if out and out[-1]["text"].endswith(("'", "’")):
            p = out[-1]
            p["text"] += t
            p["end"] = w["end"]
            continue
        out.append(dict(w, text=t))
    return out


def energy_db(path):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", "16000",
                          "-af", "highpass=f=80", "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    a = np.frombuffer(raw, np.float32)
    hop = int(16000 * FRAME)
    n = len(a) // hop
    fr = a[: n * hop].reshape(n, hop)
    rms = np.sqrt((fr ** 2).mean(1) + 1e-12)
    db = 20 * np.log10(rms + 1e-9)
    # lissage 30 ms
    db = np.convolve(db, np.ones(3) / 3, "same")
    return db, len(a) / 16000


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("words")
    ap.add_argument("out")
    ap.add_argument("--max-pause", type=float, default=0.45,
                    help="un blanc plus long que ça est coupé (s)")
    ap.add_argument("--keep-pause", type=float, default=0.14,
                    help="respiration conservée à chaque coupe de silence (s)")
    ap.add_argument("--pad-before", type=float, default=0.07)
    ap.add_argument("--pad-after", type=float, default=0.09)
    ap.add_argument("--no-retakes", action="store_true")
    ap.add_argument("--remove", default="",
                    help="retraits forcés en secondes source, ex. '13.9-14.98,190.2-191.36'")
    a = ap.parse_args()

    data = json.load(open(a.words))
    words = merge_tokens(data["words"])
    db, dur = energy_db(a.video)
    nfr = len(db)
    floor = float(np.percentile(db, 8))
    speech = float(np.percentile(db, 85))
    thr = floor + 0.30 * (speech - floor)

    def fidx(t):
        return int(min(max(t / FRAME, 0), nfr - 1))

    def voiced(s, e):
        i, j = fidx(s), max(fidx(e), fidx(s) + 1)
        return float((db[i:j] > thr).mean()) if j > i else 0.0

    removed = []
    for w in words:
        w["n"] = norm(w["text"])
        w["drop"] = None

    # 0. hallucinations Whisper (texte connu, ou mot sans aucune énergie)
    full = " ".join(w["text"].lower() for w in words)
    for h in HALLUCINATIONS:
        k = full.find(h)
        while k >= 0:
            # retrouver les mots couvrant ce passage
            pos = 0
            for w in words:
                L = len(w["text"]) + 1
                if pos + L > k and pos < k + len(h) + 25:
                    w["drop"] = w["drop"] or "hallucination"
                pos += L
            k = full.find(h, k + 1)
    for w in words:
        if not w["drop"] and voiced(w["start"], w["end"]) < 0.05 and (w["end"] - w["start"]) > 0.15:
            w["drop"] = "silence-hallucination"

    # 1. hésitations
    for i, w in enumerate(words):
        if w["drop"] or w["n"] not in FILLERS:
            continue
        if w["n"] in SOFT_FILLERS:
            prev_gap = w["start"] - words[i - 1]["end"] if i else 1
            next_gap = words[i + 1]["start"] - w["end"] if i + 1 < len(words) else 1
            near_filler = (i and words[i - 1]["n"] in FILLERS) or (
                i + 1 < len(words) and words[i + 1]["n"] in FILLERS)
            if not (near_filler or (prev_gap > 0.25 and next_gap > 0.25)):
                continue
        w["drop"] = "hésitation"

    # 1b. mots coupés en plein milieu (« respons... », « déc- »)
    for w in words:
        if not w["drop"] and re.search(r"(\.\.\.|…|-)$", w["text"]) and len(w["n"]) >= 2:
            w["drop"] = "mot coupé"

    # 2. bégaiements « le le »
    for i in range(1, len(words)):
        p, w = words[i - 1], words[i]
        if not p["drop"] and not w["drop"] and p["n"] and p["n"] == w["n"] and len(p["n"]) <= 6 \
                and w["start"] - p["end"] < 0.8 and not p["text"].endswith((".", "?", "!")):
            p["drop"] = "bégaiement"

    # 3. phrases recommencées (prise ratée → reprise)
    if not a.no_retakes:
        live = [w for w in words if not w["drop"]]
        phrases, cur = [], []
        for i, w in enumerate(live):
            if cur and (w["start"] - cur[-1]["end"] > 0.28 or cur[-1]["text"].endswith((".", "?", "!"))):
                phrases.append(cur)
                cur = []
            cur.append(w)
        if cur:
            phrases.append(cur)
        for i, P in enumerate(phrases):
            if any(w["drop"] for w in P):
                continue
            pn = [w["n"] for w in P if w["n"]]
            if not pn or len(pn) > 14:
                continue
            for j in (i + 1, i + 2):
                if j >= len(phrases):
                    break
                Q = phrases[j]
                qn = [w["n"] for w in Q if w["n"]]
                if Q[0]["start"] - P[-1]["end"] > 6 or len(qn) < 2:
                    break
                k = min(len(pn), len(qn))
                head_same = len(pn) >= 2 and pn[:2] == qn[:2]
                ratio = difflib.SequenceMatcher(None, pn, qn[:k + 1]).ratio()
                # P ne se termine pas comme une vraie phrase finie, et Q la reprend
                if (head_same and len(pn) <= len(qn) + 1) or (ratio >= 0.72 and len(pn) >= 3):
                    for R in phrases[i:j]:
                        for w in R:
                            w["drop"] = w["drop"] or "prise ratée"
                    break

    for w in words:
        if w["drop"]:
            removed.append({"type": w["drop"], "text": w["text"], "start": w["start"], "end": w["end"]})

    kept = [w for w in words if not w["drop"]]
    if not kept:
        print("Aucun mot détecté : rien à monter.", file=sys.stderr)
        sys.exit(1)

    # --- recalage des bords sur l'énergie ---
    def true_end(t, limit):
        i, lim = fidx(t - 0.06), fidx(limit)
        run = 0
        while i < lim:
            run = run + 1 if db[i] < thr else 0
            if run >= 6:  # 60 ms de silence
                return (i - 5) * FRAME
            i += 1
        return min(t + 0.04, limit)

    def true_start(t, limit):
        i, lim = fidx(t + 0.04), fidx(limit)
        run = 0
        while i > lim:
            run = run + 1 if db[i] < thr else 0
            if run >= 6:
                return (i + 6) * FRAME
            i -= 1
        return max(t - 0.04, limit)

    segs = []
    s0 = true_start(kept[0]["start"], max(0, kept[0]["start"] - 0.4)) - a.pad_before
    seg_start = max(0.0, s0)
    for i in range(len(kept) - 1):
        w, nx = kept[i], kept[i + 1]
        gap = nx["start"] - w["end"]
        dropped_between = any(x["drop"] and x["start"] >= w["end"] - 0.01 and x["end"] <= nx["start"] + 0.01
                              for x in words)
        if gap < a.max_pause and not dropped_between:
            continue
        e = true_end(w["end"], nx["start"])
        s = true_start(nx["start"], e)
        half = a.keep_pause / 2
        cut_a = e + max(a.pad_after, half)
        cut_b = s - max(a.pad_before, half)
        if cut_b - cut_a < 0.12:  # coupe trop petite = inutile, on laisse respirer
            continue
        segs.append([seg_start, cut_a])
        seg_start = cut_b
    last = kept[-1]
    segs.append([seg_start, min(dur, true_end(last["end"], min(dur, last["end"] + 0.6)) + a.pad_after + 0.15)])
    # retraits forcés : hésitations repérées par la passe rapide (fillers) + --remove manuel.
    # Chaque bord est recalé sur le creux d'énergie le plus proche (±0,12 s) pour couper net.
    forced = [(f["start"], f["end"], f.get("type", "hésitation"), f.get("text", ""))
              for f in data.get("fillers", [])]
    for part in filter(None, a.remove.split(",")):
        x, y = part.split("-")
        forced.append((float(x), float(y), "retrait manuel", ""))

    def valley(t):
        i0, i1 = fidx(t - 0.12), fidx(t + 0.12)
        return (i0 + int(np.argmin(db[i0:i1 + 1]))) * FRAME if i1 > i0 else t

    for rs, re_, kind, txt in forced:
        rs, re_ = valley(rs), valley(re_)
        if re_ - rs < 0.08:
            continue
        new = []
        for s, e in segs:
            if re_ <= s or rs >= e:
                new.append([s, e])
                continue
            if rs - s > 0.05:
                new.append([s, rs])
            if e - re_ > 0.05:
                new.append([re_, e])
        if new != segs:
            removed.append({"type": kind, "text": txt, "start": round(rs, 3), "end": round(re_, 3)})
        segs = new
    segs = [[round(s, 3), round(e, 3)] for s, e in segs if e - s > 0.05]

    # remap des mots dans le temps monté
    out_words, offset = [], 0.0
    bounds = []
    for s, e in segs:
        bounds.append((s, e, offset))
        offset += e - s
    for w in kept:
        for s, e, off in bounds:
            if w["start"] < e and w["end"] > s:
                ns = off + max(w["start"], s) - s
                ne = off + min(w["end"], e) - s
                out_words.append({"text": w["text"], "start": round(ns, 3), "end": round(max(ne, ns + 0.05), 3)})
                break
    cut_points = [round(off, 3) for (_, _, off) in bounds[1:]]

    res = {"source": a.video, "duration_in": round(dur, 3), "duration_out": round(offset, 3),
           "segments": segs, "cut_points": cut_points, "removed": removed, "words": out_words,
           "audio": {"floor_db": round(floor, 1), "speech_db": round(speech, 1), "thr_db": round(thr, 1)}}
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    kinds = {}
    for r in removed:
        kinds[r["type"]] = kinds.get(r["type"], 0) + 1
    print(f"[cuts] {dur:.1f}s -> {offset:.1f}s | {len(segs)} segments, {len(cut_points)} coupes | "
          f"retirés: {kinds}", file=sys.stderr)


if __name__ == "__main__":
    main()
