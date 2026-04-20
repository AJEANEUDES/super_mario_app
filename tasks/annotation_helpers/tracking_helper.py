"""
Tracking Helper - Propagation automatique avec suivi d'objets
Version améliorée avec compensation de scrolling pour les jeux vidéo

Propage les annotations d'un frame aux frames suivants en utilisant
le suivi d'objets (tracking) et la compensation de mouvement de caméra.
"""

import os
from typing import List, Optional, Dict, Any, Tuple
from dataclasses import dataclass, field
import cv2
from .base_helper import BaseAnnotationHelper, HelperInfo, HelperResult, HelperStatus

# Imports optionnels
try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class TrackedObject:
    """Objet suivi"""
    class_id: int
    class_name: str
    bbox: Tuple[int, int, int, int]  # x, y, w, h
    original_bbox: Tuple[int, int, int, int]  # Position originale
    tracker: Any = None
    is_static: bool = True  # Objet statique (décor) ou dynamique (personnage)
    is_lost: bool = False
    lost_frames: int = 0
    cumulative_offset: Tuple[int, int] = (0, 0)  # Décalage cumulé


@dataclass 
class TrackingConfig:
    """Configuration du tracking"""
    mode: str = "scroll_compensation"  # "scroll_compensation", "pure_tracking", "static_only", "manual_offset"
    tracker_type: str = "KCF"  # "CSRT", "KCF", "MOSSE", "MIL"
    max_frames: int = 50
    stop_on_scene_change: bool = True
    scene_change_threshold: float = 0.3
    lost_threshold: int = 5
    save_after_each: bool = True
    
    # Options de compensation de scrolling
    use_scroll_compensation: bool = True
    scroll_region_height: int = 50  # Hauteur de la région pour détecter le scroll
    scroll_region_y: int = 100  # Position Y de la région (éviter le HUD)
    reinit_every_n_frames: int = 10  # Réinitialiser les trackers tous les N frames
    
    # Décalage manuel (pixels par frame) - NOUVEAU
    manual_offset_x: float = 0.0  # Décalage horizontal par frame (positif = scroll vers droite)
    manual_offset_y: float = 0.0  # Décalage vertical par frame
    use_manual_offset: bool = False  # Utiliser le décalage manuel au lieu de la détection auto
    
    # Classes considérées comme statiques (ne bougent pas dans le monde du jeu)
    static_classes: List[str] = field(default_factory=lambda: [
        'brick_block', 'mystery_block', 'undestructible_block', 'pipe',
        'ground', 'platform', 'cloud', 'bush', 'hill', 'castle', 'flag',
        'coin', 'block', 'brick', 'floor', 'wall', 'background'
    ])


