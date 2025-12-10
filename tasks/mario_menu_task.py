"""
Mario Menu Finder Task - Détection de l'écran WORLD 1-1 de Super Mario Bros
Analyse les frames pour trouver le début du jeu et créer un dataset nettoyé
"""

import os
import time
import json
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional

from .base_task import BaseTask, TaskStatus, TaskPriority

# Import conditionnel de OpenCV et NumPy
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class DetectionResult:
    """Résultat de détection pour une frame"""
    filename: str
    filepath: str
    position: int
    black_ratio: float
    text_ratio: float
    mean_brightness: float
    center_white: float
    hud_white: float
    final_score: float
    is_world_screen: bool


@dataclass
class MarioMenuConfig:
    """Configuration pour la détection du menu Mario"""
    # Seuils de détection
    score_threshold: float = 0.75
    black_threshold: float = 0.75  # % minimum de pixels noirs
    text_threshold: float = 0.02   # % minimum de texte blanc
    brightness_threshold: float = 80.0  # Luminosité max
    
    # Poids du scoring
    weight_black: float = 0.30
    weight_text: float = 0.25
    weight_brightness: float = 0.20
    weight_center: float = 0.15
    weight_hud: float = 0.10
    
    # Options de sortie
    output_suffix: str = "_cleaned"
    overwrite_existing: bool = False


