"""
Unknown Reviewer Task - Révision manuelle des images non classifiées
Permet de visualiser, classer manuellement ou supprimer les images du dossier unknown
"""

import os
import shutil
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from collections import defaultdict
from datetime import datetime
import cv2
import logging
import re


try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class ReviewerConfig:
    """Configuration du reviewer"""
    unknown_dir: str = ""
    levels_base_dir: str = ""
    create_backup: bool = True


@dataclass
class ImageInfo:
    """Informations sur une image"""
    filepath: str
    filename: str
    size_bytes: int
    width: int = 0
    height: int = 0
    frame_number: str = ""


@dataclass
class ReviewStats:
    """Statistiques de révision"""
    total_images: int = 0
    reviewed: int = 0
    moved: int = 0
    deleted: int = 0
    skipped: int = 0
    bulk_deleted: int = 0
    movements: Dict[str, int] = field(default_factory=dict)


class UnknownReviewerTask:
    """
    Tâche de révision des images non classifiées
    """
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    PROGRESS_FILE = "review_progress.json"
    
    def __init__(self):
        self.config: Optional[ReviewerConfig] = None
        self.available_levels: List[str] = []
        self.unknown_images: List[str] = []
        self.current_index: int = 0
        self.stats = ReviewStats()
        
        # Callbacks
        self.log_callback: Optional[Callable[[str], None]] = None
    
    def _log(self, message: str):
        """Logger un message"""
        if self.log_callback:
            self.log_callback(message)
    
    def configure(self, config: ReviewerConfig, log_callback: Optional[Callable] = None):
        """Configurer la tâche"""
        self.config = config
        self.log_callback = log_callback
        
        # Découvrir les niveaux disponibles
        self.available_levels = self._discover_available_levels()
        
        # Charger les images unknown
        self.unknown_images = self._get_unknown_images()
        self.stats.total_images = len(self.unknown_images)
    
    def _discover_available_levels(self) -> List[str]:
        """Découvre automatiquement les niveaux disponibles"""
        levels = []
        
        if self.config and os.path.exists(self.config.levels_base_dir):
            for item in os.listdir(self.config.levels_base_dir):
                item_path = os.path.join(self.config.levels_base_dir, item)
                if os.path.isdir(item_path) and item.startswith('level_'):
                    level_name = item.replace('level_', '')
                    levels.append(level_name)
        
        return sorted(levels)
    
    def _get_unknown_images(self) -> List[str]:
        """Récupère toutes les images du dossier unknown"""
        images = []
        
        if not self.config or not os.path.exists(self.config.unknown_dir):
            return images
        
        for filename in os.listdir(self.config.unknown_dir):
            ext = os.path.splitext(filename)[1].lower()
            if ext in self.IMAGE_EXTENSIONS:
                full_path = os.path.join(self.config.unknown_dir, filename)
                if os.path.isfile(full_path):
                    images.append(full_path)
        
        return sorted(images)
    
    def refresh_images(self):
        """Rafraîchir la liste des images"""
        self.unknown_images = self._get_unknown_images()
        self.stats.total_images = len(self.unknown_images)
        
        # Ajuster l'index si nécessaire
        if self.current_index >= len(self.unknown_images):
            self.current_index = max(0, len(self.unknown_images) - 1)
    
    def get_image_info(self, index: int = None) -> Optional[ImageInfo]:
        """Obtenir les informations sur une image"""
        if index is None:
            index = self.current_index
        
        if index < 0 or index >= len(self.unknown_images):
            return None
        
        filepath = self.unknown_images[index]
        filename = Path(filepath).name
        
        try:
            size_bytes = os.path.getsize(filepath)
            
            # Dimensions
            width, height = 0, 0
            if CV2_AVAILABLE:
                img = cv2.imread(filepath)
                if img is not None:
                    height, width = img.shape[:2]
            
            # Numéro de frame
            import re
            match = re.search(r'(\d+)', filename)
            frame_number = match.group(1) if match else ""
            
            return ImageInfo(
                filepath=filepath,
                filename=filename,
                size_bytes=size_bytes,
                width=width,
                height=height,
                frame_number=frame_number
            )
        except Exception as e:
            self._log(f"⚠️ Erreur lecture info: {e}")
            return ImageInfo(
                filepath=filepath,
                filename=filename,
                size_bytes=0
            )
    
    def get_current_image_path(self) -> Optional[str]:
        """Obtenir le chemin de l'image courante"""
        if 0 <= self.current_index < len(self.unknown_images):
            return self.unknown_images[self.current_index]
        return None
    
    def navigate(self, direction: int) -> bool:
        """Naviguer: direction = 1 (suivant) ou -1 (précédent)"""
        new_index = self.current_index + direction
        if 0 <= new_index < len(self.unknown_images):
            self.current_index = new_index
            return True
        return False
    
    def go_to_index(self, index: int) -> bool:
        """Aller à un index spécifique"""
        if 0 <= index < len(self.unknown_images):
            self.current_index = index
            return True
        return False
    
    def move_to_level(self, level: str) -> bool:
        """Déplacer l'image courante vers un niveau"""
        if self.current_index >= len(self.unknown_images):
            return False
        
        img_path = self.unknown_images[self.current_index]
        filename = Path(img_path).name
        
        try:
            level_dir = os.path.join(self.config.levels_base_dir, f"level_{level}")
            os.makedirs(level_dir, exist_ok=True)
            
            dst_path = os.path.join(level_dir, filename)
            
            # Vérifier si existe déjà
            if os.path.exists(dst_path):
                # Ajouter un suffixe unique
                base, ext = os.path.splitext(filename)
                timestamp = datetime.now().strftime("%H%M%S")
                dst_path = os.path.join(level_dir, f"{base}_{timestamp}{ext}")
            
            shutil.move(img_path, dst_path)
            
            self._log(f"✅ {filename} → level_{level}")
            
            # Mettre à jour stats
            self.stats.moved += 1
            self.stats.reviewed += 1
            if level not in self.stats.movements:
                self.stats.movements[level] = 0
            self.stats.movements[level] += 1
            
            # Retirer de la liste
            self.unknown_images.pop(self.current_index)
            if self.current_index >= len(self.unknown_images):
                self.current_index = max(0, len(self.unknown_images) - 1)
            
            return True
            
        except Exception as e:
            self._log(f"❌ Erreur déplacement: {e}")
            return False
    
    def delete_current(self) -> bool:
        """Supprimer l'image courante"""
        if self.current_index >= len(self.unknown_images):
            return False
        
        img_path = self.unknown_images[self.current_index]
        filename = Path(img_path).name
        
        try:
            os.remove(img_path)
            
            self._log(f"🗑️ {filename} supprimé")
            
            # Mettre à jour stats
            self.stats.deleted += 1
            self.stats.reviewed += 1
            
            # Retirer de la liste
            self.unknown_images.pop(self.current_index)
            if self.current_index >= len(self.unknown_images):
                self.current_index = max(0, len(self.unknown_images) - 1)
            
            return True
            
        except Exception as e:
            self._log(f"❌ Erreur suppression: {e}")
            return False
    
    def skip_current(self):
        """Ignorer l'image courante et passer à la suivante"""
        self.stats.skipped += 1
        self.stats.reviewed += 1
        self.navigate(1)
    
    def delete_all_remaining(self, create_backup: bool = True) -> Dict[str, Any]:
        """Supprimer toutes les images restantes"""
        remaining = self.unknown_images[self.current_index:]
        
        result = {
            'success': False,
            'deleted': 0,
            'backup_dir': None,
            'errors': []
        }
        
        if not remaining:
            result['success'] = True
            return result
        
        # Créer backup si demandé
        if create_backup:
            backup_dir = self._create_backup(remaining)
            result['backup_dir'] = backup_dir
        
        # Supprimer
        for img_path in remaining:
            try:
                os.remove(img_path)
                result['deleted'] += 1
            except Exception as e:
                result['errors'].append(f"{Path(img_path).name}: {e}")
        
        self.stats.bulk_deleted += result['deleted']
        
        # Rafraîchir la liste
        self.refresh_images()
        
        result['success'] = True
        self._log(f"🗑️ Suppression massive: {result['deleted']} images supprimées")
        
        return result
    
    def delete_by_pattern(self, pattern: str, pattern_type: str = "name") -> Dict[str, Any]:
        """
        Supprimer les images par motif
        pattern_type: "name", "size_under", "size_over"
        """
        result = {
            'success': False,
            'matching': 0,
            'deleted': 0,
            'errors': []
        }
        
        matching_images = []
        
        for img_path in self.unknown_images:
            filename = Path(img_path).name
            
            if pattern_type == "name":
                if pattern.lower() in filename.lower():
                    matching_images.append(img_path)
            
            elif pattern_type == "size_under":
                try:
                    size_kb = int(pattern)
                    if os.path.getsize(img_path) < size_kb * 1024:
                        matching_images.append(img_path)
                except:
                    pass
            
            elif pattern_type == "size_over":
                try:
                    size_kb = int(pattern)
                    if os.path.getsize(img_path) > size_kb * 1024:
                        matching_images.append(img_path)
                except:
                    pass
        
        result['matching'] = len(matching_images)
        
        if not matching_images:
            result['success'] = True
            return result
        
        # Supprimer
        for img_path in matching_images:
            try:
                os.remove(img_path)
                result['deleted'] += 1
            except Exception as e:
                result['errors'].append(f"{Path(img_path).name}: {e}")
        
        self.stats.bulk_deleted += result['deleted']
        
        # Rafraîchir
        self.refresh_images()
        
        result['success'] = True
        self._log(f"🗑️ Suppression par motif '{pattern}': {result['deleted']} images")
        
        return result
    
    def _create_backup(self, images: List[str]) -> Optional[str]:
        """Créer une sauvegarde des images"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = os.path.join(self.config.levels_base_dir, f"backup_before_delete_{timestamp}")
        
        try:
            os.makedirs(backup_dir, exist_ok=True)
            
            for img_path in images:
                filename = Path(img_path).name
                backup_path = os.path.join(backup_dir, filename)
                shutil.copy2(img_path, backup_path)
            
            self._log(f"💾 Sauvegarde créée: {backup_dir}")
            return backup_dir
            
        except Exception as e:
            self._log(f"⚠️ Erreur création backup: {e}")
            return None
    
    def save_progress(self) -> bool:
        """Sauvegarder le progrès"""
        if not self.config:
            return False
        
        progress_file = os.path.join(self.config.levels_base_dir, self.PROGRESS_FILE)
        
        progress_data = {
            'last_reviewed_index': self.current_index,
            'stats': {
                'total_images': self.stats.total_images,
                'reviewed': self.stats.reviewed,
                'moved': self.stats.moved,
                'deleted': self.stats.deleted,
                'skipped': self.stats.skipped,
                'bulk_deleted': self.stats.bulk_deleted
            },
            'movements': dict(self.stats.movements),
            'timestamp': datetime.now().isoformat(),
            'unknown_dir': self.config.unknown_dir,
            'remaining': len(self.unknown_images)
        }
        
        try:
            with open(progress_file, 'w', encoding='utf-8') as f:
                json.dump(progress_data, f, indent=2, ensure_ascii=False)
            
            self._log(f"💾 Progrès sauvegardé (index {self.current_index})")
            return True
        except Exception as e:
            self._log(f"❌ Erreur sauvegarde: {e}")
            return False
    
    def load_progress(self) -> bool:
        """Charger le progrès précédent"""
        if not self.config:
            return False
        
        progress_file = os.path.join(self.config.levels_base_dir, self.PROGRESS_FILE)
        
        if not os.path.exists(progress_file):
            return False
        
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                progress_data = json.load(f)
            
            # Vérifier que c'est le même dossier
            if progress_data.get('unknown_dir') != self.config.unknown_dir:
                self._log("⚠️ Progrès d'un autre dossier, ignoré")
                return False
            
            # Restaurer l'index
            self.current_index = progress_data.get('last_reviewed_index', 0)
            
            # Restaurer les stats
            stats_data = progress_data.get('stats', {})
            self.stats.reviewed = stats_data.get('reviewed', 0)
            self.stats.moved = stats_data.get('moved', 0)
            self.stats.deleted = stats_data.get('deleted', 0)
            self.stats.skipped = stats_data.get('skipped', 0)
            self.stats.bulk_deleted = stats_data.get('bulk_deleted', 0)
            self.stats.movements = progress_data.get('movements', {})
            
            timestamp = progress_data.get('timestamp', 'Unknown')
            self._log(f"📂 Progrès chargé (sauvé: {timestamp})")
            self._log(f"📍 Reprise à l'image #{self.current_index + 1}")
            
            return True
        except Exception as e:
            self._log(f"⚠️ Erreur chargement progrès: {e}")
            return False
    
    def has_saved_progress(self) -> bool:
        """Vérifier s'il y a un progrès sauvegardé"""
        if not self.config:
            return False
        
        progress_file = os.path.join(self.config.levels_base_dir, self.PROGRESS_FILE)
        return os.path.exists(progress_file)
    
    def get_progress_info(self) -> Optional[Dict]:
        """Obtenir les infos du progrès sauvegardé"""
        if not self.config:
            return None
        
        progress_file = os.path.join(self.config.levels_base_dir, self.PROGRESS_FILE)
        
        if not os.path.exists(progress_file):
            return None
        
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return None
    
    def clear_progress(self):
        """Effacer le progrès sauvegardé"""
        if not self.config:
            return
        
        progress_file = os.path.join(self.config.levels_base_dir, self.PROGRESS_FILE)
        
        if os.path.exists(progress_file):
            os.remove(progress_file)
            self._log("🗑️ Progrès effacé")
    
    def get_stats_summary(self) -> str:
        """Obtenir un résumé des statistiques"""
        lines = [
            "📊 RÉSUMÉ DE LA SESSION",
            "=" * 35,
            f"📸 Images révisées: {self.stats.reviewed}",
            f"✅ Déplacées: {self.stats.moved}",
            f"🗑️ Supprimées: {self.stats.deleted}",
            f"💥 Suppression massive: {self.stats.bulk_deleted}",
            f"⏭️ Ignorées: {self.stats.skipped}",
            f"📂 Restantes: {len(self.unknown_images)}"
        ]
        
        if self.stats.movements:
            lines.append("\n📋 RÉPARTITION PAR NIVEAU:")
            for level, count in sorted(self.stats.movements.items()):
                lines.append(f"   level_{level}: +{count}")
        
        return "\n".join(lines)