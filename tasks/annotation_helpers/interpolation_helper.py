"""
Interpolation Helper - Interpolation interactive entre frames annotés

Permet d'annoter le frame de début et le frame de fin, puis d'interpoler
automatiquement les positions des objets entre les deux.

Version interactive: détecte les objets qui apparaissent/disparaissent
et demande à l'utilisateur d'annoter les frames intermédiaires.
"""

import os
from typing import List, Optional, Dict, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

from .base_helper import BaseAnnotationHelper, HelperInfo, HelperResult, HelperStatus


class MatchStatus(Enum):
    MATCHED = "matched"          # Objet présent début ET fin
    DISAPPEARED = "disappeared"  # Objet présent début, absent fin
    APPEARED = "appeared"        # Objet absent début, présent fin


@dataclass
class InterpolatedObject:
    """Objet à interpoler"""
    class_id: int
    class_name: str
    status: MatchStatus
    start_bbox: Optional[Tuple[int, int, int, int]] = None  # x, y, w, h au frame de début
    end_bbox: Optional[Tuple[int, int, int, int]] = None    # x, y, w, h au frame de fin
    start_frame: int = 0        # Frame où l'objet commence à exister
    end_frame: int = 0          # Frame où l'objet cesse d'exister
    intermediate_bbox: Optional[Tuple[int, int, int, int]] = None  # Position intermédiaire
    intermediate_frame: Optional[int] = None  # Frame intermédiaire annoté


@dataclass
class InterpolationConfig:
    """Configuration de l'interpolation"""
    start_frame: int = 0
    end_frame: int = 0
    interpolation_type: str = "linear"
    save_after_each: bool = True
    overwrite_existing: bool = True


