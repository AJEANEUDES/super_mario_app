"""
Mario Level Segmentation Task - Segmentation intelligente par niveaux Mario
Utilise intervalles réguliers + dichotomie pour localiser les transitions entre niveaux
"""

import os
import re
import time
import json
import shutil
import random
from pathlib import Path
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Tuple, Optional, Callable, Set
from collections import defaultdict

from .base_task import BaseTask, TaskStatus, TaskPriority

# Import conditionnel
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class FrameData:
    """Données d'une frame"""
    filename: str
    filepath: str
    frame_number: int
    index: int
    level: Optional[str] = None


@dataclass 
class LevelSegment:
    """Segment de niveau détecté"""
    level: str
    start_idx: int
    end_idx: int
    start_filename: str
    end_filename: str
    start_frame: int
    end_frame: int
    count: int


@dataclass
class MarioLevelConfig:
    """Configuration pour la segmentation par niveaux"""
    interval_size: Optional[int] = None  # None = auto-calculé
    world_roi: Tuple[float, float, float, float] = (0.62, 0.04, 0.88, 0.18)  # x1, y1, x2, y2 relatifs
    output_dir: str = "mario_level_dataset"
    create_yolo_dataset: bool = False
    train_ratio: float = 0.7
    val_ratio: float = 0.2
    test_ratio: float = 0.1


