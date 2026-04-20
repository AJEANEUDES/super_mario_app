"""
Dataset Augmentation Widget - Interface pour augmenter un dataset annoté

Permet de:
- Sélectionner un dossier d'annotations
- Choisir un niveau spécifique (1-1, 1-2, etc.)
- Configurer les types d'augmentation
- Générer le dataset augmenté au format YOLO

Version 1.1.0 - Correction affichage mode sombre + détection images améliorée
Fichier: ui/dataset_augmentation_widget.py
"""

import os
import cv2
import numpy as np
from pathlib import Path
import shutil
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QGridLayout, QProgressBar, QLineEdit, QCheckBox, QComboBox,
    QSpinBox, QListWidget, QListWidgetItem, QTextEdit, QSplitter,
    QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QPixmap


@dataclass
class AugmentationConfig:
    """Configuration pour l'augmentation"""
    annotations_dir: str
    frames_dir: str
    output_dir: str
    selected_levels: List[str]
    multiplier: int
    augmentation_types: List[str]


class AugmentationWorker(QThread):
    """Thread pour l'augmentation en arrière-plan"""
    
    progress = pyqtSignal(int, int)  # current, total
    log = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str, int)  # success, message, count
    
    def __init__(self, config: AugmentationConfig):
        super().__init__()
        self.config = config
        self.cancelled = False
        
        # Liste des catégories connues (pour YOLO)
        self.category_list = [
            'big_mario', 'brick_block', 'coin', 'empty_block', 'fire_mario', 
            'fireball', 'flower', 'goal_pole', 'goomba', 'hard_block',
            'koopa', 'little_mario', 'mushroom', 'mystery_block', 'pipe', 
            'pipe_head', 'shell', 'undestructible_block', 'flag', 'hammer',
            'fish_flying', 'piranha', 'turtle', 'lakitu', 'magic_bean', 'spike'
        ]
    
    def cancel(self):
        self.cancelled = True
    
    def run(self):
        try:
            total_generated = self.augment_dataset()
            if not self.cancelled:
                self.finished_signal.emit(True, "Augmentation terminée avec succès!", total_generated)
            else:
                self.finished_signal.emit(False, "Augmentation annulée", total_generated)
        except Exception as e:
            import traceback
            self.log.emit(f"❌ Erreur: {str(e)}")
            self.log.emit(traceback.format_exc())
            self.finished_signal.emit(False, f"Erreur: {str(e)}", 0)
    
    def _find_image_for_label(self, label_path: str, level: str,
                              verbose: bool = False) -> Optional[str]:
        """Trouve l'image correspondant à un fichier label.

        Stratégies testées dans l'ordre:
        1. frames_dir / base_name.ext                       (direct)
        2. frames_dir / level / base_name.ext               (sous-dossier niveau)
        3. Même dossier que le label
        4. Dossier frère 'images' (si 'labels' dans le chemin)
        5. Parent du dossier label / images|frames|img / base_name.ext
        6. Recherche récursive dans frames_dir (insensible à la casse)
        """
        base_name = Path(label_path).stem
        label_dir  = os.path.dirname(label_path)
        extensions = ['.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG']

        candidates = []

        # S1 — frames_dir / base_name.ext  (le cas le plus courant)
        for ext in extensions:
            candidates.append(os.path.join(self.config.frames_dir, base_name + ext))

        # S2 — frames_dir / level / base_name.ext
        for ext in extensions:
            candidates.append(os.path.join(self.config.frames_dir, level, base_name + ext))

        # S3 — même dossier que le label
        for ext in extensions:
            candidates.append(os.path.join(label_dir, base_name + ext))

        # S4 — dossier frère 'images' (remplace 'labels' dans le chemin)
        if 'labels' in label_dir:
            images_dir = label_dir.replace('labels', 'images')
            for ext in extensions:
                candidates.append(os.path.join(images_dir, base_name + ext))

        # S5 — parent / images|frames|img / base_name.ext
        parent_dir = os.path.dirname(label_dir)
        for folder in ['images', 'frames', 'img']:
            for ext in extensions:
                candidates.append(os.path.join(parent_dir, folder, base_name + ext))

        # Tester les candidats
        for path in candidates:
            if os.path.exists(path):
                return path

        # S6 — recherche récursive insensible à la casse dans frames_dir
        base_lower = base_name.lower()
        for root, _, files in os.walk(self.config.frames_dir):
            for f in files:
                stem, ext = os.path.splitext(f)
                if stem.lower() == base_lower and ext.lower() in ['.jpg', '.jpeg', '.png']:
                    return os.path.join(root, f)

        # ── diagnostic : log les chemins testés si rien trouvé ──────────────
        if verbose:
            self.log.emit(f"      🔎 base_name recherché : {base_name}")
            self.log.emit(f"         frames_dir          : {self.config.frames_dir}")
            shown = set()
            for p in candidates[:8]:          # montrer les 8 premiers
                d = os.path.dirname(p)
                if d not in shown:
                    shown.add(d)
                    exists = "✅" if os.path.isdir(d) else "❌"
                    self.log.emit(f"         {exists} dossier testé : {d}")

        return None

    def _list_frames_dir_sample(self) -> str:
        """Retourne un échantillon des fichiers présents dans frames_dir (pour diagnostic)."""
        d = self.config.frames_dir
        if not os.path.isdir(d):
            return f"❌ Dossier images introuvable: {d}"
        files = [f for f in os.listdir(d) if os.path.isfile(os.path.join(d, f))]
        exts  = {os.path.splitext(f)[1].lower() for f in files}
        sample = files[:5]
        return (f"📁 {d}  ({len(files)} fichiers, extensions: {exts})\n"
                f"   Exemples: {sample}")

    def collect_annotated_images(self) -> List[Tuple[str, str, str, str]]:
        """Collecte les images annotées des niveaux sélectionnés.

        Utilise directement les chemins absolus stockés dans UserRole par _scan_levels,
        ce qui évite tout problème de reconstruction de chemin.
        """
        annotated_images = []

        for entry in self.config.selected_levels:
            # entry peut être un tuple (display_name, abs_ann_path)
            # ou une chaîne (display_name uniquement, ancien format)
            if isinstance(entry, (list, tuple)) and len(entry) == 2:
                display_name, level_ann_path = entry
            else:
                # Fallback : ancienne logique (nom de niveau relatif)
                display_name  = str(entry)
                level_ann_path = os.path.join(self.config.annotations_dir, display_name)
                if not os.path.isdir(level_ann_path):
                    level_ann_path = self.config.annotations_dir

            if not os.path.isdir(level_ann_path):
                self.log.emit(f"⚠️ Dossier introuvable: {level_ann_path}")
                continue

            self.log.emit(f"📂 Niveau   : {display_name}")
            self.log.emit(f"   Labels  : {level_ann_path}")
            self.log.emit(f"   Images  : {self.config.frames_dir}")

            # Lister les .txt non vides
            label_files = [f for f in os.listdir(level_ann_path) if f.endswith('.txt')]
            non_empty   = [f for f in label_files
                           if os.path.getsize(os.path.join(level_ann_path, f)) > 0]
            self.log.emit(f"   .txt    : {len(label_files)} trouvés, {len(non_empty)} non vides")

            if not non_empty:
                self.log.emit("   ⚠️ Aucun fichier .txt non vide — niveau ignoré.")
                continue

            diag_done  = False
            found_count = 0

            for ann_file in non_empty:
                label_path = os.path.join(level_ann_path, ann_file)
                image_path = self._find_image_for_label(label_path, display_name,
                                                         verbose=False)
                if image_path:
                    annotated_images.append((display_name, os.path.basename(image_path),
                                             label_path, image_path))
                    found_count += 1
                else:
                    if not diag_done:
                        self.log.emit(f"   ⚠️ Image introuvable pour : {ann_file}")
                        self.log.emit(f"      base_name : {Path(ann_file).stem}")
                        self.log.emit(self._list_frames_dir_sample())
                        self._find_image_for_label(label_path, display_name, verbose=True)
                        diag_done = True

            self.log.emit(f"   ✅ Résultat : {found_count} / {len(non_empty)} images trouvées")

        return annotated_images
    
    def load_yolo_annotations(self, label_path: str) -> List[List[float]]:
        """Charge les annotations au format YOLO"""
        annotations = []
        
        try:
            with open(label_path, 'r') as f:
                for line in f:
                    parts = line.strip().split()
                    if len(parts) >= 5:
                        class_id = int(parts[0])
                        x_center, y_center, width, height = map(float, parts[1:5])
                        annotations.append([class_id, x_center, y_center, width, height])
        except Exception as e:
            self.log.emit(f"⚠️ Erreur lecture {label_path}: {e}")
        
        return annotations
    
    def save_yolo_annotations(self, annotations: List[List[float]], output_path: str):
        """Sauvegarde les annotations au format YOLO"""
        with open(output_path, 'w') as f:
            for ann in annotations:
                class_id, x_center, y_center, width, height = ann
                f.write(f"{int(class_id)} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
    
    def apply_augmentation(self, image: np.ndarray, annotations: List[List[float]], 
                          aug_type: str) -> Tuple[np.ndarray, List[List[float]]]:
        """Applique une augmentation à l'image et aux annotations YOLO"""
        h, w = image.shape[:2]
        
        if aug_type == 'horizontal_flip':
            augmented_img = cv2.flip(image, 1)
            augmented_annotations = []
            for ann in annotations:
                class_id, x_center, y_center, bbox_w, bbox_h = ann
                new_x_center = 1.0 - x_center
                augmented_annotations.append([class_id, new_x_center, y_center, bbox_w, bbox_h])
            return augmented_img, augmented_annotations
        
        elif aug_type == 'brightness':
            brightness = random.uniform(0.7, 1.4)
            augmented_img = cv2.convertScaleAbs(image, alpha=brightness, beta=0)
            return augmented_img, [ann.copy() for ann in annotations]
        
        elif aug_type == 'contrast':
            contrast = random.uniform(0.7, 1.3)
            mean = np.mean(image)
            augmented_img = cv2.convertScaleAbs(image, alpha=contrast, beta=(1 - contrast) * mean)
            return augmented_img, [ann.copy() for ann in annotations]
        
        elif aug_type == 'hue_shift':
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
            hue_shift = random.randint(-15, 15)
            hsv[:, :, 0] = (hsv[:, :, 0].astype(int) + hue_shift) % 180
            augmented_img = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
            return augmented_img, [ann.copy() for ann in annotations]
        
        elif aug_type == 'saturation':
            hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV).astype(np.float32)
            sat_factor = random.uniform(0.7, 1.3)
            hsv[:, :, 1] = np.clip(hsv[:, :, 1] * sat_factor, 0, 255)
            augmented_img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
            return augmented_img, [ann.copy() for ann in annotations]
        
        elif aug_type == 'noise':
            noise = np.random.normal(0, 10, image.shape).astype(np.int16)
            augmented_img = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
            return augmented_img, [ann.copy() for ann in annotations]
        
        elif aug_type == 'blur':
            kernel_size = random.choice([3, 5])
            augmented_img = cv2.GaussianBlur(image, (kernel_size, kernel_size), 0)
            return augmented_img, [ann.copy() for ann in annotations]
        
        elif aug_type == 'rotation':
            angle = random.uniform(-5, 5)
            center = (w // 2, h // 2)
            rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
            augmented_img = cv2.warpAffine(image, rotation_matrix, (w, h), 
                                           borderMode=cv2.BORDER_REFLECT)
            
            augmented_annotations = []
            for ann in annotations:
                class_id, x_center, y_center, bbox_w, bbox_h = ann
                
                abs_x_center = x_center * w
                abs_y_center = y_center * h
                abs_w = bbox_w * w
                abs_h = bbox_h * h
                
                x1 = abs_x_center - abs_w / 2
                y1 = abs_y_center - abs_h / 2
                x2 = abs_x_center + abs_w / 2
                y2 = abs_y_center + abs_h / 2
                
                points = np.array([
                    [x1, y1], [x2, y1], [x2, y2], [x1, y2]
                ]).reshape(-1, 1, 2).astype(np.float32)
                
                transformed = cv2.transform(points, rotation_matrix)
                
                x_coords = transformed[:, 0, 0]
                y_coords = transformed[:, 0, 1]
                
                new_x1 = max(0, np.min(x_coords))
                new_y1 = max(0, np.min(y_coords))
                new_x2 = min(w, np.max(x_coords))
                new_y2 = min(h, np.max(y_coords))
                
                new_w_abs = new_x2 - new_x1
                new_h_abs = new_y2 - new_y1
                
                if new_w_abs > 5 and new_h_abs > 5:
                    new_x_center = (new_x1 + new_w_abs / 2) / w
                    new_y_center = (new_y1 + new_h_abs / 2) / h
                    new_bbox_w = new_w_abs / w
                    new_bbox_h = new_h_abs / h
                    augmented_annotations.append([class_id, new_x_center, new_y_center, 
                                                 new_bbox_w, new_bbox_h])
            
            return augmented_img, augmented_annotations
        
        elif aug_type == 'combination_brightness_contrast':
            img_temp, ann_temp = self.apply_augmentation(image, annotations, 'brightness')
            return self.apply_augmentation(img_temp, ann_temp, 'contrast')
        
        elif aug_type == 'combination_flip_hue':
            img_temp, ann_temp = self.apply_augmentation(image, annotations, 'horizontal_flip')
            return self.apply_augmentation(img_temp, ann_temp, 'hue_shift')
        
        return image, [ann.copy() for ann in annotations]
    
    def _create_data_yaml(self, output_dir: str):
        """Crée le fichier data.yaml pour l'entraînement YOLO"""
        yaml_content = f"""# Dataset augmenté - Généré automatiquement
path: {os.path.abspath(output_dir)}
train: images
val: images

nc: {len(self.category_list)}
names: {self.category_list}
"""
        yaml_path = os.path.join(output_dir, "data.yaml")
        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
        
        self.log.emit(f"📄 Fichier data.yaml créé")
    
    def augment_dataset(self) -> int:
        """Augmente le dataset et retourne le nombre d'images générées"""
        self.log.emit("🔍 Collection des images annotées...")
        self.log.emit(f"   Dossier labels: {self.config.annotations_dir}")
        self.log.emit(f"   Dossier images: {self.config.frames_dir}")
        self.log.emit("")
        
        annotated_images = self.collect_annotated_images()
        
        if not annotated_images:
            self.log.emit("")
            self.log.emit("❌ Aucune image annotée trouvée!")
            self.log.emit("")
            self.log.emit("💡 Vérifiez que:")
            self.log.emit("   1. Le dossier Labels contient des fichiers .txt non vides")
            self.log.emit("   2. Le dossier Images contient les images correspondantes")
            self.log.emit("   3. Les noms correspondent (ex: frame001.txt ↔ frame001.jpg)")
            self.log.emit("")
            self.log.emit("📁 Structures supportées:")
            self.log.emit("   - images/ et labels/ dans le même dossier parent")
            self.log.emit("   - Images dans le même dossier que les labels")
            self.log.emit("   - frames_dir/level/image.jpg")
            return 0
        
        self.log.emit("")
        self.log.emit(f"✅ Trouvé {len(annotated_images)} images avec annotations")
        
        # Créer dossiers de sortie (structure YOLO)
        output_dir = self.config.output_dir
        images_output = os.path.join(output_dir, "images")
        labels_output = os.path.join(output_dir, "labels")
        Path(images_output).mkdir(parents=True, exist_ok=True)
        Path(labels_output).mkdir(parents=True, exist_ok=True)
        
        # Calcul du total estimé
        aug_types = self.config.augmentation_types
        multiplier = self.config.multiplier
        total_to_generate = len(annotated_images) * (1 + len(aug_types) * multiplier)
        current = 0
        total_generated = 0
        
        self.log.emit(f"🚀 Génération de ~{total_to_generate} images...")
        self.log.emit("")
        
        for level, image_name, label_path, image_path in annotated_images:
            if self.cancelled:
                break
            
            # Charger l'image
            image = cv2.imread(image_path)
            if image is None:
                self.log.emit(f"⚠️ Impossible de charger: {image_path}")
                continue
            
            # Charger les annotations YOLO
            annotations = self.load_yolo_annotations(label_path)
            if not annotations:
                continue
            
            # Nom de base (level_imagename)
            base_name = f"{level}_{Path(image_name).stem}"
            
            # 1. Copier l'original
            orig_img_path = os.path.join(images_output, f"{base_name}.jpg")
            orig_lbl_path = os.path.join(labels_output, f"{base_name}.txt")
            
            cv2.imwrite(orig_img_path, image)
            self.save_yolo_annotations(annotations, orig_lbl_path)
            total_generated += 1
            current += 1
            self.progress.emit(current, total_to_generate)
            
            # 2. Générer les augmentations
            for aug_idx in range(multiplier):
                for aug_type in aug_types:
                    if self.cancelled:
                        break
                    
                    try:
                        aug_img, aug_ann = self.apply_augmentation(image, annotations, aug_type)
                        
                        if aug_ann:
                            aug_name = f"{base_name}_{aug_type}_{aug_idx}"
                            aug_img_path = os.path.join(images_output, f"{aug_name}.jpg")
                            aug_lbl_path = os.path.join(labels_output, f"{aug_name}.txt")
                            
                            cv2.imwrite(aug_img_path, aug_img)
                            self.save_yolo_annotations(aug_ann, aug_lbl_path)
                            total_generated += 1
                    
                    except Exception as e:
                        self.log.emit(f"⚠️ Erreur {aug_type}: {e}")
                    
                    current += 1
                    self.progress.emit(current, total_to_generate)
            
            if total_generated % 100 == 0:
                self.log.emit(f"📊 Progression: {total_generated} images générées")
        
        # Créer le fichier data.yaml
        self._create_data_yaml(output_dir)
        
        self.log.emit("")
        self.log.emit(f"✅ Terminé: {total_generated} images générées")
        return total_generated


class DatasetAugmentationWidget(QWidget):
    """Widget principal pour l'augmentation de dataset"""
    
    # ========== STYLES GLOBAUX POUR MODE SOMBRE ==========
    
    LABEL_STYLE = """
        QLabel {
            color: #ddd;
            font-size: 12px;
        }
    """
    
    SPINBOX_STYLE = """
        QSpinBox {
            background-color: #3d3d3d;
            color: #fff;
            border: 2px solid #666;
            border-radius: 5px;
            padding: 6px 12px;
            min-width: 100px;
            font-size: 14px;
            font-weight: bold;
        }
        QSpinBox:focus {
            border-color: #7b1fa2;
        }
        QSpinBox::up-button, QSpinBox::down-button {
            background-color: #555;
            border: none;
            width: 22px;
        }
        QSpinBox::up-button:hover, QSpinBox::down-button:hover {
            background-color: #777;
        }
        QSpinBox::up-arrow {
            image: none;
            border-left: 6px solid transparent;
            border-right: 6px solid transparent;
            border-bottom: 6px solid #fff;
            width: 0;
            height: 0;
        }
        QSpinBox::down-arrow {
            image: none;
            border-left: 6px solid transparent;
            border-right: 6px solid transparent;
            border-top: 6px solid #fff;
            width: 0;
            height: 0;
        }
    """
    
    CHECKBOX_STYLE = """
        QCheckBox {
            color: #eee;
            spacing: 10px;
            font-size: 12px;
            padding: 5px;
        }
        QCheckBox::indicator {
            width: 22px;
            height: 22px;
            border-radius: 4px;
            border: 2px solid #888;
            background-color: #3d3d3d;
        }
        QCheckBox::indicator:checked {
            background-color: #4caf50;
            border-color: #4caf50;
            image: none;
        }
        QCheckBox::indicator:checked::after {
            content: "✓";
        }
        QCheckBox::indicator:hover {
            border-color: #aaa;
            background-color: #4d4d4d;
        }
        QCheckBox::indicator:checked:hover {
            background-color: #5cbf60;
            border-color: #5cbf60;
        }
    """
    
    LINEEDIT_STYLE = """
        QLineEdit {
            background-color: #3d3d3d;
            color: #fff;
            border: 2px solid #666;
            border-radius: 5px;
            padding: 8px 10px;
            font-size: 11px;
        }
        QLineEdit:focus {
            border-color: #7b1fa2;
        }
        QLineEdit::placeholder {
            color: #888;
        }
    """
    
    BUTTON_SMALL_STYLE = """
        QPushButton {
            background-color: #555;
            color: white;
            border: none;
            border-radius: 5px;
            padding: 8px 14px;
            font-size: 12px;
        }
        QPushButton:hover {
            background-color: #666;
        }
        QPushButton:pressed {
            background-color: #444;
        }
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self._create_ui()
    
    def _get_groupbox_style(self, color: str) -> str:
        """Retourne le style CSS pour un QGroupBox"""
        return f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                color: {color};
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 14px;
                padding-top: 14px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 8px;
                background-color: transparent;
            }}
        """
    
    def _create_styled_label(self, text: str, bold: bool = False) -> QLabel:
        """Crée un QLabel avec le style approprié"""
        label = QLabel(text)
        style = "color: #ddd; font-size: 12px;"
        if bold:
            style += " font-weight: bold;"
        label.setStyleSheet(style)
        return label
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Titre
        title = QLabel("🔄 Augmentation de Dataset")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: #7b1fa2; padding: 10px;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "Augmentez votre dataset annoté en appliquant des transformations.\n"
            "Sélectionnez un ou plusieurs niveaux spécifiques à augmenter."
        )
        desc.setStyleSheet("color: #aaa; padding: 5px; font-style: italic;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Splitter horizontal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ===== PANNEAU GAUCHE: Configuration =====
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)
        
        left_layout.addWidget(self._create_folders_group())
        left_layout.addWidget(self._create_level_selection_group())
        left_layout.addWidget(self._create_augmentation_config_group())
        left_layout.addStretch()
        
        splitter.addWidget(left_panel)
        
        # ===== PANNEAU DROIT: Logs et progression =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Progression
        progress_group = QGroupBox("📊 Progression")
        progress_group.setStyleSheet(self._get_groupbox_style("#4caf50"))
        progress_layout = QVBoxLayout()
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #7b1fa2;
                border-radius: 5px;
                text-align: center;
                height: 28px;
                background-color: #333;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7b1fa2, stop:1 #9c27b0);
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        
        self.progress_label = QLabel("En attente...")
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("color: #ccc; font-size: 12px;")
        progress_layout.addWidget(self.progress_label)
        
        progress_group.setLayout(progress_layout)
        right_layout.addWidget(progress_group)
        
        # Logs
        logs_group = QGroupBox("📋 Logs")
        logs_group.setStyleSheet(self._get_groupbox_style("#1976D2"))
        logs_layout = QVBoxLayout()
        
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #ddd;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #444;
                border-radius: 5px;
                padding: 8px;
            }
        """)
        logs_layout.addWidget(self.logs_text)
        
        logs_group.setLayout(logs_layout)
        right_layout.addWidget(logs_group)
        
        splitter.addWidget(right_panel)
        splitter.setSizes([480, 520])
        
        layout.addWidget(splitter)
        
        # ===== Boutons d'action =====
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(15)
        
        self.btn_start = QPushButton("🚀 Lancer l'augmentation")
        self.btn_start.setMinimumHeight(48)
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #7b1fa2;
                color: white;
                border: none;
                padding: 14px 30px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #9c27b0; }
            QPushButton:pressed { background-color: #6a1b9a; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.btn_start.clicked.connect(self._start_augmentation)
        buttons_layout.addWidget(self.btn_start)
        
        self.btn_cancel = QPushButton("⏹️ Annuler")
        self.btn_cancel.setMinimumHeight(48)
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 14px 30px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #e53935; }
            QPushButton:pressed { background-color: #c62828; }
            QPushButton:disabled { background-color: #555; color: #888; }
        """)
        self.btn_cancel.clicked.connect(self._cancel_augmentation)
        buttons_layout.addWidget(self.btn_cancel)
        
        self.btn_open_output = QPushButton("📂 Ouvrir le dossier de sortie")
        self.btn_open_output.setMinimumHeight(48)
        self.btn_open_output.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 14px 30px;
                border-radius: 6px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1e88e5; }
            QPushButton:pressed { background-color: #1565c0; }
        """)
        self.btn_open_output.clicked.connect(self._open_output_folder)
        buttons_layout.addWidget(self.btn_open_output)
        
        layout.addLayout(buttons_layout)
    
    def _create_folders_group(self) -> QGroupBox:
        """Créer le groupe de sélection des dossiers"""
        group = QGroupBox("📁 Dossiers")
        group.setStyleSheet(self._get_groupbox_style("#7b1fa2"))
        
        layout = QGridLayout()
        layout.setSpacing(10)
        layout.setColumnStretch(1, 1)
        
        # Dossier annotations (labels)
        layout.addWidget(self._create_styled_label("Labels (annotations):"), 0, 0)
        
        self.edit_annotations_dir = QLineEdit()
        self.edit_annotations_dir.setPlaceholderText("Dossier contenant les fichiers .txt (YOLO)...")
        self.edit_annotations_dir.setStyleSheet(self.LINEEDIT_STYLE)
        layout.addWidget(self.edit_annotations_dir, 0, 1)
        
        btn_browse_ann = QPushButton("📂")
        btn_browse_ann.setFixedSize(42, 38)
        btn_browse_ann.setStyleSheet(self.BUTTON_SMALL_STYLE)
        btn_browse_ann.clicked.connect(lambda: self._browse_folder(self.edit_annotations_dir))
        layout.addWidget(btn_browse_ann, 0, 2)
        
        # Dossier frames (images)
        layout.addWidget(self._create_styled_label("Images (frames):"), 1, 0)
        
        self.edit_frames_dir = QLineEdit()
        self.edit_frames_dir.setPlaceholderText("Dossier contenant les images...")
        self.edit_frames_dir.setStyleSheet(self.LINEEDIT_STYLE)
        layout.addWidget(self.edit_frames_dir, 1, 1)
        
        btn_browse_frames = QPushButton("📂")
        btn_browse_frames.setFixedSize(42, 38)
        btn_browse_frames.setStyleSheet(self.BUTTON_SMALL_STYLE)
        btn_browse_frames.clicked.connect(lambda: self._browse_folder(self.edit_frames_dir))
        layout.addWidget(btn_browse_frames, 1, 2)
        
        # Dossier sortie
        layout.addWidget(self._create_styled_label("Sortie:"), 2, 0)
        
        self.edit_output_dir = QLineEdit()
        self.edit_output_dir.setPlaceholderText("Dossier de sortie pour le dataset augmenté...")
        self.edit_output_dir.setText("augmented_dataset")
        self.edit_output_dir.setStyleSheet(self.LINEEDIT_STYLE)
        layout.addWidget(self.edit_output_dir, 2, 1)
        
        btn_browse_output = QPushButton("📂")
        btn_browse_output.setFixedSize(42, 38)
        btn_browse_output.setStyleSheet(self.BUTTON_SMALL_STYLE)
        btn_browse_output.clicked.connect(lambda: self._browse_folder(self.edit_output_dir))
        layout.addWidget(btn_browse_output, 2, 2)
        
        # Bouton pour scanner les niveaux
        btn_scan = QPushButton("🔍 Scanner les niveaux")
        btn_scan.setMinimumHeight(40)
        btn_scan.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #66bb6a; }
            QPushButton:pressed { background-color: #43a047; }
        """)
        btn_scan.clicked.connect(self._scan_levels)
        layout.addWidget(btn_scan, 3, 0, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_level_selection_group(self) -> QGroupBox:
        """Créer le groupe de sélection du niveau"""
        group = QGroupBox("🎮 Sélection du niveau")
        group.setStyleSheet(self._get_groupbox_style("#1976D2"))
        
        layout = QVBoxLayout()
        layout.setSpacing(8)
        
        info = QLabel("Sélectionnez le(s) niveau(x) à augmenter:")
        info.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(info)
        
        self.levels_list = QListWidget()
        self.levels_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.levels_list.setMinimumHeight(100)
        self.levels_list.setMaximumHeight(150)
        self.levels_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                color: #fff;
                border: 1px solid #555;
                border-radius: 5px;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #3d3d3d;
            }
            QListWidget::item:selected {
                background-color: #1976D2;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #3d3d3d;
            }
        """)
        self.levels_list.itemSelectionChanged.connect(self._update_estimation)
        layout.addWidget(self.levels_list)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        btn_select_all = QPushButton("✅ Tout sélectionner")
        btn_select_all.setStyleSheet(self.BUTTON_SMALL_STYLE)
        btn_select_all.clicked.connect(lambda: self.levels_list.selectAll())
        btn_layout.addWidget(btn_select_all)
        
        btn_deselect_all = QPushButton("❌ Tout désélectionner")
        btn_deselect_all.setStyleSheet(self.BUTTON_SMALL_STYLE)
        btn_deselect_all.clicked.connect(lambda: self.levels_list.clearSelection())
        btn_layout.addWidget(btn_deselect_all)
        
        layout.addLayout(btn_layout)
        
        self.level_stats_label = QLabel("Aucun niveau scanné")
        self.level_stats_label.setStyleSheet("color: #888; font-style: italic; font-size: 11px;")
        layout.addWidget(self.level_stats_label)
        
        group.setLayout(layout)
        return group
    
    def _create_augmentation_config_group(self) -> QGroupBox:
        """Créer le groupe de configuration de l'augmentation"""
        group = QGroupBox("⚙️ Configuration")
        group.setStyleSheet(self._get_groupbox_style("#ff9800"))
        
        layout = QVBoxLayout()
        layout.setSpacing(12)
        
        # Multiplicateur
        mult_layout = QHBoxLayout()
        mult_label = self._create_styled_label("Multiplicateur:", bold=True)
        mult_layout.addWidget(mult_label)
        
        self.spin_multiplier = QSpinBox()
        self.spin_multiplier.setRange(1, 20)
        self.spin_multiplier.setValue(5)
        self.spin_multiplier.setToolTip("Nombre de fois que chaque augmentation est appliquée")
        self.spin_multiplier.setStyleSheet(self.SPINBOX_STYLE)
        self.spin_multiplier.valueChanged.connect(self._update_estimation)
        mult_layout.addWidget(self.spin_multiplier)
        
        mult_layout.addStretch()
        layout.addLayout(mult_layout)
        
        # Séparateur
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFixedHeight(2)
        separator.setStyleSheet("background-color: #555;")
        layout.addWidget(separator)
        
        # Titre des types d'augmentation
        aug_title = self._create_styled_label("Types d'augmentation:", bold=True)
        layout.addWidget(aug_title)
        
        # Grille des checkboxes
        self.aug_checkboxes = {}
        augmentation_types = [
            ('horizontal_flip', '↔️ Flip horizontal', True),
            ('brightness', '☀️ Luminosité', True),
            ('contrast', '🔲 Contraste', True),
            ('hue_shift', '🎨 Teinte', True),
            ('saturation', '💧 Saturation', False),
            ('noise', '📺 Bruit', False),
            ('blur', '🌫️ Flou', False),
            ('rotation', '🔄 Rotation (±5°)', False),
            ('combination_brightness_contrast', '⚡ Combo lum+cont', False),
            ('combination_flip_hue', '🎭 Combo flip+teinte', False),
        ]
        
        grid = QGridLayout()
        grid.setSpacing(8)
        
        for i, (key, label, default) in enumerate(augmentation_types):
            cb = QCheckBox(label)
            cb.setChecked(default)
            cb.setStyleSheet(self.CHECKBOX_STYLE)
            cb.stateChanged.connect(self._update_estimation)
            self.aug_checkboxes[key] = cb
            grid.addWidget(cb, i // 2, i % 2)
        
        layout.addLayout(grid)
        
        # Estimation
        self.estimation_label = QLabel("Sélectionnez un niveau et des augmentations")
        self.estimation_label.setStyleSheet("""
            QLabel {
                color: #ff9800;
                font-weight: bold;
                font-size: 13px;
                margin-top: 10px;
                padding: 10px;
                background-color: rgba(255, 152, 0, 0.15);
                border-radius: 5px;
                border: 1px solid rgba(255, 152, 0, 0.3);
            }
        """)
        self.estimation_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.estimation_label)
        
        group.setLayout(layout)
        return group
    
    def _browse_folder(self, line_edit: QLineEdit):
        """Ouvrir un dialogue pour sélectionner un dossier"""
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner un dossier")
        if folder:
            line_edit.setText(folder)
    
    def _scan_levels(self):
        """Scanner les niveaux disponibles dans le dossier d'annotations.

        Stocke dans UserRole le chemin ABSOLU du dossier contenant les .txt,
        ce qui évite toute ambiguïté de nommage (ex: sous-dossier "labels").
        """
        ann_dir = self.edit_annotations_dir.text()

        if not ann_dir or not os.path.exists(ann_dir):
            QMessageBox.warning(self, "Erreur",
                "Veuillez sélectionner un dossier d'annotations (labels) valide.")
            return

        self.levels_list.clear()
        self.logs_text.clear()
        levels_found = []
        total_images = 0

        def add_level(display_name: str, ann_path: str, count: int):
            """Ajoute une entrée dans la liste des niveaux."""
            levels_found.append(display_name)
            item = QListWidgetItem(f"📁 {display_name} ({count} annotations)")
            # UserRole = chemin absolu du dossier contenant les .txt
            item.setData(Qt.ItemDataRole.UserRole, os.path.abspath(ann_path))
            self.levels_list.addItem(item)
            self._log(f"📂 {display_name} → {ann_path}  ({count} annotations)")

        # ── Cas 1 : le dossier sélectionné contient directement des .txt ──
        root_txts = [f for f in os.listdir(ann_dir)
                     if f.endswith('.txt') and os.path.isfile(os.path.join(ann_dir, f))]
        non_empty_root = sum(1 for f in root_txts
                             if os.path.getsize(os.path.join(ann_dir, f)) > 0)
        if non_empty_root > 0:
            total_images += non_empty_root
            add_level(os.path.basename(ann_dir), ann_dir, non_empty_root)

        # ── Cas 2 : sous-dossiers (ex: 1-1, 1-2, ou "labels" en YOLO) ──
        for item in sorted(os.listdir(ann_dir)):
            item_path = os.path.join(ann_dir, item)
            if not os.path.isdir(item_path):
                continue

            # Compter les .txt non vides
            txts = [f for f in os.listdir(item_path) if f.endswith('.txt')]
            count = sum(1 for f in txts
                        if os.path.getsize(os.path.join(item_path, f)) > 0)
            if count == 0:
                continue

            # Nom d'affichage : si le sous-dossier s'appelle "labels" ou "images",
            # on préfixe avec le nom du dossier parent pour plus de clarté.
            if item.lower() in ('labels', 'images', 'annotations', 'img'):
                display = f"{os.path.basename(ann_dir)} [{item}]"
            else:
                display = item

            total_images += count
            add_level(display, item_path, count)

        if levels_found:
            self.level_stats_label.setText(
                f"✅ {len(levels_found)} niveau(x) trouvé(s), {total_images} annotations"
            )
            self.level_stats_label.setStyleSheet(
                "color: #4caf50; font-style: italic; font-size: 11px;")
            self._log(f"\n🔍 Scan terminé : {len(levels_found)} niveaux, {total_images} annotations")

            if self.levels_list.count() > 0:
                self.levels_list.item(0).setSelected(True)
            self._update_estimation()
        else:
            self.level_stats_label.setText("❌ Aucun niveau avec annotations trouvé")
            self.level_stats_label.setStyleSheet(
                "color: #f44336; font-style: italic; font-size: 11px;")
            QMessageBox.warning(self, "Aucun niveau",
                "Aucun niveau avec des annotations n'a été trouvé.\n\n"
                "Assurez-vous que le dossier sélectionné contient:\n"
                "• Des fichiers .txt au format YOLO directement, OU\n"
                "• Des sous-dossiers (ex: 1-1, 1-2, labels) avec des .txt")
    
    def _update_estimation(self):
        """Mettre à jour l'estimation du nombre d'images"""
        selected_count = 0
        for i in range(self.levels_list.count()):
            item = self.levels_list.item(i)
            if item.isSelected():
                text = item.text()
                try:
                    count = int(text.split('(')[1].split(' ')[0])
                    selected_count += count
                except:
                    pass
        
        active_augs = sum(1 for cb in self.aug_checkboxes.values() if cb.isChecked())
        multiplier = self.spin_multiplier.value()
        
        if selected_count > 0 and active_augs > 0:
            total = selected_count * (1 + multiplier * active_augs)
            self.estimation_label.setText(
                f"📊 Estimation: {selected_count} images → ~{total} images"
            )
        else:
            self.estimation_label.setText("Sélectionnez un niveau et des augmentations")
    
    def _log(self, message: str):
        """Ajouter un message aux logs"""
        self.logs_text.append(message)
        scrollbar = self.logs_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def _start_augmentation(self):
        """Lancer l'augmentation"""
        ann_dir = self.edit_annotations_dir.text()
        frames_dir = self.edit_frames_dir.text()
        output_dir = self.edit_output_dir.text()
        
        if not ann_dir or not os.path.exists(ann_dir):
            QMessageBox.warning(self, "Erreur", "Dossier d'annotations (labels) invalide.")
            return
        
        if not frames_dir or not os.path.exists(frames_dir):
            QMessageBox.warning(self, "Erreur", "Dossier d'images (frames) invalide.")
            return
        
        if not output_dir:
            QMessageBox.warning(self, "Erreur", "Spécifiez un dossier de sortie.")
            return
        
        selected_levels = []
        for i in range(self.levels_list.count()):
            item = self.levels_list.item(i)
            if item.isSelected():
                # UserRole contient le chemin absolu du dossier labels
                abs_ann_path = item.data(Qt.ItemDataRole.UserRole)
                # Extraire le nom d'affichage depuis le texte de l'item
                display_name = item.text().split(' (')[0].lstrip('📁').strip()
                # Stocker le tuple (display_name, abs_path) pour collect_annotated_images
                selected_levels.append((display_name, abs_ann_path))
        
        if not selected_levels:
            QMessageBox.warning(self, "Erreur", "Sélectionnez au moins un niveau.")
            return
        
        aug_types = [key for key, cb in self.aug_checkboxes.items() if cb.isChecked()]
        
        if not aug_types:
            QMessageBox.warning(self, "Erreur", "Sélectionnez au moins un type d'augmentation.")
            return
        
        config = AugmentationConfig(
            annotations_dir=ann_dir,
            frames_dir=frames_dir,
            output_dir=output_dir,
            selected_levels=selected_levels,
            multiplier=self.spin_multiplier.value(),
            augmentation_types=aug_types
        )
        
        level_names = [n for n, _ in selected_levels]

        self._log("=" * 55)
        self._log("🚀 Démarrage de l'augmentation...")
        self._log(f"📁 Niveaux       : {', '.join(level_names)}")
        self._log(f"🔧 Augmentations : {', '.join(aug_types)}")
        self._log(f"✖️ Multiplicateur : {config.multiplier}")
        self._log("")
        
        self.btn_start.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setValue(0)
        
        self.worker = AugmentationWorker(config)
        self.worker.progress.connect(self._on_progress)
        self.worker.log.connect(self._log)
        self.worker.finished_signal.connect(self._on_finished)
        self.worker.start()
    
    def _cancel_augmentation(self):
        """Annuler l'augmentation"""
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self._log("⏹️ Annulation demandée...")
    
    def _on_progress(self, current: int, total: int):
        """Mise à jour de la progression"""
        if total > 0:
            percent = int(current * 100 / total)
            self.progress_bar.setValue(percent)
            self.progress_label.setText(f"{current} / {total} ({percent}%)")
    
    def _on_finished(self, success: bool, message: str, count: int):
        """Fin de l'augmentation"""
        self.btn_start.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        
        if success:
            self._log(f"✅ {message}")
            self._log(f"📊 Total: {count} images générées")
            self.progress_bar.setValue(100)
            self.progress_label.setText(f"Terminé: {count} images")
            
            QMessageBox.information(self, "✅ Terminé",
                f"{message}\n\n"
                f"• Images générées: {count}\n"
                f"• Dossier: {self.edit_output_dir.text()}\n\n"
                f"Le fichier data.yaml a été créé pour l'entraînement YOLO.")
        else:
            self._log(f"❌ {message}")
            self.progress_label.setText("Échec")
            if count == 0:
                QMessageBox.warning(self, "Attention", 
                    f"{message}\n\n"
                    "Consultez les logs pour plus de détails.\n\n"
                    "Assurez-vous que:\n"
                    "• Les dossiers Labels et Images sont corrects\n"
                    "• Les noms de fichiers correspondent\n"
                    "  (ex: frame001.txt ↔ frame001.jpg)")
            else:
                QMessageBox.warning(self, "Erreur", message)
        
        self.worker = None
    
    def _open_output_folder(self):
        """Ouvrir le dossier de sortie"""
        output_dir = self.edit_output_dir.text()
        if output_dir and os.path.exists(output_dir):
            import subprocess
            import platform
            
            if platform.system() == 'Windows':
                os.startfile(output_dir)
            elif platform.system() == 'Darwin':
                subprocess.run(['open', output_dir])
            else:
                subprocess.run(['xdg-open', output_dir])
        else:
            QMessageBox.warning(self, "Erreur", 
                "Le dossier de sortie n'existe pas encore.\n"
                "Lancez d'abord une augmentation.")


# Pour test standalone
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    # Style sombre pour test
    app.setStyleSheet("QWidget { background-color: #2d2d2d; }")
    
    widget = DatasetAugmentationWidget()
    widget.setWindowTitle("Dataset Augmentation - Test")
    widget.resize(1100, 800)
    widget.show()
    sys.exit(app.exec())