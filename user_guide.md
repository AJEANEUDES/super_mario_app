# 📖 Manuel d'utilisation — Speedrun Pipeline Manager

> Application : LADDER — Speedrun Pipeline Manager v2.2.0  
> Document : Guide Utilisateur Complet  
> Audience : Chercheurs, étudiants en maîtrise

---

## Table des matières

1. [Premier lancement](#1-premier-lancement)
2. [Interface principale](#2-interface-principale)
3. [Phase 1 — Collecte des données](#3-phase-1--collecte-des-données)
4. [Phase 2 — Extraction et nettoyage](#4-phase-2--extraction-et-nettoyage)
5. [Phase 3 — Segmentation par niveau](#5-phase-3--segmentation-par-niveau)
6. [Phase 4 — Annotation et entraînement](#6-phase-4--annotation-et-entraînement)
7. [Phase 5 — Prédiction et analyse](#7-phase-5--prédiction-et-analyse)
8. [Workflow complet recommandé](#8-workflow-complet-recommandé)
9. [Dépannage](#9-dépannage)

---

## 1. Premier lancement

### Prérequis système

Avant de lancer l'application, vérifiez que les dépendances suivantes sont installées :

```bash
# Vérifier Python
python --version          # 3.10 minimum requis

# Vérifier YOLO
yolo --version            # ultralytics 8.0+

# Vérifier les dépendances Python
pip list | grep -E "PyQt6|opencv|ultralytics|selenium|yt-dlp|pandas"
```

### Lancer l'application

```bash
cd /chemin/vers/LADDER
python main.py
```

### Organisation recommandée des dossiers de travail

Créez cette structure **avant** de commencer :

```
votre_projet/
├── performance_data/
│   └── super_mario_desktop/   ← dossier de travail principal
└── runs/                      ← sorties d'entraînement YOLO (auto-créé)
```

---

## 2. Interface principale

L'application se présente sous forme de **barre d'onglets** horizontale.  
Chaque onglet correspond à une étape du pipeline.

```
┌─────────────────────────────────────────────────────────┐
│  🎮 Speedrun Pipeline Manager          Mode Clair  v2.2 │
├─────────────────────────────────────────────────────────┤
│ ⚙️ Configuration des Tâches                             │
│ [Extraction] [Téléchargement] [Visualisation] [...]     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│   Panneau de configuration    │   Panneau de logs       │
│   (gauche)                    │   (droite)              │
│                               │                         │
├─────────────────────────────────────────────────────────┤
│ ● Prêt    Tâches: 0 en attente | 0 complétées | 0 ❌   │
└─────────────────────────────────────────────────────────┘
```

### Barre de statut (bas de l'écran)

| Indicateur | Signification |
|---|---|
| 🟢 Prêt | Aucune tâche en cours |
| 🟡 En cours | Tâche active |
| 🔴 Erreur | Une tâche a échoué |
| `X en attente` | Tâches dans la file |
| `X complétées` | Tâches terminées avec succès |

### Bouton Mode Clair / Mode Sombre

En haut à droite — bascule le thème visuel de toute l'application.

---

## 3. Phase 1 — Collecte des données

### 3.1 Onglet 📊 Extraction Speedrun

**Objectif :** Récupérer les données du classement speedrun.com.

**Étapes :**

1. Coller l'URL du leaderboard speedrun.com  
   *Exemple :* `https://www.speedrun.com/smb1?h=Any-NTSC`

2. Définir la **page de départ** et la **page de fin**  
   *Chaque page contient ~20 runs.*

3. Choisir le **dossier de sortie**  
   *Recommandé :* `performance_data/super_mario_desktop/speedrun_data/`

4. Cliquer **▶ Lancer l'extraction**

**Sortie produite :**
```
speedrun_data/runs_20250417_143022.csv
```

> ⚠️ **Note :** Chrome doit être installé sur votre machine. Le scraper ouvre  
> un navigateur automatisé — ne pas le fermer manuellement.

---

### 3.2 Onglet ⬇️ Téléchargement

**Objectif :** Télécharger les vidéos listées dans le CSV.

**Étapes :**

1. Sélectionner le **fichier CSV** produit à l'étape précédente

2. Choisir le **dossier de destination** des vidéos  
   *Recommandé :* `performance_data/super_mario_desktop/videos/`

3. Définir le **nombre maximum de vidéos** à télécharger  
   *Commencer par 5–10 pour tester*

4. Choisir la **qualité vidéo** (best / 720p / 480p)

5. Cliquer **▶ Lancer le téléchargement**

**Sortie produite :**
```
videos/Kosmic_1.mp4
videos/darbian_2.mp4
...
```

> ⚠️ Certaines vidéos Twitch ou privées peuvent échouer — c'est normal.  
> Le téléchargement continue automatiquement sur la suivante.

---

## 4. Phase 2 — Extraction et nettoyage

### 4.1 Onglet 🎬 Extraction Frames

**Objectif :** Découper les vidéos en images individuelles.

**Paramètres recommandés :**

| Paramètre | Valeur recommandée | Explication |
|---|---|---|
| FPS d'extraction | 1 frame/sec | Bon compromis volume/couverture |
| Format | JPG | Compression sans perte perceptible |
| Qualité JPG | 90–95 | Bonne qualité, taille raisonnable |

**Étapes :**

1. Sélectionner le **dossier des vidéos**
2. Choisir le **dossier de sortie des frames**  
   *Recommandé :* `performance_data/super_mario_desktop/frames/`
3. Configurer le FPS d'extraction
4. Cliquer **▶ Lancer l'extraction**

**Sortie produite :**
```
frames/
└── Kosmic_1/
    ├── frame_000001.jpg
    ├── frame_000002.jpg
    └── ...
```

---

### 4.2 Onglet 🧹 Nettoyage Frames

**Objectif :** Supprimer les frames noires, corrompues ou hors-jeu.

**Paramètres :**

| Paramètre | Valeur par défaut | Description |
|---|---|---|
| Seuil de luminosité | 5 % | Frames plus sombres → supprimées |

**Étapes :**

1. Sélectionner le **dossier des frames**
2. Ajuster le seuil si nécessaire
3. Cliquer **▶ Nettoyer**

---

### 4.3 Onglet 🔬 Détection Avancée (flou)

**Objectif :** Filtrer les frames floues (transitions, mouvements rapides).

**Méthode :** Variance du Laplacien — un score bas = image floue.

**Recommandation :** Seuil de **100** pour les vidéos de jeux.  
Augmentez à 150 si trop de frames sont conservées.

---

## 5. Phase 3 — Segmentation par niveau

### 5.1 Onglet ✂️ Crop Auto

**Objectif :** Détecter et supprimer les bandes noires (letterbox/pillarbox).

> Utile pour les captures d'écran 16:9 sur jeux 4:3 (NES).

---

### 5.2 Onglet 🎮 Mario Menu

**Objectif :** Identifier et exclure les frames d'écrans de menu, de mort,  
ou de transition pour ne garder que le gameplay réel.

---

### 5.3 Onglet 🔄 Segmentation

**Objectif :** Découper automatiquement la vidéo en segments  
correspondant aux changements de niveau.

**Comment ça marche :**  
Le module compare les frames consécutives. Une différence importante  
entre deux frames consécutives = début d'un nouveau segment.

---

### 5.4 Onglet 🎮 Niveaux Mario

**Objectif :** Identifier le numéro de chaque niveau dans chaque segment.

**Sortie produite :**
```
classified_levels/
├── level_1-1/
├── level_1-2/
├── level_2-1/
└── unknown/     ← frames non identifiées
```

---

### 5.5 Onglet 📊 Classification

**Objectif :** Affiner la classification et gérer les cas limites.

---

### 5.6 Onglet 🔍 Révision Unknown

**Objectif :** Revoir manuellement les frames classifiées comme `unknown`  
et les réaffecter au bon niveau.

**Étapes :**

1. Sélectionner le **dossier `unknown/`**
2. L'interface affiche chaque frame une par une
3. Choisir le **niveau cible** ou **supprimer** la frame
4. Cliquer **Suivant**

---

## 6. Phase 4 — Annotation et entraînement

### 6.1 Onglet 📊 Analyse Frames

**Objectif :** Analyser la distribution des frames par niveau  
et identifier les frames les plus représentatives à annoter.

---

### 6.2 Onglet 🎮 Annotateur YOLO

**Objectif :** Annoter manuellement les objets de jeu dans les frames.

**Interface :**

```
┌──────────────────────────────────────────────────────┐
│  Frame en cours          │  Outils                   │
│                          │  ┌─ Classe sélectionnée ─┐│
│  [IMAGE]                 │  │  11: little_mario      ││
│                          │  └────────────────────────┘│
│                          │                            │
│                          │  Raccourcis clavier :       │
│                          │  Ctrl+C  Copier bbox       │
│                          │  Ctrl+V  Coller bbox       │
│                          │  Ctrl+→  Propager frame    │
│                          │  Del     Supprimer bbox    │
└──────────────────────────────────────────────────────┘
```

**Workflow d'annotation :**

1. Sélectionner le **dossier d'images** (un niveau)
2. Sélectionner le **dossier de labels** (annotations)
3. Choisir une **classe** dans la liste
4. **Dessiner** un rectangle autour de l'objet (clic + glisser)
5. Répéter pour tous les objets visibles
6. Appuyer **→** pour passer à la frame suivante

**Conseils :**
- Annoter les objets **entièrement visibles** uniquement
- Pour les objets partiels (bord d'écran), inclure la partie visible
- Utiliser **Ctrl+→** (propagation) pour les frames très similaires
- Annoter au minimum **50–100 frames** par niveau pour l'entraînement

---

### 6.3 Onglet 🔄 Augmentation

**Objectif :** Multiplier les images annotées par transformations automatiques.

**Étapes :**

1. **Dossier Labels :** sélectionner le dossier contenant les fichiers `.txt`  
   *Exemple :* `annotations/level_1-1/labels/`

2. **Dossier Images :** sélectionner le dossier des images correspondantes  
   *Exemple :* `classified_levels/level_1-1/`

3. **Dossier de sortie :** nom du dataset augmenté  
   *Recommandé :* `augmented_dataset`

4. Cliquer **🔍 Scanner les niveaux**  
   → Le niveau apparaît dans la liste avec le nombre d'annotations

5. **Sélectionner** le(s) niveau(x) à augmenter

6. Configurer :
   - **Multiplicateur** : 5 (recommandé pour débuter)
   - **Types d'augmentation** : Flip, Luminosité, Contraste, Teinte (défaut)

7. Vérifier l'**estimation** : `X images → ~Y images`

8. Cliquer **🚀 Lancer l'augmentation**

**Estimation du temps :**
- ~100 images × multiplicateur 5 × 4 augmentations = **2 100 images**
- Durée approximative : 2–5 minutes sur CPU standard

**Sortie produite :**
```
augmented_dataset/
├── images/     (2 100 fichiers .jpg)
├── labels/     (2 100 fichiers .txt)
└── data.yaml
```

---

### 6.4 Onglet 🤖 YOLO Training

**Objectif :** Entraîner le modèle de détection.

**Configuration recommandée pour démarrer :**

| Paramètre | Valeur recommandée |
|---|---|
| Modèle de base | yolov8n.pt (nano) |
| Epochs | 100 |
| Batch size | 16 |
| Image size | 640 |
| data.yaml | augmented_dataset/data.yaml |

**Durée estimée :**
- Sur GPU : 30–60 minutes (100 epochs)
- Sur CPU : 4–8 heures (non recommandé)

**Sortie produite :**
```
runs/detect/train/
├── weights/
│   ├── best.pt       ← modèle le plus performant
│   └── last.pt       ← dernier checkpoint
└── results.csv       ← courbes d'apprentissage
```

> 💡 **Le fichier à utiliser est toujours `best.pt`**

---

## 7. Phase 5 — Prédiction et analyse

### 7.1 Onglet 🤖 Prédiction

**Objectif :** Appliquer le modèle entraîné sur un dossier de niveaux  
pour générer automatiquement les détections.

**Étapes :**

1. **Modèle YOLO :** cliquer `🔍 Trouver automatiquement` ou sélectionner manuellement `best.pt`

2. **Dossier images :** sélectionner le dossier source  
   *Options :*
   - `augmented_dataset/images` (dataset augmenté)
   - `classified_levels/level_1-1` (frames brutes d'un niveau)

3. **Dossier de sortie :** nom du dossier de résultats  
   *Exemple :* `predictions`

4. **Nom du run :** identifiant de cette session de prédiction  
   *Exemple :* `level_1-1_predict`

5. **Paramètres :**

| Paramètre | Recommandé | Description |
|---|---|---|
| Confidence | 0.25 | Seuil de détection minimal |
| IOU | 0.45 | Seuil de suppression des doublons |
| Image size | 640 | Doit correspondre à l'entraînement |
| Device | auto | GPU si disponible, CPU sinon |

6. **Options de sauvegarde :**
   - ✅ Labels .txt — nécessaires pour l'analyse
   - ✅ Confidence — utile pour filtrer les détections incertaines
   - ☐ Crops — optionnel, prend plus d'espace disque

7. Cliquer **▶ Lancer la prédiction**

**Sortie produite :**
```
predictions/level_1-1_predict/
├── images/         ← frames avec les bboxes dessinées
└── labels/
    └── *.txt       ← détections au format YOLO + confidence
```

**Format d'un fichier de prédiction :**
```
# frame_000042.txt (avec save_conf=True)
11 0.512 0.743 0.045 0.089 0.987   # little_mario  conf=98.7%
8  0.720 0.810 0.032 0.058 0.834   # goomba        conf=83.4%
```

---

### 7.2 Onglet 📈 Métriques

**Objectif :** Visualiser les statistiques des runs collectés  
(distribution des temps, classement des joueurs, etc.)

---

### 7.3 Onglet 👁️ Visualisation

**Objectif :** Afficher et explorer les frames avec leurs annotations.

---

## 8. Workflow complet recommandé

Voici l'ordre optimal pour traiter un nouveau jeu / niveau :

```
Semaine 1 — Collecte
═══════════════════
□ 1. Scraper speedrun.com (50–100 runs minimum)
□ 2. Télécharger 10–20 vidéos représentatives
□ 3. Extraire les frames (1 frame/sec)
□ 4. Nettoyer les frames (filtre noir + flou)

Semaine 2 — Structuration
═════════════════════════
□ 5. Crop automatique (retirer letterbox)
□ 6. Détecter les menus/transitions
□ 7. Segmenter par niveau
□ 8. Réviser les frames "unknown"
□ 9. Analyser la distribution des frames

Semaine 3 — Annotation
═══════════════════════
□ 10. Annoter manuellement 50–100 frames du level_1-1
       Objectif : au moins 3 occurrences de chaque classe
□ 11. Vérifier la qualité des annotations (Révision Unknown)

Semaine 4 — Entraînement
═════════════════════════
□ 12. Augmenter le dataset (×5, 4 types)
       → ~1 000–2 000 images
□ 13. Entraîner YOLO (100 epochs)
□ 14. Évaluer les métriques (mAP50 cible : >90%)

Semaine 5 — Prédiction & Analyse
══════════════════════════════════
□ 15. Lancer la prédiction sur tous les niveaux disponibles
□ 16. Analyser les détections par niveau
□ 17. Comparer la densité d'objets entre niveaux
□ 18. Documenter les résultats
```

---

## 9. Dépannage

### ❌ "Commande 'yolo' introuvable"

```bash
pip install ultralytics
# Vérifier :
yolo --version
```

### ❌ "ChromeDriver introuvable" (Scraper)

```bash
pip install webdriver-manager
# Ou télécharger ChromeDriver manuellement :
# https://chromedriver.chromium.org/downloads
```

### ❌ "Aucune image annotée trouvée" (Augmentation)

Vérifier la structure des dossiers :

```
✅ Structure attendue :
   Dossier Labels : .../annotations/level_1-1/labels/
   Dossier Images : .../classified_levels/level_1-1/

   Les noms de fichiers doivent correspondre :
   frame_000001.txt ↔ frame_000001.jpg
```

Vérifier que les fichiers `.txt` ne sont pas vides :
```bash
# Linux/macOS
find . -name "*.txt" -empty -delete

# Windows PowerShell
Get-ChildItem -Recurse -Filter *.txt | Where-Object { $_.Length -eq 0 }
```

### ❌ Modèle YOLO non trouvé (Prédiction)

```bash
# Recherche manuelle :
find . -name "best.pt" 2>/dev/null

# Chemin typique après entraînement :
runs/detect/train/weights/best.pt
# Ou avec suffixe numérique si plusieurs entraînements :
runs/detect/train2/weights/best.pt
```

### ❌ Interface gelée pendant une opération

Les tâches longues (extraction, entraînement, augmentation) s'exécutent  
dans un thread séparé — l'interface ne devrait pas geler.  
Si c'est le cas, **ne pas fermer l'application**, attendre la fin.

### ❌ Mémoire insuffisante (YOLO Training)

Réduire le batch size :
```
batch=8  (au lieu de 16)
# ou
batch=4  (sur très petite mémoire GPU)
```

### ⚠️ Faible mAP50 après entraînement (<80%)

Causes possibles et solutions :

| Cause | Solution |
|---|---|
| Trop peu d'images annotées | Annoter 100+ frames, viser 10+ exemples par classe |
| Déséquilibre des classes | Annoter plus d'exemples des classes rares |
| Mauvaise qualité des annotations | Réviser avec l'outil de révision |
| Epochs insuffisants | Augmenter à 150–200 epochs |
| Résolution trop faible | Utiliser imgsz=800 ou 1024 |

---

## Aide et contact

Pour toute question sur l'application ou le dataset :

- **Auteur :** Yao Jean-eudes Adjanohoun
- **Institution :** Université du Québec à Chicoutimi (UQAC)
- **Superviseurs :** Prof. Bruno Bouchard · Hugo Tremblay · Yannick Francillette