class MarioLevelSegmentTask(BaseTask):
    """
    Tâche de segmentation intelligente par niveaux Mario
    Utilise intervalles + dichotomie pour trouver les transitions
    """
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
    
    # Tous les niveaux Mario possibles (32)
    ALL_LEVELS = [f"{w}-{s}" for w in range(1, 9) for s in range(1, 5)]
    
    def __init__(self, priority: TaskPriority = TaskPriority.NORMAL):
        super().__init__(
            name="Segmentation Niveaux Mario",
            description="Détection des transitions entre niveaux Mario",
            priority=priority
        )
        
        self.frames_dir = None
        self.level_config = MarioLevelConfig()
        self.cancel_flag = False
        
        # Données
        self.all_frames: List[FrameData] = []
        self.level_classifications: Dict[int, str] = {}  # index -> level
        self.detected_levels: Set[str] = set()
        
        # Résultats
        self.level_segments: Dict[str, List[LevelSegment]] = defaultdict(list)
        self.stats: Dict = {}
        
        # Callback pour classification interactive
        self.classification_callback: Optional[Callable] = None
    
    def configure(self,
                  frames_dir: str,
                  config: MarioLevelConfig = None,
                  classification_callback: Callable = None):
        """
        Configurer la tâche
        
        Args:
            frames_dir: Dossier contenant les frames
            config: Configuration
            classification_callback: Fonction callback pour identifier le niveau
                                    Signature: callback(frame_data, roi_coords, context) -> str (ex: "1-1")
        """
        self.frames_dir = Path(frames_dir)
        
        if config:
            self.level_config = config
        
        self.classification_callback = classification_callback
        
        self.config = {
            'frames_dir': str(self.frames_dir),
            'level_config': asdict(self.level_config)
        }
    
    def validate_config(self) -> Tuple[bool, str]:
        """Valider la configuration"""
        if not CV2_AVAILABLE:
            return False, "OpenCV (cv2) n'est pas installé"
        
        if not self.frames_dir or not self.frames_dir.exists():
            return False, f"Dossier non trouvé: {self.frames_dir}"
        
        return True, "Configuration valide"
    
    def _extract_frame_number(self, filename: str) -> int:
        """Extraire le numéro de frame"""
        match = re.search(r'(\d+)', Path(filename).stem)
        return int(match.group(1)) if match else 0
    
    def _scan_frames(self) -> List[FrameData]:
        """Scanner et indexer toutes les frames"""
        frames = []
        
        for f in self.frames_dir.iterdir():
            if f.suffix.lower() in self.IMAGE_EXTENSIONS:
                frame_num = self._extract_frame_number(f.name)
                frames.append(FrameData(
                    filename=f.name,
                    filepath=str(f),
                    frame_number=frame_num,
                    index=len(frames)
                ))
        
        # Trier par numéro de frame
        frames.sort(key=lambda x: x.frame_number)
        
        # Réindexer
        for i, frame in enumerate(frames):
            frame.index = i
        
        return frames
    
    def classify_frame(self, frame: FrameData, context: str = "") -> Optional[str]:
        """
        Classifier une frame (niveau Mario)
        Retourne un niveau (ex: "1-1", "2-3") ou "unknown"
        """
        # Vérifier si déjà classifiée
        if frame.index in self.level_classifications:
            return self.level_classifications[frame.index]
        
        # Utiliser le callback si disponible
        if self.classification_callback:
            result = self.classification_callback(
                frame, 
                self.level_config.world_roi,
                context
            )
            
            if result and result != "cancel":
                self.level_classifications[frame.index] = result
                frame.level = result
                
                if result != "unknown":
                    self.detected_levels.add(result)
                
                return result
            elif result == "cancel":
                return None
        
        return "unknown"
    
    def _dichotomy_segmentation(self, start_idx: int, end_idx: int, 
                                 known_start_level: str = None) -> List[dict]:
        """Segmentation par dichotomie récursive"""
        if self.cancel_flag:
            return []
        
        if end_idx - start_idx < 1:
            return []
        
        # Cas de base : intervalle très petit
        if end_idx - start_idx <= 10:
            return self._analyze_small_interval(start_idx, end_idx)
        
        # Point milieu
        mid_idx = (start_idx + end_idx) // 2
        mid_frame = self.all_frames[mid_idx]
        
        self.log(f"  Dichotomie [{start_idx}→{end_idx}]: test frame {mid_idx}", "DEBUG")
        
        # Identifier le niveau au milieu
        mid_level = self.classify_frame(mid_frame, f"MILIEU ({start_idx}→{end_idx})")
        
        if mid_level is None:  # Annulé
            return []
        
        # Obtenir les niveaux de début et fin
        start_frame = self.all_frames[start_idx]
        end_frame = self.all_frames[end_idx]
        
        if known_start_level is None:
            start_level = self.classify_frame(start_frame, f"DEBUT ({start_idx})")
        else:
            start_level = known_start_level
        
        if start_level is None:
            return []
        
        end_level = self.classify_frame(end_frame, f"FIN ({end_idx})")
        
        if end_level is None:
            return []
        
        segments = []
        
        # Segmenter récursivement
        if start_level == mid_level:
            # Transition après le milieu
            segments.append({
                'level': start_level,
                'start_idx': start_idx,
                'end_idx': mid_idx,
                'count': mid_idx - start_idx + 1
            })
            segments.extend(self._dichotomy_segmentation(mid_idx + 1, end_idx))
        else:
            # Transition avant le milieu
            segments.extend(self._dichotomy_segmentation(start_idx, mid_idx, start_level))
            segments.extend(self._dichotomy_segmentation(mid_idx, end_idx))
        
        return segments
    
    def _analyze_small_interval(self, start_idx: int, end_idx: int) -> List[dict]:
        """Analyse détaillée d'un petit intervalle"""
        segments = []
        current_level = None
        current_start = start_idx
        
        for idx in range(start_idx, end_idx + 1):
            if self.cancel_flag:
                return segments
            
            frame = self.all_frames[idx]
            level = self.classify_frame(frame, f"Frame {idx}")
            
            if level is None:  # Annulé
                return segments
            
            if current_level is None:
                current_level = level
            elif level != current_level and level != "unknown":
                # Transition détectée
                if current_level != "unknown":
                    segments.append({
                        'level': current_level,
                        'start_idx': current_start,
                        'end_idx': idx - 1,
                        'count': idx - current_start
                    })
                current_level = level
                current_start = idx
        
        # Ajouter le dernier segment
        if current_level and current_level != "unknown":
            segments.append({
                'level': current_level,
                'start_idx': current_start,
                'end_idx': end_idx,
                'count': end_idx - current_start + 1
            })
        
        return segments
    
    def _consolidate_segments(self, segments: List[dict]):
        """Consolider les segments par niveau"""
        self.level_segments = defaultdict(list)
        
        for segment in segments:
            level = segment['level']
            if level and level != "unknown":
                seg = LevelSegment(
                    level=level,
                    start_idx=segment['start_idx'],
                    end_idx=segment['end_idx'],
                    start_filename=self.all_frames[segment['start_idx']].filename,
                    end_filename=self.all_frames[segment['end_idx']].filename,
                    start_frame=self.all_frames[segment['start_idx']].frame_number,
                    end_frame=self.all_frames[segment['end_idx']].frame_number,
                    count=segment['count']
                )
                self.level_segments[level].append(seg)
    
    def execute(self) -> bool:
        """Exécuter la segmentation intelligente"""
        try:
            self.update_status(TaskStatus.RUNNING, "Démarrage...")
            
            start_time = time.time()
            
            # Scanner les frames
            self.log("Scan des frames...", "INFO")
            self.update_progress(5, "Indexation...")
            
            self.all_frames = self._scan_frames()
            
            if not self.all_frames:
                self.update_status(TaskStatus.FAILED, "Aucune frame trouvée")
                return False
            
            total_frames = len(self.all_frames)
            self.log(f"Trouvé {total_frames:,} frames", "INFO")
            
            # Calculer la taille d'intervalle optimale
            if self.level_config.interval_size is None:
                estimated_per_level = total_frames // 20
                interval_size = max(500, min(2000, estimated_per_level))
            else:
                interval_size = self.level_config.interval_size
            
            self.log(f"Taille d'intervalle: {interval_size}", "INFO")
            
            # Créer les intervalles
            intervals = []
            for start_idx in range(0, total_frames, interval_size):
                end_idx = min(start_idx + interval_size - 1, total_frames - 1)
                if start_idx < end_idx:
                    intervals.append((start_idx, end_idx))
            
            self.log(f"Intervalles créés: {len(intervals)}", "INFO")
            
            # Analyser chaque intervalle
            all_segments = []
            
            for i, (start_idx, end_idx) in enumerate(intervals):
                if self.cancel_flag:
                    self.update_status(TaskStatus.CANCELLED, "Annulé")
                    return False
                
                self.update_progress(
                    10 + int((i / len(intervals)) * 80),
                    f"Intervalle {i+1}/{len(intervals)}"
                )
                
                self.log(f"Intervalle {i+1}/{len(intervals)}: [{start_idx}→{end_idx}]", "INFO")
                
                start_frame = self.all_frames[start_idx]
                end_frame = self.all_frames[end_idx]
                
                # Classifier début et fin
                start_level = self.classify_frame(start_frame, f"DEBUT intervalle {i+1}")
                if start_level is None:
                    self.update_status(TaskStatus.CANCELLED, "Annulé")
                    return False
                
                end_level = self.classify_frame(end_frame, f"FIN intervalle {i+1}")
                if end_level is None:
                    self.update_status(TaskStatus.CANCELLED, "Annulé")
                    return False
                
                if start_level == end_level and start_level != "unknown":
                    # Intervalle homogène
                    self.log(f"  Intervalle homogène: {start_level}", "INFO")
                    all_segments.append({
                        'level': start_level,
                        'start_idx': start_idx,
                        'end_idx': end_idx,
                        'count': end_idx - start_idx + 1
                    })
                else:
                    # Intervalle hétérogène → dichotomie
                    self.log(f"  Transition détectée: {start_level} → {end_level}", "INFO")
                    sub_segments = self._dichotomy_segmentation(start_idx, end_idx, start_level)
                    all_segments.extend(sub_segments)
            
            # Consolider les segments
            self._consolidate_segments(all_segments)
            
            # Calculer les statistiques
            total_classified = sum(
                sum(seg.count for seg in segs) 
                for segs in self.level_segments.values()
            )
            
            self.stats = {
                'total_frames': total_frames,
                'interval_size': interval_size,
                'intervals_analyzed': len(intervals),
                'levels_detected': len(self.level_segments),
                'detected_levels': sorted(list(self.detected_levels)),
                'classifications_count': len(self.level_classifications),
                'total_classified': total_classified,
                'coverage': round(total_classified / total_frames * 100, 1) if total_frames > 0 else 0,
                'segments': {
                    level: [asdict(seg) for seg in segs]
                    for level, segs in self.level_segments.items()
                }
            }
            
            # Sauvegarder les résultats
            self._save_results()
            
            # Afficher le résumé
            self.log(f"✅ Segmentation terminée!", "INFO")
            self.log(f"   Niveaux détectés: {len(self.level_segments)}", "INFO")
            self.log(f"   Niveaux: {sorted(self.detected_levels)}", "INFO")
            self.log(f"   Classifications: {len(self.level_classifications)}", "INFO")
            self.log(f"   Couverture: {self.stats['coverage']}%", "INFO")
            
            # Créer dataset YOLO si demandé
            if self.level_config.create_yolo_dataset:
                self._create_yolo_dataset()
            
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
    
    def _save_results(self):
        """Sauvegarder les résultats"""
        output_dir = Path(self.level_config.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        results_path = output_dir / "segmentation_results.json"
        
        results = {
            'segmentation_method': 'smart_intervals_with_dichotomy',
            'source_dir': str(self.frames_dir),
            'timestamp': time.strftime("%Y-%m-%d %H:%M:%S"),
            'statistics': self.stats
        }
        
        try:
            with open(results_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            self.log(f"💾 Résultats sauvés: {results_path}", "INFO")
        except Exception as e:
            self.log(f"Erreur sauvegarde: {e}", "WARNING")
    
    def _create_yolo_dataset(self):
        """Créer le dataset YOLO à partir des segments"""
        if not self.level_segments:
            self.log("Aucun segment pour créer le dataset YOLO", "WARNING")
            return
        
        self.log("Création du dataset YOLO...", "INFO")
        
        output_dir = Path(self.level_config.output_dir) / "yolo_dataset"
        
        # Créer structure
        for split in ['train', 'val', 'test']:
            (output_dir / split / 'images').mkdir(parents=True, exist_ok=True)
            (output_dir / split / 'labels').mkdir(parents=True, exist_ok=True)
        
        # Collecter les images avec labels
        labeled_images = []
        level_to_id = {level: i for i, level in enumerate(sorted(self.detected_levels))}
        
        for level, segments in self.level_segments.items():
            class_id = level_to_id[level]
            
            for segment in segments:
                for idx in range(segment.start_idx, segment.end_idx + 1):
                    frame = self.all_frames[idx]
                    labeled_images.append({
                        'frame': frame,
                        'level': level,
                        'class_id': class_id
                    })
        
        # Mélanger et diviser
        random.shuffle(labeled_images)
        
        total = len(labeled_images)
        train_end = int(total * self.level_config.train_ratio)
        val_end = int(total * (self.level_config.train_ratio + self.level_config.val_ratio))
        
        splits = {
            'train': labeled_images[:train_end],
            'val': labeled_images[train_end:val_end],
            'test': labeled_images[val_end:]
        }
        
        self.log(f"Distribution: Train {len(splits['train'])} | Val {len(splits['val'])} | Test {len(splits['test'])}", "INFO")
        
        # Copier et annoter
        roi = self.level_config.world_roi
        center_x = (roi[0] + roi[2]) / 2
        center_y = (roi[1] + roi[3]) / 2
        width = roi[2] - roi[0]
        height = roi[3] - roi[1]
        
        for split_name, split_images in splits.items():
            for item in split_images:
                frame = item['frame']
                
                # Copier image
                dst_path = output_dir / split_name / 'images' / frame.filename
                shutil.copy2(frame.filepath, dst_path)
                
                # Créer annotation
                label_path = output_dir / split_name / 'labels' / (Path(frame.filename).stem + '.txt')
                with open(label_path, 'w') as f:
                    f.write(f"{item['class_id']} {center_x:.6f} {center_y:.6f} {width:.6f} {height:.6f}\n")
        
        # Créer data.yaml
        yaml_content = f"""# Mario Level Segmentation Dataset
path: {output_dir.absolute()}
train: train/images
val: val/images
test: test/images

nc: {len(level_to_id)}
names:
"""
        for level, class_id in sorted(level_to_id.items(), key=lambda x: x[1]):
            yaml_content += f"  {class_id}: '{level}'\n"
        
        with open(output_dir / 'data.yaml', 'w') as f:
            f.write(yaml_content)
        
        self.log(f"✅ Dataset YOLO créé: {output_dir}", "INFO")
    
    def cancel(self):
        """Annuler la tâche"""
        self.cancel_flag = True
        self.log("Annulation demandée...", "WARNING")
    
    def get_summary(self) -> str:
        """Résumé des résultats"""
        if not self.stats:
            return "Aucune statistique disponible"
        
        s = self.stats
        return f"""🎮 Segmentation Niveaux Mario:
• Total frames: {s['total_frames']:,}
• Niveaux détectés: {s['levels_detected']} ({', '.join(s['detected_levels'])})
• Classifications: {s['classifications_count']}
• Couverture: {s['coverage']}%"""