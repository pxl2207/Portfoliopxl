#!/usr/bin/env python3
"""Le réalisateur — transforme les mots montés en plan d'habillage (plan.json).

Entrée : cuts.json (mots remappés dans le temps monté + points de coupe), style.json
Sortie : plan.json, lisible et éditable, que Claude affine ensuite (mots clés, punchs, cartes) :
  {
    "duration": 42.3,
    "captions": [ {"id","start","end","words":[{"text","start","end","emph"}]} ],
    "punches":  [ {"id","start","end","lines":[{"text","style":"sans|serif"}], "hook":bool} ],
    "fullscreens": [ {"id","start","end","big","ctx"} ],
    "cards": [],   # motion design optionnel, ajouté par Claude (voir SKILL.md)
    "camera": [ {"t","scale","ease","dur"} ],
    "sfx": [ {"t","name","vol"} ]
  }
Toutes les décisions sont heuristiques et volontairement sobres (peu d'effets, la vidéo d'abord).
"""
import argparse
import json
import re
import sys

STOP = set("""
le la les un une des du de d l au aux et ou mais donc or ni car que qu qui quoi dont où ce cet
cette ces se sa son ses mon ma mes ton ta tes leur leurs notre nos votre vos je j tu il elle on nous
vous ils elles me m te t lui y en ne n pas plus très trop bien a à est c ça ca cest c'est sont été être
avoir ai as avez ont fait faire va vais vont dans sur sous avec pour par chez entre comme si alors
aussi encore déjà tout tous toute toutes même quand puis voilà bon bref genre ok oui non là ici
the a an and or but so to of in on at for with is are was were be been it this that you i we they
he she my your our their just like can will do does did have has had not no yes
""".split())
STRONG = set("""
énorme jamais toujours gratuit gratuite gratuits incroyable fou folle dingue abusé vraiment
secret secrets erreur erreurs problème problèmes facile simple rapide meilleur meilleure pire
argent riche pauvre million millions milliard mille record exactement personne rien tout
interdit danger attention stop important essentiel parfait parfaite impossible gratuitement
difficile compliqué responsabilité rêve rêves vocation
free never always secret mistake money best worst easy fast huge insane crazy zero
""".split())
UNITS = {"€", "%", "$", "euros", "euro", "pourcent", "pour", "cent", "mille", "millions", "million",
         "milliards", "k", "ans", "mois", "jours", "heures", "minutes", "secondes", "fois", "x",
         "dollars", "percent", "years", "months", "days", "hours"}
NUM_RE = re.compile(r"^\d[\d\s., ]*(%|€|\$|k)?$")


def clean(t):
    return re.sub(r"[\s]+", " ", t).strip()


def bare(t):
    return re.sub(r"[^\wÀ-ÿ%€$'’-]", "", t.lower())


def is_num(t):
    return bool(NUM_RE.match(t.strip(".,!?;:")))


def score(w, prev):
    b = bare(w["text"])
    if not b or b in STOP:
        return 0.0
    s = 0.0
    if is_num(w["text"]):
        s += 6
    if b in STRONG:
        s += 4.5
    letters = len(re.sub(r"[^a-zà-ÿ]", "", b))
    if letters >= 7:
        s += 1.5 + (letters - 7) * 0.35
    elif letters >= 5:
        s += 0.8
    if w["text"][:1].isupper() and prev is not None and not prev["text"].endswith((".", "?", "!")):
        s += 2.0  # nom propre
    if w["text"].isupper() and len(b) >= 2:
        s += 2.0  # sigle (CDI, IA...)
    return s


