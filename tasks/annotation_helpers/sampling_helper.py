"""
Sampling Helper - Échantillonnage intelligent des frames

Permet de réduire le nombre de frames à annoter en sélectionnant
intelligemment un sous-ensemble représentatif.
"""

import os
import random
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .base_helper import BaseAnnotationHelper, HelperInfo, HelperResult, HelperStatus
import cv2

# Imports optionnels pour la détection de similarité
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class SamplingConfig:
    """Configuration de l'échantillonnage"""
    method: str = "interval"  # "interval", "random", "keyframe", "diversity"
    interval: int = 10        # Pour méthode interval: 1 frame sur N
    count: int = 100          # Pour méthode random: nombre de frames à sélectionner
    threshold: float = 0.3    # Pour méthode keyframe: seuil de différence
    include_first: bool = True
    include_last: bool = True


class SamplingHelper(BaseAnnotationHelper):
    """
    Helper d'échantillonnage intelligent.
    
    Méthodes disponibles:
    - interval: Sélectionne 1 frame sur N (ex: 1 sur 10)
    - random: Sélection aléatoire de N frames
    - keyframe: Détecte les changements significatifs (scènes)
    - diversity: Sélectionne les frames les plus différents
    """
    
    def __init__(self):
        super().__init__()
        self.task = None
        self.config = SamplingConfig()
        self.selected_indices: List[int] = []
    
    @staticmethod
    def get_info() -> HelperInfo:
        return HelperInfo(
            id="sampling",
            name="Échantillonnage intelligent",
            icon="🎯",
            short_description="Réduire le nombre de frames à annoter",
            long_description="""
L'échantillonnage intelligent permet de réduire considérablement 
le travail d'annotation en sélectionnant un sous-ensemble représentatif de frames.

Au lieu d'annoter 2000 frames, vous pouvez n'en annoter que 100-200 
tout en obtenant un dataset de qualité suffisante pour entraîner YOLO.

**Comment ça marche:**
1. Choisissez une méthode d'échantillonnage
2. Le système sélectionne les frames à annoter
3. Les frames non sélectionnés sont masqués
4. Vous annotez uniquement les frames sélectionnés

**Pourquoi ça fonctionne:**
Les frames consécutifs d'une vidéo sont très similaires. 
YOLO peut apprendre efficacement avec 200-500 images bien annotées 
plutôt que 2000 images mal annotées.
            """.strip(),
            requirements=[],
            estimated_speedup="10-20x plus rapide",
            best_for=[
                "Grandes quantités de frames",
                "Vidéos avec peu de changements",
                "Création rapide d'un dataset de base"
            ],
            limitations=[
                "Peut manquer des objets rares",
                "Moins efficace si beaucoup de mouvements",
                "Nécessite OpenCV pour les méthodes avancées"
            ]
        )
    
    def configure(self, task, **kwargs) -> bool:
        """Configurer le helper"""
        self.task = task
        
        # Appliquer la configuration
        self.config.method = kwargs.get('method', 'interval')
        self.config.interval = kwargs.get('interval', 10)
        self.config.count = kwargs.get('count', 100)
        self.config.threshold = kwargs.get('threshold', 0.3)
        self.config.include_first = kwargs.get('include_first', True)
        self.config.include_last = kwargs.get('include_last', True)
        
        return True
    
    def execute(self) -> HelperResult:
        """Exécuter l'échantillonnage"""
        if not self.task or not self.task.images:
            return HelperResult(
                success=False,
                message="Aucune image chargée"
            )
        
        self.status = HelperStatus.RUNNING
        self.selected_indices = []
        
        total = len(self.task.images)
        
        try:
            if self.config.method == "interval":
                self.selected_indices = self._sample_interval(total)
            elif self.config.method == "random":
                self.selected_indices = self._sample_random(total)
            elif self.config.method == "keyframe":
                self.selected_indices = self._sample_keyframe()
            elif self.config.method == "diversity":
                self.selected_indices = self._sample_diversity()
            else:
                return HelperResult(
                    success=False,
                    message=f"Méthode inconnue: {self.config.method}"
                )
            
            # Toujours inclure le premier et le dernier si demandé
            if self.config.include_first and 0 not in self.selected_indices:
                self.selected_indices.insert(0, 0)
            if self.config.include_last and (total - 1) not in self.selected_indices:
                self.selected_indices.append(total - 1)
            
            # Trier et dédupliquer
            self.selected_indices = sorted(set(self.selected_indices))
            
            self.status = HelperStatus.COMPLETED
            
            return HelperResult(
                success=True,
                message=f"{len(self.selected_indices)} frames sélectionnés sur {total}",
                processed=len(self.selected_indices),
                skipped=total - len(self.selected_indices),
                details={
                    'method': self.config.method,
                    'selected_indices': self.selected_indices,
                    'reduction_ratio': len(self.selected_indices) / total
                }
            )
            
        except Exception as e:
            self.status = HelperStatus.ERROR
            return HelperResult(
                success=False,
                message=f"Erreur: {str(e)}",
                errors=1
            )
    
    def _sample_interval(self, total: int) -> List[int]:
        """Échantillonnage par intervalle (1 sur N)"""
        indices = []
        for i in range(0, total, self.config.interval):
            if self._check_cancelled():
                break
            indices.append(i)
            self._update_progress(i / total, f"Sélection {len(indices)}/{total // self.config.interval}")
        
        return indices
    
    def _sample_random(self, total: int) -> List[int]:
        """Échantillonnage aléatoire"""
        count = min(self.config.count, total)
        indices = random.sample(range(total), count)
        self._update_progress(1.0, f"{count} frames sélectionnés aléatoirement")
        return sorted(indices)
    
    def _sample_keyframe(self) -> List[int]:
        """Échantillonnage par détection de keyframes (changements de scène)"""
        if not CV2_AVAILABLE:
            self._log("⚠️ OpenCV non disponible, utilisation de la méthode interval")
            return self._sample_interval(len(self.task.images))
        
        indices = [0]  # Toujours inclure le premier
        prev_hist = None
        
        for i, img in enumerate(self.task.images):
            if self._check_cancelled():
                break
            
            self._update_progress(i / len(self.task.images), f"Analyse frame {i+1}")
            
            try:
                frame = cv2.imread(img.image_path)
                if frame is None:
                    continue
                
                # Calculer l'histogramme de couleur
                hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                hist = cv2.normalize(hist, hist).flatten()
                
                if prev_hist is not None:
                    # Comparer avec le frame précédent
                    diff = cv2.compareHist(prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
                    
                    if diff > self.config.threshold:
                        indices.append(i)
                        self._log(f"🎬 Keyframe détecté: {i} (diff={diff:.3f})")
                
                prev_hist = hist
                
            except Exception as e:
                self._log(f"⚠️ Erreur frame {i}: {e}")
        
        return indices
    
    def _sample_diversity(self) -> List[int]:
        """Échantillonnage par diversité (frames les plus différents)"""
        if not CV2_AVAILABLE:
            self._log("⚠️ OpenCV non disponible, utilisation de la méthode random")
            return self._sample_random(len(self.task.images))
        
        # Calculer les features de tous les frames
        features = []
        for i, img in enumerate(self.task.images):
            if self._check_cancelled():
                break
            
            self._update_progress(i / len(self.task.images) * 0.5, f"Extraction features {i+1}")
            
            try:
                frame = cv2.imread(img.image_path)
                if frame is None:
                    features.append(None)
                    continue
                
                # Réduire et calculer histogramme
                small = cv2.resize(frame, (64, 64))
                hist = cv2.calcHist([small], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
                features.append(cv2.normalize(hist, hist).flatten())
                
            except Exception:
                features.append(None)
        
        # Sélectionner les frames les plus différents
        selected = [0]
        count = min(self.config.count, len(self.task.images))
        
        while len(selected) < count and not self._check_cancelled():
            self._update_progress(0.5 + len(selected) / count * 0.5, f"Sélection {len(selected)}/{count}")
            
            max_min_dist = -1
            best_idx = -1
            
            for i, feat in enumerate(features):
                if i in selected or feat is None:
                    continue
                
                # Distance minimale aux frames déjà sélectionnés
                min_dist = float('inf')
                for j in selected:
                    if features[j] is not None:
                        dist = cv2.compareHist(feat, features[j], cv2.HISTCMP_BHATTACHARYYA)
                        min_dist = min(min_dist, dist)
                
                if min_dist > max_min_dist:
                    max_min_dist = min_dist
                    best_idx = i
            
            if best_idx >= 0:
                selected.append(best_idx)
            else:
                break
        
        return sorted(selected)
    
    def get_selected_indices(self) -> List[int]:
        """Retourne les indices des frames sélectionnés"""
        return self.selected_indices
    
    def apply_filter(self):
        """Appliquer le filtre aux images du task"""
        if not self.task or not self.selected_indices:
            return False
        
        # Marquer les images non sélectionnées
        for i, img in enumerate(self.task.images):
            img.is_filtered = i not in self.selected_indices
        
        self._log(f"✅ Filtre appliqué: {len(self.selected_indices)} frames actifs")
        return True
    
    def clear_filter(self):
        """Supprimer le filtre"""
        if not self.task:
            return False
        
        for img in self.task.images:
            img.is_filtered = False
        
        self.selected_indices = list(range(len(self.task.images)))
        self._log("✅ Filtre supprimé: tous les frames actifs")
        return True