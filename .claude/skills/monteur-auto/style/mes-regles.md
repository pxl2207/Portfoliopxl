# Mes règles — direction artistique

> Tirées de mes vidéos de référence (talking head architecte FR, « How Claude edits my videos »)
> et de mes visuels (« Une vidéo, 4 métiers »). **Inspire-t'en, ne copie pas.**
> Ce fichier fait foi. Les chiffres correspondants sont dans `style.json`.

## 1. Le principe
- **La vidéo d'abord.** On voit la personne qui parle ~90 % du temps. Les effets *accompagnent* la
  parole, ils ne la remplacent jamais. Jamais de carte sur le visage.
- **Sobre, éditorial, premium.** Peu d'éléments, mais chacun soigné. Rien de « template TikTok ».
- **Le son raconte aussi.** Chaque effet sonore a une cause à l'écran.

## 2. Le rythme et les coupes
- On coupe **seulement** : les blancs > 0,45 s, les « euh / hum », les mots ratés et les phrases
  recommencées (on garde toujours la **dernière** prise, la bonne).
- On garde une respiration de ~0,14 s à chaque coupe : la parole doit rester naturelle,
  jamais hachée ni « jump-cut toutes les 2 s ».
- Chaque coupe est masquée par un **changement de cadrage** (alternance plan large 1.0 ↔ plan
  serré ~1.09). Entre les coupes, une **dérive lente** (zoom +3,5 %) garde l'image vivante.

## 3. Les sous-titres dynamiques (signature)
- 2 à 4 mots par groupe, en **minuscules**, police **Inter Tight 800**, blanc, ombre douce.
- Apparition **mot par mot** au moment exact où il est dit ; les mots à venir du groupe sont
  déjà là en **blanc à 38 %** (on lit en avance, le mot dit s'allume).
- **Un mot clé** par groupe environ 4 fois sur 10 : en **Instrument Serif italique**, couleur
  accent (orange `#E8763A`), 1,3× plus grand. Mots clés = chiffres, noms, mots forts
  (« énorme », « jamais », « gratuit »), le cœur de la phrase.
- Placés dans la zone basse sûre (bas du texte ≤ 1210 px), centrés, jamais sur le visage.

## 4. Les « punchs » typographiques
- Le **hook** (1re phrase) est toujours en gros titre : mot fort en sans-serif 900 serré
  + mot clé en serif italique orange (ex. « on ne respecte pas / *les architectes* »).
- Ensuite un punch toutes les ~11 s maximum, sur l'idée forte (pas sur une phrase de liaison).
- Pendant un punch : le sous-titre normal disparaît, la caméra pousse (zoom 1.12), **whoosh**.
- Le texte entre par le bas avec un masque + léger flou, sort en fondu vers le haut.

## 5. Cartes plein écran (rares)
- Uniquement pour un **chiffre / montant / statistique** (« 150 000 € », « 10 % »).
- Fond papier `#F3F1EC`, encre `#141414`, chiffre en Inter Tight 900, contexte en serif italique.
- 1,5 s maximum, 1 toutes les 30 s maximum → la vidéo revient vite. Impact basse discret.

## 6. Motion design léger (optionnel, décidé par Claude)
- Cartes blanches arrondies type « fiche » (label mono + titre gras + icône orange),
  pour une énumération ou un outil cité. Petite pastille verte `#1F9D57` pour un sous-titre
  de carte. Glissent du bas, 2–4 s, dans le tiers haut si le visage est bas, sinon à la place
  des sous-titres.

## 7. Couleur & son
- **Ne jamais changer les couleurs de mes vidéos.** Aucun étalonnage, aucune LUT, aucune vignette.
  Une vidéo HDR (iPhone : HLG / Dolby Vision) reste en HDR, telle qu'elle a été filmée
  (`style.json` → `"grade": {"enabled": false}`, `"hdr": "keep"`).
- Voix : nettoyée, compressée, **-14 LUFS**. Effets à ~0,4 de volume, jamais plus fort que la voix.
- Palette de sons : whoosh (punch), impact basse (carte chiffre), pop (carte), clic doux
  (rare, sur un mot clé). On fait varier les prises (pitch) pour ne jamais répéter le même son.
