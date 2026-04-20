"""
Level Splitter Task - Classification automatique des images par niveau Mario
Utilise un modèle YOLO entraîné pour classer les images dans des dossiers par niveau
"""

import os
import shutil
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List
from collections import defaultdict
from datetime import datetime
import sys
import logging
import traceback
import threading
from ultralytics import YOLO

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class SplitterConfig:
    """Configuration du Level Splitter"""
    model_path: str = ""
    source_dir: str = ""
    output_dir: str = "classified_levels"
    confidence_threshold: float = 0.5
    save_unknown: bool = True
    copy_files: bool = True  # True = copier, False = déplacer


@dataclass
class ClassificationResult:
    """Résultat d'une classification d'image"""
    filename: str
    filepath: str
    predicted_level: Optional[str]
    confidence: float
    status: str  # 'classified', 'low_confidence', 'no_detection', 'error'
    destination: str = ""


@dataclass 
class SplitterResult:
    """Résultat global de la classification"""
    success: bool = False
    total_images: int = 0
    classified_images: int = 0
    classification_rate: float = 0.0
    levels_detected: int = 0
    level_distribution: Dict[str, int] = field(default_factory=dict)
    low_confidence_count: int = 0
    no_detection_count: int = 0
    error_count: int = 0
    output_dir: str = ""
    report_path: str = ""
    error_message: str = ""


