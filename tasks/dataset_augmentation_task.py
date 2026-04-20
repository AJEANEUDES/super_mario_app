"""
Dataset Augmentation Task - Logique métier pour l'augmentation de dataset

Ce module gère:
- La collecte des images annotées
- L'application des transformations d'augmentation
- La génération du dataset augmenté au format YOLO



Version 1.0.0
Fichier: tasks/dataset_augmentation_task.py
"""

import os
import cv2
import numpy as np
from pathlib import Path
import shutil
import random
from typing import List, Dict, Optional, Tuple, Callable
from dataclasses import dataclass, field

from tasks.base_task import BaseTask, TaskStatus


@dataclass
class AugmentationResult:
    """Résultat de l'augmentation"""
    success: bool
    message: str
    total_generated: int = 0
    original_count: int = 0
    levels_processed: List[str] = field(default_factory=list)
    output_dir: str = ""


class DatasetAugmentationTask(BaseTask):
    """Tâche d'augmentation de dataset"""
    
    name = "Dataset Augmentation"
    description = "Augmente un dataset annoté avec des transformations"
    
    # Liste des catégories connues (pour YOLO)
    CATEGORY_LIST = [
        'big_mario', 'brick_block', 'coin', 'empty_block', 'fire_mario', 
        'fireball', 'flower', 'goal_pole', 'goomba', 'hard_block',
        'koopa', 'little_mario', 'mushroom', 'mystery_block', 'pipe', 
        'pipe_head', 'shell', 'undestructible_block', 'flag', 'hammer',
        'fish_flying', 'piranha', 'turtle', 'lakitu', 'magic_bean', 'spike'
    ]
    
    # Types d'augmentation disponibles
    AUGMENTATION_TYPES = {
        'horizontal_flip': "Flip horizontal",
        'brightness': "Variation de luminosité",
        'contrast': "Variation de contraste",
        'hue_shift': "Décalage de teinte",
        'saturation': "Variation de saturation",
        'noise': "Bruit gaussien",
        'blur': "Flou gaussien",
        'rotation': "Rotation légère (±5°)",
        'combination_brightness_contrast': "Combo luminosité+contraste",
        'combination_flip_hue': "Combo flip+teinte"
    }
    
    def __init__(self):
        super().__init__()
        self.cancelled = False
        self.progress_callback: Optional[Callable[[int, int], None]] = None
        self.log_callback: Optional[Callable[[str], None]] = None
    
    def configure(self, annotations_dir: str, frames_dir: str, output_dir: str,
                  selected_levels: List[str], multiplier: int = 5,
                  augmentation_types: List[str] = None):
        """Configurer la tâche d'augmentation
        
        Args:
            annotations_dir: Dossier contenant les fichiers .txt (YOLO)
            frames_dir: Dossier contenant les images
            output_dir: Dossier de sortie
            selected_levels: Liste des niveaux à augmenter (ex: ['1-1', '1-2'])
            multiplier: Nombre de fois que chaque augmentation est appliquée
            augmentation_types: Liste des types d'augmentation à appliquer
        """
        self.config = {
            'annotations_dir': annotations_dir,
            'frames_dir': frames_dir,
            'output_dir': output_dir,
            'selected_levels': selected_levels,
            'multiplier': multiplier,
            'augmentation_types': augmentation_types or ['horizontal_flip', 'brightness', 'contrast', 'hue_shift']
        }
    
    def cancel(self):
        """Annuler la tâche"""
        self.cancelled = True
    
    def _log(self, message: str):
        """Logger un message"""
        if self.log_callback:
            self.log_callback(message)
        print(message)
    
    def _update_progress(self, current: int, total: int):
        """Mettre à jour la progression"""
        if self.progress_callback:
            self.progress_callback(current, total)
        
        if total > 0:
            percent = int(current * 100 / total)
            self.progress = percent
    
    def run(self) -> AugmentationResult:
        """Exécuter l'augmentation"""
        self.status = TaskStatus.RUNNING
        self.cancelled = False
        
        try:
            result = self._augment_dataset()
            
            if result.success:
                self.status = TaskStatus.COMPLETED
            else:
                self.status = TaskStatus.FAILED
            
            return result
            
        except Exception as e:
            self.status = TaskStatus.FAILED
            return AugmentationResult(
                success=False,
                message=f"Erreur: {str(e)}"
            )
    
    def _collect_annotated_images(self) -> List[Tuple[str, str, str, str]]:
        """Collecte les images annotées des niveaux sélectionnés
        
        Returns:
            Liste de tuples (level, image_name, label_path, image_path)
        """
        annotated_images = []
        
        for level in self.config['selected_levels']:
            level_ann_path = os.path.join(self.config['annotations_dir'], level)
            
            if not os.path.isdir(level_ann_path):
                self._log(f"⚠️ Niveau non trouvé: {level}")
                continue
            
            self._log(f"📂 Scan du niveau: {level}")
            
            # Chercher les fichiers d'annotation (.txt pour YOLO)
            for ann_file in os.listdir(level_ann_path):
                if not ann_file.endswith('.txt'):
                    continue
                
                label_path = os.path.join(level_ann_path, ann_file)
                
                # Vérifier que le fichier n'est pas vide
                if os.path.getsize(label_path) == 0:
                    continue
                
                # Trouver l'image correspondante
                base_name = ann_file.replace('.txt', '')
                image_name = None
                image_path = None
                
                for ext in ['.jpg', '.jpeg', '.png']:
                    potential_path = os.path.join(self.config['frames_dir'], level, base_name + ext)
                    if os.path.exists(potential_path):
                        image_name = base_name + ext
                        image_path = potential_path
                        break
                
                if image_path and os.path.exists(image_path):
                    annotated_images.append((level, image_name, label_path, image_path))
        
        return annotated_images
    
    def _load_yolo_annotations(self, label_path: str) -> List[List[float]]:
        """Charge les annotations au format YOLO
        
        Returns:
            Liste de [class_id, x_center, y_center, width, height] (normalisés)
        """
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
            self._log(f"⚠️ Erreur lecture {label_path}: {e}")
        
        return annotations
    
    def _save_yolo_annotations(self, annotations: List[List[float]], output_path: str):
        """Sauvegarde les annotations au format YOLO"""
        with open(output_path, 'w') as f:
            for ann in annotations:
                class_id, x_center, y_center, width, height = ann
                f.write(f"{int(class_id)} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}\n")
    
    def _apply_augmentation(self, image: np.ndarray, annotations: List[List[float]], 
                           aug_type: str) -> Tuple[np.ndarray, List[List[float]]]:
        """Applique une augmentation à l'image et aux annotations YOLO
        
        Les annotations sont au format YOLO normalisé: [class_id, x_center, y_center, w, h]
        """
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
                
                # Convertir en coordonnées absolues
                abs_x_center = x_center * w
                abs_y_center = y_center * h
                abs_w = bbox_w * w
                abs_h = bbox_h * h
                
                # Coins du rectangle
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
            img_temp, ann_temp = self._apply_augmentation(image, annotations, 'brightness')
            return self._apply_augmentation(img_temp, ann_temp, 'contrast')
        
        elif aug_type == 'combination_flip_hue':
            img_temp, ann_temp = self._apply_augmentation(image, annotations, 'horizontal_flip')
            return self._apply_augmentation(img_temp, ann_temp, 'hue_shift')
        
        return image, [ann.copy() for ann in annotations]
    
    def _create_data_yaml(self, output_dir: str):
        """Crée le fichier data.yaml pour l'entraînement YOLO"""
        yaml_content = f"""# Dataset augmenté - Généré automatiquement
path: {os.path.abspath(output_dir)}
train: images
val: images

nc: {len(self.CATEGORY_LIST)}
names: {self.CATEGORY_LIST}
"""
        yaml_path = os.path.join(output_dir, "data.yaml")
        with open(yaml_path, 'w') as f:
            f.write(yaml_content)
        
        self._log(f"📄 Fichier data.yaml créé")
    
    def _augment_dataset(self) -> AugmentationResult:
        """Exécute l'augmentation du dataset"""
        self._log("🔍 Collection des images annotées...")
        annotated_images = self._collect_annotated_images()
        
        if not annotated_images:
            return AugmentationResult(
                success=False,
                message="Aucune image annotée trouvée!"
            )
        
        self._log(f"✅ Trouvé {len(annotated_images)} images avec annotations")
        
        # Créer dossiers de sortie (structure YOLO)
        output_dir = self.config['output_dir']
        images_output = os.path.join(output_dir, "images")
        labels_output = os.path.join(output_dir, "labels")
        Path(images_output).mkdir(parents=True, exist_ok=True)
        Path(labels_output).mkdir(parents=True, exist_ok=True)
        
        # Calcul du total estimé
        aug_types = self.config['augmentation_types']
        multiplier = self.config['multiplier']
        total_to_generate = len(annotated_images) * (1 + len(aug_types) * multiplier)
        current = 0
        total_generated = 0
        
        levels_processed = set()
        
        for level, image_name, label_path, image_path in annotated_images:
            if self.cancelled:
                break
            
            # Charger l'image
            image = cv2.imread(image_path)
            if image is None:
                self._log(f"⚠️ Impossible de charger: {image_path}")
                continue
            
            # Charger les annotations YOLO
            annotations = self._load_yolo_annotations(label_path)
            if not annotations:
                continue
            
            levels_processed.add(level)
            
            # Nom de base (level_imagename)
            base_name = f"{level}_{Path(image_name).stem}"
            
            # 1. Copier l'original
            orig_img_path = os.path.join(images_output, f"{base_name}.jpg")
            orig_lbl_path = os.path.join(labels_output, f"{base_name}.txt")
            
            cv2.imwrite(orig_img_path, image)
            self._save_yolo_annotations(annotations, orig_lbl_path)
            total_generated += 1
            current += 1
            self._update_progress(current, total_to_generate)
            
            # 2. Générer les augmentations et voir si cela maarche
            for aug_idx in range(multiplier):
                for aug_type in aug_types:
                    if self.cancelled:
                        break
                    
                    try:
                        aug_img, aug_ann = self._apply_augmentation(image, annotations, aug_type)
                        
                        if aug_ann:
                            aug_name = f"{base_name}_{aug_type}_{aug_idx}"
                            aug_img_path = os.path.join(images_output, f"{aug_name}.jpg")
                            aug_lbl_path = os.path.join(labels_output, f"{aug_name}.txt")
                            
                            cv2.imwrite(aug_img_path, aug_img)
                            self._save_yolo_annotations(aug_ann, aug_lbl_path)
                            total_generated += 1
                    
                    except Exception as e:
                        self._log(f"⚠️ Erreur {aug_type}: {e}")
                    
                    current += 1
                    self._update_progress(current, total_to_generate)
            
            if total_generated % 50 == 0:
                self._log(f"📊 Progression: {total_generated} images générées")
        
        if self.cancelled:
            return AugmentationResult(
                success=False,
                message="Augmentation annulée",
                total_generated=total_generated,
                original_count=len(annotated_images),
                levels_processed=list(levels_processed),
                output_dir=output_dir
            )
        
        # Créer le fichier data.yaml
        self._create_data_yaml(output_dir)
        
        self._log(f"✅ Terminé: {total_generated} images générées")
        
        return AugmentationResult(
            success=True,
            message="Augmentation terminée avec succès!",
            total_generated=total_generated,
            original_count=len(annotated_images),
            levels_processed=list(levels_processed),
            output_dir=output_dir
        )
    
    @classmethod
    def get_available_levels(cls, annotations_dir: str) -> List[Dict]:
        """Retourne la liste des niveaux disponibles avec leurs statistiques
        
        Args:
            annotations_dir: Dossier contenant les annotations
            
        Returns:
            Liste de dictionnaires avec 'name' et 'count'
        """
        levels = []
        
        if not os.path.exists(annotations_dir):
            return levels
        
        for item in sorted(os.listdir(annotations_dir)):
            item_path = os.path.join(annotations_dir, item)
            if os.path.isdir(item_path):
                # Compter les fichiers d'annotation .txt non vides
                ann_files = [f for f in os.listdir(item_path) if f.endswith('.txt')]
                ann_count = sum(1 for f in ann_files 
                               if os.path.getsize(os.path.join(item_path, f)) > 0)
                
                if ann_count > 0:
                    levels.append({
                        'name': item,
                        'count': ann_count
                    })
        
        return levels


# Pour test standalone
if __name__ == "__main__":
    # Test basique
    task = DatasetAugmentationTask()
    
    task.configure(
        annotations_dir="annotations",
        frames_dir="frames",
        output_dir="augmented_test",
        selected_levels=["1-1"],
        multiplier=2,
        augmentation_types=['horizontal_flip', 'brightness']
    )
    
    task.log_callback = print
    task.progress_callback = lambda c, t: print(f"Progress: {c}/{t}")
    
    result = task.run()
    print(f"\nRésultat: {result}")