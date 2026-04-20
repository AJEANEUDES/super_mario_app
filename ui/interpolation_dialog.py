"""
Interpolation Dialog - Module pour l'interpolation interactive entre frames

Version 5.4.0 - Compensation automatique du SCROLLING

AMÉLIORATIONS:
- Détection automatique du scrolling horizontal (basée sur les objets statiques)
- Compensation du scrolling pour le matching des objets
- Objets statiques (blocs) vs dynamiques (Mario, Goombas) traités différemment
- Re-capture des annotations au moment de l'analyse (pas à l'ouverture)
- Avertissement si peu d'objets détectés

LOGIQUE:
1. Détecter le scrolling en comparant les positions des blocs entre début et fin
2. Pour les objets statiques: compenser le scrolling avant le matching
3. Pour les objets dynamiques: matcher par position directe
4. Interpoler linéairement entre les positions de début et fin

Workflow:
1. L'utilisateur annote le frame de DÉBUT et SAUVEGARDE
2. L'utilisateur annote le frame de FIN et SAUVEGARDE
3. Clic sur "Analyser" → détection scrolling + matching intelligent
4. Localisation des nouveaux objets si nécessaire
5. Interpolation avec compensation du scrolling
"""

import os
import math
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass, field

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QSpinBox, QCheckBox, QSlider,
    QListWidget, QListWidgetItem, QMessageBox, QFrame,
    QScrollArea, QSizePolicy, QWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QFont, QBrush


@dataclass
class ObjectInstance:
    """
    Représente une instance unique d'un objet annoté.
    
    L'instance_id permet de distinguer plusieurs objets de même classe.
    Ex: mystery_block#1, mystery_block#2
    """
    instance_id: str      # ID unique: "class_name#number"
    class_id: int
    class_name: str
    x: int
    y: int
    width: int
    height: int
    
    @property
    def center_x(self) -> float:
        return self.x + self.width / 2
    
    @property
    def center_y(self) -> float:
        return self.y + self.height / 2
    
    def distance_to(self, other: 'ObjectInstance') -> float:
        """Calculer la distance euclidienne vers un autre objet"""
        dx = self.center_x - other.center_x
        dy = self.center_y - other.center_y
        return math.sqrt(dx * dx + dy * dy)


@dataclass  
class InterpolationPair:
    """Paire d'objets à interpoler avec leur frame d'apparition"""
    instance_id: str
    start_obj: ObjectInstance
    end_obj: ObjectInstance
    appear_frame: int  # Frame où l'objet apparaît (start_frame si présent dès le début)