class LevelSplitterTask:
    """
    Tâche de classification automatique des images par niveau Mario
    Utilise un modèle YOLO pour détecter le niveau et organiser les images
    """
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    
    def __init__(self):
        self.config: Optional[SplitterConfig] = None
        self.model: Optional[Any] = None
        self.level_names: Dict[int, str] = {}
        
        # Statistiques
        self.detection_stats: Dict[str, int] = defaultdict(int)
        self.confidence_stats: Dict[str, List[float]] = defaultdict(list)
        
        # État
        self.is_running = False
        self.should_stop = False
        self.is_paused = False
        self.current_progress = 0
        self.total_files = 0
        
        # État de reprise (pour pause/resume)
        self.resume_state = None  # {'index': int, 'image_files': list, 'classifications': list}
        
        # Callbacks
        self.log_callback: Optional[Callable[[str], None]] = None
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
        self.status_callback: Optional[Callable[[str], None]] = None
    
    @staticmethod
    def check_dependencies() -> Dict[str, bool]:
        """Vérifier les dépendances"""
        return {
            "ultralytics": YOLO_AVAILABLE,
            "cv2": CV2_AVAILABLE
        }
    
    @staticmethod
    def find_yolo_models(base_dir: str = "runs/train") -> List[Dict[str, Any]]:
        """Trouver les modèles YOLO disponibles"""
        models = []
        
        if not os.path.exists(base_dir):
            return models
        
        # Chercher dans runs/train/*/weights/
        for folder in os.listdir(base_dir):
            folder_path = os.path.join(base_dir, folder)
            if os.path.isdir(folder_path):
                weights_dir = os.path.join(folder_path, "weights")
                if os.path.exists(weights_dir):
                    for weight_file in ['best.pt', 'last.pt']:
                        weight_path = os.path.join(weights_dir, weight_file)
                        if os.path.exists(weight_path):
                            models.append({
                                "name": f"{folder}/{weight_file}",
                                "path": weight_path,
                                "folder": folder,
                                "type": weight_file.replace('.pt', ''),
                                "date": datetime.fromtimestamp(
                                    os.path.getmtime(weight_path)
                                ).strftime("%Y-%m-%d %H:%M")
                            })
        
        # Trier par date (plus récent en premier)
        models.sort(key=lambda x: x["date"], reverse=True)
        return models
    
    def _log(self, message: str):
        """Logger un message"""
        if self.log_callback:
            self.log_callback(message)
    
    def _update_progress(self, current: int, total: int, filename: str = ""):
        """Mettre à jour la progression"""
        self.current_progress = current
        self.total_files = total
        if self.progress_callback:
            self.progress_callback(current, total, filename)
    
    def _update_status(self, status: str):
        """Mettre à jour le statut"""
        if self.status_callback:
            self.status_callback(status)
    
    def configure(self, config: SplitterConfig,
                  log_callback: Optional[Callable] = None,
                  progress_callback: Optional[Callable] = None,
                  status_callback: Optional[Callable] = None):
        """Configurer la tâche"""
        self.config = config
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.status_callback = status_callback
    
    def validate_config(self) -> tuple:
        """Valider la configuration"""
        if not self.config:
            return False, "Configuration manquante"
        
        if not self.config.model_path:
            return False, "Modèle YOLO non spécifié"
        
        if not os.path.exists(self.config.model_path):
            return False, f"Modèle non trouvé: {self.config.model_path}"
        
        if not self.config.source_dir:
            return False, "Dossier source non spécifié"
        
        if not os.path.exists(self.config.source_dir):
            return False, f"Dossier source non trouvé: {self.config.source_dir}"
        
        if not YOLO_AVAILABLE:
            return False, "ultralytics non installé. Installez avec: pip install ultralytics"
        
        return True, "Configuration valide"
    
    def load_model(self) -> bool:
        """Charger le modèle YOLO"""
        try:
            self._log(f"🤖 Chargement du modèle: {self.config.model_path}")
            self._update_status("Chargement du modèle...")
            
            self.model = YOLO(self.config.model_path)
            self.level_names = self.model.names
            
            self._log(f"✅ Modèle chargé avec {len(self.level_names)} classes")
            self._log(f"📋 Classes: {', '.join(str(n) for n in self.level_names.values())}")
            
            return True
        except Exception as e:
            self._log(f"❌ Erreur chargement modèle: {e}")
            return False
    
    def get_image_files(self) -> List[str]:
        """Récupérer tous les fichiers images du dossier source"""
        image_files = []
        
        for filename in os.listdir(self.config.source_dir):
            ext = os.path.splitext(filename)[1].lower()
            if ext in self.IMAGE_EXTENSIONS:
                full_path = os.path.join(self.config.source_dir, filename)
                if os.path.isfile(full_path):
                    image_files.append(full_path)
        
        return sorted(image_files)
    
    def classify_image(self, img_path: str) -> ClassificationResult:
        """Classifier une seule image"""
        filename = Path(img_path).name
        
        try:
            # Prédiction YOLO
            results = self.model.predict(img_path, verbose=False)
            
            if len(results) > 0 and len(results[0].boxes) > 0:
                boxes = results[0].boxes
                best_idx = boxes.conf.argmax()
                
                confidence = float(boxes.conf[best_idx])
                class_id = int(boxes.cls[best_idx])
                level_name = str(self.level_names[class_id])
                
                if confidence >= self.config.confidence_threshold:
                    return ClassificationResult(
                        filename=filename,
                        filepath=img_path,
                        predicted_level=level_name,
                        confidence=confidence,
                        status='classified'
                    )
                else:
                    return ClassificationResult(
                        filename=filename,
                        filepath=img_path,
                        predicted_level=level_name,
                        confidence=confidence,
                        status='low_confidence'
                    )
            else:
                return ClassificationResult(
                    filename=filename,
                    filepath=img_path,
                    predicted_level=None,
                    confidence=0.0,
                    status='no_detection'
                )
                
        except Exception as e:
            self._log(f"⚠️ Erreur avec {filename}: {e}")
            return ClassificationResult(
                filename=filename,
                filepath=img_path,
                predicted_level=None,
                confidence=0.0,
                status='error'
            )
    
    def preview_classification(self, sample_size: int = 10) -> List[ClassificationResult]:
        """Tester la classification sur un échantillon"""
        valid, message = self.validate_config()
        if not valid:
            self._log(f"❌ {message}")
            return []
        
        if not self.model:
            if not self.load_model():
                return []
        
        image_files = self.get_image_files()
        sample_files = image_files[:sample_size]
        
        self._log(f"\n🔍 Test sur {len(sample_files)} images échantillon...")
        self._log(f"🎯 Seuil de confiance: {self.config.confidence_threshold}")
        self._log("-" * 50)
        
        results = []
        for i, img_path in enumerate(sample_files):
            result = self.classify_image(img_path)
            results.append(result)
            
            if result.status == 'classified':
                self._log(f"✅ {result.filename}: {result.predicted_level} ({result.confidence:.3f})")
            elif result.status == 'low_confidence':
                self._log(f"⚠️ {result.filename}: {result.predicted_level} ({result.confidence:.3f}) - confiance faible")
            elif result.status == 'no_detection':
                self._log(f"❌ {result.filename}: Aucune détection")
            else:
                self._log(f"💥 {result.filename}: Erreur")
            
            self._update_progress(i + 1, len(sample_files), result.filename)
        
        # Résumé
        classified = sum(1 for r in results if r.status == 'classified')
        self._log("-" * 50)
        self._log(f"📊 Résumé: {classified}/{len(results)} images classifiées avec succès")
        
        return results
    
    def execute(self, resume_from_state: bool = False) -> SplitterResult:
        """Exécuter la classification complète"""
        result = SplitterResult()
        self.is_running = True
        self.should_stop = False
        self.is_paused = False
        
        # Si reprise, récupérer l'état précédent
        start_index = 0
        image_files = []
        previous_classifications = []
        
        if resume_from_state and self.resume_state:
            start_index = self.resume_state.get('index', 0)
            image_files = self.resume_state.get('image_files', [])
            previous_classifications = self.resume_state.get('classifications', [])
            
            # Restaurer les statistiques
            for c in previous_classifications:
                self._update_stats(c)
            
            self._log(f"\n▶️ REPRISE DE LA CLASSIFICATION")
            self._log(f"📍 Reprise à l'image {start_index + 1}/{len(image_files)}")
        else:
            # Réinitialiser les statistiques
            self.detection_stats = defaultdict(int)
            self.confidence_stats = defaultdict(list)
            self.resume_state = None
        
        try:
            # Validation
            valid, message = self.validate_config()
            if not valid:
                result.error_message = message
                self._log(f"❌ {message}")
                return result
            
            # Charger le modèle
            if not self.model:
                if not self.load_model():
                    result.error_message = "Échec du chargement du modèle"
                    return result
            
            # Scanner les images (seulement si pas en reprise)
            if not image_files:
                image_files = self.get_image_files()
            
            result.total_images = len(image_files)
            
            if result.total_images == 0:
                result.error_message = "Aucune image trouvée dans le dossier source"
                self._log(f"❌ {result.error_message}")
                return result
            
            if not resume_from_state:
                self._log(f"\n🎮 CLASSIFICATION DES IMAGES PAR NIVEAU")
                self._log("=" * 50)
                self._log(f"📁 Source: {self.config.source_dir}")
                self._log(f"📁 Destination: {self.config.output_dir}")
                self._log(f"📊 Images à traiter: {result.total_images:,}")
                self._log(f"🎯 Seuil de confiance: {self.config.confidence_threshold}")
                self._log("=" * 50)
                
                # Créer la structure de dossiers
                self._create_output_structure()
            
            self._update_status("Classification en cours...")
            
            # Classifier chaque image
            classifications = list(previous_classifications)  # Copier les précédentes
            
            for i in range(start_index, len(image_files)):
                if self.should_stop:
                    if self.is_paused:
                        # Sauvegarder l'état pour reprise
                        self.resume_state = {
                            'index': i,
                            'image_files': image_files,
                            'classifications': classifications
                        }
                        self._log(f"\n⏸️ Classification mise en pause à l'image {i + 1}/{len(image_files)}")
                        self._log(f"💾 État sauvegardé - {len(classifications)} images déjà traitées")
                    else:
                        self._log("\n⏹️ Classification arrêtée par l'utilisateur")
                    break
                
                img_path = image_files[i]
                
                # Classifier
                classification = self.classify_image(img_path)
                
                # Copier/déplacer le fichier
                self._process_classified_image(classification)
                
                # Mettre à jour les statistiques
                self._update_stats(classification)
                
                classifications.append(classification)
                
                # Progression
                self._update_progress(i + 1, result.total_images, classification.filename)
                
                # Log périodique
                if (i + 1) % 500 == 0:
                    self._log(f"📈 Progression: {i + 1:,}/{result.total_images:,} images traitées")
            
            # Calculer les résultats
            result.classified_images = sum(1 for c in classifications if c.status == 'classified')
            result.low_confidence_count = self.detection_stats.get('low_confidence', 0)
            result.no_detection_count = self.detection_stats.get('no_detection', 0)
            result.error_count = self.detection_stats.get('error', 0)
            
            result.classification_rate = round(
                result.classified_images / result.total_images * 100, 2
            ) if result.total_images > 0 else 0
            
            # Distribution par niveau
            result.level_distribution = {
                level: count for level, count in self.detection_stats.items()
                if level not in ['low_confidence', 'no_detection', 'error']
            }
            result.levels_detected = len(result.level_distribution)
            
            result.output_dir = self.config.output_dir
            
            # Générer le rapport seulement si terminé complètement
            if not self.is_paused and not self.should_stop:
                report_path = self._generate_report(result, classifications)
                result.report_path = report_path
                result.success = True
                self._log(f"\n🎉 Classification terminée avec succès!")
                self._update_status("Terminé!")
            elif self.is_paused:
                result.success = True  # Pause réussie
                self._update_status("En pause")
            
        except Exception as e:
            result.error_message = str(e)
            self._log(f"\n❌ Erreur: {e}")
            self._update_status("Erreur!")
        
        finally:
            self.is_running = False
        
        return result
    
    def pause(self):
        """Mettre en pause la classification"""
        self.is_paused = True
        self.should_stop = True
        self._log("⏸️ Pause demandée...")
    
    def resume(self) -> bool:
        """Vérifier si une reprise est possible"""
        return self.resume_state is not None and len(self.resume_state.get('image_files', [])) > 0
    
    def get_resume_info(self) -> dict:
        """Obtenir les informations de reprise"""
        if not self.resume_state:
            return {}
        
        return {
            'current_index': self.resume_state.get('index', 0),
            'total_images': len(self.resume_state.get('image_files', [])),
            'processed': len(self.resume_state.get('classifications', [])),
            'remaining': len(self.resume_state.get('image_files', [])) - self.resume_state.get('index', 0)
        }
    
    def clear_resume_state(self):
        """Effacer l'état de reprise"""
        self.resume_state = None
        self.detection_stats = defaultdict(int)
        self.confidence_stats = defaultdict(list)
    
    def _create_output_structure(self):
        """Créer la structure de dossiers de sortie"""
        os.makedirs(self.config.output_dir, exist_ok=True)
        
        # Dossiers par niveau
        for level_name in self.level_names.values():
            level_dir = os.path.join(self.config.output_dir, f"level_{level_name}")
            os.makedirs(level_dir, exist_ok=True)
        
        # Dossier pour images non classifiées
        if self.config.save_unknown:
            unknown_dir = os.path.join(self.config.output_dir, "unknown")
            os.makedirs(unknown_dir, exist_ok=True)
    
    def _process_classified_image(self, classification: ClassificationResult):
        """Copier ou déplacer l'image classifiée"""
        if classification.status == 'classified':
            dest_dir = os.path.join(
                self.config.output_dir, 
                f"level_{classification.predicted_level}"
            )
        elif self.config.save_unknown:
            dest_dir = os.path.join(self.config.output_dir, "unknown")
        else:
            return
        
        dest_path = os.path.join(dest_dir, classification.filename)
        classification.destination = dest_path
        
        try:
            if self.config.copy_files:
                shutil.copy2(classification.filepath, dest_path)
            else:
                shutil.move(classification.filepath, dest_path)
        except Exception as e:
            self._log(f"⚠️ Erreur copie {classification.filename}: {e}")
    
    def _update_stats(self, classification: ClassificationResult):
        """Mettre à jour les statistiques"""
        if classification.status == 'classified':
            self.detection_stats[classification.predicted_level] += 1
            self.confidence_stats[classification.predicted_level].append(classification.confidence)
        elif classification.status == 'low_confidence':
            self.detection_stats['low_confidence'] += 1
        elif classification.status == 'no_detection':
            self.detection_stats['no_detection'] += 1
        else:
            self.detection_stats['error'] += 1
    
    def _generate_report(self, result: SplitterResult, classifications: List[ClassificationResult]) -> str:
        """Générer le rapport de classification"""
        report_path = os.path.join(self.config.output_dir, "classification_report.json")
        
        # Détails par niveau
        level_details = {}
        for level_name, count in result.level_distribution.items():
            confidences = self.confidence_stats.get(level_name, [])
            level_details[level_name] = {
                'count': count,
                'avg_confidence': round(sum(confidences) / len(confidences), 4) if confidences else 0,
                'min_confidence': round(min(confidences), 4) if confidences else 0,
                'max_confidence': round(max(confidences), 4) if confidences else 0
            }
        
        report = {
            'classification_summary': {
                'total_images': result.total_images,
                'classified_images': result.classified_images,
                'classification_rate': result.classification_rate,
                'confidence_threshold': self.config.confidence_threshold,
                'levels_detected': result.levels_detected,
                'timestamp': datetime.now().isoformat()
            },
            'level_distribution': level_details,
            'detection_issues': {
                'low_confidence': result.low_confidence_count,
                'no_detection': result.no_detection_count,
                'errors': result.error_count
            },
            'config': {
                'model_path': self.config.model_path,
                'source_dir': self.config.source_dir,
                'output_dir': self.config.output_dir,
                'copy_files': self.config.copy_files,
                'save_unknown': self.config.save_unknown
            },
            'model_info': {
                'total_classes': len(self.level_names),
                'class_names': list(self.level_names.values())
            }
        }
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # Afficher le résumé
        self._print_summary(result, level_details)
        
        self._log(f"\n📄 Rapport sauvegardé: {report_path}")
        
        return report_path
    
    def _print_summary(self, result: SplitterResult, level_details: Dict):
        """Afficher le résumé de classification"""
        self._log("\n" + "=" * 50)
        self._log("🎉 CLASSIFICATION TERMINÉE")
        self._log("=" * 50)
        
        self._log(f"📊 Images traitées: {result.total_images:,}")
        self._log(f"✅ Images classifiées: {result.classified_images:,} ({result.classification_rate}%)")
        self._log(f"🎯 Niveaux détectés: {result.levels_detected}")
        
        self._log("\n📋 DISTRIBUTION PAR NIVEAU:")
        for level_name, stats in sorted(level_details.items()):
            self._log(f"   {level_name}: {stats['count']:,} images (confiance moy: {stats['avg_confidence']:.3f})")
        
        if result.low_confidence_count > 0 or result.no_detection_count > 0:
            self._log("\n⚠️ PROBLÈMES DE DÉTECTION:")
            if result.low_confidence_count > 0:
                self._log(f"   Confiance faible: {result.low_confidence_count:,} images")
            if result.no_detection_count > 0:
                self._log(f"   Aucune détection: {result.no_detection_count:,} images")
        
        self._log("\n📁 STRUCTURE CRÉÉE:")
        self._log(f"   {self.config.output_dir}/")
        for level_name in sorted(level_details.keys()):
            self._log(f"   ├── level_{level_name}/ ({level_details[level_name]['count']} images)")
        if result.low_confidence_count > 0 or result.no_detection_count > 0:
            total_unknown = result.low_confidence_count + result.no_detection_count
            self._log(f"   └── unknown/ ({total_unknown} images)")
    
    def stop(self):
        """Arrêter la classification"""
        self.should_stop = True
        self._log("⏹️ Arrêt demandé...")