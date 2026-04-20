# 🏗️ Architecture Technique — LADDER

> Document : Architecture & Design Technique  
> Version : 1.0.0  
> Dernière mise à jour : 2025

---

## Table des matières

1. [Vue d'ensemble](#1-vue-densemble)
2. [Stack technologique](#2-stack-technologique)
3. [Architecture en couches](#3-architecture-en-couches)
4. [Modules du pipeline](#4-modules-du-pipeline)
5. [Système de tâches](#5-système-de-tâches)
6. [Interface graphique](#6-interface-graphique)
7. [Flux de données](#7-flux-de-données)
8. [Modèle YOLO](#8-modèle-yolo)
9. [Conventions de code](#9-conventions-de-code)

---

## 1. Vue d'ensemble

LADDER est structuré selon un pattern **pipeline modulaire** :

- Chaque étape de traitement est une **tâche indépendante** (`BaseTask`)
- Les tâches sont orchestrées par un **PipelineManager**
- L'interface graphique (**PyQt6**) est entièrement découplée de la logique métier
- Chaque widget UI communique avec sa tâche via des **callbacks** et **signaux Qt**

```
┌─────────────────────────────────────────────────┐
│              Interface PyQt6 (UI)               │
│         main_window.py + widgets/*.py           │
└────────────────────┬────────────────────────────┘
                     │ signaux Qt / callbacks
┌────────────────────▼────────────────────────────┐
│           PipelineManager (orchestration)        │
│              pipeline_manager.py                │
└────────────────────┬────────────────────────────┘
                     │ appels directs
┌────────────────────▼────────────────────────────┐
│              Couche Tasks (métier)              │
│    tasks/base_task.py + tasks/*_task.py         │
└────────────────────┬────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────┐
│           Données (filesystem)                  │
│      performance_data/super_mario_desktop/      │
└─────────────────────────────────────────────────┘
```

---

## 2. Stack technologique

### Backend / Logique métier

| Technologie | Usage |
|---|---|
| **Python 3.10+** | Langage principal |
| **ultralytics YOLOv8** | Détection d'objets, annotation, prédiction |
| **OpenCV** | Traitement d'images, extraction de frames |
| **Selenium** | Scraping web (speedrun.com) |
| **yt-dlp** | Téléchargement de vidéos YouTube |
| **pandas** | Manipulation des données tabulaires |
| **NumPy** | Calculs matriciels (augmentation d'images) |
| **subprocess** | Appel externe à `yolo` CLI |

### Interface graphique

| Technologie | Usage |
|---|---|
| **PyQt6** | Framework UI principal |
| **QThread** | Exécution des tâches sans bloquer l'UI |
| **pyqtSignal** | Communication thread-safe |
| **QSplitter** | Layouts redimensionnables |
| **QScrollArea** | Panneau gauche scrollable |

### Infrastructure

| Technologie | Usage |
|---|---|
| **Git** | Contrôle de version |
| **data.yaml** | Configuration dataset YOLO |
| **JSON / CSV** | Stockage des données scrappées |

---

## 3. Architecture en couches

### Couche 1 — Présentation (`ui/`)

Responsabilité : afficher les données, capturer les interactions utilisateur.

```
ui/
├── main_window.py                  # Fenêtre principale, onglets
├── dataset_annotator_widget.py     # Annotation manuelle YOLO
├── dataset_augmentation_widget.py  # Augmentation du dataset
└── batch_predict_widget.py         # Prédiction YOLO par lot
```

**Règles :**
- Les widgets n'ont **pas de logique métier**
- Ils communiquent via des `QThread` workers et des `pyqtSignal`
- Les styles CSS sont définis localement dans chaque widget pour l'isolation

### Couche 2 — Orchestration (`pipeline_manager.py`)

Responsabilité : séquencer les tâches, gérer les états, router les callbacks.

```python
class PipelineManager:
    def add_task(task: BaseTask) -> None
    def run_all() -> None
    def cancel_current() -> None
```

### Couche 3 — Métier (`tasks/`)

Responsabilité : logique pure, sans dépendance à l'UI.

```
tasks/
├── base_task.py           # Classe abstraite de base
├── scraper_task.py        # Phase 1 : collecte web
├── download_task.py       # Phase 1 : téléchargement vidéos
├── frame_extraction_task.py    # Phase 2
├── frame_cleaning_task.py      # Phase 2
├── advanced_blur_task.py       # Phase 2
├── auto_crop_task.py           # Phase 3
├── mario_menu_task.py          # Phase 3
├── segment_transition_task.py  # Phase 3
├── mario_level_segment_task.py # Phase 3
├── yolo_training_task.py       # Phase 4
├── level_splitter_task.py      # Phase 3
├── unknown_reviewer_task.py    # Phase 4
├── frame_analyzer_task.py      # Phase 4
├── dataset_annotator_task.py   # Phase 4
├── dataset_augmentation_task.py # Phase 4
└── batch_predict_task.py       # Phase 5
```

---

## 4. Modules du pipeline

### Phase 1 — Collecte

#### `scraper_task.py` — ScraperTask
Scrape les leaderboards de speedrun.com.

```python
ScraperTask.configure(url, start_page, end_page, output_dir)
# Sortie : speedrun_data/runs_{timestamp}.csv
# Colonnes : rank, player, time_seconds, date, video_url, platform
```

**Dépendances :** Selenium, ChromeDriver  
**Sortie :** `speedrun_data/*.csv`

---

#### `download_task.py` — DownloadTask
Télécharge les vidéos à partir des URLs collectées.

```python
DownloadTask.configure(csv_path, output_dir, max_videos, quality)
# Sortie : videos/{player}_{rank}.mp4
```

**Dépendances :** yt-dlp  
**Sortie :** `videos/*.mp4`

---

### Phase 2 — Extraction & Nettoyage

#### `frame_extraction_task.py` — FrameExtractionTask
Extrait les frames des vidéos à intervalle régulier.

```python
FrameExtractionTask.configure(
    video_dir, output_dir,
    fps=1,              # 1 frame par seconde
    format='jpg',
    quality=95
)
# Sortie : frames/{video_name}/frame_{NNNNNN}.jpg
```

**Algorithme clé :** intervalle-plus-dichotomie pour l'échantillonnage efficace sur 15 000+ frames.

---

#### `frame_cleaning_task.py` — FrameCleaningTask
Supprime les frames de mauvaise qualité (noires, hors-jeu).

```python
FrameCleaningTask.configure(frames_dir, threshold_dark=0.05)
```

---

#### `advanced_blur_task.py` — AdvancedBlurTask
Détecte et filtre les frames floues via variance du Laplacien.

```python
# Score de netteté = variance(Laplacien(image_grise))
# Seuil : score < 100 → frame rejetée
```

---

### Phase 3 — Segmentation

#### `auto_crop_task.py` — AutoCropTask
Détecte et supprime les bordures noires (letterbox/pillarbox).

#### `mario_menu_task.py` — MarioMenuTask
Détecte les écrans de menu, de mort, et de chargement pour les exclure.

**Méthode :** comparaison d'histogrammes + templates matching.

#### `segment_transition_task.py` — SegmentTransitionTask
Détecte les transitions entre niveaux par différence de frames.

```python
# Différence inter-frame > seuil → transition détectée
diff = cv2.absdiff(frame_n, frame_n1)
score = np.mean(diff)
```

#### `mario_level_segment_task.py` — MarioLevelSegmentTask
Segmente la vidéo en séquences par niveau (1-1, 1-2, etc.).

#### `level_splitter_task.py` — LevelSplitterTask
Classifie et trie les frames par niveau dans des dossiers dédiés.

```
classified_levels/
├── level_1-1/
├── level_1-2/
└── unknown/
```

---

### Phase 4 — Annotation & Entraînement

#### `dataset_annotator_task.py` — DatasetAnnotatorTask
Fournit la logique de sauvegarde des annotations YOLO.

**Format de sortie :**
```
# annotations/level_1-1/labels/frame_000001.txt
0 0.512 0.743 0.045 0.089   # class x_center y_center width height
```

**26 classes :**
```python
CLASSES = [
    'big_mario', 'brick_block', 'coin', 'empty_block', 'fire_mario',
    'fireball', 'flower', 'goal_pole', 'goomba', 'hard_block',
    'koopa', 'little_mario', 'mushroom', 'mystery_block', 'pipe',
    'pipe_head', 'shell', 'undestructible_block', 'flag', 'hammer',
    'fish_flying', 'piranha', 'turtle', 'lakitu', 'magic_bean', 'spike'
]
```

---

#### `dataset_augmentation_task.py` — DatasetAugmentationTask
Génère des variations d'images annotées pour enrichir le dataset.

**10 types d'augmentation :**

| Type | Transformation | Annotations modifiées ? |
|---|---|---|
| `horizontal_flip` | Miroir horizontal | ✅ x_center = 1 - x_center |
| `brightness` | Facteur aléatoire [0.7, 1.4] | ❌ |
| `contrast` | Facteur aléatoire [0.7, 1.3] | ❌ |
| `hue_shift` | Décalage HSV [-15°, +15°] | ❌ |
| `saturation` | Facteur aléatoire [0.7, 1.3] | ❌ |
| `noise` | Bruit gaussien σ=10 | ❌ |
| `blur` | Gaussian blur 3×3 ou 5×5 | ❌ |
| `rotation` | Rotation ±5° | ✅ transformation des bboxes |
| `combination_brightness_contrast` | Combo | ❌ |
| `combination_flip_hue` | Combo | ✅ partiel |

**Structure de sortie :**
```
augmented_dataset/
├── images/    # {level}_{frame}_{augtype}_{idx}.jpg
├── labels/    # fichiers .txt YOLO correspondants
└── data.yaml  # configuration pour entraînement YOLO
```

---

#### `yolo_training_task.py` — YOLOTrainingTask
Lance l'entraînement d'un modèle YOLOv8.

```python
TrainingConfig(
    data_yaml   = "augmented_dataset/data.yaml",
    model       = "yolov8n.pt",    # nano, small, medium, large, xlarge
    epochs      = 100,
    imgsz       = 640,
    batch       = 16,
    project     = "runs/detect",
    name        = "mario_yolo"
)
```

**Résultats obtenus :**
- mAP50 : **~97–99 %**
- mAP50-95 : ~85 %

---

#### `batch_predict_task.py` — BatchPredictTask  
Exécute `yolo predict` sur un dossier de niveaux complet.

```python
PredictConfig(
    model_path  = "runs/detect/train/weights/best.pt",
    source_dir  = "classified_levels/level_1-1",
    output_dir  = "predictions",
    run_name    = "level_1-1_predict",
    confidence  = 0.25,
    save_txt    = True,
    save_conf   = True
)
```

---

## 5. Système de tâches

### Classe de base — `BaseTask`

```python
class BaseTask:
    name:     str
    status:   TaskStatus        # PENDING | RUNNING | COMPLETED | FAILED | CANCELLED
    progress: int               # 0–100
    
    def run(self) -> Any: ...   # À implémenter
    def cancel(self) -> None: ...
    
    # Callbacks optionnels
    log_callback:      Callable[[str], None]
    progress_callback: Callable[[int, int], None]
```

### Cycle de vie d'une tâche

```
PENDING → RUNNING → COMPLETED
                 ↘ FAILED
                 ↘ CANCELLED
```

### Pattern Worker (thread-safety)

```python
# Dans chaque widget UI :
class MyWorker(QThread):
    sig_log      = pyqtSignal(str)
    sig_progress = pyqtSignal(int, int)
    sig_done     = pyqtSignal(bool, str)

    def run(self):
        task = MyTask()
        task.log_callback      = lambda m: self.sig_log.emit(m)
        task.progress_callback = lambda c, t: self.sig_progress.emit(c, t)
        result = task.run()
        self.sig_done.emit(result.success, result.message)
```

---

## 6. Interface graphique

### Structure des onglets (main_window.py)

| # | Onglet | Widget | Tâche associée |
|---|---|---|---|
| 1 | 📊 Extraction Speedrun | Inline | ScraperTask |
| 2 | ⬇️ Téléchargement | Inline | DownloadTask |
| 3 | 👁️ Visualisation | Inline | ViewerTask |
| 4 | 📈 Métriques | Inline | MetricsTask |
| 5 | 🎬 Extraction Frames | Inline | FrameExtractionTask |
| 6 | 🧹 Nettoyage Frames | FrameCleaningWidget | FrameCleaningTask |
| 7 | 🔬 Détection Avancée | AdvancedBlurWidget | AdvancedBlurTask |
| 8 | ✂️ Crop Auto | AutoCropWidget | AutoCropTask |
| 9 | 📊 Comparaison | CropComparisonWidget | CropComparisonTask |
| 10 | 🎮 Mario Menu | MarioMenuWidget | MarioMenuTask |
| 11 | 🔄 Segmentation | SegmentWidget | SegmentTransitionTask |
| 12 | 🎮 Niveaux Mario | MarioLevelWidget | MarioLevelSegmentTask |
| 13 | 🤖 YOLO Training | YOLOTrainingWidget | YOLOTrainingTask |
| 14 | 📊 Classification | LevelSplitterWidget | LevelSplitterTask |
| 15 | 🔍 Révision Unknown | UnknownReviewerWidget | UnknownReviewerTask |
| 16 | 📊 Analyse Frames | FrameAnalyzerWidget | FrameAnalyzerTask |
| 17 | 🎮 Annotateur YOLO | DatasetAnnotatorWidget | DatasetAnnotatorTask |
| 18 | 🔄 Augmentation | DatasetAugmentationWidget | DatasetAugmentationTask |
| 19 | 🤖 Prédiction | BatchPredictWidget | BatchPredictTask |

### Pattern d'intégration d'un nouveau widget

```python
# Dans main_window.py, dans _create_left_panel() :
from ui.mon_widget import MonWidget
self.mon_widget = MonWidget()
tabs.addTab(self.mon_widget, "🆕 Mon Module")
```

Le widget est **totalement autonome** : logique interne + thread + UI.

---

## 7. Flux de données

```
speedrun.com
    │
    ▼ ScraperTask
runs_{timestamp}.csv  (rank, player, time, url, platform)
    │
    ▼ DownloadTask
videos/{player}_{rank}.mp4
    │
    ▼ FrameExtractionTask
frames/{video}/frame_{NNNNNN}.jpg   (1 frame/seconde)
    │
    ▼ FrameCleaningTask + AdvancedBlurTask
frames/{video}/frame_{NNNNNN}.jpg   (filtrées)
    │
    ▼ AutoCropTask + MarioMenuTask + SegmentTransitionTask
frames/{video}/frame_{NNNNNN}.jpg   (nettoyées)
    │
    ▼ MarioLevelSegmentTask + LevelSplitterTask
classified_levels/level_{X-Y}/frame_{NNNNNN}.jpg
    │
    ▼ DatasetAnnotatorTask (manuel)
annotations/level_{X-Y}/labels/frame_{NNNNNN}.txt   (YOLO format)
    │
    ▼ DatasetAugmentationTask
augmented_dataset/images/*.jpg
augmented_dataset/labels/*.txt
augmented_dataset/data.yaml
    │
    ▼ YOLOTrainingTask
runs/detect/train/weights/best.pt
    │
    ▼ BatchPredictTask
predictions/{run_name}/labels/*.txt  (détections automatiques)
```

---

## 8. Modèle YOLO

### Architecture
- **Modèle de base :** YOLOv8n (nano) — optimisé vitesse/précision
- **Fine-tuning :** Transfer learning depuis les poids COCO
- **Dataset d'entraînement :** images annotées de level_1-1 + augmentations

### Fichier `data.yaml`

```yaml
path: /chemin/vers/augmented_dataset
train: images
val: images

nc: 26
names:
  - big_mario
  - brick_block
  - coin
  - empty_block
  - fire_mario
  - fireball
  - flower
  - goal_pole
  - goomba
  - hard_block
  - koopa
  - little_mario
  - mushroom
  - mystery_block
  - pipe
  - pipe_head
  - shell
  - undestructible_block
  - flag
  - hammer
  - fish_flying
  - piranha
  - turtle
  - lakitu
  - magic_bean
  - spike
```

### Performances

| Métrique | Valeur |
|---|---|
| mAP50 | ~97–99 % |
| mAP50-95 | ~85 % |
| Vitesse inférence | ~5–15 ms/image (GPU) |
| Modèle de base | YOLOv8n |

---

## 9. Conventions de code

### Nommage

```python
# Fichiers : snake_case
frame_extraction_task.py

# Classes : PascalCase
class FrameExtractionTask(BaseTask): ...

# Méthodes privées : _underscore
def _collect_frames(self): ...

# Constantes : UPPER_SNAKE_CASE
MAX_FRAMES = 15000
```

### Structure d'un module tâche

```python
"""
Description du module.

Version : X.Y.Z
Fichier : tasks/ma_tache.py
"""

from dataclasses import dataclass
from tasks.base_task import BaseTask, TaskStatus

@dataclass
class MaConfig:
    champ1: str
    champ2: int

@dataclass
class MonResultat:
    success: bool
    message: str
    # ... autres champs

class MaTache(BaseTask):
    def __init__(self):
        super().__init__(name="MaTache")
        self.config = None

    def configure(self, config: MaConfig):
        self.config = config

    def run(self) -> MonResultat:
        self.status = TaskStatus.RUNNING
        try:
            # logique métier
            self.status = TaskStatus.COMPLETED
            return MonResultat(success=True, message="OK")
        except Exception as e:
            self.status = TaskStatus.FAILED
            return MonResultat(success=False, message=str(e))
```

### Structure d'un widget UI

```python
"""
Description du widget.

Version : X.Y.Z
Fichier : ui/mon_widget.py
"""

class _MonWorker(QThread):
    sig_log  = pyqtSignal(str)
    sig_done = pyqtSignal(bool, str)

    def run(self): ...

class MonWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self): ...    # construction des groupes
    def _start(self): ...       # lancer le worker
    def _on_done(self, ...): ...  # réception des résultats
```