class InstanceTracker:
    """
    Gestionnaire d'instances d'objets.
    
    Assigne des IDs uniques et gère le matching par proximité.
    """
    
    def __init__(self):
        self.instance_counter: Dict[str, int] = {}  # class_name -> counter
        self.instances: Dict[str, ObjectInstance] = {}  # instance_id -> ObjectInstance
    
    def reset(self):
        """Réinitialiser le tracker"""
        self.instance_counter.clear()
        self.instances.clear()
    
    def create_instance_id(self, class_name: str) -> str:
        """Créer un nouvel ID d'instance unique"""
        if class_name not in self.instance_counter:
            self.instance_counter[class_name] = 0
        
        self.instance_counter[class_name] += 1
        return f"{class_name}#{self.instance_counter[class_name]}"
    
    def create_instances_from_frame(self, task, frame_index: int) -> List[ObjectInstance]:
        """
        Créer des instances pour tous les objets d'un frame.
        Chaque objet reçoit un ID unique.
        """
        instances = []
        
        if frame_index < len(task.images):
            img = task.images[frame_index]
            for box in img.boxes:
                instance_id = self.create_instance_id(box.class_name)
                instance = ObjectInstance(
                    instance_id=instance_id,
                    class_id=box.class_id,
                    class_name=box.class_name,
                    x=box.x, y=box.y,
                    width=box.width, height=box.height
                )
                instances.append(instance)
                self.instances[instance_id] = instance
        
        return instances
    
    def match_by_proximity(
        self, 
        start_instances: List[ObjectInstance], 
        end_instances: List[ObjectInstance],
        max_distance: float = 2000.0  # Augmenté pour couvrir tout l'écran
    ) -> Tuple[List[Tuple[ObjectInstance, ObjectInstance]], List[ObjectInstance], List[ObjectInstance]]:
        """
        Matcher les objets entre deux frames de manière intelligente.
        
        LOGIQUE AMÉLIORÉE AVEC COMPENSATION DU SCROLLING:
        1. Détecter le scrolling horizontal en comparant les objets statiques
        2. Appliquer la compensation de scrolling avant le matching
        3. Compter les objets par classe au début et à la fin
        4. Matcher par proximité (avec positions corrigées)
        
        Returns:
            - matched: Liste de (start_obj, end_obj) matchés
            - unmatched_starts: Objets du début sans correspondance (disparus)
            - unmatched_ends: Objets de la fin sans correspondance (apparus)
        """
        matched = []
        unmatched_starts = []
        unmatched_ends = []
        
        # ========================================
        # ÉTAPE 1: Détecter le scrolling horizontal
        # ========================================
        scroll_offset_x = self._detect_scrolling(start_instances, end_instances)
        
        # Grouper par classe
        start_by_class: Dict[str, List[ObjectInstance]] = {}
        end_by_class: Dict[str, List[ObjectInstance]] = {}
        
        for obj in start_instances:
            if obj.class_name not in start_by_class:
                start_by_class[obj.class_name] = []
            start_by_class[obj.class_name].append(obj)
        
        for obj in end_instances:
            if obj.class_name not in end_by_class:
                end_by_class[obj.class_name] = []
            end_by_class[obj.class_name].append(obj)
        
        # Toutes les classes présentes
        all_classes = set(list(start_by_class.keys()) + list(end_by_class.keys()))
        
        for class_name in all_classes:
            starts = start_by_class.get(class_name, [])
            ends = end_by_class.get(class_name, [])
            
            start_count = len(starts)
            end_count = len(ends)
            
            # Nombre d'objets à matcher (le minimum des deux)
            match_count = min(start_count, end_count)
            
            # Déterminer si c'est un objet statique (affecté par le scrolling)
            is_static = self._is_static_class(class_name)
            
            # Matcher par proximité optimale (avec compensation scrolling pour objets statiques)
            available_starts = list(starts)
            available_ends = list(ends)
            
            for _ in range(match_count):
                if not available_starts or not available_ends:
                    break
                
                # Trouver la paire avec la distance minimale
                best_pair = None
                best_distance = float('inf')
                best_start_idx = -1
                best_end_idx = -1
                
                for i, start_obj in enumerate(available_starts):
                    for j, end_obj in enumerate(available_ends):
                        # Calculer la distance avec compensation de scrolling
                        if is_static:
                            # Pour objets statiques: compenser le scrolling
                            adjusted_start_x = start_obj.center_x + scroll_offset_x
                            dx = adjusted_start_x - end_obj.center_x
                        else:
                            # Pour objets dynamiques (Mario, Goombas): pas de compensation
                            dx = start_obj.center_x - end_obj.center_x
                        
                        dy = start_obj.center_y - end_obj.center_y
                        dist = math.sqrt(dx * dx + dy * dy)
                        
                        if dist < best_distance:
                            best_distance = dist
                            best_pair = (start_obj, end_obj)
                            best_start_idx = i
                            best_end_idx = j
                
                if best_pair:
                    matched.append(best_pair)
                    available_starts.pop(best_start_idx)
                    available_ends.pop(best_end_idx)
            
            # Objets restants au début = disparus
            unmatched_starts.extend(available_starts)
            
            # Objets restants à la fin = nouveaux
            unmatched_ends.extend(available_ends)
        
        return matched, unmatched_starts, unmatched_ends
    
    def _detect_scrolling(self, start_instances: List[ObjectInstance], end_instances: List[ObjectInstance]) -> float:
        """
        Détecter le scrolling horizontal en comparant les positions des objets statiques.
        
        Logique: Les blocs (brick, mystery, undestructible) sont fixes dans le niveau.
        Si leur position X change, c'est à cause du scrolling de la caméra.
        
        Returns:
            scroll_offset_x: Décalage en X (négatif = scroll vers la droite)
        """
        static_classes = {'brick_block', 'mystery_block', 'undestructible_block', 'pipe', 'pipe_head'}
        
        # Collecter les positions X des objets statiques
        start_static_x = []
        end_static_x = []
        
        for obj in start_instances:
            if obj.class_name in static_classes:
                start_static_x.append(obj.center_x)
        
        for obj in end_instances:
            if obj.class_name in static_classes:
                end_static_x.append(obj.center_x)
        
        if not start_static_x or not end_static_x:
            return 0.0  # Pas assez de données pour détecter le scrolling
        
        # Calculer le décalage médian
        # On compare la moyenne des positions (approximation simple)
        start_avg = sum(start_static_x) / len(start_static_x)
        end_avg = sum(end_static_x) / len(end_static_x)
        
        scroll_offset = end_avg - start_avg
        
        return scroll_offset
    
    def _is_static_class(self, class_name: str) -> bool:
        """Déterminer si une classe d'objet est statique (affectée par le scrolling)"""
        static_classes = {
            'brick_block', 'mystery_block', 'undestructible_block', 
            'pipe', 'pipe_head', 'flagpole', 'castle', 'platform'
        }
        return class_name in static_classes


