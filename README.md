# 🎮 LADDER
### *Level Analysis Dataset for Difficulty and Experience Research*

> Projet de maîtrise — Université du Québec à Chicoutimi (UQAC)  
> Auteur : **Yao Jean-eudes Adjanohoun**  
> Superviseurs : Prof. Bruno Bouchard · Hugo Tremblay · Yannick Francillette

---

## 📌 Vue d'ensemble

**LADDER** est un dataset structuré conçu pour l'analyse comparative de la difficulté dans les jeux vidéo de type plateformer. Il repose sur un pipeline de traitement automatisé qui collecte, nettoie, annote et analyse des données de performance de joueurs extraites de vidéos de speedrun.

Les jeux ciblés sont :
- 🍄 **Super Mario Bros** (NES)
- 🩸 **Super Meat Boy**
- 🤖 **Mega Man**

---

## 🏗️ Architecture du projet

```
LADDER/
├── README.md                   ← Ce fichier
├── docs/
│   ├── ARCHITECTURE.md         ← Architecture technique détaillée
│   ├── DATASET.md              ← Documentation du dataset
│   └── USER_GUIDE.md           ← Manuel d'utilisation du pipeline
├── tasks/                      ← Logique métier (tâches du pipeline)
│   ├── base_task.py
│   ├── scraper_task.py
│   ├── download_task.py
│   ├── frame_extraction_task.py
│   ├── frame_cleaning_task.py
│   ├── advanced_blur_task.py
│   ├── auto_crop_task.py
│   ├── crop_comparison_task.py
│   ├── mario_menu_task.py
│   ├── segment_transition_task.py
│   ├── mario_level_segment_task.py
│   ├── yolo_training_task.py
│   ├── level_splitter_task.py
│   ├── unknown_reviewer_task.py
│   ├── frame_analyzer_task.py
│   ├── dataset_annotator_task.py
│   ├── dataset_augmentation_task.py
│   └── batch_predict_task.py
├── ui/                         ← Interface graphique (PyQt6)
│   ├── main_window.py
│   ├── dataset_annotator_widget.py
│   ├── dataset_augmentation_widget.py
│   └── batch_predict_widget.py
├── pipeline_manager.py         ← Orchestrateur du pipeline
└── main.py                     ← Point d'entrée
```

---

## 🚀 Démarrage rapide

### Prérequis

| Dépendance | Version minimale |
|---|---|
| Python | 3.10+ |
| PyQt6 | 6.4+ |
| ultralytics (YOLO) | 8.0+ |
| OpenCV | 4.8+ |
| yt-dlp | dernière version |
| Selenium | 4.0+ |
| pandas | 2.0+ |

### Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/votre-repo/LADDER.git
cd LADDER

# 2. Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
.venv\Scripts\activate           # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Lancer l'application
python main.py
```

### Structure des données de sortie

```
performance_data/
└── super_mario_desktop/
    ├── speedrun_data/           ← Données scrappées (CSV, JSON)
    ├── videos/                  ← Vidéos téléchargées
    ├── frames/                  ← Frames extraites
    ├── classified_levels/       ← Frames classifiées par niveau
    │   └── level_1-1/
    ├── annotations/             ← Labels YOLO (.txt)
    │   └── level_1-1/
    │       └── labels/
    ├── augmented_dataset/       ← Dataset augmenté
    │   ├── images/
    │   ├── labels/
    │   └── data.yaml
    └── predictions/             ← Résultats des prédictions YOLO
```

---

## 🔄 Pipeline de traitement

Le pipeline LADDER comporte **19 étapes** organisées en 5 phases :

```
Phase 1 — Collecte
    [1] Scraping speedrun.com  →  [2] Téléchargement vidéos

Phase 2 — Extraction & Nettoyage
    [3] Extraction frames  →  [4] Nettoyage  →  [5] Détection flou avancée

Phase 3 — Segmentation
    [6] Crop automatique  →  [7] Détection menus  →
    [8] Segmentation transitions  →  [9] Classification niveaux

Phase 4 — Annotation & Entraînement
    [10] Révision unknown  →  [11] Analyse frames  →
    [12] Annotation YOLO  →  [13] Augmentation dataset  →
    [14] Entraînement YOLO

Phase 5 — Prédiction & Analyse
    [15] Prédiction par lot  →  [16] Métriques  →  [17] Visualisation
```

---

## 📊 Résultats préliminaires

| Métrique | Valeur |
|---|---|
| Jeu traité (avancé) | Super Mario Bros |
| Niveaux annotés | level_1-1 (complet) |
| Précision modèle YOLO | ~97–99 % mAP50 |
| Classes d'objets détectées | 26 |
| Sources de données | speedrun.com |

---

## 📚 Documentation

| Document | Description |
|---|---|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Architecture technique, modules, flux de données |
| [DATASET.md](docs/DATASET.md) | Structure du dataset, variables, format des données |
| [USER_GUIDE.md](docs/USER_GUIDE.md) | Manuel d'utilisation complet du pipeline |

---

## 🤝 Encadrement académique

Ce projet est réalisé dans le cadre d'une maîtrise en informatique à l'**UQAC** sous la supervision de :

- **Prof. Bruno Bouchard** — Directeur de recherche
- **Hugo Tremblay** — Co-superviseur
- **Yannick Francillette** — Co-superviseur

---

## 📄 Licence

Ce projet est développé à des fins de recherche académique.  
© 2024–2025 Yao Jean-eudes Adjanohoun — UQAC
