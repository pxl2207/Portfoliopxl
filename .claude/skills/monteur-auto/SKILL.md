---
name: monteur-auto
description: Monte automatiquement une vidéo face caméra (talking head) dans MA direction artistique, de A à Z et sans poser de questions - coupe les blancs, silences, « euh » et mots ratés (sans sur-couper), ajoute sous-titres dynamiques mot par mot, punchs typographiques, zooms caméra, un peu de motion design et des effets sonores, puis rend le MP4 vertical 1080x1920. Utilise les 4 outils FFmpeg, Whisper, yt-dlp et HyperFrames. À utiliser dès qu'on me donne une vidéo (fichier ou lien) à monter - « monte ma vidéo », « fais le montage », « edit this video », « sous-titre et monte », /monteur-auto.
---

# Monteur auto — une vidéo, 4 métiers

| Métier | Outil | Script |
| --- | --- | --- |
| Les oreilles | **Whisper** (faster-whisper) | `scripts/transcribe.py` |
| Les ciseaux | **FFmpeg** | `scripts/plan_cuts.py` + `scripts/cut.py` |
| Le monteur | **HyperFrames** | `scripts/plan_edit.py` + `scripts/build_hf.py` |
| Les yeux | **yt-dlp** | lien → vidéo (dans `monte.py`) et références (`/apprendre-mon-style`) |

`SKILL_DIR` = le dossier de ce fichier (dans ce repo : `.claude/skills/monteur-auto`).
La direction artistique fait foi : **lis `style/mes-regles.md` avant de commencer.** Les chiffres sont
dans `style/style.json`.

