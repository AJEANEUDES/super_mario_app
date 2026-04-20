# 📊 Documentation du Dataset — LADDER

> Document : Description du Dataset  
> Version : 1.0.0  
> Jeu couvert : Super Mario Bros (NES)

---

## Table des matières

1. [Description générale](#1-description-générale)
2. [Sources des données](#2-sources-des-données)
3. [Structure des fichiers](#3-structure-des-fichiers)
4. [Variables et format](#4-variables-et-format)
5. [Classes d'objets YOLO](#5-classes-dobjets-yolo)
6. [Statistiques du dataset](#6-statistiques-du-dataset)
7. [Limites et biais connus](#7-limites-et-biais-connus)
8. [Utilisation recommandée](#8-utilisation-recommandée)

---

## 1. Description générale

Le dataset LADDER est composé de **deux couches de données complémentaires** :

### Couche 1 — Données de performance joueur

Informations structurées sur les runs de speedrun collectées depuis speedrun.com.

| Attribut | Description |
|---|---|
| Jeu | Super Mario Bros (NES) |
| Catégorie | Any% NTSC |
| Source | speedrun.com |
| Format | CSV / JSON |
| Granularité | Par run (une entrée = un run complet) |

### Couche 2 — Données visuelles annotées

Frames extraites des vidéos de speedrun, annotées avec les positions des objets de jeu.

| Attribut | Description |
|---|---|
| Format images | JPEG (.jpg), résolution native |
| Format annotations | YOLO (.txt), coordonnées normalisées |
| Niveau annoté (complet) | 1-1 |
| Classes détectées | 26 classes d'objets |
| Modèle de détection | YOLOv8n, mAP50 ~97–99 % |

---

## 2. Sources des données

### speedrun.com

- **URL de base :** `https://www.speedrun.com/smb1`
- **Catégorie principale :** Any% NTSC
- **Données collectées :** rang, pseudo joueur, temps en secondes, date, URL vidéo, plateforme
- **Méthode :** Scraping Selenium (navigateur automatisé)
- **Fréquence de collecte :** ponctuelle (snapshot)

### Vidéos YouTube / Twitch

- Téléchargées via **yt-dlp**
- Format : MP4, qualité maximale disponible
- Résolution typique : 1280×720 ou 1920×1080

---

## 3. Structure des fichiers

```
performance_data/
└── super_mario_desktop/
    │
    ├── speedrun_data/
    │   └── runs_{YYYYMMDD_HHMMSS}.csv       ← données de performance
    │
    ├── videos/
    │   └── {player}_{rank}.mp4              ← vidéos brutes
    │
    ├── frames/
    │   └── {video_name}/
    │       └── frame_{NNNNNN}.jpg           ← frames extraites (1/sec)
    │
    ├── classified_levels/
    │   └── level_{X-Y}/
    │       └── frame_{NNNNNN}.jpg           ← frames triées par niveau
    │
    ├── annotations/
    │   └── level_{X-Y}/
    │       └── labels/
    │           └── frame_{NNNNNN}.txt       ← annotations YOLO
    │
    ├── augmented_dataset/
    │   ├── images/
    │   │   └── level_{X-Y}_{frame}_{aug}_{idx}.jpg
    │   ├── labels/
    │   │   └── level_{X-Y}_{frame}_{aug}_{idx}.txt
    │   └── data.yaml
    │
    └── predictions/
        └── {run_name}/
            ├── images/                     ← images avec bbox dessinées
            └── labels/
                └── frame_{NNNNNN}.txt      ← prédictions YOLO
```

---

## 4. Variables et format

### 4.1 Données de performance — `runs_{timestamp}.csv`

| Colonne | Type | Description | Exemple |
|---|---|---|---|
| `rank` | int | Classement dans le leaderboard | `1` |
| `player` | str | Pseudo du joueur | `"Kosmic"` |
| `time_seconds` | float | Temps de run en secondes | `296.516` |
| `time_formatted` | str | Temps au format mm:ss.ms | `"4:56.516"` |
| `date` | str | Date de soumission | `"2023-08-15"` |
| `video_url` | str | URL de la vidéo | `"https://youtu.be/..."` |
| `platform` | str | Plateforme de jeu | `"NES"` |
| `category` | str | Catégorie du run | `"Any% NTSC"` |

**Exemple de ligne :**
```csv
rank,player,time_seconds,time_formatted,date,video_url,platform,category
1,Kosmic,296.516,4:56.516,2023-08-15,https://youtu.be/xxx,NES,Any% NTSC
```

---

### 4.2 Annotations YOLO — `frame_{NNNNNN}.txt`

Format standard YOLO : une ligne par objet détecté.

```
{class_id} {x_center} {y_center} {width} {height}
```

| Champ | Type | Description | Contraintes |
|---|---|---|---|
| `class_id` | int | Identifiant de la classe (0–25) | 0 ≤ id ≤ 25 |
| `x_center` | float | Centre horizontal de la bbox | 0.0 ≤ x ≤ 1.0 |
| `y_center` | float | Centre vertical de la bbox | 0.0 ≤ y ≤ 1.0 |
| `width` | float | Largeur de la bbox | 0.0 < w ≤ 1.0 |
| `height` | float | Hauteur de la bbox | 0.0 < h ≤ 1.0 |

**Toutes les coordonnées sont normalisées** par rapport aux dimensions de l'image.

**Exemple :**
```
# frame_000042.txt
11 0.512 0.743 0.045 0.089   # little_mario
8  0.720 0.810 0.032 0.058   # goomba
1  0.250 0.600 0.062 0.062   # brick_block
1  0.312 0.600 0.062 0.062   # brick_block
```

**Conversion en coordonnées pixels :**
```python
x_min = (x_center - width / 2)  * image_width
y_min = (y_center - height / 2) * image_height
x_max = (x_center + width / 2)  * image_width
y_max = (y_center + height / 2) * image_height
```

---

### 4.3 Configuration dataset — `data.yaml`

```yaml
# Généré automatiquement par DatasetAugmentationTask
path: /chemin/absolu/vers/augmented_dataset
train: images
val: images

nc: 26    # nombre de classes
names:
  - big_mario           # 0
  - brick_block         # 1
  - coin                # 2
  - empty_block         # 3
  - fire_mario          # 4
  - fireball            # 5
  - flower              # 6
  - goal_pole           # 7
  - goomba              # 8
  - hard_block          # 9
  - koopa               # 10
  - little_mario        # 11
  - mushroom            # 12
  - mystery_block       # 13
  - pipe                # 14
  - pipe_head           # 15
  - shell               # 16
  - undestructible_block # 17
  - flag                # 18
  - hammer              # 19
  - fish_flying         # 20
  - piranha             # 21
  - turtle              # 22
  - lakitu              # 23
  - magic_bean          # 24
  - spike               # 25
```

---

## 5. Classes d'objets YOLO

### Personnages

| ID | Classe | Description |
|---|---|---|
| 0 | `big_mario` | Mario en grande forme |
| 11 | `little_mario` | Mario en petite forme |
| 4 | `fire_mario` | Mario avec pouvoir de feu |

### Ennemis

| ID | Classe | Description |
|---|---|---|
| 8 | `goomba` | Champignon ennemi basique |
| 10 | `koopa` | Tortue verte/rouge |
| 16 | `shell` | Carapace de koopa |
| 22 | `turtle` | Tortue (variante) |
| 23 | `lakitu` | Lakitu sur son nuage |
| 21 | `piranha` | Plante piranha |
| 20 | `fish_flying` | Poisson volant (Cheep-cheep) |
| 25 | `spike` | Pointe/épine |

### Blocs & terrain

| ID | Classe | Description |
|---|---|---|
| 1 | `brick_block` | Bloc de briques cassable |
| 3 | `empty_block` | Bloc vide (après frappe) |
| 9 | `hard_block` | Bloc indestructible de terrain |
| 13 | `mystery_block` | Bloc "?" |
| 17 | `undestructible_block` | Bloc totalement indestructible |

### Objets & power-ups

| ID | Classe | Description |
|---|---|---|
| 2 | `coin` | Pièce |
| 5 | `fireball` | Boule de feu |
| 6 | `flower` | Fleur de feu (power-up) |
| 12 | `mushroom` | Champignon (power-up) |
| 24 | `magic_bean` | Haricot magique |
| 19 | `hammer` | Marteau |

### Éléments de niveau

| ID | Classe | Description |
|---|---|---|
| 14 | `pipe` | Tuyau (corps) |
| 15 | `pipe_head` | Tête de tuyau |
| 7 | `goal_pole` | Mât d'arrivée |
| 18 | `flag` | Drapeau |

---

## 6. Statistiques du dataset

> ⚠️ Ces statistiques sont indicatives et seront mises à jour au fil du projet.

### Données de performance

| Métrique | Valeur |
|---|---|
| Nombre de runs collectés | Variable (selon scraping) |
| Catégorie | Any% NTSC — Super Mario Bros |
| Fourchette de temps | ~4:55 (WR) → ~30:00 (joueurs novices) |
| Source | speedrun.com |

### Données visuelles — level_1-1

| Métrique | Valeur |
|---|---|
| Frames annotées manuellement | ~10–100 (base) |
| Images après augmentation | base × (1 + multiplicateur × nb_augmentations) |
| Multiplicateur typique | 5× |
| Augmentations actives (défaut) | 4 (flip, brightness, contrast, hue) |
| Classes présentes dans level_1-1 | ~12–15 sur 26 |

### Formule d'estimation du dataset augmenté

```
total_images = images_originales × (1 + multiplicateur × nb_augmentations)

Exemple :
  100 images × (1 + 5 × 4) = 100 × 21 = 2 100 images
```

---

## 7. Limites et biais connus

### Biais de compétence
Les données de speedrun.com représentent **exclusivement des joueurs experts**. Les joueurs novices et intermédiaires ne sont pas représentés dans la couche de performance. Ce biais est inhérent à la source de données.

**Impact :** les métriques de difficulté calculées reflètent la performance d'experts, pas celle du public général.

### Couverture des niveaux
Actuellement, seul le **level_1-1** est entièrement annoté. Les autres niveaux (1-2, 1-3, etc.) sont classifiés mais pas annotés en YOLO.

### Jeux couverts
Le pipeline est opérationnel pour **Super Mario Bros**. L'intégration de Super Meat Boy et Mega Man est prévue mais non complète.

### Variabilité des vidéos
Les vidéos proviennent de sources diverses (encodeurs différents, résolutions variables, overlays streamers). Cela peut introduire de la variabilité dans la qualité des frames.

### Annotations manuelles
Les annotations YOLO ont été réalisées manuellement via l'outil intégré. Des erreurs de placement ou d'omission peuvent exister, notamment pour les objets partiellement visibles ou à très petite taille.

---

## 8. Utilisation recommandée

### Pour l'entraînement d'un modèle YOLO

```bash
# 1. Lancer l'augmentation depuis l'interface
# Onglet : 🔄 Augmentation → configurer → Scanner → Lancer

# 2. Vérifier le data.yaml généré
cat augmented_dataset/data.yaml

# 3. Lancer l'entraînement
yolo train \
    data=augmented_dataset/data.yaml \
    model=yolov8n.pt \
    epochs=100 \
    imgsz=640 \
    project=runs/detect \
    name=mario_yolo
```

### Pour la prédiction sur un niveau

```bash
yolo predict \
    model=runs/detect/train/weights/best.pt \
    source=classified_levels/level_1-1 \
    conf=0.25 \
    save_txt=True \
    save_conf=True \
    project=predictions \
    name=level_1-1_predict
```

### Pour charger les données en Python

```python
import pandas as pd
import os
from pathlib import Path

# Charger les données de performance
df = pd.read_csv("performance_data/super_mario_desktop/speedrun_data/runs_*.csv")

# Charger les annotations d'un niveau
def load_annotations(level_dir: str) -> list[dict]:
    annotations = []
    for txt_file in Path(level_dir).glob("*.txt"):
        with open(txt_file) as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 5:
                    annotations.append({
                        "file": txt_file.stem,
                        "class_id": int(parts[0]),
                        "x_center": float(parts[1]),
                        "y_center": float(parts[2]),
                        "width": float(parts[3]),
                        "height": float(parts[4]),
                    })
    return annotations

anns = load_annotations("annotations/level_1-1/labels")
print(f"{len(anns)} annotations chargées")
```

### Citation recommandée

```bibtex
@mastersthesis{adjanohoun2025ladder,
  title   = {LADDER: Level Analysis Dataset for Difficulty and
             Experience Research in Platformer Video Games},
  author  = {Adjanohoun, Yao Jean-eudes},
  school  = {Université du Québec à Chicoutimi},
  year    = {2025},
  advisor = {Bouchard, Bruno}
}
```