def display(t, lower):
    t = t.strip()
    t = re.sub(r"[,;:]+$", "", t)
    t = re.sub(r"\.+$", "", t) if not t.endswith("...") else t
    if lower and not (t.isupper() and len(t) >= 2):
        t = t.lower()
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cuts")
    ap.add_argument("style")
    ap.add_argument("out")
    a = ap.parse_args()
    cuts = json.load(open(a.cuts))
    st = json.load(open(a.style))
    C, P, Z, F, S = st["captions"], st["punch"], st["zoom"], st["fullscreen"], st["sfx"]
    words = [dict(w) for w in cuts["words"]]
    D = cuts["duration_out"]
    for i, w in enumerate(words):
        w["i"] = i
        w["score"] = score(w, words[i - 1] if i else None)

    # ---------- phrases (pour les punchs) ----------
    sentences, cur = [], []
    for w in words:
        cur.append(w)
        if w["text"].endswith((".", "?", "!")):
            sentences.append(cur)
            cur = []
    if cur:
        sentences.append(cur)

    used = set()       # indices de mots « mangés » par un punch / plein écran
    punches, fulls, busy = [], [], []  # busy = intervalles occupés par un gros élément

    def free(s, e, gap):
        return all(e + gap <= bs or s >= be + gap for bs, be in busy)

    def make_punch(ws, hook=False):
        """Lignes dans l'ordre de la phrase : [sans lourd] [*mot clé* serif italique] [sans].
        Le mot clé emporte avec lui ses petits mots (« les architectes »)."""
        n = len(ws)
        k = max(range(n), key=lambda j: ws[j]["score"] + (2.5 * j / n if hook else 0))
        if k + 1 < n and bare(ws[k + 1]["text"]) in UNITS:
            k2 = k + 1
        else:
            k2 = k
        k0 = k
        while k0 > 0 and k - k0 < 2 and bare(ws[k0 - 1]["text"]) in STOP and k0 - 1 > 0:
            k0 -= 1
        lines = []
        if ws[:k0]:
            lines.append({"text": " ".join(display(x["text"], True) for x in ws[:k0]), "style": "sans"})
        lines.append({"text": " ".join(display(x["text"], True) for x in ws[k0:k2 + 1]), "style": "serif"})
        if ws[k2 + 1:]:
            lines.append({"text": " ".join(display(x["text"], True) for x in ws[k2 + 1:]), "style": "sans"})
        span = ws
        s = max(0.08, span[0]["start"] - 0.06)
        e = max(span[-1]["end"] + 0.3, s + 1.0)
        nxt = [w for w in words if w["start"] > span[-1]["end"]]
        if nxt:
            e = min(e, max(nxt[0]["start"] + 0.15, span[-1]["end"] + 0.12))
        e = min(e, D)
        for x in span:
            used.add(x["i"])
        busy.append((s, e))
        punches.append({"id": f"p{len(punches)}", "start": round(s, 3), "end": round(e, 3),
                        "lines": lines, "hook": hook})

    # Hook : la première phrase (ou ses 6 premiers mots) en gros titre
    if P.get("first_hook") and sentences:
        first = sentences[0]
        cut = first[:8] if len(first) > 8 else first
        # coupe à la virgule si possible
        for j, w in enumerate(cut):
            if w["text"].endswith(",") and j >= 2:
                cut = cut[:j + 1]
                break
        if len(cut) >= 2:
            make_punch(cut, hook=True)

    # Plein écran : chiffres / montants / pourcentages
    if F.get("enabled"):
        for i, w in enumerate(words):
            if w["i"] in used or not is_num(w["text"]):
                continue
            nxt = words[i + 1] if i + 1 < len(words) else None
            big = [w] + ([nxt] if nxt and bare(nxt["text"]) in UNITS else [])
            if len(re.sub(r"\D", "", w["text"])) < 2 and len(big) == 1:
                continue  # un « 2 » isolé n'est pas un chiffre clé
            s = max(0.2, w["start"] - 0.05)
            e = min(D, s + F["dur"])
            if s < 2.5 or not free(s, e, F["min_gap_s"] / 2):
                continue
            if fulls and s - fulls[-1]["start"] < max(F["min_gap_s"], 30 / max(F["max_per_30s"], 1)):
                continue
            ctx_words = []
            for x in words[i + len(big):i + len(big) + 3]:
                if x["start"] >= e or (ctx_words and ctx_words[-1]["text"].endswith((".", ",", "?", "!"))):
                    break
                ctx_words.append(x)
            while ctx_words and bare(ctx_words[-1]["text"]) in STOP:
                ctx_words.pop()
            for x in big + ctx_words:
                used.add(x["i"])
            busy.append((s, e))
            fulls.append({"id": f"f{len(fulls)}", "start": round(s, 3), "end": round(e, 3),
                          "big": " ".join(display(x["text"], False) for x in big).replace(" %", " %")
                          .replace(" €", " €"),
                          "ctx": " ".join(display(x["text"], True) for x in ctx_words)})

    # Punchs réguliers sur les idées fortes
    t = punches[-1]["end"] + 2.5 if punches else 2.5
    while t < D - 2.0:
        win = [w for w in words if t <= w["start"] < t + P["every_s"] and w["i"] not in used]
        best = max(win, key=lambda w: w["score"], default=None)
        if not best or best["score"] < 3.5:
            t += P["every_s"] / 2
            continue
        sent = next(s for s in sentences if best in s)
        k = sent.index(best)
        lo = k
        while lo > 0 and k - lo < 3 and not sent[lo - 1]["text"].endswith(",") and sent[lo - 1]["i"] not in used:
            lo -= 1
        ws = sent[lo:k + 1]
        if k + 1 < len(sent) and bare(sent[k + 1]["text"]) in UNITS:
            ws = ws + [sent[k + 1]]
        if any(x["i"] in used for x in ws):
            t += 2
            continue
        s = ws[0]["start"]
        if not free(s - 0.1, ws[-1]["end"] + 0.4, P["min_gap_s"]):
            t += 2
            continue
        make_punch(ws)
        t = punches[-1]["end"] + P["every_s"] * 0.7

    # ---------- sous-titres (mots restants) ----------
    caps, grp = [], []

    def flush():
        if grp:
            caps.append(list(grp))
            grp.clear()

    for i, w in enumerate(words):
        if w["i"] in used:
            flush()
            continue
        if grp:
            gap = w["start"] - grp[-1]["end"]
            chars = sum(len(x["text"]) + 1 for x in grp) + len(w["text"])
            crossed = any(grp[-1]["end"] - 0.02 <= c <= w["start"] + 0.02 for c in cuts.get("cut_points", []))
            punct = grp[-1]["text"].endswith((".", "?", "!", ",", ";", ":"))
            if crossed or gap > 0.3 or punct:
                flush()
            elif len(grp) >= C["max_words"] or chars > C["max_chars"]:
                # ne jamais finir un groupe sur un petit mot (« une », « de », « et »)
                carry = []
                while len(grp) > 2 and bare(grp[-1]["text"]) in STOP:
                    carry.insert(0, grp.pop())
                flush()
                grp.extend(carry)
        grp.append(w)
    flush()

    # mot clé par groupe (part des groupes = emphasis_ratio, les plus forts)
    best_per = [max(g, key=lambda x: x["score"]) for g in caps]
    ranked = sorted([b["score"] for b in best_per], reverse=True)
    n_emph = int(round(len(caps) * C["emphasis_ratio"]))
    cutoff = max(3.0, ranked[n_emph - 1] if n_emph and ranked else 99)
    captions = []
    for gi, g in enumerate(caps):
        b = best_per[gi]
        s = max(0.1, g[0]["start"] - 0.06)
        nxt_start = caps[gi + 1][0]["start"] - 0.06 if gi + 1 < len(caps) else D
        e = min(nxt_start, g[-1]["end"] + 0.45, D)
        for bs, be in busy:  # jamais en même temps qu'un gros élément
            if s < be and e > bs:
                if s < bs:
                    e = min(e, bs)
                else:
                    s = max(s, be)
        if e - s < 0.12:
            continue
        captions.append({"id": f"c{len(captions)}", "start": round(s, 3), "end": round(e, 3),
                         "words": [{"text": display(x["text"], C["lowercase"]),
                                    "start": round(max(x["start"], s), 3), "end": round(x["end"], 3),
                                    "emph": bool(x is b and b["score"] >= cutoff)} for x in g]})

    # ---------- caméra : alternance aux coupes + dérive + push sur les punchs ----------
    bounds = [0.0] + [c for c in cuts.get("cut_points", []) if 0 < c < D] + [D]
    camera = []
    alt = Z["cut_alt"]
    for k in range(len(bounds) - 1):
        s, e = bounds[k], bounds[k + 1]
        base = alt[k % len(alt)]
        camera.append({"t": round(s, 3), "scale": base, "set": True})
        camera.append({"t": round(e - 0.001, 3), "scale": round(base + Z["drift"] * min(1, (e - s) / 6), 4),
                       "ease": "none", "from_t": round(s, 3)})
    for p in punches + fulls:
        camera.append({"t": p["start"], "push": P["zoom"] if p in punches else 1.0, "until": p["end"]})

    # ---------- sons ----------
    sfx, last_emph = [], -99
    for k, p in enumerate(punches):
        sfx.append({"t": p["start"], "name": S["punch"][k % len(S["punch"])], "vol": S["volume"],
                    "var": k % 3})
    for k, f in enumerate(fulls):
        sfx.append({"t": f["start"], "name": S["fullscreen"][k % len(S["fullscreen"])],
                    "vol": S["volume"] * 0.9, "var": k % 3})
    for c in captions:
        for w in c["words"]:
            if w["emph"] and w["start"] - last_emph >= S["emph_every_s"]:
                sfx.append({"t": w["start"], "name": S["emph"][0], "vol": S["volume"] * 0.55,
                            "var": len(sfx) % 3})
                last_emph = w["start"]
    sfx.sort(key=lambda x: x["t"])

    plan = {"duration": D, "captions": captions, "punches": punches, "fullscreens": fulls,
            "cards": [], "camera": camera, "sfx": sfx,
            "transcript": " ".join(w["text"] for w in words)}
    json.dump(plan, open(a.out, "w"), ensure_ascii=False, indent=1)
    ne = sum(w["emph"] for c in captions for w in c["words"])
    print(f"[plan] {len(captions)} groupes de sous-titres ({ne} mots clés), {len(punches)} punchs, "
          f"{len(fulls)} plein écran, {len(sfx)} sons, {len(bounds) - 2} coupes caméra", file=sys.stderr)


if __name__ == "__main__":
    main()