## Règle d'or : 100 % autonome
Ne pose **aucune question**. Toutes les décisions de style viennent de `mes-regles.md`. Si un choix est
ambigu, prends le plus sobre (moins d'effets, plus de vidéo visible) et note-le dans le compte rendu
final. Ne t'arrête que si la vidéo est illisible ou sans parole.

## Le déroulé

### 0. Outils
`python3 SKILL_DIR/scripts/monte.py` installe ce qui manque tout seul (`scripts/setup.sh`, idempotent).
Réseau : Whisper télécharge son modèle depuis huggingface.co au premier lancement
(`HF_HUB_DISABLE_XET=1` est déjà réglé).

### 1. Préparer (transcrire → planifier les coupes → couper → planifier l'habillage)
```bash
python3 -I SKILL_DIR/scripts/monte.py prep <video.mp4|lien> [--lang fr] [--model small]
```
Crée `<video>_montage/` avec `words.json`, `cuts.json`, `cut.mp4`, `plan.json`.
Langue : auto-détectée ; passe `--lang fr` si la vidéo est en français.
- Modèle par défaut **medium** (bien meilleur sur les noms propres, sigles, écoles, marques) + une passe
  rapide **small** qui ne sert qu'à repérer les « euh » et faux départs que medium « avale » dans les
  mots voisins (ils sont dans `words.json` → `fillers`, et coupés automatiquement).
- Vidéo iPhone/Android **HDR** (HLG/PQ) : convertie automatiquement en SDR par `cut.py` (sinon l'image
  sort grise et délavée).
- Compte ~2 min de calcul par minute de vidéo pour la transcription et ~2 min par minute pour la coupe.

**Vidéo dans Dropbox** (trop lourde pour le chat) : `search` (catégorie vidéo) → `download_link` →
`curl -o` dans un dossier de travail. Le lien est à usage unique (ne pas le tester avant) et chaque lien
pointe vers un sous-domaine aléatoire `uc….dl.dropboxusercontent.com` : si le réseau est limité, il faut
l'ouvrir le temps du téléchargement puis le refermer.

### 2. Relire et affiner (c'est là que tu es le monteur)
Lis `cuts.json` puis `plan.json` en entier, avec la transcription. Corrige directement les JSON :

**Les coupes (`cuts.json` → `removed`)** — vérifie chaque retrait :
- une « prise ratée » qui n'en est pas une (deux phrases différentes qui commencent pareil) → relance
  `plan_cuts.py` avec `--no-retakes`, ou ajuste `segments` à la main ;
- un « euh » oublié, un faux départ, une phrase reprise (« me correspond plutôt, et correspond plutôt
  vraiment ») → relance `plan_cuts.py ... --remove "13.9-14.1,190.16-191.33"` (secondes de la source ;
  chaque bord est recalé sur le creux de son le plus proche). Pour un timing précis, re-transcris
  juste l'extrait de 3 s (Whisper est bien plus précis sur un court extrait) et regarde l'énergie ;
- si tu modifies `cuts.json`, relance `cut.py` puis `plan_edit.py` (commandes dans `monte.py`), puis
  reviens au plan.
- **Pas trop de coupes** : jamais de coupe au milieu d'une phrase fluide, jamais pour gagner 0,2 s.

**Le plan (`plan.json`)** :
- `captions[].words[].text` : corrige l'orthographe et les noms propres mal entendus par Whisper
  (marques, prénoms, sigles, écoles : EDHEC, NEOMA, SKEMA, HGGSP…). Ne change jamais les temps. Un mot
  vidé (`""`) disparaît. Un nom de personne que tu ne peux pas vérifier : garde la meilleure
  transcription et signale-le dans le compte rendu.
- Si tu supprimes un punch, remets ses mots en sous-titres (sinon ils disparaissent de l'écran) ; si
  tu en ajoutes un, retire ces mots des sous-titres. Recalcule ensuite les `push` de `camera` et les
  sons (`sfx`) pour qu'ils suivent les punchs et pleins écrans.
- `emph` : ~1 mot clé par groupe 4 fois sur 10 — le cœur de la phrase (chiffre, nom, mot fort).
  Jamais sur un mot outil (« le », « de », « c'est »).
- `punches` : le hook (1re phrase) doit être percutant ; les autres punchs tombent sur les **idées
  fortes** (une affirmation, une chute, un chiffre), max 1 toutes les ~11 s. Remplace un punch faible
  par un meilleur moment, ou supprime-le. `lines` : ligne `sans` (blanc, gras) + ligne `serif`
  (italique orange) qui porte le mot clé, 2 à 6 mots au total. Les mots d'un punch ne sont pas en
  sous-titre au même moment : si tu déplaces un punch, retire/rajoute ces mots dans `captions`.
- `fullscreens` : seulement pour un chiffre / montant / pourcentage marquant. 1,5 s max.
- `cards` (motion design, optionnel, 0 à 2 par vidéo) : quand la personne cite une liste d'outils,
  d'étapes ou un nom à retenir. Format :
  `{"id":"k0","start":12.3,"end":15.0,"label":"Les ciseaux","title":"FFmpeg","icon":"scissors","pill":"gratuit","position":"top"}`
  icônes : play, scissors, wave, eye, check, star, bolt, euro, clock. `position` : `top` (tiers haut,
  si le visage est bas) ou `bottom` (à la place des sous-titres : alors coupe les sous-titres sur ce
  créneau). Ajoute un son `{"t": start, "name": "pop", "vol": 0.35, "var": 0}` dans `sfx`.
- `sfx` : un son = une cause à l'écran. Pas plus d'un son toutes les ~2 s.

### 3. Rendre
```bash
python3 -I SKILL_DIR/scripts/monte.py render --work <video>_montage [--music musique.mp3]
```
Construit le projet HyperFrames (`<work>/projet/`), lance `hyperframes check` (s'arrête sur une erreur),
rend le MP4 et écrit `rapport.json` + `controle.jpg` (12 images).
`--quality draft` pour un essai rapide. Musique : seulement si on t'en fournit une (volume 0,10).

### 4. Contrôler (obligatoire)
- **Regarde `controle.jpg`** (outil Read). Vérifie : visage jamais caché, texte lisible, pas de
  sous-titre en double, punchs bien placés, rien de coupé au bord.
- Pour zoomer sur un moment : `hyperframes snapshot --at 3.2,8.5 --no-end` dans `<work>/projet`.
- `rapport.json` : loudness ≈ -14 LUFS, true peak < -1 dB.
- Un problème → corrige `plan.json` (ou `style.json`) et relance l'étape 3. Deux passes max.

### 5. Livrer
Donne le chemin du MP4 final et un compte rendu court : durée brute → montée, nombre de coupes et
ce qui a été retiré (blancs, hésitations, prises ratées), nombre de punchs / mots clés / sons,
et les choix faits à ta place. Précise que le son a été mesuré, pas écouté.
Pour retoucher à la main : `hyperframes preview` dans `<work>/projet` (le studio HyperFrames).

## Tout d'un coup (sans relecture)
`python3 -I SKILL_DIR/scripts/monte.py all <video> --lang fr` enchaîne 1 et 3 avec les choix
automatiques. À réserver aux essais : la relecture de l'étape 2 fait la qualité.

## Changer de style
- À la main : édite `style/mes-regles.md` (les mots) et `style/style.json` (les chiffres).
- À partir de nouvelles vidéos de référence : `/apprendre-mon-style`.

## Dépannage
| Symptôme | Remède |
| --- | --- |
| `403` / blocage en téléchargeant le modèle Whisper | autoriser `huggingface.co`, `us.aws.cdn.hf.co` (ou `eu.`) dans le réseau ; `HF_HUB_DISABLE_XET=1` |
| `TypeError: open() got an unexpected keyword argument 'metadata_errors'` | ne pas passer par PyAV : `transcribe.py` décode déjà via FFmpeg |
| Whisper invente une phrase à la fin (« Sous-titres réalisés par… ») | filtrée par `plan_cuts.py` (hallucinations) ; sinon supprime les mots dans `cuts.json` |
| Vidéo horizontale | recadrée au centre en 9:16 par `cut.py` (vérifie que le visage reste dans le cadre) |
| Rendu lent | `--quality draft` pour itérer ; ~5 s de calcul par seconde de vidéo sur 4 cœurs |
| Polices | embarquées dans `assets/fonts` (Inter Tight, Instrument Serif, JetBrains Mono, licence OFL) |
| GSAP | embarqué dans `assets/js` (aucun CDN requis) |

Pour aller plus loin avec HyperFrames (blocs du registre, texte derrière la tête, transitions) :
skills `/hyperframes`, `/hyperframes-registry`, `/media-use` (installés par `hyperframes skills`).
