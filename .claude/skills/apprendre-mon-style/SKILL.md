---
name: apprendre-mon-style
description: Apprend ma direction artistique à partir de vidéos de référence (fichiers ou liens TikTok/YouTube/Instagram téléchargés avec yt-dlp) - analyse le rythme, les couleurs, les sous-titres, les punchs et le son, puis met à jour les règles du monteur automatique (mes-regles.md et style.json). « Inspire-t'en, ne copie pas. » À utiliser quand on me donne des vidéos ou des liens « pour le style », « comme référence », « apprends mon goût », /apprendre-mon-style.
---

# Apprendre mon style

Nourrit le skill `/monteur-auto`. Ses fichiers de style :
`.claude/skills/monteur-auto/style/mes-regles.md` (les règles en mots) et
`.claude/skills/monteur-auto/style/style.json` (les chiffres utilisés par les scripts).

Autonome : ne pose pas de questions, décide à partir de ce que tu vois.

## 1. Analyser
```bash
python3 -I .claude/skills/monteur-auto/scripts/analyze_ref.py <dossier_sortie> <video_ou_lien> [<video_ou_lien> ...]
```
- Les liens sont téléchargés avec **yt-dlp** (les yeux), la parole transcrite avec **Whisper**
  (les oreilles), les plans détectés et mesurés avec **FFmpeg**.
- Sortie : `<dossier>/rapport.md` (plans/minute, mots/minute, loudness, luminosité, palette) et
  `<dossier>/refN/planche_XX.jpg` (1 image par seconde, horodatée).

## 2. Regarder
Ouvre **chaque planche** (outil Read) et note, pour chaque référence :
- **Sous-titres** : police (grotesque serrée ? serif ? mono ?), graisse, casse, taille relative,
  position (haut / milieu / bas), nombre de mots par groupe, animation (mot par mot, karaoké, pop),
  mots clés (couleur, police, taille), ombre ou fond.
- **Punchs** : gros titres plein cadre, fréquence, mélange de polices, couleur d'accent.
- **Cartes / motion design** : plein écran (fond, chiffres), cartes UI, split-screen, B-roll.
- **Caméra** : punch-ins aux coupes, zooms lents, durée moyenne d'un plan (rapport).
- **Couleur** : chaud/froid, contraste, saturation, vignette (rapport + planches).
- **Son** : loudness (rapport), musique, types d'effets.

## 3. Mettre à jour le style
- Réécris les sections concernées de `mes-regles.md` : des règles précises et chiffrées, avec la
  source (« vu dans réf 2 »). Garde ce qui marche déjà, ajoute, tranche quand deux références se
  contredisent (préférer le plus sobre et le plus lisible).
- Reporte les chiffres dans `style.json` (couleurs hex, tailles px, `emphasis_ratio`, `every_s` des
  punchs, `cut_alt` des zooms, `max_pause` des coupes, étalonnage...). Garde les clés existantes : les
  scripts les lisent. Valide le JSON (`python3 -m json.tool`).
- **S'inspirer, ne pas copier** : ne reprends ni logo, ni watermark, ni texte, ni personnage d'une
  référence ; seulement des principes (rythme, hiérarchie typo, palette, dosage des effets).
- Polices : seules celles de `monteur-auto/assets/fonts` sont garanties au rendu. Une nouvelle police
  doit être ajoutée en `.woff2` (licence libre, ex. paquets npm `@fontsource/<nom>`) dans
  `assets/fonts` et déclarée dans `font_faces()` de `scripts/build_hf.py`.

## 4. Vérifier
Si une vidéo de test est disponible, monte-la avec `/monteur-auto` (`--quality draft`) et regarde la
planche de contrôle pour confirmer que le nouveau style rend bien. Résume ensuite à l'utilisateur
ce qui a changé dans sa DA, en 5 lignes max.
