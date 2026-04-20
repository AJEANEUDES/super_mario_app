"""
Dataset Annotator Task - Annotation manuelle des frames pour YOLO
Gestion des classes, images de référence, et export au format YOLOv8
"""

import os
import json
import shutil
import random
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable, Tuple
from datetime import datetime
import yaml
import cv2



try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


@dataclass
class ClassInfo:
    """Information sur une classe d'annotation"""
    id: int
    name: str
    shortcut: str = ""
    reference_image: str = ""
    color: Tuple[int, int, int] = (255, 255, 255)
    count: int = 0  # Nombre d'annotations de cette classe


@dataclass
class BoundingBox:
    """Bounding box pour une annotation"""
    class_id: int
    class_name: str
    x: int  # x top-left
    y: int  # y top-left
    width: int
    height: int
    
    def to_yolo(self, img_width: int, img_height: int) -> str:
        """Convertir en format YOLO (normalisé)"""
        center_x = (self.x + self.width / 2) / img_width
        center_y = (self.y + self.height / 2) / img_height
        norm_w = self.width / img_width
        norm_h = self.height / img_height
        return f"{self.class_id} {center_x:.6f} {center_y:.6f} {norm_w:.6f} {norm_h:.6f}"
    
    @classmethod
    def from_yolo(cls, line: str, img_width: int, img_height: int, class_names: List[str]) -> 'BoundingBox':
        """Créer depuis format YOLO"""
        parts = line.strip().split()
        class_id = int(parts[0])
        center_x = float(parts[1]) * img_width
        center_y = float(parts[2]) * img_height
        w = float(parts[3]) * img_width
        h = float(parts[4]) * img_height
        
        x = int(center_x - w / 2)
        y = int(center_y - h / 2)
        
        class_name = class_names[class_id] if class_id < len(class_names) else f"class_{class_id}"
        
        return cls(
            class_id=class_id,
            class_name=class_name,
            x=x,
            y=y,
            width=int(w),
            height=int(h)
        )


@dataclass
class ImageAnnotation:
    """Annotations pour une image"""
    image_path: str
    image_name: str
    width: int
    height: int
    boxes: List[BoundingBox] = field(default_factory=list)
    is_annotated: bool = False
    
    def save_yolo(self, output_dir: str):
        """Sauvegarder au format YOLO"""
        label_name = Path(self.image_name).stem + ".txt"
        label_path = os.path.join(output_dir, label_name)
        
        with open(label_path, 'w') as f:
            for box in self.boxes:
                f.write(box.to_yolo(self.width, self.height) + "\n")
    
    def load_yolo(self, labels_dir: str, class_names: List[str]):
        """Charger depuis format YOLO"""
        label_name = Path(self.image_name).stem + ".txt"
        label_path = os.path.join(labels_dir, label_name)
        
        self.boxes = []
        if os.path.exists(label_path):
            with open(label_path, 'r') as f:
                for line in f:
                    if line.strip():
                        box = BoundingBox.from_yolo(line, self.width, self.height, class_names)
                        self.boxes.append(box)
            self.is_annotated = len(self.boxes) > 0


@dataclass 
class AnnotatorConfig:
    """Configuration de l'annotateur"""
    frames_dir: str = ""
    output_dir: str = ""
    data_yaml_path: str = ""
    references_dir: str = ""  # Dossier pour les images de référence


