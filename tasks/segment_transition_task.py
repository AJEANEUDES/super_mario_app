"""
Segment Transition Task - Détection de transitions visuelles par dichotomie
Trouve le point de transition entre deux états dans un enregistrement de frames
"""

import os
import re
import time
import json
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional, Callable

from .base_task import BaseTask, TaskStatus, TaskPriority

# Import conditionnel de OpenCV et NumPy
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class FrameInfo:
    """Informations sur une frame"""
    filename: str
    filepath: str
    frame_number: int
    index: int
    classification: Optional[str] = None


@dataclass
class SegmentConfig:
    """Configuration pour la segmentation"""
    interval_size: int = 1500
    label_state_a: str = "État A"
    label_state_b: str = "État B"
    roi_coords: Optional[Tuple[int, int, int, int]] = None  # x1, y1, x2, y2
    output_dir: str = "segmented_output"
    copy_files: bool = True


class SegmentTransitionTask(BaseTask):
    """
    Tâche de détection de transition visuelle par recherche dichotomique
    Utilise un algorithme en O(log n) pour trouver le point exact de transition
    """
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    
    def __init__(self, priority: TaskPriority = TaskPriority.NORMAL):
        super().__init__(
            name="Segmentation Transition",
            description="Détection de transition visuelle par dichotomie",
            priority=priority
        )
        
        self.frames_dir = None
        self.segment_config = SegmentConfig()
        self.cancel_flag = False
        
        # Données
        self.all_frames: List[FrameInfo] = []
        self.classifications: Dict[int, str] = {}  # index -> classification
        
        # Résultats
        self.transition_index: Optional[int] = None
        self.stats: Dict = {}
        
        # Callback pour classification interactive
        self.classification_callback: Optional[Callable] = None
    
    def configure(self,
                  frames_dir: str,
                  config: SegmentConfig = None,
                  classification_callback: Callable = None):
        """
        Configurer la tâche
        
        Args:
            frames_dir: Dossier contenant les frames
            config: Configuration de segmentation
            classification_callback: Fonction callback pour classifier une frame
                                    Signature: callback(frame_info, roi_coords) -> str ('a' ou 'b')
        """
        self.frames_dir = Path(frames_dir)
        
        if config:
            self.segment_config = config
        
        self.classification_callback = classification_callback
        
        self.config = {
            'frames_dir': str(self.frames_dir),
            'segment_config': asdict(self.segment_config)
        }
    
    def validate_config(self) -> Tuple[bool, str]:
        """Valider la configuration"""
        if not CV2_AVAILABLE:
            return False, "OpenCV (cv2) n'est pas installé"
        
        if 'frames_dir' not in self.config:
            return False, "Dossier de frames non spécifié"
        
        if not self.frames_dir.exists():
            return False, f"Dossier non trouvé: {self.frames_dir}"
        
        return True, "Configuration valide"
    
    def _extract_frame_number(self, filename: str) -> int:
        """Extraire le numéro de frame du nom de fichier"""
        match = re.search(r'(\d+)', filename)
        return int(match.group(1)) if match else 0
    
    def _discover_frames(self) -> List[FrameInfo]:
        """Découvrir et indexer toutes les frames"""
        frames = []
        
        for f in self.frames_dir.iterdir():
            if f.suffix.lower() in self.IMAGE_EXTENSIONS:
                frame_num = self._extract_frame_number(f.name)
                frames.append(FrameInfo(
                    filename=f.name,
                    filepath=str(f),
                    frame_number=frame_num,
                    index=len(frames)
                ))
        
        # Trier par numéro de frame
        frames.sort(key=lambda x: x.frame_number)
        
        # Réindexer après tri
        for i, frame in enumerate(frames):
            frame.index = i
        
        return frames
    
    def classify_frame(self, frame: FrameInfo) -> Optional[str]:
        """
        Classifier une frame (utilise le callback si défini)
        Retourne 'a' pour État A, 'b' pour État B
        """
        # Vérifier si déjà classifiée
        if frame.index in self.classifications:
            return self.classifications[frame.index]
        
        # Utiliser le callback si disponible
        if self.classification_callback:
            result = self.classification_callback(frame, self.segment_config.roi_coords)
            if result:
                self.classifications[frame.index] = result
                frame.classification = result
                return result
        
        return None
    
    def analyze_interval(self, start_idx: int, end_idx: int) -> Tuple[Optional[str], Optional[str]]:
        """Analyser un intervalle et retourner les types de début et fin"""
        start_frame = self.all_frames[start_idx]
        end_frame = self.all_frames[end_idx]
        
        self.log(f"Analyse intervalle [{start_idx}, {end_idx}]", "INFO")
        self.log(f"  Début: {start_frame.filename}", "DEBUG")
        self.log(f"  Fin: {end_frame.filename}", "DEBUG")
        
        start_type = self.classify_frame(start_frame)
        end_type = self.classify_frame(end_frame)
        
        return start_type, end_type
    
    def binary_search_transition(self, start_idx: int, end_idx: int, 
                                  start_type: str, end_type: str) -> Optional[int]:
        """
        Recherche dichotomique du point de transition exact
        Retourne l'index de la première frame de l'état B
        """
        if start_type == end_type:
            return None  # Pas de transition
        
        if end_idx - start_idx <= 1:
            # Transition trouvée entre start_idx et end_idx
            return end_idx
        
        # Point milieu
        mid_idx = (start_idx + end_idx) // 2
        mid_frame = self.all_frames[mid_idx]
        
        self.log(f"Dichotomie [{start_idx}, {end_idx}] → test {mid_idx}", "INFO")
        
        mid_type = self.classify_frame(mid_frame)
        
        if mid_type is None:
            self.log("Classification annulée", "WARNING")
            return None
        
        # Récursion
        if mid_type == start_type:
            return self.binary_search_transition(mid_idx, end_idx, mid_type, end_type)
        else:
            return self.binary_search_transition(start_idx, mid_idx, start_type, mid_type)
    
    def find_transition(self) -> Dict:
        """
        Algorithme principal: recherche par intervalles + dichotomie
        """
        total_frames = len(self.all_frames)
        interval_size = self.segment_config.interval_size
        
        self.log(f"Recherche de transition ({total_frames:,} frames)", "INFO")
        self.log(f"Taille intervalle: {interval_size}", "INFO")
        
        # Créer les intervalles
        intervals = []
        for i in range(0, total_frames, interval_size):
            end_i = min(i + interval_size - 1, total_frames - 1)
            if i < end_i:
                intervals.append((i, end_i))
        
        self.log(f"Intervalles créés: {len(intervals)}", "INFO")
        
        # Analyser chaque intervalle
        for idx, (start_idx, end_idx) in enumerate(intervals):
            if self.cancel_flag:
                return {'cancelled': True}
            
            self.update_progress(
                int((idx / len(intervals)) * 80),
                f"Intervalle {idx+1}/{len(intervals)}"
            )
            
            start_type, end_type = self.analyze_interval(start_idx, end_idx)
            
            if start_type is None or end_type is None:
                self.log("Classification interrompue", "WARNING")
                return {'cancelled': True}
            
            if start_type != end_type:
                self.log(f"Transition détectée dans [{start_idx}, {end_idx}]", "INFO")
                
                # Recherche dichotomique précise
                self.transition_index = self.binary_search_transition(
                    start_idx, end_idx, start_type, end_type
                )
                
                if self.transition_index is not None:
                    trans_frame = self.all_frames[self.transition_index]
                    self.log(f"Point de transition: {trans_frame.filename} (index {self.transition_index})", "INFO")
                    break
            else:
                self.log(f"Intervalle homogène: {start_type}", "DEBUG")
        
        # Construire les résultats
        if self.transition_index is None:
            # Dataset homogène - classifier la première frame pour connaître le type
            first_type = self.classify_frame(self.all_frames[0])
            
            return {
                'transition_found': False,
                'global_type': first_type,
                'total_frames': total_frames,
                'classifications_count': len(self.classifications)
            }
        
        trans_frame = self.all_frames[self.transition_index]
        
        return {
            'transition_found': True,
            'transition_index': self.transition_index,
            'transition_frame': trans_frame.filename,
            'transition_frame_number': trans_frame.frame_number,
            'state_a_frames': self.transition_index,
            'state_b_frames': total_frames - self.transition_index,
            'total_frames': total_frames,
            'classifications_count': len(self.classifications)
        }
    
    def create_segmented_dataset(self, results: Dict, dry_run: bool = False) -> Dict:
        """Créer le dataset segmenté"""
        output_base = Path(self.segment_config.output_dir)
        
        if results.get('transition_found'):
            trans_idx = results['transition_index']
            
            dir_a = output_base / "state_a"
            dir_b = output_base / "state_b"
            
            frames_a = self.all_frames[:trans_idx]
            frames_b = self.all_frames[trans_idx:]
            
            if not dry_run:
                dir_a.mkdir(parents=True, exist_ok=True)
                dir_b.mkdir(parents=True, exist_ok=True)
                
                self.log(f"Copie État A: {len(frames_a):,} frames...", "INFO")
                for frame in frames_a:
                    shutil.copy2(frame.filepath, dir_a / frame.filename)
                
                self.log(f"Copie État B: {len(frames_b):,} frames...", "INFO")
                for frame in frames_b:
                    shutil.copy2(frame.filepath, dir_b / frame.filename)
            
            return {
                'state_a_dir': str(dir_a),
                'state_a_count': len(frames_a),
                'state_b_dir': str(dir_b),
                'state_b_count': len(frames_b),
                'dry_run': dry_run
            }
        else:
            global_type = results.get('global_type', 'unknown')
            single_dir = output_base / global_type
            
            if not dry_run:
                single_dir.mkdir(parents=True, exist_ok=True)
                
                self.log(f"Copie {global_type}: {len(self.all_frames):,} frames...", "INFO")
                for frame in self.all_frames:
                    shutil.copy2(frame.filepath, single_dir / frame.filename)
            
            return {
                'single_dir': str(single_dir),
                'single_count': len(self.all_frames),
                'type': global_type,
                'dry_run': dry_run
            }
    
    def execute(self) -> bool:
        """Exécuter la tâche de segmentation"""
        try:
            self.update_status(TaskStatus.RUNNING, "Démarrage...")
            
            start_time = time.time()
            
            # Découvrir les frames
            self.log("Indexation des frames...", "INFO")
            self.update_progress(5, "Indexation...")
            
            self.all_frames = self._discover_frames()
            
            if not self.all_frames:
                self.update_status(TaskStatus.FAILED, "Aucune frame trouvée")
                return False
            
            self.log(f"Trouvé {len(self.all_frames):,} frames", "INFO")
            self.log(f"Première: {self.all_frames[0].filename}", "INFO")
            self.log(f"Dernière: {self.all_frames[-1].filename}", "INFO")
            
            # Recherche de transition
            self.log("Recherche de transition...", "INFO")
            results = self.find_transition()
            
            if results.get('cancelled'):
                self.update_status(TaskStatus.CANCELLED, "Annulé par l'utilisateur")
                return False
            
            self.stats = results
            
            # Afficher résultats
            if results.get('transition_found'):
                self.log(f"✅ Transition trouvée!", "INFO")
                self.log(f"   Position: frame #{results['transition_index']}", "INFO")
                self.log(f"   Fichier: {results['transition_frame']}", "INFO")
                self.log(f"   État A: {results['state_a_frames']:,} frames", "INFO")
                self.log(f"   État B: {results['state_b_frames']:,} frames", "INFO")
            else:
                self.log(f"ℹ️ Dataset homogène: {results.get('global_type', '?')}", "INFO")
            
            self.log(f"Classifications effectuées: {results['classifications_count']}", "INFO")
            
            # Sauvegarder le rapport
            self._save_report(results)
            
            elapsed = time.time() - start_time
            self.log(f"⏱️ Temps total: {elapsed:.1f}s", "INFO")
            
            self.update_progress(100, "✅ Terminé")
            self.update_status(TaskStatus.COMPLETED, "Segmentation terminée")
            
            return True
            
        except Exception as e:
            self.error_message = str(e)
            self.update_status(TaskStatus.FAILED, str(e))
            self.log(f"❌ Erreur: {str(e)}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False
    
    def _save_report(self, results: Dict):
        """Sauvegarder le rapport JSON"""
        report_path = self.frames_dir / "segmentation_report.json"
        
        report = {
            'analysis_info': {
                'frames_dir': str(self.frames_dir),
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            },
            'config': {
                'interval_size': self.segment_config.interval_size,
                'label_state_a': self.segment_config.label_state_a,
                'label_state_b': self.segment_config.label_state_b,
                'roi_coords': self.segment_config.roi_coords
            },
            'results': results
        }
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.log(f"📄 Rapport sauvé: {report_path}", "INFO")
        except Exception as e:
            self.log(f"Erreur sauvegarde rapport: {e}", "WARNING")
    
    def cancel(self):
        """Annuler la tâche"""
        self.cancel_flag = True
        self.log("Annulation demandée...", "WARNING")
    
    def get_summary(self) -> str:
        """Résumé des résultats"""
        if not self.stats:
            return "Aucune statistique disponible"
        
        s = self.stats
        if not s.get('transition_found'):
            return f"Dataset homogène: {s.get('global_type', '?')} ({s.get('total_frames', 0):,} frames)"
        
        return f"""🔄 Segmentation:
• Total: {s['total_frames']:,} frames
• Transition: frame #{s['transition_index']}
• État A: {s['state_a_frames']:,} frames
• État B: {s['state_b_frames']:,} frames
• Classifications: {s['classifications_count']}"""