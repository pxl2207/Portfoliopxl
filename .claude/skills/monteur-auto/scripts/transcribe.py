#!/usr/bin/env python3
"""Les oreilles — transcription mot par mot avec faster-whisper (Whisper).

Usage: transcribe.py <video|audio> <out_words.json> [--model small|medium|large-v3] [--lang fr]

Sortie JSON : {"lang": "fr", "duration": 61.2,
               "words": [{"text": "Bonjour", "start": 0.12, "end": 0.48, "prob": 0.98}, ...]}

L'audio est décodé par FFmpeg (pas besoin de PyAV), en 16 kHz mono.
"""
import argparse
import json
import os
import subprocess
import sys

import numpy as np

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")  # téléchargement HTTP simple (proxy-friendly)


def load_audio(path, sr=16000):
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", path, "-vn", "-ac", "1", "-ar", str(sr), "-f", "f32le", "-"],
        capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--model", default=os.environ.get("MONTEUR_WHISPER", "medium"))
    ap.add_argument("--lang", default=None, help="fr, en... (auto si absent)")
    ap.add_argument("--fillers-model", default="small",
                    help="passe rapide pour repérer euh / faux départs ('' pour désactiver)")
    a = ap.parse_args()

    from faster_whisper import WhisperModel

    audio = load_audio(a.src)
    dur = len(audio) / 16000
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    segs, info = model.transcribe(
        audio,
        language=a.lang,
        word_timestamps=True,
        vad_filter=False,              # on garde tout : les silences sont gérés par plan_cuts
        condition_on_previous_text=False,  # évite les boucles/hallucinations
        # Les hésitations doivent apparaître dans le texte pour pouvoir les couper :
        initial_prompt="Euh, alors, bah, hum... Voilà, donc euh, en fait.",
    )
    words = []
    for s in segs:
        for w in (s.words or []):
            t = w.word.strip()
            if not t:
                continue
            words.append({"text": t, "start": round(float(w.start), 3),
                          "end": round(float(w.end), 3), "prob": round(float(w.probability), 3)})
    # Les gros modèles (medium, large) écrivent mieux mais « avalent » les euh et les faux départs
    # dans les mots voisins. Une passe rapide « small » ne sert qu'à les repérer.
    fillers = []
    if a.fillers_model and a.fillers_model != a.model:
        import re
        fm = WhisperModel(a.fillers_model, device="cpu", compute_type="int8")
        fs, _ = fm.transcribe(audio, language=info.language, word_timestamps=True, vad_filter=False,
                              condition_on_previous_text=False,
                              initial_prompt="Euh, alors, bah, hum... Voilà, donc euh, en fait.")
        FILL = {"euh", "heu", "euhm", "hum", "hmm", "hm", "mmh", "mh", "uh", "um", "uhm", "erm", "ehm"}
        for s in fs:
            for w in (s.words or []):
                t = w.word.strip()
                n = re.sub(r"[^a-zà-ÿ]", "", t.lower())
                if n in FILL:
                    fillers.append({"type": "hésitation", "text": t, "start": round(float(w.start), 3),
                                    "end": round(float(w.end), 3)})
                elif re.search(r"(\.\.\.|…)$", t) and len(n) >= 2 and (w.end - w.start) > 0.45:
                    fillers.append({"type": "mot coupé", "text": t, "start": round(float(w.start), 3),
                                    "end": round(float(w.end), 3)})
    json.dump({"lang": info.language, "duration": round(dur, 3), "words": words, "fillers": fillers},
              open(a.out, "w"), ensure_ascii=False, indent=0)
    print(f"[transcribe] {len(words)} mots, {len(fillers)} hésitations, langue={info.language}, durée={dur:.1f}s -> {a.out}",
          file=sys.stderr)


if __name__ == "__main__":
    main()