class DatasetAnnotatorTask:
    """
    Tâche d'annotation de dataset pour YOLO
    """
    
    # Raccourcis clavier par défaut
    DEFAULT_SHORTCUTS = "1234567890qwertyuiopasdfghjklzxcvbnm"
    
    # Couleurs prédéfinies pour les classes
    COLORS = [
        (255, 0, 0), (0, 255, 0), (0, 0, 255), (255, 255, 0), (255, 0, 255),
        (0, 255, 255), (128, 0, 0), (0, 128, 0), (0, 0, 128), (128, 128, 0),
        (128, 0, 128), (0, 128, 128), (255, 128, 0), (255, 0, 128), (128, 255, 0),
        (0, 255, 128), (128, 0, 255), (0, 128, 255), (255, 128, 128), (128, 255, 128),
        (128, 128, 255), (255, 255, 128), (255, 128, 255), (128, 255, 255), (192, 192, 192),
        (64, 64, 64), (255, 64, 64), (64, 255, 64), (64, 64, 255), (255, 255, 64)
    ]
    
    def __init__(self):
        self.config: Optional[AnnotatorConfig] = None
        self.classes: List[ClassInfo] = []
        self.images: List[ImageAnnotation] = []
        self.current_index = 0
        
        # État
        self.is_modified = False
        self.project_file = ""
        self.current_yaml_path = ""  # Chemin du data.yaml courant
        
        # Presse-papier pour copier/coller les annotations
        self.clipboard: List[Dict] = []
        self.clipboard_source_size = (0, 0)
        
        # Callbacks
        self.log_callback: Optional[Callable[[str], None]] = None
    
    @staticmethod
    def check_dependencies() -> Dict[str, bool]:
        """Vérifier les dépendances"""
        return {
            "yaml": YAML_AVAILABLE,
            "cv2": CV2_AVAILABLE,
            "numpy": NUMPY_AVAILABLE
        }
    
    def _log(self, message: str):
        """Logger un message"""
        if self.log_callback:
            self.log_callback(message)
    
    def configure(self, config: AnnotatorConfig, log_callback: Optional[Callable] = None):
        """Configurer la tâche"""
        self.config = config
        self.log_callback = log_callback
        
        # Créer les dossiers nécessaires
        if config.output_dir:
            Path(config.output_dir).mkdir(parents=True, exist_ok=True)
            Path(os.path.join(config.output_dir, "labels")).mkdir(exist_ok=True)
            
        if config.references_dir:
            Path(config.references_dir).mkdir(parents=True, exist_ok=True)
    
    # ==================== GESTION DES CLASSES ====================
    
    def _get_references_config_path(self, yaml_path: str) -> str:
        """Obtenir le chemin du fichier de configuration des références"""
        yaml_dir = os.path.dirname(yaml_path)
        yaml_name = os.path.splitext(os.path.basename(yaml_path))[0]
        return os.path.join(yaml_dir, f"{yaml_name}_references.json")
    
    def save_references_config(self, yaml_path: str = None) -> bool:
        """Sauvegarder les images de référence dans un fichier JSON"""
        if yaml_path is None:
            yaml_path = self.current_yaml_path
        
        if not yaml_path:
            return False
        
        config_path = self._get_references_config_path(yaml_path)
        
        try:
            references_data = {
                "version": "1.0",
                "data_yaml": yaml_path,
                "timestamp": datetime.now().isoformat(),
                "references": {}
            }
            
            for cls in self.classes:
                if cls.reference_image:
                    references_data["references"][str(cls.id)] = {
                        "name": cls.name,
                        "image": cls.reference_image
                    }
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(references_data, f, indent=2, ensure_ascii=False)
            
            self._log(f"💾 Références sauvegardées: {config_path}")
            return True
            
        except Exception as e:
            self._log(f"⚠️ Erreur sauvegarde références: {e}")
            return False
    
    def load_references_config(self, yaml_path: str = None) -> bool:
        """Charger les images de référence depuis le fichier JSON"""
        if yaml_path is None:
            yaml_path = self.current_yaml_path
        
        if not yaml_path:
            return False
        
        config_path = self._get_references_config_path(yaml_path)
        
        if not os.path.exists(config_path):
            return False
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            references = data.get("references", {})
            loaded_count = 0
            
            for class_id_str, ref_data in references.items():
                class_id = int(class_id_str)
                if class_id < len(self.classes):
                    image_path = ref_data.get("image", "")
                    if image_path and os.path.exists(image_path):
                        self.classes[class_id].reference_image = image_path
                        loaded_count += 1
            
            if loaded_count > 0:
                self._log(f"✅ {loaded_count} images de référence restaurées")
            
            return True
            
        except Exception as e:
            self._log(f"⚠️ Erreur chargement références: {e}")
            return False
    
    def load_data_yaml(self, yaml_path: str) -> bool:
        """Charger les classes depuis data.yaml"""
        if not YAML_AVAILABLE:
            self._log("❌ PyYAML non installé")
            return False
        
        if not os.path.exists(yaml_path):
            self._log(f"❌ Fichier non trouvé: {yaml_path}")
            return False
        
        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            names = data.get('names', [])
            if not names:
                self._log("⚠️ Aucune classe trouvée dans data.yaml")
                return False
            
            self.classes = []
            for i, name in enumerate(names):
                # Nettoyer le nom (enlever préfixe "0- ", "1- ", etc.)
                clean_name = name
                if isinstance(name, str) and '-' in name:
                    parts = name.split('-', 1)
                    if parts[0].strip().isdigit():
                        clean_name = parts[1].strip()
                
                shortcut = self.DEFAULT_SHORTCUTS[i] if i < len(self.DEFAULT_SHORTCUTS) else ""
                color = self.COLORS[i % len(self.COLORS)]
                
                self.classes.append(ClassInfo(
                    id=i,
                    name=clean_name,
                    shortcut=shortcut,
                    color=color
                ))
            
            # Stocker le chemin du yaml courant
            self.current_yaml_path = yaml_path
            
            self._log(f"✅ {len(self.classes)} classes chargées depuis {yaml_path}")
            
            # Charger automatiquement les images de référence si elles existent
            self.load_references_config(yaml_path)
            
            return True
            
        except Exception as e:
            self._log(f"❌ Erreur lecture YAML: {e}")
            return False
    
    def save_data_yaml(self, yaml_path: str) -> bool:
        """Sauvegarder les classes dans data.yaml"""
        if not YAML_AVAILABLE:
            self._log("❌ PyYAML non installé")
            return False
        
        try:
            # Charger le fichier existant pour préserver les autres champs
            existing_data = {}
            if os.path.exists(yaml_path):
                with open(yaml_path, 'r', encoding='utf-8') as f:
                    existing_data = yaml.safe_load(f) or {}
            
            # Mettre à jour les noms
            names = [f"{cls.id}- {cls.name}" for cls in self.classes]
            existing_data['names'] = names
            existing_data['nc'] = len(self.classes)
            
            with open(yaml_path, 'w', encoding='utf-8') as f:
                yaml.dump(existing_data, f, default_flow_style=False, allow_unicode=True)
            
            self._log(f"✅ data.yaml sauvegardé: {yaml_path}")
            return True
            
        except Exception as e:
            self._log(f"❌ Erreur sauvegarde YAML: {e}")
            return False
    
    def add_class(self, name: str, reference_image: str = "") -> ClassInfo:
        """Ajouter une nouvelle classe"""
        new_id = len(self.classes)
        shortcut = self.DEFAULT_SHORTCUTS[new_id] if new_id < len(self.DEFAULT_SHORTCUTS) else ""
        color = self.COLORS[new_id % len(self.COLORS)]
        
        new_class = ClassInfo(
            id=new_id,
            name=name,
            shortcut=shortcut,
            reference_image=reference_image,
            color=color
        )
        self.classes.append(new_class)
        self.is_modified = True
        
        self._log(f"✅ Classe ajoutée: {name} (id={new_id})")
        return new_class
    
    def remove_class(self, class_id: int) -> bool:
        """Supprimer une classe"""
        if class_id < 0 or class_id >= len(self.classes):
            return False
        
        removed = self.classes.pop(class_id)
        
        # Réindexer les classes suivantes
        for i, cls in enumerate(self.classes):
            cls.id = i
            cls.shortcut = self.DEFAULT_SHORTCUTS[i] if i < len(self.DEFAULT_SHORTCUTS) else ""
        
        self.is_modified = True
        self._log(f"✅ Classe supprimée: {removed.name}")
        return True
    
    def update_class(self, class_id: int, name: str = None, 
                     reference_image: str = None, shortcut: str = None) -> bool:
        """Mettre à jour une classe"""
        if class_id < 0 or class_id >= len(self.classes):
            return False
        
        cls = self.classes[class_id]
        if name is not None:
            cls.name = name
        if reference_image is not None:
            cls.reference_image = reference_image
        if shortcut is not None:
            cls.shortcut = shortcut
        
        self.is_modified = True
        return True
    
    def set_reference_image(self, class_id: int, image_path: str, auto_save: bool = True) -> bool:
        """Définir l'image de référence pour une classe"""
        if class_id < 0 or class_id >= len(self.classes):
            return False
        
        if not os.path.exists(image_path):
            self._log(f"❌ Image non trouvée: {image_path}")
            return False
        
        # Copier l'image dans le dossier de références
        if self.config and self.config.references_dir:
            ext = Path(image_path).suffix
            dest_name = f"class_{class_id}_{self.classes[class_id].name}{ext}"
            dest_path = os.path.join(self.config.references_dir, dest_name)
            
            try:
                shutil.copy2(image_path, dest_path)
                self.classes[class_id].reference_image = dest_path
                self._log(f"✅ Image de référence définie pour {self.classes[class_id].name}")
                
                # Sauvegarder automatiquement les références
                if auto_save and self.current_yaml_path:
                    self.save_references_config()
                
                return True
            except Exception as e:
                self._log(f"❌ Erreur copie: {e}")
                return False
        else:
            self.classes[class_id].reference_image = image_path
            
            # Sauvegarder automatiquement les références
            if auto_save and self.current_yaml_path:
                self.save_references_config()
            
            return True
    
    def get_class_by_shortcut(self, shortcut: str) -> Optional[ClassInfo]:
        """Obtenir une classe par son raccourci"""
        for cls in self.classes:
            if cls.shortcut == shortcut.lower():
                return cls
        return None
    
    def get_class_names(self) -> List[str]:
        """Obtenir la liste des noms de classes"""
        return [cls.name for cls in self.classes]
    
    # ==================== GESTION DES IMAGES ====================
    
    def load_images(self, frames_dir: str, recursive: bool = True) -> int:
        """Charger les images à annoter"""
        if not os.path.exists(frames_dir):
            self._log(f"❌ Dossier non trouvé: {frames_dir}")
            return 0
        
        self.images = []
        extensions = {'.png', '.jpg', '.jpeg', '.bmp'}
        
        if recursive:
            for root, dirs, files in os.walk(frames_dir):
                for filename in sorted(files):
                    if Path(filename).suffix.lower() in extensions:
                        filepath = os.path.join(root, filename)
                        self._add_image(filepath)
        else:
            for filename in sorted(os.listdir(frames_dir)):
                if Path(filename).suffix.lower() in extensions:
                    filepath = os.path.join(frames_dir, filename)
                    if os.path.isfile(filepath):
                        self._add_image(filepath)
        
        self._log(f"✅ {len(self.images)} images chargées")
        return len(self.images)
    
    def _add_image(self, filepath: str):
        """Ajouter une image à la liste"""
        try:
            if CV2_AVAILABLE:
                img = cv2.imread(filepath)
                if img is not None:
                    h, w = img.shape[:2]
                    self.images.append(ImageAnnotation(
                        image_path=filepath,
                        image_name=Path(filepath).name,
                        width=w,
                        height=h
                    ))
        except:
            pass
    
    def load_existing_annotations(self, labels_dir: str):
        """Charger les annotations existantes"""
        if not os.path.exists(labels_dir):
            return
        
        class_names = self.get_class_names()
        loaded = 0
        
        for img in self.images:
            img.load_yolo(labels_dir, class_names)
            if img.is_annotated:
                loaded += 1
        
        self._log(f"✅ {loaded} annotations existantes chargées")
    
    def get_current_image(self) -> Optional[ImageAnnotation]:
        """Obtenir l'image courante"""
        if 0 <= self.current_index < len(self.images):
            return self.images[self.current_index]
        return None
    
    def navigate(self, direction: int) -> Optional[ImageAnnotation]:
        """Naviguer dans les images"""
        new_index = self.current_index + direction
        if 0 <= new_index < len(self.images):
            self.current_index = new_index
            return self.get_current_image()
        return None
    
    def goto_image(self, index: int) -> Optional[ImageAnnotation]:
        """Aller à une image spécifique"""
        if 0 <= index < len(self.images):
            self.current_index = index
            return self.get_current_image()
        return None
    
    # ==================== ANNOTATIONS ====================
    
    def add_annotation(self, class_id: int, x: int, y: int, width: int, height: int) -> bool:
        """Ajouter une annotation à l'image courante"""
        img = self.get_current_image()
        if not img or class_id < 0 or class_id >= len(self.classes):
            return False
        
        box = BoundingBox(
            class_id=class_id,
            class_name=self.classes[class_id].name,
            x=x,
            y=y,
            width=width,
            height=height
        )
        img.boxes.append(box)
        img.is_annotated = True
        self.classes[class_id].count += 1
        self.is_modified = True
        
        return True
    
    def remove_annotation(self, box_index: int) -> bool:
        """Supprimer une annotation de l'image courante"""
        img = self.get_current_image()
        if not img or box_index < 0 or box_index >= len(img.boxes):
            return False
        
        removed = img.boxes.pop(box_index)
        if removed.class_id < len(self.classes):
            self.classes[removed.class_id].count = max(0, self.classes[removed.class_id].count - 1)
        
        self.is_modified = True
        return True
    
    def clear_annotations(self) -> bool:
        """Effacer toutes les annotations de l'image courante"""
        img = self.get_current_image()
        if not img:
            return False
        
        for box in img.boxes:
            if box.class_id < len(self.classes):
                self.classes[box.class_id].count = max(0, self.classes[box.class_id].count - 1)
        
        img.boxes.clear()
        img.is_annotated = False
        self.is_modified = True
        return True
    
    # ==================== COPIER/COLLER ANNOTATIONS ====================
    
    def copy_annotations(self, source_index: int = None) -> int:
        """
        Copier les annotations d'un frame vers le presse-papier
        
        Args:
            source_index: Index du frame source (None = frame courant)
            
        Returns:
            Nombre d'annotations copiées
        """
        if source_index is None:
            source_index = self.current_index
        
        if source_index < 0 or source_index >= len(self.images):
            return 0
        
        img = self.images[source_index]
        
        # Copier les annotations en format normalisé
        self.clipboard = []
        for box in img.boxes:
            self.clipboard.append({
                'class_id': box.class_id,
                'class_name': box.class_name,
                'x_norm': box.x / img.width if img.width > 0 else 0,
                'y_norm': box.y / img.height if img.height > 0 else 0,
                'w_norm': box.width / img.width if img.width > 0 else 0,
                'h_norm': box.height / img.height if img.height > 0 else 0
            })
        
        self.clipboard_source_size = (img.width, img.height)
        self._log(f"📋 {len(self.clipboard)} annotations copiées depuis frame {source_index + 1}")
        return len(self.clipboard)
    
    def paste_annotations(self, replace: bool = False) -> int:
        """
        Coller les annotations du presse-papier sur le frame courant
        
        Args:
            replace: Si True, effacer les annotations existantes avant de coller
            
        Returns:
            Nombre d'annotations collées
        """
        if not self.clipboard:
            self._log("⚠️ Presse-papier vide")
            return 0
        
        img = self.get_current_image()
        if not img:
            return 0
        
        if replace:
            self.clear_annotations()
        
        count = 0
        for ann in self.clipboard:
            if ann['class_id'] >= len(self.classes):
                continue
            
            x = int(ann['x_norm'] * img.width)
            y = int(ann['y_norm'] * img.height)
            w = int(ann['w_norm'] * img.width)
            h = int(ann['h_norm'] * img.height)
            
            x = max(0, min(x, img.width - 1))
            y = max(0, min(y, img.height - 1))
            w = min(w, img.width - x)
            h = min(h, img.height - y)
            
            if w > 0 and h > 0:
                self.add_annotation(ann['class_id'], x, y, w, h)
                count += 1
        
        self._log(f"📋 {count} annotations collées")
        return count
    
    def copy_from_previous(self) -> int:
        """Copier les annotations du frame précédent et les coller sur le frame courant"""
        if self.current_index <= 0:
            self._log("⚠️ Pas de frame précédent")
            return 0
        
        self.copy_annotations(self.current_index - 1)
        return self.paste_annotations(replace=False)
    
    def propagate_annotations(self, count: int, replace: bool = False, 
                              save_each: bool = True) -> Dict[str, Any]:
        """
        Propager les annotations du frame courant aux N frames suivants
        
        Args:
            count: Nombre de frames à propager
            replace: Si True, remplacer les annotations existantes
            save_each: Si True, sauvegarder chaque frame après propagation
            
        Returns:
            Dictionnaire avec les résultats
        """
        result = {'propagated': 0, 'skipped': 0, 'errors': 0, 'frames': []}
        
        copied = self.copy_annotations()
        if copied == 0:
            self._log("⚠️ Aucune annotation à propager")
            return result
        
        start_index = self.current_index
        
        for i in range(1, count + 1):
            target_index = start_index + i
            
            if target_index >= len(self.images):
                break
            
            self.current_index = target_index
            img = self.get_current_image()
            
            if not img:
                result['errors'] += 1
                continue
            
            if not replace and img.boxes:
                result['skipped'] += 1
                result['frames'].append({'index': target_index, 'status': 'skipped'})
                continue
            
            pasted = self.paste_annotations(replace=replace)
            
            if pasted > 0:
                result['propagated'] += 1
                result['frames'].append({'index': target_index, 'status': 'propagated', 'count': pasted})
                
                if save_each:
                    self.save_current_annotations()
            else:
                result['errors'] += 1
        
        self.current_index = start_index
        self._log(f"🔄 Propagation: {result['propagated']} annotés, {result['skipped']} ignorés")
        return result
    
    def get_clipboard_info(self) -> Dict[str, Any]:
        """Obtenir les informations sur le presse-papier"""
        if not self.clipboard:
            return {'count': 0, 'classes': {}, 'source_size': None}
        
        class_counts = {}
        for ann in self.clipboard:
            name = ann['class_name']
            class_counts[name] = class_counts.get(name, 0) + 1
        
        return {
            'count': len(self.clipboard),
            'classes': class_counts,
            'source_size': self.clipboard_source_size
        }
    
    def save_current_annotations(self) -> bool:
        """Sauvegarder les annotations de l'image courante"""
        img = self.get_current_image()
        if not img or not self.config or not self.config.output_dir:
            return False
        
        labels_dir = os.path.join(self.config.output_dir, "labels")
        Path(labels_dir).mkdir(parents=True, exist_ok=True)
        
        img.save_yolo(labels_dir)
        return True
    
    # ==================== EXPORT DATASET ====================
    
    def export_yolo_dataset(self, output_dir: str, 
                           split_ratio: Tuple[float, float, float] = (0.7, 0.2, 0.1),
                           copy_images: bool = True) -> Dict[str, Any]:
        """Exporter le dataset au format YOLOv8"""
        result = {
            "success": False,
            "train": 0,
            "val": 0,
            "test": 0,
            "total": 0,
            "output_dir": output_dir
        }
        
        # Créer la structure
        for split in ['train', 'val', 'test']:
            Path(os.path.join(output_dir, split, 'images')).mkdir(parents=True, exist_ok=True)
            Path(os.path.join(output_dir, split, 'labels')).mkdir(parents=True, exist_ok=True)
        
        # Filtrer les images annotées
        annotated = [img for img in self.images if img.is_annotated and len(img.boxes) > 0]
        
        if not annotated:
            self._log("❌ Aucune image annotée à exporter")
            return result
        
        # Mélanger et diviser
        random.shuffle(annotated)
        n_total = len(annotated)
        n_train = int(n_total * split_ratio[0])
        n_val = int(n_total * split_ratio[1])
        
        splits = {
            'train': annotated[:n_train],
            'val': annotated[n_train:n_train + n_val],
            'test': annotated[n_train + n_val:]
        }
        
        # Exporter
        for split_name, split_images in splits.items():
            for img in split_images:
                # Nom unique
                unique_name = f"{Path(img.image_path).parent.name}_{img.image_name}"
                
                # Copier/lier l'image
                if copy_images:
                    dst_img = os.path.join(output_dir, split_name, 'images', unique_name)
                    shutil.copy2(img.image_path, dst_img)
                
                # Créer le label
                label_name = Path(unique_name).stem + ".txt"
                label_path = os.path.join(output_dir, split_name, 'labels', label_name)
                
                with open(label_path, 'w') as f:
                    for box in img.boxes:
                        f.write(box.to_yolo(img.width, img.height) + "\n")
        
        # Créer data.yaml
        yaml_content = {
            'path': output_dir,
            'train': 'train/images',
            'val': 'val/images',
            'test': 'test/images',
            'nc': len(self.classes),
            'names': self.get_class_names()
        }
        
        yaml_path = os.path.join(output_dir, 'data.yaml')
        with open(yaml_path, 'w', encoding='utf-8') as f:
            if YAML_AVAILABLE:
                yaml.dump(yaml_content, f, default_flow_style=False, allow_unicode=True)
            else:
                # Fallback sans PyYAML
                f.write(f"path: {output_dir}\n")
                f.write("train: train/images\n")
                f.write("val: val/images\n")
                f.write("test: test/images\n")
                f.write(f"nc: {len(self.classes)}\n")
                f.write(f"names: {self.get_class_names()}\n")
        
        result["success"] = True
        result["train"] = len(splits['train'])
        result["val"] = len(splits['val'])
        result["test"] = len(splits['test'])
        result["total"] = n_total
        
        self._log(f"✅ Dataset exporté: {n_total} images")
        self._log(f"   Train: {result['train']}, Val: {result['val']}, Test: {result['test']}")
        
        return result
    
    # ==================== PROJET ====================
    
    def save_project(self, project_path: str) -> bool:
        """Sauvegarder le projet complet"""
        try:
            project_data = {
                "version": "1.0",
                "timestamp": datetime.now().isoformat(),
                "config": {
                    "frames_dir": self.config.frames_dir if self.config else "",
                    "output_dir": self.config.output_dir if self.config else "",
                    "references_dir": self.config.references_dir if self.config else ""
                },
                "classes": [
                    {
                        "id": cls.id,
                        "name": cls.name,
                        "shortcut": cls.shortcut,
                        "reference_image": cls.reference_image,
                        "color": cls.color,
                        "count": cls.count
                    }
                    for cls in self.classes
                ],
                "current_index": self.current_index,
                "annotations": [
                    {
                        "image_path": img.image_path,
                        "boxes": [
                            {
                                "class_id": box.class_id,
                                "x": box.x,
                                "y": box.y,
                                "width": box.width,
                                "height": box.height
                            }
                            for box in img.boxes
                        ]
                    }
                    for img in self.images if img.is_annotated
                ]
            }
            
            with open(project_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)
            
            self.project_file = project_path
            self.is_modified = False
            self._log(f"✅ Projet sauvegardé: {project_path}")
            return True
            
        except Exception as e:
            self._log(f"❌ Erreur sauvegarde projet: {e}")
            return False
    
    def load_project(self, project_path: str) -> bool:
        """Charger un projet"""
        try:
            with open(project_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Charger la config
            config_data = data.get("config", {})
            self.config = AnnotatorConfig(
                frames_dir=config_data.get("frames_dir", ""),
                output_dir=config_data.get("output_dir", ""),
                references_dir=config_data.get("references_dir", "")
            )
            
            # Charger les classes
            self.classes = []
            for cls_data in data.get("classes", []):
                self.classes.append(ClassInfo(
                    id=cls_data["id"],
                    name=cls_data["name"],
                    shortcut=cls_data.get("shortcut", ""),
                    reference_image=cls_data.get("reference_image", ""),
                    color=tuple(cls_data.get("color", (255, 255, 255))),
                    count=cls_data.get("count", 0)
                ))
            
            # Charger les images
            if self.config.frames_dir:
                self.load_images(self.config.frames_dir)
            
            # Restaurer les annotations
            annotations_map = {
                ann["image_path"]: ann["boxes"]
                for ann in data.get("annotations", [])
            }
            
            for img in self.images:
                if img.image_path in annotations_map:
                    for box_data in annotations_map[img.image_path]:
                        class_id = box_data["class_id"]
                        class_name = self.classes[class_id].name if class_id < len(self.classes) else ""
                        img.boxes.append(BoundingBox(
                            class_id=class_id,
                            class_name=class_name,
                            x=box_data["x"],
                            y=box_data["y"],
                            width=box_data["width"],
                            height=box_data["height"]
                        ))
                    img.is_annotated = len(img.boxes) > 0
            
            self.current_index = data.get("current_index", 0)
            self.project_file = project_path
            self.is_modified = False
            
            self._log(f"✅ Projet chargé: {project_path}")
            return True
            
        except Exception as e:
            self._log(f"❌ Erreur chargement projet: {e}")
            return False
    
    # ==================== STATISTIQUES ====================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Obtenir les statistiques du dataset"""
        total_images = len(self.images)
        annotated_images = sum(1 for img in self.images if img.is_annotated)
        total_boxes = sum(len(img.boxes) for img in self.images)
        
        class_distribution = {}
        for cls in self.classes:
            count = sum(
                1 for img in self.images 
                for box in img.boxes 
                if box.class_id == cls.id
            )
            class_distribution[cls.name] = count
        
        return {
            "total_images": total_images,
            "annotated_images": annotated_images,
            "unannotated_images": total_images - annotated_images,
            "progress_percent": (annotated_images / total_images * 100) if total_images > 0 else 0,
            "total_boxes": total_boxes,
            "avg_boxes_per_image": total_boxes / annotated_images if annotated_images > 0 else 0,
            "class_distribution": class_distribution,
            "num_classes": len(self.classes)
        }