class InterpolationHelper(BaseAnnotationHelper):
    """
    Helper d'interpolation interactive entre frames annotés.
    
    Workflow:
    1. L'utilisateur annote le frame de départ
    2. L'utilisateur annote le frame de fin
    3. Le système identifie les objets matchés, apparus et disparus
    4. Pour les objets apparus/disparus, le système demande d'annoter un frame intermédiaire
    5. L'interpolation est faite en segments
    """
    
    def __init__(self):
        super().__init__()
        self.task = None
        self.config = InterpolationConfig()
        self.start_annotations: List[Dict] = []
        self.end_annotations: List[Dict] = []
        self.matched_objects: List[InterpolatedObject] = []
        self.estimated_scroll: int = 0
        
        # Callbacks pour l'interaction avec l'UI
        self.on_need_intermediate_frame: Optional[Callable] = None
    
    @staticmethod
    def get_info() -> HelperInfo:
        return HelperInfo(
            id="interpolation",
            name="Interpolation interactive",
            icon="📐",
            short_description="Interpoler les positions entre frames annotés",
            long_description="""
L'interpolation interactive est la méthode la plus fiable pour les jeux 2D.

**Comment ça marche:**
1. Annotez le frame de DÉBUT (tous les objets visibles)
2. Annotez le frame de FIN (tous les objets visibles)
3. Le système détecte les objets qui apparaissent/disparaissent
4. Pour chaque nouvel objet, annotez le frame où il APPARAÎT
5. L'interpolation est calculée automatiquement

**Avantages:**
- Gère les objets qui entrent/sortent de l'écran
- Plus précis que le tracking
- Contrôle total sur les points clés
            """.strip(),
            requirements=[],
            estimated_speedup="10-30x plus rapide",
            best_for=[
                "Jeux 2D avec scrolling",
                "Objets qui apparaissent/disparaissent",
                "Séquences de 20-100 frames"
            ],
            limitations=[
                "Nécessite d'annoter plusieurs frames clés",
                "Mouvement supposé linéaire entre les clés"
            ]
        )
    
    @staticmethod
    def is_available() -> bool:
        return True
    
    def configure(self, task, **kwargs) -> bool:
        """Configurer le helper"""
        self.task = task
        
        self.config.start_frame = kwargs.get('start_frame', 0)
        self.config.end_frame = kwargs.get('end_frame', 0)
        self.config.interpolation_type = kwargs.get('interpolation_type', 'linear')
        self.config.save_after_each = kwargs.get('save_after_each', True)
        self.config.overwrite_existing = kwargs.get('overwrite_existing', True)
        
        return True
    
    def set_start_frame(self, frame_index: int) -> bool:
        """Définir le frame de début et capturer ses annotations"""
        if not self.task or frame_index >= len(self.task.images):
            return False
        
        self.config.start_frame = frame_index
        img = self.task.images[frame_index]
        
        self.start_annotations = []
        for box in img.boxes:
            self.start_annotations.append({
                'class_id': box.class_id,
                'class_name': box.class_name,
                'x': box.x,
                'y': box.y,
                'w': box.width,
                'h': box.height
            })
        
        self._log(f"📍 Frame de début: {frame_index} ({len(self.start_annotations)} objets)")
        return True
    
    def set_end_frame(self, frame_index: int) -> bool:
        """Définir le frame de fin et capturer ses annotations"""
        if not self.task or frame_index >= len(self.task.images):
            return False
        
        self.config.end_frame = frame_index
        img = self.task.images[frame_index]
        
        self.end_annotations = []
        for box in img.boxes:
            self.end_annotations.append({
                'class_id': box.class_id,
                'class_name': box.class_name,
                'x': box.x,
                'y': box.y,
                'w': box.width,
                'h': box.height
            })
        
        self._log(f"📍 Frame de fin: {frame_index} ({len(self.end_annotations)} objets)")
        return True
    
    def _estimate_scroll(self) -> int:
        """Estimer le scrolling horizontal entre début et fin"""
        scroll_estimates = []
        
        for start_obj in self.start_annotations:
            for end_obj in self.end_annotations:
                if end_obj['class_id'] != start_obj['class_id']:
                    continue
                
                # Si même taille et Y similaire, c'est probablement le même objet
                dy = abs(end_obj['y'] - start_obj['y'])
                dw = abs(end_obj['w'] - start_obj['w'])
                dh = abs(end_obj['h'] - start_obj['h'])
                
                if dy < 50 and dw < 20 and dh < 20:
                    dx = start_obj['x'] - end_obj['x']
                    scroll_estimates.append(dx)
        
        if scroll_estimates:
            scroll_estimates.sort()
            self.estimated_scroll = scroll_estimates[len(scroll_estimates) // 2]
            self._log(f"  📜 Scrolling estimé: {self.estimated_scroll} px")
        else:
            self.estimated_scroll = 0
        
        return self.estimated_scroll
    
    def analyze_matching(self) -> Dict:
        """
        Analyser le matching entre début et fin.
        Retourne les objets matchés, apparus et disparus.
        """
        if not self.start_annotations and not self.end_annotations:
            return {'error': 'Pas d\'annotations'}
        
        # Estimer le scroll
        self._estimate_scroll()
        
        self.matched_objects = []
        used_end_indices = set()
        
        # Chercher les correspondances
        for start_obj in self.start_annotations:
            expected_end_x = start_obj['x'] - self.estimated_scroll
            
            best_match = None
            best_score = float('inf')
            best_idx = -1
            
            for i, end_obj in enumerate(self.end_annotations):
                if i in used_end_indices:
                    continue
                
                if end_obj['class_id'] != start_obj['class_id']:
                    continue
                
                dx = abs(end_obj['x'] - expected_end_x)
                dy = abs(end_obj['y'] - start_obj['y'])
                dw = abs(end_obj['w'] - start_obj['w'])
                dh = abs(end_obj['h'] - start_obj['h'])
                
                score = dx * 0.5 + dy * 2 + (dw + dh) * 3
                
                if score < best_score:
                    best_score = score
                    best_match = end_obj
                    best_idx = i
            
            if best_match and best_score < 300:
                used_end_indices.add(best_idx)
                self.matched_objects.append(InterpolatedObject(
                    class_id=start_obj['class_id'],
                    class_name=start_obj['class_name'],
                    status=MatchStatus.MATCHED,
                    start_bbox=(start_obj['x'], start_obj['y'], start_obj['w'], start_obj['h']),
                    end_bbox=(best_match['x'], best_match['y'], best_match['w'], best_match['h']),
                    start_frame=self.config.start_frame,
                    end_frame=self.config.end_frame
                ))
            else:
                # Objet disparu
                self.matched_objects.append(InterpolatedObject(
                    class_id=start_obj['class_id'],
                    class_name=start_obj['class_name'],
                    status=MatchStatus.DISAPPEARED,
                    start_bbox=(start_obj['x'], start_obj['y'], start_obj['w'], start_obj['h']),
                    end_bbox=None,
                    start_frame=self.config.start_frame,
                    end_frame=self.config.end_frame  # Va être ajusté
                ))
        
        # Objets apparus (dans fin mais pas matchés)
        for i, end_obj in enumerate(self.end_annotations):
            if i not in used_end_indices:
                self.matched_objects.append(InterpolatedObject(
                    class_id=end_obj['class_id'],
                    class_name=end_obj['class_name'],
                    status=MatchStatus.APPEARED,
                    start_bbox=None,
                    end_bbox=(end_obj['x'], end_obj['y'], end_obj['w'], end_obj['h']),
                    start_frame=self.config.start_frame,  # Va être ajusté
                    end_frame=self.config.end_frame
                ))
        
        # Compiler les résultats
        matched = [o for o in self.matched_objects if o.status == MatchStatus.MATCHED]
        disappeared = [o for o in self.matched_objects if o.status == MatchStatus.DISAPPEARED]
        appeared = [o for o in self.matched_objects if o.status == MatchStatus.APPEARED]
        
        return {
            'matched': matched,
            'disappeared': disappeared,
            'appeared': appeared,
            'estimated_scroll': self.estimated_scroll,
            'needs_intermediate': len(appeared) > 0 or len(disappeared) > 0
        }
    
    def get_objects_needing_intermediate(self) -> List[Dict]:
        """Retourne la liste des objets qui ont besoin d'un frame intermédiaire"""
        result = []
        for obj in self.matched_objects:
            if obj.status == MatchStatus.APPEARED and obj.intermediate_frame is None:
                result.append({
                    'class_name': obj.class_name,
                    'class_id': obj.class_id,
                    'type': 'appeared',
                    'end_bbox': obj.end_bbox,
                    'message': f"➕ {obj.class_name} apparaît - Où commence-t-il?"
                })
            elif obj.status == MatchStatus.DISAPPEARED and obj.intermediate_frame is None:
                result.append({
                    'class_name': obj.class_name,
                    'class_id': obj.class_id,
                    'type': 'disappeared',
                    'start_bbox': obj.start_bbox,
                    'message': f"⚠️ {obj.class_name} disparaît - Où finit-il?"
                })
        return result
    
    def set_intermediate_for_object(self, class_name: str, frame_index: int):
        """
        Définir le frame intermédiaire pour un objet apparu/disparu.
        Capture automatiquement les annotations de ce frame.
        """
        if not self.task or frame_index >= len(self.task.images):
            return False
        
        img = self.task.images[frame_index]
        
        for obj in self.matched_objects:
            if obj.class_name != class_name:
                continue
            
            # Chercher l'annotation correspondante dans le frame intermédiaire
            for box in img.boxes:
                if box.class_name == class_name:
                    bbox = (box.x, box.y, box.width, box.height)
                    obj.intermediate_frame = frame_index
                    obj.intermediate_bbox = bbox
                    
                    if obj.status == MatchStatus.APPEARED:
                        # L'objet commence à ce frame
                        obj.start_frame = frame_index
                        obj.start_bbox = bbox
                        self._log(f"  ✓ {class_name} APPARAÎT au frame {frame_index}")
                    elif obj.status == MatchStatus.DISAPPEARED:
                        # L'objet finit à ce frame
                        obj.end_frame = frame_index
                        obj.end_bbox = bbox
                        self._log(f"  ✓ {class_name} DISPARAÎT au frame {frame_index}")
                    
                    return True
        
        return False
    
    def _interpolate_position(self, start_bbox: Tuple, end_bbox: Tuple, progress: float) -> Tuple[int, int, int, int]:
        """Interpoler linéairement entre deux positions"""
        x1, y1, w1, h1 = start_bbox
        x2, y2, w2, h2 = end_bbox
        
        x = int(x1 + (x2 - x1) * progress)
        y = int(y1 + (y2 - y1) * progress)
        w = int(w1 + (w2 - w1) * progress)
        h = int(h1 + (h2 - h1) * progress)
        
        return (x, y, w, h)
    
    def is_ready_to_execute(self) -> Tuple[bool, str]:
        """Vérifier si l'interpolation est prête à être exécutée"""
        if not self.matched_objects:
            return False, "Analyse non effectuée"
        
        pending = self.get_objects_needing_intermediate()
        if pending:
            names = [p['class_name'] for p in pending]
            return False, f"Objets en attente: {', '.join(names)}"
        
        return True, "Prêt"
    
    def execute(self) -> HelperResult:
        """Exécuter l'interpolation"""
        if not self.task or not self.task.images:
            return HelperResult(success=False, message="Aucune image chargée")
        
        if not self.matched_objects:
            # Faire l'analyse si pas encore faite
            self.analyze_matching()
        
        if not self.matched_objects:
            return HelperResult(success=False, message="Aucun objet à interpoler")
        
        # Vérifier que tous les objets sont prêts
        ready, msg = self.is_ready_to_execute()
        if not ready:
            return HelperResult(success=False, message=msg)
        
        self.status = HelperStatus.RUNNING
        
        total_frames = self.config.end_frame - self.config.start_frame - 1
        interpolated_count = 0
        
        self._log(f"📐 Interpolation de {len(self.matched_objects)} objets sur {total_frames} frames")
        
        # Pour chaque frame intermédiaire
        for frame_offset in range(1, total_frames + 1):
            if self._check_cancelled():
                self.status = HelperStatus.CANCELLED
                break
            
            frame_index = self.config.start_frame + frame_offset
            self._update_progress(frame_offset / total_frames, f"Frame {frame_index}")
            
            # Calculer les positions pour ce frame
            new_boxes = []
            
            for obj in self.matched_objects:
                # Vérifier si l'objet existe à ce frame
                if frame_index < obj.start_frame or frame_index > obj.end_frame:
                    continue
                
                # Vérifier qu'on a les deux bboxes
                if not obj.start_bbox or not obj.end_bbox:
                    continue
                
                # Calculer la progression relative à cet objet
                obj_duration = obj.end_frame - obj.start_frame
                if obj_duration <= 0:
                    continue
                
                obj_progress = (frame_index - obj.start_frame) / obj_duration
                
                # Interpoler
                bbox = self._interpolate_position(obj.start_bbox, obj.end_bbox, obj_progress)
                
                x, y, w, h = bbox
                if w > 5 and h > 5 and x >= 0 and y >= 0:
                    new_boxes.append({
                        'class_id': obj.class_id,
                        'x': x,
                        'y': y,
                        'w': w,
                        'h': h
                    })
            
            # Appliquer les annotations
            if new_boxes:
                self.task.current_index = frame_index
                
                if self.config.overwrite_existing:
                    self.task.clear_annotations()
                
                for box in new_boxes:
                    self.task.add_annotation(
                        box['class_id'],
                        box['x'], box['y'],
                        box['w'], box['h']
                    )
                
                if self.config.save_after_each:
                    self.task.save_current_annotations()
                
                interpolated_count += 1
        
        # Revenir au frame de début
        self.task.current_index = self.config.start_frame
        
        self.status = HelperStatus.COMPLETED
        
        matched = len([o for o in self.matched_objects if o.status == MatchStatus.MATCHED])
        appeared = len([o for o in self.matched_objects if o.status == MatchStatus.APPEARED])
        disappeared = len([o for o in self.matched_objects if o.status == MatchStatus.DISAPPEARED])
        
        return HelperResult(
            success=interpolated_count > 0,
            message=f"Interpolation terminée: {interpolated_count} frames",
            processed=interpolated_count,
            skipped=total_frames - interpolated_count,
            details={
                'start_frame': self.config.start_frame,
                'end_frame': self.config.end_frame,
                'objects_matched': matched,
                'objects_appeared': appeared,
                'objects_disappeared': disappeared,
                'estimated_scroll': self.estimated_scroll
            }
        )
    def _open_interpolation_tool(self):
        """Ouvrir l'outil d'interpolation avec navigateur d'intervalle"""
        if not self.task.images:
            QMessageBox.warning(self, "Erreur", "Chargez d'abord des images.")
            return
        
        # Vérifier qu'il y a des annotations sur l'image courante
        img = self.task.get_current_image()
        if not img or not img.boxes:
            QMessageBox.warning(self, "Erreur",
                "Annotez d'abord le frame de DÉPART.\n\n"
                "L'interpolation fonctionne ainsi:\n"
                "1. Annotez le frame actuel (tous les objets visibles)\n"
                "2. Annotez le frame de fin (tous les objets visibles)\n"
                "3. Si des objets apparaissent, trouvez où ils apparaissent\n"
                "4. Lancez l'interpolation")
            return
        
        remaining = len(self.task.images) - self.task.current_index - 1
        if remaining <= 0:
            QMessageBox.warning(self, "Erreur", "Pas de frames suivants.")
            return
        
        start_frame = self.task.current_index
        start_boxes = [(b.class_id, b.class_name, b.x, b.y, b.width, b.height) for b in img.boxes]
        start_count = len(start_boxes)
        
        # Dialogue principal
        dialog = QDialog(self)
        dialog.setWindowTitle("📐 Interpolation")
        dialog.setMinimumWidth(500)
        dialog.setStyleSheet("""
            QDialog { background-color: #2d2d2d; }
            QLabel { color: white; }
            QGroupBox { color: #ff9800; border: 1px solid #5d5d5d; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
            QSpinBox { background-color: #3d3d3d; color: white; border: 1px solid #5d5d5d; padding: 5px; min-width: 80px; }
            QCheckBox { color: white; }
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setSpacing(10)
        
        # Info frame de début
        info_label = QLabel(
            f"<b style='color:#ff9800;'>Frame de DÉBUT:</b> #{start_frame} ({start_count} objets)<br><br>"
            "<b>Étape 1:</b> Définissez le frame de fin et annotez-le"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        # Frame de fin
        frame_group = QGroupBox("Configuration")
        frame_layout = QGridLayout(frame_group)
        
        frame_layout.addWidget(QLabel("Frame de fin:"), 0, 0)
        spin_end = QSpinBox()
        spin_end.setRange(start_frame + 1, len(self.task.images) - 1)
        spin_end.setValue(min(start_frame + 30, len(self.task.images) - 1))
        frame_layout.addWidget(spin_end, 0, 1)
        
        btn_goto = QPushButton("📍 Aller annoter le frame de fin")
        btn_goto.setStyleSheet("background-color: #ff9800; color: white; padding: 8px;")
        frame_layout.addWidget(btn_goto, 1, 0, 1, 2)
        
        status_label = QLabel("⏳ En attente d'annotation...")
        status_label.setStyleSheet("color: #888;")
        frame_layout.addWidget(status_label, 2, 0, 1, 2)
        
        layout.addWidget(frame_group)
        
        # Zone pour les objets qui apparaissent
        appear_group = QGroupBox("🔍 Objets supplémentaires détectés")
        appear_group.setVisible(False)
        appear_layout = QVBoxLayout(appear_group)
        
        appear_info = QLabel("")
        appear_info.setWordWrap(True)
        appear_layout.addWidget(appear_info)
        
        btn_find_appearance = QPushButton("🔎 Naviguer pour trouver où ils apparaissent")
        btn_find_appearance.setStyleSheet("background-color: #9c27b0; color: white; padding: 10px; font-weight: bold;")
        appear_layout.addWidget(btn_find_appearance)
        
        appear_status = QLabel("")
        appear_status.setStyleSheet("color: #4caf50;")
        appear_status.setVisible(False)
        appear_layout.addWidget(appear_status)
        
        layout.addWidget(appear_group)
        
        # Options
        check_overwrite = QCheckBox("Écraser les annotations existantes")
        check_overwrite.setChecked(True)
        layout.addWidget(check_overwrite)
        
        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setStyleSheet("background-color: #666; color: white; padding: 8px 20px;")
        btn_cancel.clicked.connect(dialog.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_interpolate = QPushButton("📐 Interpoler")
        btn_interpolate.setStyleSheet("background-color: #4caf50; color: white; padding: 8px 20px; font-weight: bold;")
        btn_layout.addWidget(btn_interpolate)
        
        layout.addLayout(btn_layout)
        
        # Variables pour stocker les apparitions
        appearances_found = {}  # {class_name: frame_index}
        
        def goto_end():
            target = spin_end.value()
            self.task.current_index = target
            self._display_current_image()
            
            end_img = self.task.images[target]
            if end_img.boxes:
                end_count = len(end_img.boxes)
                status_label.setText(f"✅ Frame #{target}: {end_count} objets annotés")
                status_label.setStyleSheet("color: #4caf50;")
                
                # Vérifier s'il y a des objets supplémentaires
                check_appearing_objects()
            else:
                status_label.setText(f"⚠️ Frame #{target}: pas encore annoté!")
                status_label.setStyleSheet("color: #f44336;")
                appear_group.setVisible(False)
        
        btn_goto.clicked.connect(goto_end)
        
        def check_appearing_objects():
            """Vérifier s'il y a des objets supplémentaires au frame de fin"""
            end_frame = spin_end.value()
            end_img = self.task.images[end_frame]
            if not end_img.boxes:
                return
            
            # Compter par classe
            start_by_class = {}
            end_by_class = {}
            
            for box in start_boxes:
                cls = box[1]
                start_by_class[cls] = start_by_class.get(cls, 0) + 1
            
            for box in end_img.boxes:
                cls = box.class_name
                end_by_class[cls] = end_by_class.get(cls, 0) + 1
            
            # Trouver les objets supplémentaires
            appearing = []
            for cls, count in end_by_class.items():
                s_count = start_by_class.get(cls, 0)
                if count > s_count:
                    appearing.append((cls, count - s_count))
            
            if appearing:
                text = "<b style='color:#2196f3;'>Ces objets n'étaient pas au frame de début:</b><br>"
                for cls, count in appearing:
                    text += f"• <b>{cls}</b> (+{count})<br>"
                text += "<br><span style='color:#888;'>Utilisez le navigateur pour trouver où ils apparaissent.</span>"
                
                appear_info.setText(text)
                appear_group.setVisible(True)
            else:
                appear_group.setVisible(False)
        
        def open_appearance_finder():
            """Ouvrir le dialogue pour naviguer et trouver où les objets apparaissent"""
            end_frame = spin_end.value()
            
            # Grand dialogue de navigation
            finder = QDialog(dialog)
            finder.setWindowTitle("🔎 Navigateur d'intervalle - Trouvez où les objets apparaissent")
            finder.setMinimumSize(1000, 750)
            finder.setStyleSheet("""
                QDialog { background-color: #1a1a1a; }
                QLabel { color: white; }
                QSlider::groove:horizontal { background: #3d3d3d; height: 10px; border-radius: 5px; }
                QSlider::handle:horizontal { background: #ff9800; width: 24px; margin: -7px 0; border-radius: 12px; }
                QSlider::sub-page:horizontal { background: #ff9800; border-radius: 5px; }
            """)
            
            finder_layout = QVBoxLayout(finder)
            finder_layout.setSpacing(10)
            
            # Instructions en haut
            instr = QLabel(
                "<div style='background-color: #2d2d2d; padding: 10px; border-radius: 5px;'>"
                "<b style='color:#ff9800; font-size: 14px;'>📋 Instructions:</b><br>"
                "1. Utilisez le slider ou les boutons pour naviguer dans l'intervalle<br>"
                "2. Quand vous voyez un objet apparaître pour la <b>première fois</b>, <b>annotez-le</b><br>"
                "3. Le système détectera automatiquement les nouvelles annotations<br>"
                "4. Cliquez sur <b>'Terminer'</b> quand vous avez trouvé toutes les apparitions"
                "</div>"
            )
            instr.setWordWrap(True)
            finder_layout.addWidget(instr)
            
            # Grande zone de prévisualisation
            preview_container = QFrame()
            preview_container.setStyleSheet("background-color: #2d2d2d; border: 2px solid #ff9800; border-radius: 8px;")
            preview_container.setMinimumHeight(480)
            preview_layout = QVBoxLayout(preview_container)
            
            preview_label = QLabel()
            preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            preview_label.setMinimumSize(900, 450)
            preview_layout.addWidget(preview_label)
            
            finder_layout.addWidget(preview_container)
            
            # Barre de navigation avec slider
            nav_frame = QFrame()
            nav_frame.setStyleSheet("background-color: #2d2d2d; border-radius: 5px; padding: 10px;")
            nav_layout = QVBoxLayout(nav_frame)
            
            # Label du frame actuel
            frame_info = QLabel(f"<b style='font-size: 18px; color: #ff9800;'>Frame {start_frame}</b> | Annotations: {start_count}")
            frame_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            nav_layout.addWidget(frame_info)
            
            # Slider
            frame_slider = QSlider(Qt.Orientation.Horizontal)
            frame_slider.setMinimum(start_frame)
            frame_slider.setMaximum(end_frame)
            frame_slider.setValue(start_frame)
            frame_slider.setMinimumHeight(30)
            nav_layout.addWidget(frame_slider)
            
            # Labels début/fin sous le slider
            range_layout = QHBoxLayout()
            range_layout.addWidget(QLabel(f"Début: #{start_frame}"))
            range_layout.addStretch()
            range_layout.addWidget(QLabel(f"Fin: #{end_frame}"))
            nav_layout.addLayout(range_layout)
            
            finder_layout.addWidget(nav_frame)
            
            # Boutons de navigation
            btn_nav_layout = QHBoxLayout()
            
            btn_start = QPushButton("⏮ Début")
            btn_start.setStyleSheet("background-color: #555; color: white; padding: 8px 15px;")
            btn_nav_layout.addWidget(btn_start)
            
            btn_prev10 = QPushButton("⏪ -10")
            btn_prev10.setStyleSheet("background-color: #555; color: white; padding: 8px 15px;")
            btn_nav_layout.addWidget(btn_prev10)
            
            btn_prev = QPushButton("◀ -1")
            btn_prev.setStyleSheet("background-color: #555; color: white; padding: 8px 15px;")
            btn_nav_layout.addWidget(btn_prev)
            
            btn_nav_layout.addStretch()
            
            btn_annotate = QPushButton("✏️ ANNOTER CE FRAME")
            btn_annotate.setStyleSheet("background-color: #2196f3; color: white; padding: 12px 25px; font-size: 14px; font-weight: bold;")
            btn_nav_layout.addWidget(btn_annotate)
            
            btn_nav_layout.addStretch()
            
            btn_next = QPushButton("+1 ▶")
            btn_next.setStyleSheet("background-color: #555; color: white; padding: 8px 15px;")
            btn_nav_layout.addWidget(btn_next)
            
            btn_next10 = QPushButton("+10 ⏩")
            btn_next10.setStyleSheet("background-color: #555; color: white; padding: 8px 15px;")
            btn_nav_layout.addWidget(btn_next10)
            
            btn_end = QPushButton("Fin ⏭")
            btn_end.setStyleSheet("background-color: #555; color: white; padding: 8px 15px;")
            btn_nav_layout.addWidget(btn_end)
            
            finder_layout.addLayout(btn_nav_layout)
            
            # Boutons finaux
            final_layout = QHBoxLayout()
            final_layout.addStretch()
            
            btn_cancel_finder = QPushButton("Annuler")
            btn_cancel_finder.setStyleSheet("background-color: #666; color: white; padding: 10px 25px;")
            btn_cancel_finder.clicked.connect(finder.reject)
            final_layout.addWidget(btn_cancel_finder)
            
            btn_done = QPushButton("✓ Terminer et revenir")
            btn_done.setStyleSheet("background-color: #4caf50; color: white; padding: 10px 25px; font-weight: bold;")
            final_layout.addWidget(btn_done)
            
            finder_layout.addLayout(final_layout)
            
            current_frame_idx = [start_frame]  # Mutable pour les closures
            
            def update_preview(frame_idx):
                """Mettre à jour l'aperçu du frame"""
                if frame_idx < start_frame or frame_idx > end_frame:
                    return
                
                current_frame_idx[0] = frame_idx
                frame_slider.setValue(frame_idx)
                
                img_obj = self.task.images[frame_idx]
                ann_count = len(img_obj.boxes)
                
                # Mettre à jour le label
                color = "#4caf50" if ann_count > start_count else "#ff9800" if ann_count == start_count else "#f44336"
                frame_info.setText(f"<b style='font-size: 18px; color: {color};'>Frame {frame_idx}</b> | Annotations: {ann_count}")
                
                # Charger et afficher l'image avec annotations
                pixmap = QPixmap(img_obj.file_path)
                
                if not pixmap.isNull():
                    # Dessiner les annotations
                    from PyQt6.QtGui import QPainter, QPen, QColor, QFont as QFontGui
                    painter = QPainter(pixmap)
                    
                    for box in img_obj.boxes:
                        # Boîte
                        pen = QPen(QColor("#00ff00"))
                        pen.setWidth(4)
                        painter.setPen(pen)
                        painter.drawRect(box.x, box.y, box.width, box.height)
                        
                        # Label avec fond
                        font = QFontGui()
                        font.setPointSize(14)
                        font.setBold(True)
                        painter.setFont(font)
                        
                        # Fond du label
                        painter.fillRect(box.x, box.y - 25, len(box.class_name) * 12, 25, QColor("#00ff00"))
                        painter.setPen(QColor("#000000"))
                        painter.drawText(box.x + 3, box.y - 7, box.class_name)
                    
                    painter.end()
                    
                    # Redimensionner
                    scaled = pixmap.scaled(900, 450, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    preview_label.setPixmap(scaled)
            
            def on_slider_change(value):
                update_preview(value)
            
            frame_slider.valueChanged.connect(on_slider_change)
            
            def move_frame(delta):
                new_val = current_frame_idx[0] + delta
                new_val = max(start_frame, min(end_frame, new_val))
                update_preview(new_val)
            
            btn_start.clicked.connect(lambda: update_preview(start_frame))
            btn_prev10.clicked.connect(lambda: move_frame(-10))
            btn_prev.clicked.connect(lambda: move_frame(-1))
            btn_next.clicked.connect(lambda: move_frame(1))
            btn_next10.clicked.connect(lambda: move_frame(10))
            btn_end.clicked.connect(lambda: update_preview(end_frame))
            
            def open_annotation():
                """Ouvrir l'annotation plein écran pour le frame actuel"""
                frame_idx = current_frame_idx[0]
                self.task.current_index = frame_idx
                self._display_current_image()
                
                # Ouvrir le mode plein écran si disponible
                if hasattr(self, '_open_fullscreen_annotation'):
                    self._open_fullscreen_annotation()
                
                # Rafraîchir après annotation
                update_preview(frame_idx)
            
            btn_annotate.clicked.connect(open_annotation)
            
            def finish_finding():
                """Terminer et collecter les apparitions trouvées"""
                # Scanner tous les frames pour trouver où les nouvelles classes apparaissent
                start_classes = {}
                for box in start_boxes:
                    cls = box[1]
                    start_classes[cls] = start_classes.get(cls, 0) + 1
                
                # Pour chaque frame, vérifier s'il y a de nouvelles annotations
                for frame_idx in range(start_frame + 1, end_frame + 1):
                    img_obj = self.task.images[frame_idx]
                    
                    frame_classes = {}
                    for box in img_obj.boxes:
                        cls = box.class_name
                        frame_classes[cls] = frame_classes.get(cls, 0) + 1
                    
                    # Vérifier chaque classe
                    for cls, count in frame_classes.items():
                        start_count_cls = start_classes.get(cls, 0)
                        if count > start_count_cls and cls not in appearances_found:
                            appearances_found[cls] = frame_idx
                
                finder.accept()
            
            btn_done.clicked.connect(finish_finding)
            
            # Afficher le premier frame
            update_preview(start_frame)
            
            if finder.exec() == QDialog.DialogCode.Accepted:
                # Mettre à jour l'affichage des apparitions trouvées
                if appearances_found:
                    appear_status.setText(f"✅ Apparitions trouvées: {', '.join(f'{cls} (#{f})' for cls, f in appearances_found.items())}")
                    appear_status.setVisible(True)
        
        btn_find_appearance.clicked.connect(open_appearance_finder)
        
        def do_interpolate():
            end_frame = spin_end.value()
            end_img = self.task.images[end_frame]
            
            if not end_img.boxes:
                QMessageBox.warning(dialog, "Erreur",
                    f"Le frame #{end_frame} n'a pas d'annotations!\n"
                    "Annotez-le d'abord.")
                return
            
            end_boxes = [(b.class_id, b.class_name, b.x, b.y, b.width, b.height) for b in end_img.boxes]
            
            # Organiser par classe
            start_by_class = {}
            end_by_class = {}
            
            for box in start_boxes:
                cls = box[1]
                if cls not in start_by_class:
                    start_by_class[cls] = []
                start_by_class[cls].append(box)
            
            for box in end_boxes:
                cls = box[1]
                if cls not in end_by_class:
                    end_by_class[cls] = []
                end_by_class[cls].append(box)
            
            # Collecter les données d'apparition depuis les frames intermédiaires annotés
            intermediate_data = {}  # {class_name: (appear_frame, boxes_at_appear)}
            
            for frame_idx in range(start_frame + 1, end_frame):
                img_obj = self.task.images[frame_idx]
                if not img_obj.boxes:
                    continue
                
                frame_by_class = {}
                for box in img_obj.boxes:
                    cls = box.class_name
                    if cls not in frame_by_class:
                        frame_by_class[cls] = []
                    frame_by_class[cls].append((box.class_id, box.class_name, box.x, box.y, box.width, box.height))
                
                # Vérifier chaque classe pour les nouvelles apparitions
                for cls, boxes in frame_by_class.items():
                    start_count_cls = len(start_by_class.get(cls, []))
                    if len(boxes) > start_count_cls and cls not in intermediate_data:
                        # Nouveaux objets de cette classe apparaissent ici
                        new_boxes = sorted(boxes, key=lambda x: (x[3], x[2]))[start_count_cls:]
                        intermediate_data[cls] = (frame_idx, new_boxes)
            
            dialog.accept()
            
            # Interpoler
            total_frames = end_frame - start_frame - 1
            self._log(f"📐 Interpolation de #{start_frame} à #{end_frame}")
            if intermediate_data:
                self._log(f"  Apparitions détectées: {list(intermediate_data.keys())}")
            
            for frame_offset in range(1, total_frames + 1):
                frame_idx = start_frame + frame_offset
                progress = frame_offset / (total_frames + 1)
                
                self.task.current_index = frame_idx
                
                if check_overwrite.isChecked():
                    self.task.clear_annotations()
                
                # 1. Interpoler les objets présents du début à la fin
                for cls in start_by_class:
                    if cls not in end_by_class:
                        continue
                    
                    starts = sorted(start_by_class[cls], key=lambda x: (x[3], x[2]))
                    ends = sorted(end_by_class[cls], key=lambda x: (x[3], x[2]))
                    
                    for j in range(min(len(starts), len(ends))):
                        s, e = starts[j], ends[j]
                        x = int(s[2] + (e[2] - s[2]) * progress)
                        y = int(s[3] + (e[3] - s[3]) * progress)
                        w = int(s[4] + (e[4] - s[4]) * progress)
                        h = int(s[5] + (e[5] - s[5]) * progress)
                        
                        if w > 5 and h > 5:
                            self.task.add_annotation(s[0], x, y, w, h)
                
                # 2. Interpoler les objets qui apparaissent
                for cls, (appear_frame, appear_boxes) in intermediate_data.items():
                    if frame_idx >= appear_frame:
                        # Progression depuis l'apparition jusqu'à la fin
                        if end_frame > appear_frame:
                            appear_progress = (frame_idx - appear_frame) / (end_frame - appear_frame)
                        else:
                            appear_progress = 1.0
                        
                        # Récupérer les positions finales
                        end_boxes_cls = sorted(end_by_class.get(cls, []), key=lambda x: (x[3], x[2]))
                        start_count_cls = len(start_by_class.get(cls, []))
                        
                        for j, app_box in enumerate(appear_boxes):
                            if start_count_cls + j < len(end_boxes_cls):
                                end_box = end_boxes_cls[start_count_cls + j]
                                
                                x = int(app_box[2] + (end_box[2] - app_box[2]) * appear_progress)
                                y = int(app_box[3] + (end_box[3] - app_box[3]) * appear_progress)
                                w = int(app_box[4] + (end_box[4] - app_box[4]) * appear_progress)
                                h = int(app_box[5] + (end_box[5] - app_box[5]) * appear_progress)
                                
                                if w > 5 and h > 5:
                                    self.task.add_annotation(app_box[0], x, y, w, h)
                
                self.task.save_current_annotations()
            
            # Revenir au début
            self.task.current_index = start_frame
            self._display_current_image()
            
            msg = f"✅ {total_frames} frames annotés!\n\n"
            msg += f"• Du frame #{start_frame} au frame #{end_frame}\n"
            msg += f"• Objets de base: {start_count}\n"
            if intermediate_data:
                msg += f"• Objets apparus: {len(intermediate_data)}"
            
            QMessageBox.information(self, "Interpolation terminée", msg)
        
        btn_interpolate.clicked.connect(do_interpolate)
        
        dialog.exec()