class MarioMenuTask(BaseTask):
    """
    Tâche de détection de l'écran WORLD 1-1 de Super Mario Bros
    Trouve le début du jeu et crée un dataset nettoyé
    """
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    
    def __init__(self, priority: TaskPriority = TaskPriority.NORMAL):
        super().__init__(
            name="Détection Menu Mario",
            description="Trouve l'écran WORLD 1-1 et nettoie le dataset",
            priority=priority
        )
        
        self.frames_dir = None
        self.output_dir = None
        self.menu_config = MarioMenuConfig()
        self.cancel_flag = False
        self.dry_run = True
        
        # Résultats
        self.candidates: List[DetectionResult] = []
        self.best_candidate: Optional[DetectionResult] = None
        self.stats: Dict = {}
    
    def configure(self,
                  frames_dir: str,
                  output_dir: str = None,
                  score_threshold: float = 0.75,
                  dry_run: bool = True,
                  config: MarioMenuConfig = None):
        """
        Configurer la tâche
        
        Args:
            frames_dir: Dossier contenant les frames
            output_dir: Dossier de sortie (optionnel)
            score_threshold: Seuil de score pour la détection
            dry_run: Mode simulation (True) ou exécution (False)
            config: Configuration avancée optionnelle
        """
        self.frames_dir = Path(frames_dir)
        
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(f"{frames_dir}_cleaned")
        
        if config:
            self.menu_config = config
        else:
            self.menu_config = MarioMenuConfig(score_threshold=score_threshold)
        
        self.dry_run = dry_run
        
        self.config = {
            'frames_dir': str(self.frames_dir),
            'output_dir': str(self.output_dir),
            'score_threshold': score_threshold,
            'dry_run': dry_run,
            'menu_config': asdict(self.menu_config)
        }
    
    def validate_config(self) -> Tuple[bool, str]:
        """Valider la configuration"""
        if not CV2_AVAILABLE:
            return False, "OpenCV (cv2) n'est pas installé"
        
        if 'frames_dir' not in self.config:
            return False, "Dossier de frames non spécifié"
        
        if not self.frames_dir.exists():
            return False, f"Dossier non trouvé: {self.frames_dir}"
        
        # Compter les images
        image_count = sum(1 for f in self.frames_dir.iterdir() 
                         if f.suffix.lower() in self.IMAGE_EXTENSIONS)
        if image_count == 0:
            return False, "Aucune image trouvée dans le dossier"
        
        return True, f"Configuration valide ({image_count:,} images)"
    
    def _get_sorted_frames(self) -> List[Path]:
        """Récupérer les frames triées par ordre de création"""
        frames = []
        for f in self.frames_dir.iterdir():
            if f.suffix.lower() in self.IMAGE_EXTENSIONS:
                frames.append(f)
        
        # Trier par date de création
        frames.sort(key=lambda x: x.stat().st_ctime)
        return frames
    
    def _analyze_frame(self, image_path: Path) -> Optional[Dict]:
        """
        Analyser une frame pour détecter l'écran WORLD 1-1
        """
        try:
            image = cv2.imread(str(image_path))
            if image is None:
                return None
            
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            h, w = gray.shape
            total_pixels = gray.size
            
            # 1. Analyse du fond noir
            black_pixels = np.sum(gray < 50)
            black_ratio = black_pixels / total_pixels
            
            # 2. Analyse du texte blanc
            white_pixels = np.sum(gray > 150)
            text_ratio = white_pixels / total_pixels
            
            # 3. Luminosité moyenne
            mean_brightness = np.mean(gray)
            
            # 4. Zone centrale (pour "WORLD 1-1")
            center_region = gray[int(h*0.3):int(h*0.7), int(w*0.2):int(w*0.8)]
            center_white = np.sum(center_region > 150) / center_region.size if center_region.size > 0 else 0
            
            # 5. Zone HUD (haut)
            hud_region = gray[:int(h*0.25), :]
            hud_white = np.sum(hud_region > 150) / hud_region.size if hud_region.size > 0 else 0
            
            cfg = self.menu_config
            
            # Calcul des scores
            black_score = min(black_ratio * 1.33, 1.0) if black_ratio > cfg.black_threshold else 0.0
            text_score = min(text_ratio * 50, 1.0) if text_ratio > cfg.text_threshold else 0.0
            brightness_score = max(0, 1.0 - mean_brightness / cfg.brightness_threshold) if mean_brightness < cfg.brightness_threshold else 0.0
            center_score = min(center_white * 10, 1.0)
            hud_score = min(hud_white * 5, 1.0)
            
            # Score final pondéré
            final_score = (
                black_score * cfg.weight_black +
                text_score * cfg.weight_text +
                brightness_score * cfg.weight_brightness +
                center_score * cfg.weight_center +
                hud_score * cfg.weight_hud
            )
            
            # Critères de base
            is_world_screen = (
                black_ratio > cfg.black_threshold and
                text_ratio > cfg.text_threshold and
                mean_brightness < cfg.brightness_threshold
            )
            
            return {
                'filename': image_path.name,
                'filepath': str(image_path),
                'black_ratio': black_ratio,
                'text_ratio': text_ratio,
                'mean_brightness': mean_brightness,
                'center_white': center_white,
                'hud_white': hud_white,
                'final_score': final_score,
                'is_world_screen': is_world_screen,
                'width': w,
                'height': h
            }
            
        except Exception as e:
            self.log(f"Erreur analyse {image_path.name}: {e}", "WARNING")
            return None
    
    def execute(self) -> bool:
        """Exécuter la détection et le nettoyage"""
        try:
            self.update_status(TaskStatus.RUNNING, "Démarrage de la détection...")
            
            start_time = time.time()
            
            # Récupérer les frames
            self.log("Récupération des frames...", "INFO")
            frames = self._get_sorted_frames()
            total_frames = len(frames)
            
            self.log(f"Trouvé {total_frames:,} frames à analyser", "INFO")
            
            if total_frames == 0:
                self.update_status(TaskStatus.FAILED, "Aucune frame trouvée")
                return False
            
            # Scanner toutes les frames
            self.log("Scan des frames pour détecter WORLD 1-1...", "INFO")
            self.update_progress(10, "Analyse en cours...")
            
            self.candidates = []
            threshold = self.menu_config.score_threshold
            
            for i, frame_path in enumerate(frames):
                if self.cancel_flag:
                    self.update_status(TaskStatus.CANCELLED, "Annulé")
                    return False
                
                result = self._analyze_frame(frame_path)
                
                if result and result['final_score'] >= threshold:
                    detection = DetectionResult(
                        filename=result['filename'],
                        filepath=result['filepath'],
                        position=i + 1,
                        black_ratio=result['black_ratio'],
                        text_ratio=result['text_ratio'],
                        mean_brightness=result['mean_brightness'],
                        center_white=result['center_white'],
                        hud_white=result['hud_white'],
                        final_score=result['final_score'],
                        is_world_screen=result['is_world_screen']
                    )
                    self.candidates.append(detection)
                    
                    self.log(f"✅ Candidat #{i+1}: {result['filename']} (score: {result['final_score']*100:.1f}%)", "INFO")
                
                # Progression
                if i % 500 == 0:
                    progress = 10 + int((i / total_frames) * 50)
                    self.update_progress(progress, f"Analyse {i:,}/{total_frames:,}")
            
            # Résultats du scan
            self.log(f"Scan terminé: {len(self.candidates)} candidats trouvés", "INFO")
            
            if not self.candidates:
                self.log(f"⚠️ Aucun candidat avec score ≥ {threshold*100:.0f}%", "WARNING")
                self.log("Conseil: essayez un seuil plus bas (ex: 0.60)", "INFO")
                
                self.stats = {
                    'total_frames': total_frames,
                    'candidates_found': 0,
                    'threshold_used': threshold,
                    'detection_successful': False
                }
                
                self._save_report()
                self.update_progress(100, "⚠️ Aucun candidat trouvé")
                self.update_status(TaskStatus.COMPLETED, "Aucun écran WORLD 1-1 détecté")
                return True
            
            # Sélectionner le meilleur candidat (premier dans l'ordre chronologique)
            self.best_candidate = self.candidates[0]
            start_position = self.best_candidate.position
            
            self.log(f"🎯 Meilleur candidat: position #{start_position} - {self.best_candidate.filename}", "INFO")
            self.log(f"   Score: {self.best_candidate.final_score*100:.1f}%", "INFO")
            self.log(f"   Noir: {self.best_candidate.black_ratio*100:.1f}%, Texte: {self.best_candidate.text_ratio*100:.1f}%", "INFO")
            
            # Calculer les statistiques
            files_to_skip = start_position - 1
            files_to_copy = total_frames - files_to_skip
            cleanup_percentage = (files_to_skip / total_frames) * 100
            
            self.stats = {
                'total_frames': total_frames,
                'candidates_found': len(self.candidates),
                'threshold_used': threshold,
                'detection_successful': True,
                'best_candidate': asdict(self.best_candidate),
                'start_position': start_position,
                'files_to_skip': files_to_skip,
                'files_to_copy': files_to_copy,
                'cleanup_percentage': cleanup_percentage
            }
            
            self.log(f"📊 Frames à ignorer: {files_to_skip:,} ({cleanup_percentage:.1f}%)", "INFO")
            self.log(f"📊 Frames à garder: {files_to_copy:,}", "INFO")
            
            # Mode dry run ou exécution
            if self.dry_run:
                self.log("🔍 Mode DRY RUN - Aucun fichier copié", "INFO")
                self.stats['dry_run'] = True
                self.stats['files_copied'] = 0
            else:
                self.log("📁 Création du dataset nettoyé...", "INFO")
                self.update_progress(70, "Copie des fichiers...")
                
                # Créer le dossier de sortie
                if self.output_dir.exists():
                    if self.menu_config.overwrite_existing:
                        shutil.rmtree(self.output_dir)
                        self.log(f"Dossier existant supprimé: {self.output_dir}", "INFO")
                    else:
                        self.log(f"⚠️ Le dossier existe déjà: {self.output_dir}", "WARNING")
                
                self.output_dir.mkdir(parents=True, exist_ok=True)
                
                # Copier les fichiers
                copied = 0
                failed = 0
                frames_to_copy = frames[start_position-1:]
                
                for i, frame_path in enumerate(frames_to_copy):
                    if self.cancel_flag:
                        self.update_status(TaskStatus.CANCELLED, "Annulé")
                        return False
                    
                    try:
                        dest_path = self.output_dir / frame_path.name
                        shutil.copy2(frame_path, dest_path)
                        copied += 1
                        
                        if i % 1000 == 0:
                            progress = 70 + int((i / len(frames_to_copy)) * 25)
                            self.update_progress(progress, f"Copie {i:,}/{len(frames_to_copy):,}")
                    except Exception as e:
                        failed += 1
                        self.log(f"Erreur copie {frame_path.name}: {e}", "WARNING")
                
                self.stats['dry_run'] = False
                self.stats['files_copied'] = copied
                self.stats['files_failed'] = failed
                self.stats['output_dir'] = str(self.output_dir)
                
                self.log(f"✅ Dataset créé: {copied:,} fichiers copiés", "INFO")
                if failed > 0:
                    self.log(f"⚠️ {failed} erreurs de copie", "WARNING")
            
            # Sauvegarder le rapport
            self._save_report()
            
            elapsed = time.time() - start_time
            self.log(f"⏱️ Temps total: {elapsed:.1f}s", "INFO")
            
            self.update_progress(100, "✅ Détection terminée")
            self.update_status(TaskStatus.COMPLETED, "Détection terminée")
            
            return True
            
        except Exception as e:
            self.error_message = str(e)
            self.update_status(TaskStatus.FAILED, str(e))
            self.log(f"❌ Erreur: {str(e)}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False
    
    def _save_report(self):
        """Sauvegarder le rapport JSON"""
        report_path = self.output_dir.parent / "mario_menu_report.json" if not self.dry_run else self.frames_dir / "mario_menu_report.json"
        
        report = {
            'analysis_info': {
                'frames_dir': str(self.frames_dir),
                'output_dir': str(self.output_dir),
                'timestamp': time.strftime("%Y-%m-%d %H:%M:%S")
            },
            'config': asdict(self.menu_config),
            'statistics': self.stats,
            'all_candidates': [asdict(c) for c in self.candidates[:50]]  # Top 50
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
        if not s.get('detection_successful'):
            return f"❌ Aucun écran WORLD 1-1 détecté (seuil: {s.get('threshold_used', 0)*100:.0f}%)"
        
        return f"""🎮 Détection Mario Menu:
• Total frames: {s['total_frames']:,}
• Candidats trouvés: {s['candidates_found']}
• Position début jeu: #{s['start_position']}
• Frames ignorées: {s['files_to_skip']:,} ({s['cleanup_percentage']:.1f}%)
• Frames gameplay: {s['files_to_copy']:,}
• Mode: {'Simulation' if s.get('dry_run') else 'Exécuté'}"""