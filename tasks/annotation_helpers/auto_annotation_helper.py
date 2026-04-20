"""
Auto Annotation Helper - Pré-annotation automatique avec YOLO

Utilise un modèle YOLO existant (même imparfait) pour pré-annoter
les frames. L'utilisateur n'a plus qu'à corriger les erreurs.
"""

import os
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from ultralytics import YOLO

from .base_helper import BaseAnnotationHelper, HelperInfo, HelperResult, HelperStatus

# Import optionnel de YOLO
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


@dataclass
class AutoAnnotationConfig:
    """Configuration de la pré-annotation"""
    model_path: str = ""
    confidence: float = 0.25
    iou_threshold: float = 0.45
    max_detections: int = 100
    classes_filter: List[int] = None  # None = toutes les classes
    overwrite_existing: bool = False
    save_after_each: bool = True


class AutoAnnotationHelper(BaseAnnotationHelper):
    """
    Helper de pré-annotation automatique avec YOLO.
    
    Utilise un modèle YOLO pré-entraîné pour détecter automatiquement
    les objets dans les frames. L'utilisateur peut ensuite corriger
    les détections au lieu de tout dessiner manuellement.
    """
    
    def __init__(self):
        super().__init__()
        self.task = None
        self.config = AutoAnnotationConfig()
        self.model = None
        self.class_mapping: Dict[int, int] = {}  # YOLO class -> Task class
    
    @staticmethod
    def get_info() -> HelperInfo:
        requirements = []
        if not YOLO_AVAILABLE:
            requirements.append("ultralytics (pip install ultralytics)")
        
        return HelperInfo(
            id="auto_annotation",
            name="Pré-annotation YOLO",
            icon="🤖",
            short_description="Détecter automatiquement les objets",
            long_description="""
La pré-annotation automatique utilise un modèle YOLO existant pour 
détecter les objets dans vos frames. Vous n'avez plus qu'à corriger 
les erreurs au lieu de tout dessiner manuellement.

**Comment ça marche:**
1. Chargez un modèle YOLO (.pt)
2. Configurez le mapping des classes
3. Lancez la détection automatique
4. Corrigez les erreurs manuellement

**Types de modèles utilisables:**
- Modèle pré-entraîné (yolov8n.pt, yolov8s.pt, etc.)
- Votre propre modèle entraîné sur des données similaires
- Un modèle partiellement entraîné (même imparfait)

**Conseil:** Un modèle avec 50% de précision est déjà utile!
Corriger des erreurs est plus rapide que tout annoter.
            """.strip(),
            requirements=requirements,
            estimated_speedup="5-10x plus rapide",
            best_for=[
                "Quand vous avez un modèle YOLO existant",
                "Objets communs (personnes, véhicules, etc.)",
                "Itérations sur un dataset existant"
            ],
            limitations=[
                "Nécessite un modèle YOLO",
                "Qualité dépend du modèle",
                "Peut nécessiter un mapping de classes"
            ]
        )
    
    @staticmethod
    def is_available() -> bool:
        """Vérifier si YOLO est disponible"""
        return YOLO_AVAILABLE
    
    def configure(self, task, **kwargs) -> bool:
        """Configurer le helper"""
        self.task = task
        
        # Configuration
        self.config.model_path = kwargs.get('model_path', '')
        self.config.confidence = kwargs.get('confidence', 0.25)
        self.config.iou_threshold = kwargs.get('iou_threshold', 0.45)
        self.config.max_detections = kwargs.get('max_detections', 100)
        self.config.classes_filter = kwargs.get('classes_filter', None)
        self.config.overwrite_existing = kwargs.get('overwrite_existing', False)
        self.config.save_after_each = kwargs.get('save_after_each', True)
        
        # Mapping des classes
        self.class_mapping = kwargs.get('class_mapping', {})
        
        return True
    
    def load_model(self, model_path: str = None) -> bool:
        """Charger le modèle YOLO"""
        if not YOLO_AVAILABLE:
            self._log("❌ ultralytics non installé")
            return False
        
        path = model_path or self.config.model_path
        if not path:
            self._log("❌ Chemin du modèle non spécifié")
            return False
        
        try:
            self._log(f"📥 Chargement du modèle: {path}")
            self.model = YOLO(path)
            self._log(f"✅ Modèle chargé: {len(self.model.names)} classes")
            return True
            
        except Exception as e:
            self._log(f"❌ Erreur chargement modèle: {e}")
            return False
    
    def get_model_classes(self) -> Dict[int, str]:
        """Retourne les classes du modèle"""
        if self.model:
            return self.model.names
        return {}
    
    def set_class_mapping(self, mapping: Dict[int, int]):
        """
        Définir le mapping entre les classes YOLO et les classes du task
        
        Args:
            mapping: Dict[yolo_class_id, task_class_id]
        """
        self.class_mapping = mapping
    
    def auto_map_classes(self) -> Dict[int, int]:
        """
        Tente de mapper automatiquement les classes par nom
        
        Returns:
            Dict[yolo_class_id, task_class_id]
        """
        if not self.model or not self.task:
            return {}
        
        mapping = {}
        model_classes = self.model.names
        task_classes = {cls.name.lower(): cls.id for cls in self.task.classes}
        
        for yolo_id, yolo_name in model_classes.items():
            yolo_name_lower = yolo_name.lower()
            
            # Recherche exacte
            if yolo_name_lower in task_classes:
                mapping[yolo_id] = task_classes[yolo_name_lower]
                self._log(f"✅ Mapping: {yolo_name} -> {yolo_name_lower}")
            else:
                # Recherche partielle
                for task_name, task_id in task_classes.items():
                    if yolo_name_lower in task_name or task_name in yolo_name_lower:
                        mapping[yolo_id] = task_id
                        self._log(f"✅ Mapping partiel: {yolo_name} -> {task_name}")
                        break
        
        self.class_mapping = mapping
        return mapping
    
    def execute(self) -> HelperResult:
        """Exécuter la pré-annotation"""
        if not YOLO_AVAILABLE:
            return HelperResult(
                success=False,
                message="ultralytics non installé (pip install ultralytics)"
            )
        
        if not self.task or not self.task.images:
            return HelperResult(
                success=False,
                message="Aucune image chargée"
            )
        
        if not self.model:
            if not self.load_model():
                return HelperResult(
                    success=False,
                    message="Impossible de charger le modèle"
                )
        
        self.status = HelperStatus.RUNNING
        processed = 0
        skipped = 0
        errors = 0
        total_detections = 0
        
        total = len(self.task.images)
        
        for i, img in enumerate(self.task.images):
            if self._check_cancelled():
                self.status = HelperStatus.CANCELLED
                break
            
            self._update_progress(i / total, f"Frame {i+1}/{total}")
            
            # Vérifier si on doit passer cette image
            if not self.config.overwrite_existing and img.boxes:
                skipped += 1
                continue
            
            try:
                # Effectuer la détection
                results = self.model.predict(
                    img.image_path,
                    conf=self.config.confidence,
                    iou=self.config.iou_threshold,
                    max_det=self.config.max_detections,
                    verbose=False
                )
                
                if results and len(results) > 0:
                    result = results[0]
                    
                    # Effacer les annotations existantes si demandé
                    if self.config.overwrite_existing:
                        self.task.current_index = i
                        self.task.clear_annotations()
                    
                    # Ajouter les détections
                    boxes = result.boxes
                    if boxes is not None:
                        for box in boxes:
                            yolo_class = int(box.cls[0])
                            
                            # Appliquer le mapping
                            if self.class_mapping:
                                if yolo_class not in self.class_mapping:
                                    continue
                                task_class = self.class_mapping[yolo_class]
                            else:
                                task_class = yolo_class
                            
                            # Vérifier que la classe existe dans le task
                            if task_class >= len(self.task.classes):
                                continue
                            
                            # Extraire les coordonnées
                            x1, y1, x2, y2 = box.xyxy[0].tolist()
                            x, y = int(x1), int(y1)
                            w, h = int(x2 - x1), int(y2 - y1)
                            
                            # Ajouter l'annotation
                            self.task.current_index = i
                            self.task.add_annotation(task_class, x, y, w, h)
                            total_detections += 1
                    
                    # Sauvegarder si demandé
                    if self.config.save_after_each:
                        self.task.current_index = i
                        self.task.save_current_annotations()
                
                processed += 1
                
            except Exception as e:
                self._log(f"⚠️ Erreur frame {i}: {e}")
                errors += 1
        
        self.status = HelperStatus.COMPLETED if not self._check_cancelled() else HelperStatus.CANCELLED
        
        return HelperResult(
            success=errors == 0,
            message=f"Pré-annotation terminée: {total_detections} détections",
            processed=processed,
            skipped=skipped,
            errors=errors,
            details={
                'total_detections': total_detections,
                'avg_per_frame': total_detections / max(processed, 1)
            }
        )
    
    def detect_single(self, image_path: str) -> List[Dict]:
        """
        Détecter les objets dans une seule image
        
        Returns:
            Liste de dicts avec class_id, x, y, width, height, confidence
        """
        if not self.model:
            return []
        
        try:
            results = self.model.predict(
                image_path,
                conf=self.config.confidence,
                iou=self.config.iou_threshold,
                verbose=False
            )
            
            detections = []
            if results and len(results) > 0:
                boxes = results[0].boxes
                if boxes is not None:
                    for box in boxes:
                        yolo_class = int(box.cls[0])
                        
                        # Appliquer le mapping
                        if self.class_mapping and yolo_class in self.class_mapping:
                            task_class = self.class_mapping[yolo_class]
                        else:
                            task_class = yolo_class
                        
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        
                        detections.append({
                            'class_id': task_class,
                            'x': int(x1),
                            'y': int(y1),
                            'width': int(x2 - x1),
                            'height': int(y2 - y1),
                            'confidence': float(box.conf[0])
                        })
            
            return detections
            
        except Exception as e:
            self._log(f"⚠️ Erreur détection: {e}")
            return []