class LargeFrameViewer(QWidget):
    """
    Widget pour afficher les frames en GRANDE taille avec annotations.
    Affiche aussi les IDs d'instance pour faciliter le suivi.
    
    Peut mettre en évidence:
    - Toutes les annotations d'une classe (highlight_classes)
    - Un objet spécifique par sa position (highlight_target)
    """
    
    frame_changed = pyqtSignal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.task = None
        self.current_frame = 0
        self.start_frame = 0
        self.end_frame = 0
        self.highlight_classes = []
        
        # Mise en évidence d'un objet spécifique (par position finale)
        self.highlight_target: Optional[Tuple[str, int, int]] = None  # (class_name, x, y)
        
        self._setup_ui()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Zone d'affichage de l'image
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { 
                background-color: #1a1a1a; 
                border: 2px solid #ff9800;
                border-radius: 5px;
            }
        """)
        
        self.image_container = QLabel()
        self.image_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_container.setStyleSheet("background-color: #1a1a1a;")
        self.scroll_area.setWidget(self.image_container)
        
        layout.addWidget(self.scroll_area, stretch=1)
        
        # Barre d'info
        info_layout = QHBoxLayout()
        
        self.frame_label = QLabel("Frame #0")
        self.frame_label.setStyleSheet("color: #ff9800; font-size: 18px; font-weight: bold; padding: 5px;")
        info_layout.addWidget(self.frame_label)
        
        info_layout.addStretch()
        
        self.annotations_label = QLabel("0 annotations")
        self.annotations_label.setStyleSheet("color: #4caf50; font-size: 14px; padding: 5px;")
        info_layout.addWidget(self.annotations_label)
        
        layout.addLayout(info_layout)
        
        # Navigation
        slider_layout = QHBoxLayout()
        
        self.btn_prev10 = QPushButton("⏪ -10")
        self.btn_prev10.setStyleSheet("background-color: #444; color: white; padding: 8px 12px;")
        self.btn_prev10.clicked.connect(lambda: self._move_frames(-10))
        slider_layout.addWidget(self.btn_prev10)
        
        self.btn_prev = QPushButton("◀ -1")
        self.btn_prev.setStyleSheet("background-color: #555; color: white; padding: 8px 15px;")
        self.btn_prev.clicked.connect(lambda: self._move_frames(-1))
        slider_layout.addWidget(self.btn_prev)
        
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setMinimumHeight(25)
        self.slider.setStyleSheet("""
            QSlider::groove:horizontal { background: #444; height: 10px; border-radius: 5px; }
            QSlider::handle:horizontal { background: #ff9800; width: 24px; margin: -7px 0; border-radius: 12px; }
            QSlider::sub-page:horizontal { background: #ff9800; border-radius: 5px; }
        """)
        self.slider.valueChanged.connect(self._on_slider_change)
        slider_layout.addWidget(self.slider, stretch=1)
        
        self.btn_next = QPushButton("+1 ▶")
        self.btn_next.setStyleSheet("background-color: #555; color: white; padding: 8px 15px;")
        self.btn_next.clicked.connect(lambda: self._move_frames(1))
        slider_layout.addWidget(self.btn_next)
        
        self.btn_next10 = QPushButton("+10 ⏩")
        self.btn_next10.setStyleSheet("background-color: #444; color: white; padding: 8px 12px;")
        self.btn_next10.clicked.connect(lambda: self._move_frames(10))
        slider_layout.addWidget(self.btn_next10)
        
        layout.addLayout(slider_layout)
    
    def set_task(self, task):
        self.task = task
    
    def set_range(self, start: int, end: int):
        self.start_frame = start
        self.end_frame = end
        self.slider.setRange(start, end)
        self.current_frame = start
        self.slider.setValue(start)
        self.refresh_display()
    
    def set_highlight_classes(self, classes: List[str]):
        self.highlight_classes = classes
    
    def set_highlight_target(self, target: Optional[Tuple[str, int, int]]):
        """
        Définir un objet spécifique à mettre en évidence.
        
        Args:
            target: Tuple (class_name, x, y) ou None pour désactiver
        """
        self.highlight_target = target
        self.refresh_display()
    
    def go_to_frame(self, frame: int):
        if self.start_frame <= frame <= self.end_frame:
            self.current_frame = frame
            self.slider.blockSignals(True)
            self.slider.setValue(frame)
            self.slider.blockSignals(False)
            self.refresh_display()
            self.frame_changed.emit(frame)
    
    def _move_frames(self, delta: int):
        new_frame = max(self.start_frame, min(self.end_frame, self.current_frame + delta))
        if new_frame != self.current_frame:
            self.go_to_frame(new_frame)
    
    def _on_slider_change(self, value):
        if value != self.current_frame:
            self.current_frame = value
            self.refresh_display()
            self.frame_changed.emit(value)
    
    def refresh_display(self):
        if not self.task or self.current_frame >= len(self.task.images):
            return
        
        img_data = self.task.images[self.current_frame]
        
        pixmap = QPixmap(img_data.image_path)
        if pixmap.isNull():
            return
        
        # Dessiner les annotations
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        for idx, box in enumerate(img_data.boxes):
            # Compter les instances de cette classe avant cet index
            instance_num = 1
            for i in range(idx):
                if img_data.boxes[i].class_name == box.class_name:
                    instance_num += 1
            
            # Déterminer si c'est l'objet cible (par classe et proximité de position)
            is_target = False
            if self.highlight_target:
                target_class, target_x, target_y = self.highlight_target
                if box.class_name == target_class:
                    # Vérifier si c'est proche de la position cible (tolérance de 200px)
                    dist = math.sqrt((box.x - target_x)**2 + (box.y - target_y)**2)
                    if dist < 200:
                        is_target = True
            
            # Couleur selon le type
            if is_target:
                # OBJET CIBLE: Rouge vif avec bordure épaisse
                pen = QPen(QColor(255, 0, 0), 5)  # Rouge
                brush = QBrush(QColor(255, 0, 0, 50))
                label_bg = QColor(255, 0, 0)
                label_text_color = QColor(255, 255, 255)
            elif box.class_name in self.highlight_classes:
                # Classe à rechercher mais pas l'objet cible: Orange
                pen = QPen(QColor(255, 152, 0), 3)
                brush = QBrush(QColor(255, 152, 0, 30))
                label_bg = QColor(255, 152, 0)
                label_text_color = QColor(0, 0, 0)
            else:
                # Autres objets: Vert
                pen = QPen(QColor(76, 175, 80), 2)
                brush = QBrush(QColor(76, 175, 80, 20))
                label_bg = QColor(76, 175, 80)
                label_text_color = QColor(0, 0, 0)
            
            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawRect(box.x, box.y, box.width, box.height)
            
            # Pour l'objet cible, dessiner un indicateur supplémentaire (croix au centre)
            if is_target:
                center_x = box.x + box.width // 2
                center_y = box.y + box.height // 2
                cross_size = 15
                painter.setPen(QPen(QColor(255, 255, 0), 3))  # Jaune
                painter.drawLine(center_x - cross_size, center_y, center_x + cross_size, center_y)
                painter.drawLine(center_x, center_y - cross_size, center_x, center_y + cross_size)
            
            # Label avec numéro d'instance
            font = QFont("Arial", 11, QFont.Weight.Bold)
            painter.setFont(font)
            
            label_text = f"{box.class_name}#{instance_num}"
            metrics = painter.fontMetrics()
            text_width = metrics.horizontalAdvance(label_text) + 8
            text_height = metrics.height() + 4
            
            painter.fillRect(box.x, box.y - text_height - 2, text_width, text_height, label_bg)
            painter.setPen(label_text_color)
            painter.drawText(box.x + 4, box.y - 6, label_text)
        
        painter.end()
        
        # Afficher
        display_width = min(pixmap.width(), 1200)
        scaled = pixmap.scaledToWidth(display_width, Qt.TransformationMode.SmoothTransformation)
        self.image_container.setPixmap(scaled)
        
        # Labels
        self.frame_label.setText(f"Frame #{self.current_frame}")
        count = len(img_data.boxes)
        self.annotations_label.setText(f"{count} annotation{'s' if count != 1 else ''}")
        
        if count == 0:
            self.annotations_label.setStyleSheet("color: #f44336; font-size: 14px; padding: 5px;")
        else:
            self.annotations_label.setStyleSheet("color: #4caf50; font-size: 14px; padding: 5px;")


class InterpolationDialog(QDialog):
    """
    Dialogue d'interpolation interactive avec tracking d'instances.
    
    Chaque objet est identifié de manière unique par son instance_id,
    ce qui permet un suivi correct même avec plusieurs objets de même classe.
    """
    
    def __init__(self, task, start_frame: int, parent=None):
        super().__init__(parent)
        self.task = task
        self.start_frame = start_frame
        self.end_frame = min(start_frame + 30, len(task.images) - 1)
        self.parent_widget = parent
        
        # Tracker d'instances
        self.tracker = InstanceTracker()
        
        # Données
        self.start_instances: List[ObjectInstance] = []
        self.end_instances: List[ObjectInstance] = []
        self.matched_pairs: List[Tuple[ObjectInstance, ObjectInstance]] = []
        self.appearing_instances: List[ObjectInstance] = []  # Nouveaux objets
        self.appearance_frames: Dict[str, int] = {}  # instance_id -> frame d'apparition
        
        # Scrolling détecté
        self.scroll_offset_x: float = 0.0
        
        # Callback
        self.log_callback: Optional[Callable] = None
        
        # Capturer les objets du début
        self._capture_start_instances()
        
        self._setup_ui()
    
    def _log(self, msg: str):
        if self.log_callback:
            self.log_callback(msg)
    
    def _capture_start_instances(self):
        """Capturer les instances du frame de début"""
        self.tracker.reset()
        self.start_instances = self.tracker.create_instances_from_frame(self.task, self.start_frame)
        
        # Log détaillé de chaque objet capturé
        self._log(f"📍 Frame #{self.start_frame}: {len(self.start_instances)} objets capturés")
        for inst in self.start_instances:
            self._log(f"   • {inst.instance_id} at ({inst.x}, {inst.y})")
    
    def _setup_ui(self):
        self.setWindowTitle("📐 Interpolation Interactive v5.4")
        self.setMinimumSize(1200, 800)
        self.setStyleSheet("""
            QDialog { background-color: #2d2d2d; }
            QLabel { color: white; }
            QGroupBox { 
                color: #ff9800; 
                border: 1px solid #5d5d5d; 
                border-radius: 5px; 
                margin-top: 10px; 
                padding-top: 10px;
                font-weight: bold;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QSpinBox { 
                background-color: #3d3d3d; 
                color: white; 
                border: 1px solid #5d5d5d; 
                padding: 5px;
                min-width: 80px;
            }
            QCheckBox { color: white; }
            QListWidget {
                background-color: #3d3d3d;
                color: white;
                border: 1px solid #5d5d5d;
                font-size: 13px;
            }
            QListWidget::item { padding: 8px; }
            QListWidget::item:selected { background-color: #ff9800; color: black; }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # === LIGNE 1: Configuration ===
        top_layout = QHBoxLayout()
        
        # Config frames
        config_group = QGroupBox("📍 Configuration")
        config_layout = QGridLayout(config_group)
        
        # Afficher les instances du début
        start_summary = self._get_instances_summary(self.start_instances)
        config_layout.addWidget(QLabel(f"Frame DÉBUT: #{self.start_frame}"), 0, 0)
        self.start_count_label = QLabel(f"({len(self.start_instances)} objets)")
        self.start_count_label.setStyleSheet("color: #4caf50;")
        self.start_count_label.setToolTip(start_summary)
        config_layout.addWidget(self.start_count_label, 0, 1)
        
        config_layout.addWidget(QLabel("Frame FIN:"), 1, 0)
        self.spin_end = QSpinBox()
        self.spin_end.setRange(self.start_frame + 1, len(self.task.images) - 1)
        self.spin_end.setValue(self.end_frame)
        self.spin_end.valueChanged.connect(self._on_end_frame_changed)
        config_layout.addWidget(self.spin_end, 1, 1)
        
        self.btn_goto_end = QPushButton("📍 Aller annoter la FIN")
        self.btn_goto_end.setStyleSheet("background-color: #ff9800; color: white; padding: 10px; font-weight: bold;")
        self.btn_goto_end.clicked.connect(self._goto_end_frame)
        config_layout.addWidget(self.btn_goto_end, 2, 0, 1, 2)
        
        self.end_status_label = QLabel("⏳ En attente...")
        self.end_status_label.setStyleSheet("color: #888;")
        config_layout.addWidget(self.end_status_label, 3, 0, 1, 2)
        
        top_layout.addWidget(config_group)
        
        # Analyse
        analysis_group = QGroupBox("🔍 Analyse par classe + proximité")
        analysis_layout = QVBoxLayout(analysis_group)
        
        self.btn_analyze = QPushButton("🔍 Analyser et matcher les objets")
        self.btn_analyze.setStyleSheet("background-color: #2196f3; color: white; padding: 12px; font-weight: bold; font-size: 14px;")
        self.btn_analyze.clicked.connect(self._analyze_and_match)
        analysis_layout.addWidget(self.btn_analyze)
        
        self.analysis_result = QLabel("Annotez le frame de fin puis cliquez Analyser")
        self.analysis_result.setWordWrap(True)
        self.analysis_result.setStyleSheet("color: #888; padding: 5px;")
        analysis_layout.addWidget(self.analysis_result)
        
        top_layout.addWidget(analysis_group)
        
        # Objets à localiser
        locate_group = QGroupBox("➕ Nouveaux objets à localiser")
        locate_layout = QVBoxLayout(locate_group)
        
        self.pending_list = QListWidget()
        self.pending_list.setMaximumHeight(120)
        locate_layout.addWidget(self.pending_list)
        
        self.locate_info = QLabel("")
        self.locate_info.setWordWrap(True)
        self.locate_info.setStyleSheet("color: #ff9800; padding: 5px;")
        locate_layout.addWidget(self.locate_info)
        
        top_layout.addWidget(locate_group)
        
        main_layout.addLayout(top_layout)
        
        # === LIGNE 2: Visualiseur ===
        viewer_group = QGroupBox("🖼️ Navigateur - Les annotations affichent leur ID d'instance (ex: mystery_block#1)")
        viewer_layout = QVBoxLayout(viewer_group)
        
        self.frame_viewer = LargeFrameViewer()
        self.frame_viewer.set_task(self.task)
        self.frame_viewer.frame_changed.connect(self._on_viewer_frame_changed)
        viewer_layout.addWidget(self.frame_viewer)
        
        # Boutons
        action_layout = QHBoxLayout()
        
        self.btn_refresh = QPushButton("🔄 Rafraîchir")
        self.btn_refresh.setStyleSheet("background-color: #555; color: white; padding: 10px;")
        self.btn_refresh.clicked.connect(self._refresh_viewer)
        action_layout.addWidget(self.btn_refresh)
        
        action_layout.addStretch()
        
        self.btn_confirm_appearance = QPushButton("✓ Confirmer: l'objet apparaît sur ce frame")
        self.btn_confirm_appearance.setStyleSheet("background-color: #9c27b0; color: white; padding: 12px 20px; font-weight: bold; font-size: 14px;")
        self.btn_confirm_appearance.clicked.connect(self._confirm_appearance)
        self.btn_confirm_appearance.setEnabled(False)
        action_layout.addWidget(self.btn_confirm_appearance)
        
        viewer_layout.addLayout(action_layout)
        
        main_layout.addWidget(viewer_group, stretch=1)
        
        # === LIGNE 3: Boutons finaux ===
        bottom_layout = QHBoxLayout()
        
        self.check_overwrite = QCheckBox("Écraser les annotations existantes")
        self.check_overwrite.setChecked(True)
        bottom_layout.addWidget(self.check_overwrite)
        
        bottom_layout.addStretch()
        
        self.btn_cancel = QPushButton("Annuler")
        self.btn_cancel.setStyleSheet("background-color: #666; color: white; padding: 12px 25px;")
        self.btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(self.btn_cancel)
        
        self.btn_interpolate = QPushButton("📐 Lancer l'interpolation")
        self.btn_interpolate.setStyleSheet("background-color: #4caf50; color: white; padding: 12px 25px; font-weight: bold; font-size: 14px;")
        self.btn_interpolate.clicked.connect(self._execute_interpolation)
        self.btn_interpolate.setEnabled(False)
        bottom_layout.addWidget(self.btn_interpolate)
        
        main_layout.addLayout(bottom_layout)
        
        # Init
        self.frame_viewer.set_range(self.start_frame, self.end_frame)
    
    def _get_instances_summary(self, instances: List[ObjectInstance]) -> str:
        """Créer un résumé des instances pour tooltip"""
        if not instances:
            return "Aucun objet"
        
        lines = []
        for inst in instances:
            lines.append(f"• {inst.instance_id} at ({inst.x}, {inst.y})")
        return "\n".join(lines)
    
    def _on_end_frame_changed(self, value):
        self.end_frame = value
        self._update_end_status()
    
    def _update_end_status(self):
        end_img = self.task.images[self.end_frame]
        count = len(end_img.boxes)
        if count > 0:
            self.end_status_label.setText(f"✅ Frame #{self.end_frame}: {count} objets")
            self.end_status_label.setStyleSheet("color: #4caf50;")
        else:
            self.end_status_label.setText(f"⚠️ Frame #{self.end_frame}: pas annoté")
            self.end_status_label.setStyleSheet("color: #f44336;")
    
    def _goto_end_frame(self):
        self.end_frame = self.spin_end.value()
        self.task.current_index = self.end_frame
        
        if self.parent_widget:
            self.parent_widget._display_current_image()
        
        self._update_end_status()
        
        QMessageBox.information(self, "Navigation",
            f"Vous êtes maintenant au frame #{self.end_frame}.\n\n"
            f"Annotez tous les objets visibles, puis revenez\n"
            f"et cliquez 'Analyser et matcher les objets'.")
    
    def _analyze_and_match(self):
        """Analyser et matcher les objets par proximité et compte de classe"""
        self.end_frame = self.spin_end.value()
        
        # ========================================
        # IMPORTANT: Re-capturer les instances du DÉBUT
        # (au cas où l'utilisateur a ajouté des annotations depuis l'ouverture du dialogue)
        # ========================================
        self._capture_start_instances()
        
        # Mettre à jour l'affichage du nombre d'objets au début
        start_summary = self._get_instances_summary(self.start_instances)
        self.start_count_label.setText(f"({len(self.start_instances)} objets)")
        self.start_count_label.setToolTip(start_summary)
        
        # Vérifier qu'il y a des annotations au début
        if not self.start_instances:
            QMessageBox.warning(self, "Erreur",
                f"Le frame de début #{self.start_frame} n'a pas d'annotations!\n\n"
                f"Annotez d'abord le frame de début avant d'analyser.")
            return
        
        # Avertissement si peu d'objets (probable oubli de sauvegarde)
        if len(self.start_instances) < 3:
            result = QMessageBox.question(self, "Vérification",
                f"Le frame #{self.start_frame} n'a que {len(self.start_instances)} objet(s) annotés.\n\n"
                f"Objets trouvés:\n" + "\n".join([f"  • {inst.instance_id}" for inst in self.start_instances]) + "\n\n"
                f"Si vous avez annoté plus d'objets, assurez-vous de:\n"
                f"1. Fermer la fenêtre 'Annotation Plein Écran'\n"
                f"2. Cliquer 'Sauvegarder' dans l'interface principale\n\n"
                f"Voulez-vous continuer quand même?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if result != QMessageBox.StandardButton.Yes:
                return
        
        # Créer les instances de fin
        end_img = self.task.images[self.end_frame]
        if not end_img.boxes:
            QMessageBox.warning(self, "Erreur",
                f"Le frame #{self.end_frame} n'a pas d'annotations!")
            return
        
        # Créer des instances temporaires pour la fin avec des IDs lisibles
        self.end_instances = []
        class_counters: Dict[str, int] = {}
        
        for idx, box in enumerate(end_img.boxes):
            # Compter les instances de cette classe
            if box.class_name not in class_counters:
                class_counters[box.class_name] = 0
            class_counters[box.class_name] += 1
            instance_num = class_counters[box.class_name]
            
            instance_id = f"{box.class_name}#{instance_num}"
            instance = ObjectInstance(
                instance_id=instance_id,
                class_id=box.class_id,
                class_name=box.class_name,
                x=box.x, y=box.y,
                width=box.width, height=box.height
            )
            self.end_instances.append(instance)
        
        # Compter par classe pour l'affichage
        start_class_count: Dict[str, int] = {}
        end_class_count: Dict[str, int] = {}
        
        for obj in self.start_instances:
            start_class_count[obj.class_name] = start_class_count.get(obj.class_name, 0) + 1
        for obj in self.end_instances:
            end_class_count[obj.class_name] = end_class_count.get(obj.class_name, 0) + 1
        
        # Log le compte par classe
        self._log(f"📊 Analyse par classe:")
        self._log(f"   Frame début #{self.start_frame}: {len(self.start_instances)} objets")
        self._log(f"   Frame fin #{self.end_frame}: {len(self.end_instances)} objets")
        
        all_classes = set(list(start_class_count.keys()) + list(end_class_count.keys()))
        for cls in sorted(all_classes):
            s = start_class_count.get(cls, 0)
            e = end_class_count.get(cls, 0)
            diff = e - s
            if diff > 0:
                self._log(f"   {cls}: {s} → {e} (+{diff} nouveau)")
            elif diff < 0:
                self._log(f"   {cls}: {s} → {e} ({diff} disparu)")
            else:
                self._log(f"   {cls}: {s} → {e} (=)")
        
        # Matcher par proximité ET par compte de classe (avec détection scrolling)
        self.matched_pairs, disappeared, self.appearing_instances = \
            self.tracker.match_by_proximity(self.start_instances, self.end_instances)
        
        # Récupérer le scrolling détecté
        self.scroll_offset_x = self.tracker._detect_scrolling(self.start_instances, self.end_instances)
        
        # Log le scrolling
        if abs(self.scroll_offset_x) > 10:
            self._log(f"📜 Scrolling détecté: {self.scroll_offset_x:.0f}px (vers la {'droite' if self.scroll_offset_x < 0 else 'gauche'})")
        
        # Log le matching
        self._log(f"🔗 Matching: {len(self.matched_pairs)} paires")
        for start_obj, end_obj in self.matched_pairs:
            dist = start_obj.distance_to(end_obj)
            self._log(f"   {start_obj.instance_id} → {end_obj.instance_id} ({dist:.0f}px)")
        
        if self.appearing_instances:
            self._log(f"➕ Nouveaux: {len(self.appearing_instances)}")
            for obj in self.appearing_instances:
                self._log(f"   {obj.instance_id} at ({obj.x}, {obj.y})")
        
        if disappeared:
            self._log(f"➖ Disparus: {len(disappeared)}")
            for obj in disappeared:
                self._log(f"   {obj.instance_id}")
        
        # Réinitialiser les frames d'apparition
        self.appearance_frames.clear()
        
        # Afficher le résultat avec détail par classe
        result_html = f"<b style='color:#4caf50;'>✓ {len(self.matched_pairs)} objets matchés</b><br>"
        result_html += f"Début: {len(self.start_instances)} | Fin: {len(self.end_instances)}<br>"
        
        # Afficher le scrolling détecté
        if abs(self.scroll_offset_x) > 10:
            direction = "→" if self.scroll_offset_x < 0 else "←"
            result_html += f"<br><b style='color:#2196f3;'>📜 Scrolling: {abs(self.scroll_offset_x):.0f}px {direction}</b>"
        
        # Montrer les différences par classe
        changes = []
        for cls in sorted(all_classes):
            s = start_class_count.get(cls, 0)
            e = end_class_count.get(cls, 0)
            if e > s:
                changes.append(f"+{e-s} {cls}")
            elif s > e:
                changes.append(f"-{s-e} {cls}")
        
        if changes:
            result_html += f"<br><small>Changements: {', '.join(changes)}</small>"
        
        if disappeared:
            result_html += f"<br><b style='color:#f44336;'>✗ {len(disappeared)} disparus</b>"
        
        if self.appearing_instances:
            result_html += f"<br><b style='color:#ff9800;'>➕ {len(self.appearing_instances)} nouveaux</b>"
        
        self.analysis_result.setText(result_html)
        self.analysis_result.setStyleSheet("color: white; padding: 5px;")
        
        # Remplir la liste des objets à localiser avec les instance_ids
        self.pending_list.clear()
        
        # Déconnecter l'ancien signal si connecté
        try:
            self.pending_list.currentRowChanged.disconnect(self._on_pending_selection_changed)
        except:
            pass
        
        for obj in self.appearing_instances:
            # Afficher l'instance_id complet
            item = QListWidgetItem(f"➕ {obj.instance_id} at ({obj.x}, {obj.y}) - À localiser")
            # Stocker les données complètes pour identifier l'objet
            item.setData(Qt.ItemDataRole.UserRole, {
                'instance_id': obj.instance_id,
                'class_name': obj.class_name,
                'x': obj.x,
                'y': obj.y
            })
            self.pending_list.addItem(item)
        
        # Connecter le changement de sélection
        self.pending_list.currentRowChanged.connect(self._on_pending_selection_changed)
        
        # Mettre à jour l'UI
        if self.appearing_instances:
            self.pending_list.setCurrentRow(0)
            self._update_target_highlight(0)
            
            self.frame_viewer.set_highlight_classes([obj.class_name for obj in self.appearing_instances])
            self.frame_viewer.set_range(self.start_frame, self.end_frame)
            self.btn_confirm_appearance.setEnabled(True)
            self.btn_interpolate.setEnabled(False)
        else:
            self.locate_info.setText("✅ Aucun nouvel objet - Prêt à interpoler!")
            self.locate_info.setStyleSheet("color: #4caf50; padding: 5px;")
            self.frame_viewer.set_highlight_classes([])
            self.frame_viewer.set_highlight_target(None)
            self.frame_viewer.set_range(self.start_frame, self.end_frame)
            self.btn_confirm_appearance.setEnabled(False)
            self.btn_interpolate.setEnabled(True)
    
    def _on_pending_selection_changed(self, row: int):
        """Quand la sélection change dans la liste des objets à localiser"""
        self._update_target_highlight(row)
    
    def _update_target_highlight(self, row: int):
        """Mettre à jour la mise en évidence de l'objet cible"""
        if row < 0 or row >= self.pending_list.count():
            self.frame_viewer.set_highlight_target(None)
            return
        
        item = self.pending_list.item(row)
        data = item.data(Qt.ItemDataRole.UserRole)
        
        if data:
            # Définir l'objet cible pour la mise en évidence
            self.frame_viewer.set_highlight_target((data['class_name'], data['x'], data['y']))
            
            # Mettre à jour le texte d'info
            self.locate_info.setText(
                f"🔍 Recherchez: <b style='color:#ff0000;'>{data['instance_id']}</b>\n"
                f"Position finale: ({data['x']}, {data['y']})\n"
                f"L'objet est en <b style='color:#ff0000;'>ROUGE</b> sur l'image.\n"
                f"Annotez-le, puis cliquez 'Confirmer'."
            )
            self.locate_info.setStyleSheet("color: #ff9800; padding: 5px;")
    
    def _on_viewer_frame_changed(self, frame: int):
        self.task.current_index = frame
        if self.parent_widget:
            self.parent_widget._display_current_image()
    
    def _refresh_viewer(self):
        self.frame_viewer.refresh_display()
        self._log(f"🔄 Rafraîchi - Frame #{self.frame_viewer.current_frame}")
    
    def _confirm_appearance(self):
        """Confirmer l'apparition d'un objet"""
        if not self.appearing_instances or self.pending_list.currentRow() < 0:
            return
        
        current_frame = self.frame_viewer.current_frame
        current_item = self.pending_list.currentItem()
        data = current_item.data(Qt.ItemDataRole.UserRole)
        
        if not data:
            return
        
        instance_id = data['instance_id']
        target_class = data['class_name']
        target_x = data['x']
        target_y = data['y']
        
        # Trouver l'objet correspondant dans appearing_instances
        target_obj = None
        for obj in self.appearing_instances:
            if obj.instance_id == instance_id:
                target_obj = obj
                break
        
        if not target_obj:
            return
        
        # Vérifier qu'il y a une annotation de cette classe sur ce frame
        current_img = self.task.images[current_frame]
        found = False
        for box in current_img.boxes:
            if box.class_name == target_class:
                found = True
                break
        
        if not found:
            QMessageBox.warning(self, "Objet non trouvé",
                f"Aucun '{target_class}' annoté sur le frame #{current_frame}!\n\n"
                f"1. Annotez '{target_class}' sur ce frame\n"
                f"2. Cliquez '🔄 Rafraîchir'\n"
                f"3. Cliquez 'Confirmer' à nouveau")
            return
        
        # Enregistrer
        self.appearance_frames[instance_id] = current_frame
        self._log(f"✓ {instance_id} apparaît au frame #{current_frame}")
        
        # Mettre à jour l'item
        current_item.setText(f"✓ {instance_id} - Frame #{current_frame}")
        current_item.setBackground(QColor(76, 175, 80))
        current_item.setForeground(QColor(255, 255, 255))
        
        # Prochain objet
        remaining = [obj for obj in self.appearing_instances 
                     if obj.instance_id not in self.appearance_frames]
        
        if remaining:
            next_obj = remaining[0]
            for i in range(self.pending_list.count()):
                item = self.pending_list.item(i)
                item_data = item.data(Qt.ItemDataRole.UserRole)
                if item_data and item_data['instance_id'] == next_obj.instance_id:
                    self.pending_list.setCurrentRow(i)
                    break
        else:
            self.locate_info.setText("✅ Tous les objets localisés - Prêt à interpoler!")
            self.locate_info.setStyleSheet("color: #4caf50; padding: 5px;")
            self.btn_confirm_appearance.setEnabled(False)
            self.btn_interpolate.setEnabled(True)
            self.frame_viewer.set_highlight_target(None)
    
    def _execute_interpolation(self):
        """Exécuter l'interpolation en respectant les IDs d'instance"""
        self._log(f"📐 Interpolation #{self.start_frame} → #{self.end_frame}")
        
        # Construire la liste des paires d'interpolation
        interpolation_pairs: List[InterpolationPair] = []
        
        # 1. Objets matchés (présents du début à la fin)
        for start_obj, end_obj in self.matched_pairs:
            interpolation_pairs.append(InterpolationPair(
                instance_id=start_obj.instance_id,
                start_obj=start_obj,
                end_obj=end_obj,
                appear_frame=self.start_frame
            ))
        
        # 2. Objets qui apparaissent
        for obj in self.appearing_instances:
            appear_frame = self.appearance_frames.get(obj.instance_id, (self.start_frame + self.end_frame) // 2)
            
            # Récupérer la position au frame d'apparition
            appear_img = self.task.images[appear_frame]
            start_obj = None
            
            # Trouver l'annotation correspondante par classe et proximité
            best_match = None
            best_dist = float('inf')
            
            for box in appear_img.boxes:
                if box.class_name == obj.class_name:
                    # Calculer distance avec la position finale
                    dist = math.sqrt((box.x - obj.x)**2 + (box.y - obj.y)**2)
                    if dist < best_dist:
                        best_dist = dist
                        best_match = box
            
            if best_match:
                start_obj = ObjectInstance(
                    instance_id=f"{obj.class_name}#appear",
                    class_id=best_match.class_id,
                    class_name=best_match.class_name,
                    x=best_match.x, y=best_match.y,
                    width=best_match.width, height=best_match.height
                )
            else:
                # Fallback: utiliser la position finale
                start_obj = obj
            
            interpolation_pairs.append(InterpolationPair(
                instance_id=obj.instance_id,
                start_obj=start_obj,
                end_obj=obj,
                appear_frame=appear_frame
            ))
        
        # Log les paires
        self._log(f"📊 {len(interpolation_pairs)} paires à interpoler:")
        for pair in interpolation_pairs:
            self._log(f"   {pair.instance_id}: frame {pair.appear_frame} → {self.end_frame}")
        
        # Exécuter l'interpolation
        total_frames = self.end_frame - self.start_frame - 1
        
        for frame_offset in range(1, total_frames + 1):
            frame_idx = self.start_frame + frame_offset
            
            self.task.current_index = frame_idx
            
            if self.check_overwrite.isChecked():
                self.task.clear_annotations()
            
            for pair in interpolation_pairs:
                # Ignorer si l'objet n'est pas encore apparu
                if frame_idx < pair.appear_frame:
                    continue
                
                # Calculer la progression
                if pair.appear_frame == self.start_frame:
                    # Objet présent dès le début
                    progress = frame_offset / (total_frames + 1)
                else:
                    # Objet qui apparaît plus tard
                    segment_length = self.end_frame - pair.appear_frame
                    if segment_length <= 0:
                        progress = 1.0
                    else:
                        progress = (frame_idx - pair.appear_frame) / segment_length
                
                # Interpoler
                start = pair.start_obj
                end = pair.end_obj
                
                x = int(start.x + (end.x - start.x) * progress)
                y = int(start.y + (end.y - start.y) * progress)
                w = int(start.width + (end.width - start.width) * progress)
                h = int(start.height + (end.height - start.height) * progress)
                
                if w > 5 and h > 5:
                    self.task.add_annotation(end.class_id, x, y, w, h)
            
            self.task.save_current_annotations()
        
        # Retour au début
        self.task.current_index = self.start_frame
        
        # Stats
        common_count = len(self.matched_pairs)
        appearing_count = len(self.appearing_instances)
        
        self._log(f"✅ Interpolation terminée: {total_frames} frames")
        
        QMessageBox.information(self, "Interpolation terminée",
            f"✅ {total_frames} frames annotés!\n\n"
            f"• Objets suivis (matchés): {common_count}\n"
            f"• Objets apparus: {appearing_count}\n"
            f"• Du frame #{self.start_frame} au frame #{self.end_frame}\n\n"
            f"Chaque objet a été interpolé individuellement\n"
            f"grâce à son ID d'instance unique.")
        
        self.accept()