class TrackingHelper(BaseAnnotationHelper):
    """
    Helper de propagation automatique avec tracking et compensation de scrolling.
    
    Modes disponibles:
    - scroll_compensation: Détecte le scrolling et l'applique (recommandé pour jeux)
    - pure_tracking: Tracking classique sans compensation
    - static_only: Applique uniquement le décalage global (pour objets statiques)
    """
    
    TRACKER_TYPES = {
        "KCF": "Rapide et équilibré - Recommandé",
        "CSRT": "Plus précis mais plus lent",
        "MOSSE": "Très rapide, moins précis",
        "MIL": "Résistant aux occultations"
    }
    
    MODES = {
        "scroll_compensation": "Compensation auto de scrolling",
        "manual_offset": "Décalage manuel (recommandé SMB)",
        "pure_tracking": "Tracking classique",
        "static_only": "Décalage global uniquement"
    }
    
    def __init__(self):
        super().__init__()
        self.task = None
        self.config = TrackingConfig()
        self.tracked_objects: List[TrackedObject] = []
        self.prev_frame = None
        self.prev_gray = None
        self.prev_hist = None
        self.total_scroll_x = 0
        self.total_scroll_y = 0
    
    @staticmethod
    def get_info() -> HelperInfo:
        requirements = []
        if not CV2_AVAILABLE:
            requirements.append("opencv-contrib-python")
        
        return HelperInfo(
            id="tracking",
            name="Propagation avec tracking",
            icon="🎬",
            short_description="Suivre les objets entre les frames",
            long_description="""
La propagation avec tracking propage automatiquement vos annotations 
aux frames suivants.

**Version améliorée pour les jeux vidéo!**

Cette version inclut la **compensation de scrolling** qui détecte 
le mouvement de caméra (scrolling horizontal/vertical) et l'applique 
automatiquement aux objets statiques (blocs, décor).

**Modes disponibles:**
- **Compensation de scrolling**: Idéal pour les jeux avec scrolling (SMB, etc.)
- **Tracking classique**: Pour les vidéos sans scrolling
- **Décalage global**: Applique uniquement le mouvement de caméra

**Comment ça marche:**
1. Le système détecte le scrolling entre chaque frame
2. Les objets statiques (blocs, tuyaux) sont déplacés avec le scrolling
3. Les objets dynamiques (Mario, ennemis) sont suivis individuellement

**Conseil:** Pour Super Mario Bros, utilisez le mode "Compensation de scrolling"
avec réinitialisation tous les 10 frames.
            """.strip(),
            requirements=requirements,
            estimated_speedup="20-50x plus rapide",
            best_for=[
                "Jeux avec scrolling (platformers)",
                "Éléments statiques (décor, blocs)",
                "Séquences de gameplay"
            ],
            limitations=[
                "Nécessite OpenCV contrib",
                "Moins efficace pour rotations",
                "Peut dériver sur longues séquences"
            ]
        )
    
    @staticmethod
    def is_available() -> bool:
        """Vérifier si OpenCV avec les trackers est disponible"""
        if not CV2_AVAILABLE:
            return False
        
        # Vérifier si au moins un tracker est disponible
        has_tracker = False
        
        if hasattr(cv2, 'legacy'):
            if hasattr(cv2.legacy, 'TrackerKCF_create') or hasattr(cv2.legacy, 'TrackerCSRT_create'):
                has_tracker = True
        
        if hasattr(cv2, 'TrackerKCF_create') or hasattr(cv2, 'TrackerCSRT_create'):
            has_tracker = True
        
        if hasattr(cv2, 'TrackerKCF') or hasattr(cv2, 'TrackerCSRT'):
            has_tracker = True
        
        return has_tracker
    
    @staticmethod
    def get_install_help() -> str:
        return (
            "Pour utiliser le tracking, installez opencv-contrib-python:\n\n"
            "pip uninstall opencv-python opencv-python-headless\n"
            "pip install opencv-contrib-python\n\n"
            "La version contrib inclut les trackers (KCF, CSRT, etc.)"
        )
    
    def configure(self, task, **kwargs) -> bool:
        """Configurer le helper"""
        self.task = task
        
        self.config.mode = kwargs.get('mode', 'scroll_compensation')
        self.config.tracker_type = kwargs.get('tracker_type', 'KCF')
        self.config.max_frames = kwargs.get('max_frames', 50)
        self.config.stop_on_scene_change = kwargs.get('stop_on_scene_change', True)
        self.config.scene_change_threshold = kwargs.get('scene_change_threshold', 0.3)
        self.config.lost_threshold = kwargs.get('lost_threshold', 5)
        self.config.save_after_each = kwargs.get('save_after_each', True)
        self.config.use_scroll_compensation = kwargs.get('use_scroll_compensation', True)
        self.config.reinit_every_n_frames = kwargs.get('reinit_every_n_frames', 10)
        
        # Décalage manuel
        self.config.manual_offset_x = kwargs.get('manual_offset_x', 0.0)
        self.config.manual_offset_y = kwargs.get('manual_offset_y', 0.0)
        self.config.use_manual_offset = kwargs.get('use_manual_offset', False)
        
        # Si mode manual_offset, activer use_manual_offset
        if self.config.mode == 'manual_offset':
            self.config.use_manual_offset = True
        
        if 'static_classes' in kwargs:
            self.config.static_classes = kwargs['static_classes']
        
        return True
    
    def _create_tracker(self, tracker_type: str):
        """Créer un tracker OpenCV (compatible avec différentes versions)"""
        if not CV2_AVAILABLE:
            return None
        
        tracker = None
        
        # Méthode 1: cv2.legacy (OpenCV 4.5+)
        if hasattr(cv2, 'legacy'):
            try:
                if tracker_type == "CSRT":
                    tracker = cv2.legacy.TrackerCSRT_create()
                elif tracker_type == "KCF":
                    tracker = cv2.legacy.TrackerKCF_create()
                elif tracker_type == "MOSSE":
                    tracker = cv2.legacy.TrackerMOSSE_create()
                elif tracker_type == "MIL":
                    tracker = cv2.legacy.TrackerMIL_create()
                
                if tracker:
                    return tracker
            except Exception as e:
                pass
        
        # Méthode 2: cv2.TrackerXXX_create
        try:
            if tracker_type == "CSRT" and hasattr(cv2, 'TrackerCSRT_create'):
                return cv2.TrackerCSRT_create()
            elif tracker_type == "KCF" and hasattr(cv2, 'TrackerKCF_create'):
                return cv2.TrackerKCF_create()
            elif tracker_type == "MOSSE" and hasattr(cv2, 'TrackerMOSSE_create'):
                return cv2.TrackerMOSSE_create()
            elif tracker_type == "MIL" and hasattr(cv2, 'TrackerMIL_create'):
                return cv2.TrackerMIL_create()
        except Exception:
            pass
        
        # Méthode 3: cv2.TrackerXXX.create()
        try:
            if tracker_type == "CSRT" and hasattr(cv2, 'TrackerCSRT'):
                return cv2.TrackerCSRT.create()
            elif tracker_type == "KCF" and hasattr(cv2, 'TrackerKCF'):
                return cv2.TrackerKCF.create()
            elif tracker_type == "MIL" and hasattr(cv2, 'TrackerMIL'):
                return cv2.TrackerMIL.create()
        except Exception:
            pass
        
        # Fallback
        for fallback_type in ["KCF", "CSRT", "MIL"]:
            if hasattr(cv2, 'legacy'):
                try:
                    creator = getattr(cv2.legacy, f'Tracker{fallback_type}_create', None)
                    if creator:
                        return creator()
                except:
                    pass
        
        return None
    
    def _detect_scroll(self, prev_frame, curr_frame) -> Tuple[int, int]:
        """
        Détecter le scrolling entre deux frames.
        Retourne (dx, dy) le décalage en pixels.
        """
        if prev_frame is None or curr_frame is None:
            return (0, 0)
        
        # Convertir en niveaux de gris
        if len(prev_frame.shape) == 3:
            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        else:
            prev_gray = prev_frame
            
        if len(curr_frame.shape) == 3:
            curr_gray = cv2.cvtColor(curr_frame, cv2.COLOR_BGR2GRAY)
        else:
            curr_gray = curr_frame
        
        h, w = prev_gray.shape
        
        # Utiliser une région stable pour détecter le scroll
        # Éviter le HUD en haut et le sol en bas
        y1 = min(self.config.scroll_region_y, h // 4)
        y2 = min(y1 + self.config.scroll_region_height, h - 50)
        
        if y2 <= y1:
            y1, y2 = h // 4, h // 2
        
        # Extraire les régions
        prev_region = prev_gray[y1:y2, :]
        curr_region = curr_gray[y1:y2, :]
        
        # Méthode 1: Template matching pour détecter le décalage horizontal
        # Prendre le centre de la région précédente comme template
        margin = w // 4
        template = prev_region[:, margin:w-margin]
        
        if template.shape[1] < 50:
            return (0, 0)
        
        try:
            # Chercher le template dans l'image courante
            result = cv2.matchTemplate(curr_region, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)
            
            if max_val > 0.7:  # Bonne correspondance
                dx = max_loc[0] - margin
                
                # Pour le décalage vertical, on peut faire de même
                # mais généralement dans les platformers c'est surtout horizontal
                dy = 0
                
                return (dx, dy)
        except Exception as e:
            self._log(f"⚠️ Erreur détection scroll: {e}")
        
        return (0, 0)
    
    def _detect_scene_change(self, frame) -> bool:
        """Détecter un changement de scène"""
        if not self.config.stop_on_scene_change:
            return False
        
        hist = cv2.calcHist([frame], [0, 1, 2], None, [8, 8, 8], [0, 256, 0, 256, 0, 256])
        hist = cv2.normalize(hist, hist).flatten()
        
        if self.prev_hist is not None:
            diff = cv2.compareHist(self.prev_hist, hist, cv2.HISTCMP_BHATTACHARYYA)
            self.prev_hist = hist
            
            if diff > self.config.scene_change_threshold:
                self._log(f"🎬 Changement de scène détecté (diff={diff:.3f})")
                return True
        else:
            self.prev_hist = hist
        
        return False
    
    def _is_static_class(self, class_name: str) -> bool:
        """Vérifier si une classe est considérée comme statique"""
        class_name_lower = class_name.lower()
        for static in self.config.static_classes:
            if static.lower() in class_name_lower or class_name_lower in static.lower():
                return True
        return False
    
    def _reinit_tracker(self, obj: TrackedObject, frame) -> bool:
        """Réinitialiser le tracker d'un objet"""
        try:
            obj.tracker = self._create_tracker(self.config.tracker_type)
            if obj.tracker:
                obj.tracker.init(frame, obj.bbox)
                obj.lost_frames = 0
                return True
        except Exception as e:
            self._log(f"⚠️ Erreur réinit tracker: {e}")
        return False
    
    def execute(self) -> HelperResult:
        """Exécuter la propagation avec tracking"""
        if not CV2_AVAILABLE:
            return HelperResult(
                success=False,
                message="OpenCV non installé"
            )
        
        if not self.task or not self.task.images:
            return HelperResult(
                success=False,
                message="Aucune image chargée"
            )
        
        # Vérifier qu'il y a des annotations sur le frame courant
        current_img = self.task.get_current_image()
        if not current_img or not current_img.boxes:
            return HelperResult(
                success=False,
                message="Annotez d'abord le frame courant"
            )
        
        start_index = self.task.current_index
        remaining = len(self.task.images) - start_index - 1
        frames_to_process = min(self.config.max_frames, remaining)
        
        if frames_to_process <= 0:
            return HelperResult(
                success=False,
                message="Pas de frames suivants à propager"
            )
        
        self.status = HelperStatus.RUNNING
        self._log(f"🎬 Mode: {self.config.mode} | {len(current_img.boxes)} objets sur {frames_to_process} frames")
        
        # Charger le premier frame
        first_frame = cv2.imread(current_img.image_path)
        if first_frame is None:
            return HelperResult(
                success=False,
                message=f"Impossible de charger: {current_img.image_path}"
            )
        
        self.prev_frame = first_frame.copy()
        self.prev_hist = None
        self.total_scroll_x = 0
        self.total_scroll_y = 0
        
        # Initialiser les objets à suivre
        self.tracked_objects = []
        for box in current_img.boxes:
            bbox = (box.x, box.y, box.width, box.height)
            is_static = self._is_static_class(box.class_name)
            
            tracker = None
            if self.config.mode != "static_only":
                tracker = self._create_tracker(self.config.tracker_type)
                if tracker:
                    try:
                        tracker.init(first_frame, bbox)
                    except Exception as e:
                        self._log(f"⚠️ Erreur init tracker pour {box.class_name}: {e}")
                        tracker = None
            
            self.tracked_objects.append(TrackedObject(
                class_id=box.class_id,
                class_name=box.class_name,
                bbox=bbox,
                original_bbox=bbox,
                tracker=tracker,
                is_static=is_static,
                cumulative_offset=(0, 0)
            ))
            
            status = "statique" if is_static else "dynamique"
            self._log(f"  • {box.class_name}: {status}")
        
        # Propager aux frames suivants
        propagated = 0
        stopped_reason = None
        
        for i in range(1, frames_to_process + 1):
            if self._check_cancelled():
                self.status = HelperStatus.CANCELLED
                stopped_reason = "Annulé"
                break
            
            frame_index = start_index + i
            self._update_progress(i / frames_to_process, f"Frame {frame_index + 1}")
            
            # Charger le frame
            img = self.task.images[frame_index]
            frame = cv2.imread(img.image_path)
            
            if frame is None:
                self._log(f"⚠️ Impossible de charger frame {frame_index}")
                continue
            
            # Détecter changement de scène
            if self._detect_scene_change(frame):
                stopped_reason = "Changement de scène"
                break
            
            # Détecter le scrolling (automatique ou manuel)
            scroll_dx, scroll_dy = (0, 0)
            
            if self.config.mode == "manual_offset" or self.config.use_manual_offset:
                # Utiliser le décalage manuel spécifié par l'utilisateur
                # Accumuler le décalage fractionnaire
                if not hasattr(self, '_accumulated_offset_x'):
                    self._accumulated_offset_x = 0.0
                    self._accumulated_offset_y = 0.0
                
                self._accumulated_offset_x += self.config.manual_offset_x
                self._accumulated_offset_y += self.config.manual_offset_y
                
                # Extraire la partie entière
                scroll_dx = int(self._accumulated_offset_x)
                scroll_dy = int(self._accumulated_offset_y)
                
                # Garder la partie fractionnaire
                self._accumulated_offset_x -= scroll_dx
                self._accumulated_offset_y -= scroll_dy
                
                if i == 1:
                    self._log(f"  📐 Décalage manuel: {self.config.manual_offset_x:.1f}px/frame")
                    
            elif self.config.use_scroll_compensation and self.config.mode == "scroll_compensation":
                scroll_dx, scroll_dy = self._detect_scroll(self.prev_frame, frame)
                
                if i <= 3:  # Log les premiers frames pour debug
                    self._log(f"  📜 Frame {i}: scroll détecté dx={scroll_dx}, dy={scroll_dy}")
            
            self.total_scroll_x += scroll_dx
            self.total_scroll_y += scroll_dy
            
            # Réinitialiser les trackers périodiquement
            should_reinit = (i % self.config.reinit_every_n_frames == 0)
            
            # Mettre à jour chaque objet
            new_boxes = []
            active_count = 0
            frame_h, frame_w = frame.shape[:2]
            
            for obj in self.tracked_objects:
                if obj.is_lost:
                    continue
                
                new_bbox = None
                
                # Modes qui utilisent le décalage pour objets statiques
                use_offset_mode = (
                    self.config.mode == "static_only" or 
                    self.config.mode == "manual_offset" or
                    (self.config.mode == "scroll_compensation" and obj.is_static)
                )
                
                if use_offset_mode:
                    # Appliquer le décalage de scroll
                    x, y, w, h = obj.bbox
                    new_x = x - scroll_dx
                    new_y = y - scroll_dy
                    
                    # Vérifier les limites (permettre sortie partielle)
                    # L'objet est perdu seulement s'il est complètement hors écran
                    if new_x + w > 0 and new_x < frame_w and new_y + h > 0 and new_y < frame_h:
                        # Ajuster si partiellement hors écran
                        if new_x < 0:
                            w = w + new_x
                            new_x = 0
                        if new_y < 0:
                            h = h + new_y
                            new_y = 0
                        if new_x + w > frame_w:
                            w = frame_w - new_x
                        if new_y + h > frame_h:
                            h = frame_h - new_y
                        
                        if w > 10 and h > 10:  # Garder seulement si taille suffisante
                            new_bbox = (int(new_x), int(new_y), int(w), int(h))
                            obj.bbox = (int(x - scroll_dx), int(y - scroll_dy), obj.bbox[2], obj.bbox[3])  # Garder taille originale pour prochain calcul
                        else:
                            obj.is_lost = True
                            self._log(f"  ⚠️ {obj.class_name} trop petit")
                    else:
                        obj.is_lost = True
                        self._log(f"  ⚠️ {obj.class_name} sorti de l'écran (x={new_x})")
                        continue
                        
                elif self.config.mode == "scroll_compensation" and not obj.is_static:
                    # Mode scroll + tracking pour objets dynamiques
                    if obj.tracker:
                        try:
                            success, tracked_bbox = obj.tracker.update(frame)
                            if success:
                                x, y, w, h = [int(v) for v in tracked_bbox]
                                if w > 5 and h > 5 and x >= 0 and y >= 0:
                                    new_bbox = (x, y, w, h)
                                    obj.bbox = new_bbox
                                else:
                                    obj.lost_frames += 1
                            else:
                                obj.lost_frames += 1
                        except:
                            obj.lost_frames += 1
                    else:
                        obj.lost_frames += 1
                        
                elif self.config.mode == "pure_tracking":
                    # Mode tracking pur
                    if obj.tracker:
                        try:
                            success, tracked_bbox = obj.tracker.update(frame)
                            if success:
                                x, y, w, h = [int(v) for v in tracked_bbox]
                                if w > 5 and h > 5:
                                    new_bbox = (x, y, w, h)
                                    obj.bbox = new_bbox
                                else:
                                    obj.lost_frames += 1
                            else:
                                obj.lost_frames += 1
                        except:
                            obj.lost_frames += 1
                
                # Réinitialiser le tracker si nécessaire
                if should_reinit and obj.tracker and new_bbox:
                    self._reinit_tracker(obj, frame)
                
                # Vérifier si l'objet est perdu
                if obj.lost_frames >= self.config.lost_threshold:
                    obj.is_lost = True
                    self._log(f"  ⚠️ {obj.class_name} perdu")
                    continue
                
                if new_bbox:
                    new_boxes.append({
                        'class_id': obj.class_id,
                        'x': int(new_bbox[0]),
                        'y': int(new_bbox[1]),
                        'w': int(new_bbox[2]),
                        'h': int(new_bbox[3])
                    })
                    active_count += 1
            
            # Vérifier si tous les objets sont perdus
            if active_count == 0:
                stopped_reason = "Tous les objets perdus"
                break
            
            # Ajouter les annotations
            self.task.current_index = frame_index
            self.task.clear_annotations()
            
            for box in new_boxes:
                self.task.add_annotation(
                    box['class_id'],
                    box['x'], box['y'],
                    box['w'], box['h']
                )
            
            # Sauvegarder
            if self.config.save_after_each:
                self.task.save_current_annotations()
            
            self.prev_frame = frame.copy()
            propagated += 1
        
        # Revenir au frame de départ
        self.task.current_index = start_index
        
        self.status = HelperStatus.COMPLETED if not self._check_cancelled() else HelperStatus.CANCELLED
        
        message = f"Propagation: {propagated} frames"
        if stopped_reason:
            message += f" ({stopped_reason})"
        
        return HelperResult(
            success=propagated > 0,
            message=message,
            processed=propagated,
            skipped=frames_to_process - propagated,
            details={
                'start_index': start_index,
                'end_index': start_index + propagated,
                'stopped_reason': stopped_reason,
                'total_scroll': (self.total_scroll_x, self.total_scroll_y),
                'objects_tracked': len(self.tracked_objects),
                'objects_lost': sum(1 for obj in self.tracked_objects if obj.is_lost),
                'mode': self.config.mode
            }
        )
    
    def get_tracker_types(self) -> Dict[str, str]:
        """Retourne les types de trackers disponibles"""
        return self.TRACKER_TYPES
    
    def get_modes(self) -> Dict[str, str]:
        """Retourne les modes disponibles"""
        return self.MODES