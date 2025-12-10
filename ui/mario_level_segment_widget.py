"""
Mario Level Segment Widget - Interface pour la segmentation par niveaux Mario
Widget interactif avec classification des niveaux (1-1, 2-3, etc.)
"""

import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QGridLayout, QProgressBar, QLineEdit, QSpinBox, QCheckBox,
    QDialog, QTextEdit, QComboBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QImage

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class ROISelectorWidget(QLabel):
    """Widget pour sélectionner une région d'intérêt (ROI) sur une image"""
    
    roi_selected = pyqtSignal(tuple)  # (x1_rel, y1_rel, x2_rel, y2_rel)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.original_pixmap = None
        self.scale_factor = 1.0
        self.image_offset = QPoint(0, 0)
        self.original_size = (0, 0)  # (width, height)
        
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.roi_rect = None  # En coordonnées relatives (0-1)
        
        self.setFixedHeight(250)
        self.setMinimumWidth(400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background-color: #2D2D2D; border: 2px solid #FF9800;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Chargez un dossier pour définir la zone WORLD")
    
    def set_image(self, image_path: str):
        """Charger une image"""
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.original_pixmap = pixmap
            self.original_size = (pixmap.width(), pixmap.height())
            self._update_display()
    
    def _update_display(self):
        """Mettre à jour l'affichage"""
        if self.original_pixmap is None:
            return
        
        available_width = self.width() - 4
        available_height = self.height() - 4
        
        scale_w = available_width / self.original_pixmap.width()
        scale_h = available_height / self.original_pixmap.height()
        self.scale_factor = min(scale_w, scale_h, 1.0)
        
        scaled = self.original_pixmap.scaled(
            int(self.original_pixmap.width() * self.scale_factor),
            int(self.original_pixmap.height() * self.scale_factor),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.image_offset = QPoint(
            (self.width() - scaled.width()) // 2,
            (self.height() - scaled.height()) // 2
        )
        
        display = QPixmap(self.size())
        display.fill(QColor("#2D2D2D"))
        
        painter = QPainter(display)
        painter.drawPixmap(self.image_offset, scaled)
        
        # Dessiner la ROI si définie
        if self.roi_rect:
            pen = QPen(QColor(255, 0, 0, 200), 3)
            painter.setPen(pen)
            
            x1 = int(self.roi_rect[0] * scaled.width()) + self.image_offset.x()
            y1 = int(self.roi_rect[1] * scaled.height()) + self.image_offset.y()
            x2 = int(self.roi_rect[2] * scaled.width()) + self.image_offset.x()
            y2 = int(self.roi_rect[3] * scaled.height()) + self.image_offset.y()
            
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
            
            # Label
            painter.setPen(QPen(QColor(255, 0, 0)))
            painter.drawText(x1, y1 - 5, "ZONE WORLD")
        
        # Rectangle en cours de dessin
        if self.drawing and self.start_point and self.end_point:
            pen = QPen(QColor(0, 255, 0, 200), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            from PyQt6.QtCore import QRect
            rect = QRect(self.start_point, self.end_point).normalized()
            painter.drawRect(rect)
        
        painter.end()
        super().setPixmap(display)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.original_pixmap:
            self.drawing = True
            self.start_point = event.pos()
            self.end_point = event.pos()
    
    def mouseMoveEvent(self, event):
        if self.drawing:
            self.end_point = event.pos()
            self._update_display()
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            self.end_point = event.pos()
            
            if self.start_point and self.end_point and self.original_pixmap:
                scaled_width = int(self.original_pixmap.width() * self.scale_factor)
                scaled_height = int(self.original_pixmap.height() * self.scale_factor)
                
                # Convertir en coordonnées relatives (0-1)
                x1 = (self.start_point.x() - self.image_offset.x()) / scaled_width
                y1 = (self.start_point.y() - self.image_offset.y()) / scaled_height
                x2 = (self.end_point.x() - self.image_offset.x()) / scaled_width
                y2 = (self.end_point.y() - self.image_offset.y()) / scaled_height
                
                # Normaliser et clamper
                x1, x2 = min(x1, x2), max(x1, x2)
                y1, y2 = min(y1, y2), max(y1, y2)
                x1, x2 = max(0, x1), min(1, x2)
                y1, y2 = max(0, y1), min(1, y2)
                
                if (x2 - x1) > 0.02 and (y2 - y1) > 0.02:
                    self.roi_rect = (x1, y1, x2, y2)
                    self._update_display()
                    self.roi_selected.emit(self.roi_rect)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display()
    
    def get_roi(self):
        return self.roi_rect
    
    def set_roi(self, roi: tuple):
        """Définir la ROI manuellement"""
        self.roi_rect = roi
        self._update_display()
    
    def clear_roi(self):
        self.roi_rect = None
        self._update_display()


class LevelClassificationDialog(QDialog):
    """Dialogue de classification du niveau Mario"""
    
    # Tous les niveaux possibles
    ALL_LEVELS = [f"{w}-{s}" for w in range(1, 9) for s in range(1, 5)]
    
    def __init__(self, frame_data, roi_coords, context: str, parent=None):
        super().__init__(parent)
        
        self.frame_data = frame_data
        self.roi_coords = roi_coords  # (x1_rel, y1_rel, x2_rel, y2_rel)
        self.result = None
        
        self.setWindowTitle(f"Classification Niveau - {context}")
        self.setMinimumSize(850, 650)
        self.setModal(True)
        
        self._create_ui(context)
        self._load_image()
    
    def _create_ui(self, context: str):
        """Créer l'interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # Info
        info_layout = QHBoxLayout()
        info_layout.addWidget(QLabel(f"<b>Contexte:</b> {context}"))
        info_layout.addStretch()
        info_layout.addWidget(QLabel(f"<b>Frame:</b> {self.frame_data.filename}"))
        layout.addLayout(info_layout)
        
        # Image
        self.image_label = QLabel("Chargement...")
        self.image_label.setFixedSize(800, 400)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1E1E1E; border: 2px solid #FF5722;")
        layout.addWidget(self.image_label)
        
        # Instruction - texte court et visible
        instr = QLabel("🎯 Regardez la zone ROUGE et identifiez le niveau (ex: 1-1, 2-3, 8-4)")
        instr.setStyleSheet("font-size: 13px; font-weight: bold; color: #FF5722; padding: 8px; background-color: #FFF3E0; border-radius: 4px;")
        instr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instr)
        
        # Sélection rapide par World
        world_group = QGroupBox("🌍 Sélection Rapide par World")
        world_layout = QGridLayout()
        
        for world in range(1, 9):
            world_label = QLabel(f"World {world}:")
            world_label.setStyleSheet("font-weight: bold;")
            world_layout.addWidget(world_label, world - 1, 0)
            
            for stage in range(1, 5):
                level = f"{world}-{stage}"
                btn = QPushButton(level)
                btn.setFixedSize(60, 35)
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background-color: {self._get_world_color(world)};
                        color: white;
                        font-weight: bold;
                        border: none;
                        border-radius: 4px;
                    }}
                    QPushButton:hover {{
                        background-color: {self._get_world_color(world)}CC;
                    }}
                """)
                btn.clicked.connect(lambda checked, l=level: self._select_level(l))
                world_layout.addWidget(btn, world - 1, stage)
        
        world_group.setLayout(world_layout)
        layout.addWidget(world_group)
        
        # Saisie manuelle
        manual_layout = QHBoxLayout()
        
        manual_layout.addWidget(QLabel("Ou saisie manuelle:"))
        
        self.level_input = QLineEdit()
        self.level_input.setPlaceholderText("Ex: 1-1, 2-3, 8-4...")
        self.level_input.setFixedWidth(100)
        self.level_input.returnPressed.connect(self._validate_manual)
        manual_layout.addWidget(self.level_input)
        
        btn_validate = QPushButton("✓ Valider")
        btn_validate.clicked.connect(self._validate_manual)
        manual_layout.addWidget(btn_validate)
        
        manual_layout.addSpacing(30)
        
        btn_unknown = QPushButton("❓ Inconnu")
        btn_unknown.setStyleSheet("background-color: #9E9E9E; color: white;")
        btn_unknown.clicked.connect(lambda: self._select_level("unknown"))
        manual_layout.addWidget(btn_unknown)
        
        btn_cancel = QPushButton("✖ Annuler")
        btn_cancel.setStyleSheet("background-color: #F44336; color: white;")
        btn_cancel.clicked.connect(self._cancel)
        manual_layout.addWidget(btn_cancel)
        
        manual_layout.addStretch()
        
        layout.addLayout(manual_layout)
        
        # Raccourcis
        shortcut_label = QLabel("💡 Cliquez sur un niveau ou tapez X-Y puis Entrée | Échap = Annuler")
        shortcut_label.setStyleSheet("color: #888; font-size: 10px;")
        shortcut_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(shortcut_label)
    
    def _get_world_color(self, world: int) -> str:
        """Couleur par world"""
        colors = {
            1: "#4CAF50",  # Vert
            2: "#FF9800",  # Orange
            3: "#2196F3",  # Bleu
            4: "#9C27B0",  # Violet
            5: "#F44336",  # Rouge
            6: "#00BCD4",  # Cyan
            7: "#795548",  # Marron
            8: "#607D8B",  # Gris
        }
        return colors.get(world, "#666")
    
    def _load_image(self):
        """Charger et afficher l'image avec ROI"""
        try:
            if CV2_AVAILABLE:
                img = cv2.imread(self.frame_data.filepath)
                if img is not None:
                    h, w = img.shape[:2]
                    
                    # Dessiner la ROI si définie
                    if self.roi_coords and len(self.roi_coords) == 4:
                        x1 = int(w * self.roi_coords[0])
                        y1 = int(h * self.roi_coords[1])
                        x2 = int(w * self.roi_coords[2])
                        y2 = int(h * self.roi_coords[3])
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 3)
                        cv2.putText(img, "NIVEAU ICI", (x1, max(y1 - 10, 20)),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    
                    # Convertir
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    qimg = QImage(img_rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg)
                    
                    # Redimensionner pour tenir dans le label
                    scaled = pixmap.scaled(
                        780, 380,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.image_label.setPixmap(scaled)
                    return
            
            # Fallback
            pixmap = QPixmap(self.frame_data.filepath)
            if not pixmap.isNull():
                scaled = pixmap.scaled(780, 380, Qt.AspectRatioMode.KeepAspectRatio)
                self.image_label.setPixmap(scaled)
        except Exception as e:
            self.image_label.setText(f"Erreur: {e}")
    
    def _select_level(self, level: str):
        """Sélectionner un niveau"""
        self.result = level
        self.accept()
    
    def _validate_manual(self):
        """Valider la saisie manuelle"""
        text = self.level_input.text().strip()
        
        import re
        if re.match(r'^\d-\d$', text):
            self._select_level(text)
        elif text.lower() in ['unknown', 'skip', '?']:
            self._select_level("unknown")
        else:
            QMessageBox.warning(self, "Format invalide", 
                              "Utilisez le format X-Y (ex: 1-1, 2-3, 8-4)")
    
    def _cancel(self):
        """Annuler"""
        self.result = "cancel"
        self.reject()
    
    def keyPressEvent(self, event):
        """Raccourcis clavier"""
        if event.key() == Qt.Key.Key_Escape:
            self._cancel()
        elif event.key() == Qt.Key.Key_U:
            self._select_level("unknown")
        else:
            super().keyPressEvent(event)


class LevelSegmentCard(QFrame):
    """Carte affichant un segment de niveau"""
    
    def __init__(self, level: str, segments: list, parent=None):
        super().__init__(parent)
        
        total_count = sum(seg.get('count', 0) for seg in segments)
        
        # Couleur par world
        world = int(level.split('-')[0]) if '-' in level else 1
        colors = {
            1: "#4CAF50", 2: "#FF9800", 3: "#2196F3", 4: "#9C27B0",
            5: "#F44336", 6: "#00BCD4", 7: "#795548", 8: "#607D8B"
        }
        color = colors.get(world, "#666")
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color}20;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 8px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        
        # Niveau
        level_label = QLabel(f"🎮 World {level}")
        level_label.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")
        layout.addWidget(level_label)
        
        # Count
        count_label = QLabel(f"{total_count:,} frames")
        count_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(count_label)
        
        # Segments
        seg_label = QLabel(f"{len(segments)} segment(s)")
        seg_label.setStyleSheet("font-size: 10px; color: #666;")
        layout.addWidget(seg_label)


class MarioLevelSegmentWidget(QWidget):
    """
    Widget pour la segmentation par niveaux Mario
    """
    
    task_requested = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.frames_dir = None
        self.current_task = None
        self.last_results = None
        self.level_classifications = {}
        self.analysis_completed = False
        self.roi_coords = None  # ROI définie par l'utilisateur
        
        self._create_ui()
    
    def _create_ui(self):
        """Créer l'interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)
        
        # 1. Bannière
        content_layout.addWidget(self._create_info_banner())
        
        # 2. Sélection dossier
        content_layout.addWidget(self._create_folder_group())
        
        # 3. Configuration ROI
        content_layout.addWidget(self._create_roi_group())
        
        # 4. Configuration avancée
        content_layout.addWidget(self._create_config_group())
        
        # 5. Résultats
        content_layout.addWidget(self._create_results_group())
        
        content_layout.addStretch()
        
        # 6. Boutons
        content_layout.addLayout(self._create_action_buttons())
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def _create_info_banner(self):
        """Bannière d'info"""
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background-color: #FFF3E0;
                border: 2px solid #FF9800;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(banner)
        
        title = QLabel("🎮 Segmentation par Niveaux Mario")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #E65100;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Segmente automatiquement les frames par niveau Mario (1-1, 2-3, 8-4, etc.)\n\n"
            "<b>Algorithme:</b> Intervalles réguliers + dichotomie pour trouver les transitions\n"
            "<b>Processus:</b> Classifiez quelques frames, l'algorithme déduit les frontières\n"
            "<b>Sortie:</b> Dataset organisé par niveau + export YOLO optionnel"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #E65100; font-size: 11px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_folder_group(self):
        """Groupe sélection dossier"""
        group = QGroupBox("📁 Dossier de Frames")
        group.setStyleSheet(self._get_group_style("#2196F3"))
        
        layout = QGridLayout()
        
        layout.addWidget(QLabel("Dossier:"), 0, 0)
        
        self.folder_label = QLabel("Non sélectionné")
        self.folder_label.setStyleSheet(self._get_label_style(False))
        layout.addWidget(self.folder_label, 0, 1)
        
        btn_browse = QPushButton("📂 Parcourir")
        btn_browse.setStyleSheet(self._get_button_style("#2196F3"))
        btn_browse.clicked.connect(self._browse_folder)
        layout.addWidget(btn_browse, 0, 2)
        
        self.folder_info = QLabel("")
        self.folder_info.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.folder_info, 1, 1, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def _create_roi_group(self):
        """Groupe configuration de la zone WORLD"""
        group = QGroupBox("🎯 Zone d'Identification du Niveau")
        group.setStyleSheet(self._get_group_style("#FF5722"))
        
        layout = QVBoxLayout()
        
        # Instructions
        instr = QLabel("Dessinez un rectangle autour de la zone affichant le niveau (ex: WORLD 1-1)")
        instr.setWordWrap(True)
        instr.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        layout.addWidget(instr)
        
        # Sélecteur ROI
        self.roi_selector = ROISelectorWidget()
        self.roi_selector.roi_selected.connect(self._on_roi_selected)
        layout.addWidget(self.roi_selector)
        
        # Infos ROI
        roi_info_layout = QHBoxLayout()
        
        self.roi_status = QLabel("⚠️ ROI non définie - Dessinez un rectangle sur l'image")
        self.roi_status.setStyleSheet("color: #FF5722; font-weight: bold;")
        roi_info_layout.addWidget(self.roi_status)
        
        roi_info_layout.addStretch()
        
        btn_default_roi = QPushButton("📍 ROI par défaut")
        btn_default_roi.setToolTip("Utiliser la position par défaut (coin supérieur droit)")
        btn_default_roi.clicked.connect(self._set_default_roi)
        roi_info_layout.addWidget(btn_default_roi)
        
        btn_clear_roi = QPushButton("🗑️ Effacer")
        btn_clear_roi.clicked.connect(self._clear_roi)
        roi_info_layout.addWidget(btn_clear_roi)
        
        layout.addLayout(roi_info_layout)
        
        group.setLayout(layout)
        return group
    
    def _on_roi_selected(self, roi: tuple):
        """Quand la ROI est sélectionnée"""
        self.roi_coords = roi
        self.roi_status.setText(f"✅ ROI définie: ({roi[0]:.2f}, {roi[1]:.2f}) → ({roi[2]:.2f}, {roi[3]:.2f})")
        self.roi_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self._check_ready()
    
    def _set_default_roi(self):
        """Définir la ROI par défaut"""
        default_roi = (0.62, 0.04, 0.88, 0.18)
        self.roi_coords = default_roi
        self.roi_selector.set_roi(default_roi)
        self.roi_status.setText(f"✅ ROI par défaut: ({default_roi[0]:.2f}, {default_roi[1]:.2f}) → ({default_roi[2]:.2f}, {default_roi[3]:.2f})")
        self.roi_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self._check_ready()
    
    def _clear_roi(self):
        """Effacer la ROI"""
        self.roi_coords = None
        self.roi_selector.clear_roi()
        self.roi_status.setText("⚠️ ROI non définie - Dessinez un rectangle sur l'image")
        self.roi_status.setStyleSheet("color: #FF5722; font-weight: bold;")
        self._check_ready()
    
    def _check_ready(self):
        """Vérifier si prêt à lancer"""
        ready = self.frames_dir is not None and self.roi_coords is not None
        self.btn_start.setEnabled(ready)
    
    def _create_config_group(self):
        """Groupe configuration"""
        group = QGroupBox("⚙️ Configuration")
        group.setStyleSheet(self._get_group_style("#FF9800"))
        group.setCheckable(True)
        group.setChecked(False)
        
        layout = QGridLayout()
        
        # Taille intervalle
        layout.addWidget(QLabel("Taille intervalle:"), 0, 0)
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(100, 5000)
        self.spin_interval.setValue(1000)
        self.spin_interval.setSuffix(" frames")
        self.spin_interval.setSpecialValueText("Auto")
        layout.addWidget(self.spin_interval, 0, 1)
        
        # Dossier sortie
        layout.addWidget(QLabel("Dossier sortie:"), 1, 0)
        self.edit_output = QLineEdit("mario_level_dataset")
        layout.addWidget(self.edit_output, 1, 1)
        
        # Option YOLO
        self.check_yolo = QCheckBox("Créer dataset YOLO après segmentation")
        layout.addWidget(self.check_yolo, 2, 0, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def _create_results_group(self):
        """Groupe résultats"""
        group = QGroupBox("📊 Résultats")
        group.setStyleSheet(self._get_group_style("#4CAF50"))
        
        layout = QVBoxLayout()
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar)
        
        # Status
        self.status_label = QLabel("En attente...")
        layout.addWidget(self.status_label)
        
        # Cartes des niveaux détectés
        self.levels_scroll = QScrollArea()
        self.levels_scroll.setWidgetResizable(True)
        self.levels_scroll.setMaximumHeight(150)
        self.levels_scroll.setStyleSheet("QScrollArea { border: 1px solid #E0E0E0; }")
        
        self.levels_container = QWidget()
        self.levels_layout = QHBoxLayout(self.levels_container)
        self.levels_layout.setSpacing(10)
        self.levels_layout.addStretch()
        
        self.levels_scroll.setWidget(self.levels_container)
        layout.addWidget(self.levels_scroll)
        
        # Résumé texte
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(120)
        layout.addWidget(self.results_text)
        
        group.setLayout(layout)
        return group
    
    def _create_action_buttons(self):
        """Boutons d'action"""
        layout = QHBoxLayout()
        
        self.btn_report = QPushButton("📄 Rapport")
        self.btn_report.setStyleSheet(self._get_button_style("#607D8B"))
        self.btn_report.clicked.connect(self._view_report)
        self.btn_report.setEnabled(False)
        layout.addWidget(self.btn_report)
        
        self.btn_reset = QPushButton("🔄 Réinitialiser")
        self.btn_reset.setStyleSheet(self._get_button_style("#FF5722"))
        self.btn_reset.clicked.connect(self._reset)
        self.btn_reset.setEnabled(False)
        layout.addWidget(self.btn_reset)
        
        layout.addStretch()
        
        self.btn_start = QPushButton("🎮 Lancer la Segmentation")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 15px 30px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: #BDBDBD; }
        """)
        self.btn_start.clicked.connect(self._start_segmentation)
        self.btn_start.setEnabled(False)
        layout.addWidget(self.btn_start)
        
        return layout
    
    def _get_group_style(self, color: str) -> str:
        return f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                color: {color};
            }}
        """
    
    def _get_button_style(self, color: str) -> str:
        return f"""
            QPushButton {{
                background-color: {color};
                color: white;
                font-weight: bold;
                padding: 8px 15px;
                border: none;
                border-radius: 4px;
            }}
            QPushButton:hover {{ background-color: {color}CC; }}
        """
    
    def _get_label_style(self, selected: bool) -> str:
        if selected:
            return "padding: 8px; background-color: #E3F2FD; border: 1px solid #2196F3; border-radius: 4px; color: #1565C0; font-weight: bold;"
        return "padding: 8px; background-color: #FAFAFA; border: 1px solid #E0E0E0; border-radius: 4px; color: #757575;"
    
    def _browse_folder(self):
        """Parcourir"""
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier", "")
        
        if folder:
            if self.frames_dir and self.frames_dir != folder:
                self._reset_state()
            
            self.frames_dir = folder
            self.folder_label.setText(f"📁 {os.path.basename(folder)}")
            self.folder_label.setToolTip(folder)
            self.folder_label.setStyleSheet(self._get_label_style(True))
            
            # Analyser
            count = self._count_images(folder)
            self.folder_info.setText(f"📷 {count:,} images")
            
            # Charger une image sample pour le sélecteur ROI
            self._load_sample_image(folder)
            
            # Vérifier rapport
            report_path = os.path.join(folder, "segmentation_results.json")
            if not os.path.exists(report_path):
                report_path = os.path.join(self.edit_output.text(), "segmentation_results.json")
            self.btn_report.setEnabled(os.path.exists(report_path))
            
            self._check_ready()
    
    def _load_sample_image(self, folder: str):
        """Charger une image sample pour le sélecteur ROI"""
        extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        files = sorted([f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in extensions])
        
        if files:
            # Prendre une image du milieu
            middle = len(files) // 2
            image_path = os.path.join(folder, files[middle])
            self.roi_selector.set_image(image_path)
    
    def _count_images(self, folder: str) -> int:
        """Compter les images"""
        extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.webp'}
        return sum(1 for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in extensions)
    
    def _reset_state(self):
        """Réinitialiser l'état"""
        self.level_classifications = {}
        self.analysis_completed = False
        self.last_results = None
        self.roi_coords = None
        self.progress_bar.setValue(0)
        self.status_label.setText("En attente...")
        self.results_text.clear()
        self._clear_level_cards()
        self.roi_selector.clear_roi()
        self.roi_status.setText("⚠️ ROI non définie - Dessinez un rectangle sur l'image")
        self.roi_status.setStyleSheet("color: #FF5722; font-weight: bold;")
    
    def _reset(self):
        """Réinitialiser manuellement"""
        reply = QMessageBox.question(
            self, "Réinitialiser",
            f"Effacer les {len(self.level_classifications)} classifications ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.level_classifications = {}
            self.analysis_completed = False
            self.last_results = None
            self.progress_bar.setValue(0)
            self.status_label.setText("En attente...")
            self.results_text.clear()
            self._clear_level_cards()
            self.btn_reset.setEnabled(False)
            self.btn_start.setEnabled(self.roi_coords is not None)
            self.btn_start.setText("🎮 Lancer la Segmentation")
    
    def _clear_level_cards(self):
        """Effacer les cartes de niveaux"""
        while self.levels_layout.count() > 1:
            item = self.levels_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
    
    def _classification_callback(self, frame_data, roi_coords, context):
        """Callback de classification"""
        dialog = LevelClassificationDialog(frame_data, roi_coords, context, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.result
        return "cancel"
    
    def _start_segmentation(self):
        """Démarrer la segmentation"""
        if not self.frames_dir:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un dossier.")
            return
        
        if not self.roi_coords:
            QMessageBox.warning(self, "ROI requise", 
                              "Veuillez définir la zone d'identification du niveau.\n\n"
                              "Dessinez un rectangle sur l'image ou utilisez 'ROI par défaut'.")
            return
        
        if self.analysis_completed:
            reply = QMessageBox.question(
                self, "Analyse déjà effectuée",
                "Voulez-vous réutiliser les classifications existantes ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        else:
            reply = QMessageBox.question(
                self, "Lancer la segmentation",
                "Vous devrez classifier plusieurs frames.\n\n"
                "L'algorithme trouvera automatiquement les transitions entre niveaux.\n\n"
                "Continuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            from tasks.mario_level_segment_task import MarioLevelSegmentTask, MarioLevelConfig
            
            interval = self.spin_interval.value() if self.spin_interval.value() >= 100 else None
            
            config = MarioLevelConfig(
                interval_size=interval,
                world_roi=self.roi_coords,  # Utiliser la ROI définie par l'utilisateur
                output_dir=self.edit_output.text() or "mario_level_dataset",
                create_yolo_dataset=self.check_yolo.isChecked()
            )
            
            task = MarioLevelSegmentTask()
            task.configure(
                frames_dir=self.frames_dir,
                config=config,
                classification_callback=self._classification_callback
            )
            
            # Restaurer classifications
            if self.level_classifications:
                task.level_classifications = self.level_classifications.copy()
            
            self.current_task = task
            self.btn_start.setEnabled(False)
            self.btn_start.setText("⏳ Analyse en cours...")
            self.status_label.setText("🔄 Segmentation en cours...")
            
            success = task.execute()
            
            # Sauvegarder
            self.level_classifications = task.level_classifications.copy()
            
            if success:
                self.last_results = task.stats
                self.analysis_completed = True
                self._display_results(task.stats)
                self.btn_report.setEnabled(True)
                self.btn_reset.setEnabled(True)
                self.btn_start.setText("✅ Terminé")
                
                QMessageBox.information(
                    self, "Segmentation terminée",
                    f"✅ {task.stats['levels_detected']} niveaux détectés!\n\n"
                    f"Niveaux: {', '.join(task.stats['detected_levels'])}\n"
                    f"Classifications: {task.stats['classifications_count']}\n"
                    f"Couverture: {task.stats['coverage']}%"
                )
            else:
                self.status_label.setText("❌ Annulé ou échoué")
                self.btn_start.setEnabled(True)
                self.btn_start.setText("🎮 Relancer")
                
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
            self.btn_start.setEnabled(True)
            self.btn_start.setText("🎮 Relancer")
    
    def _display_results(self, stats: dict):
        """Afficher les résultats"""
        self.progress_bar.setValue(100)
        self.status_label.setText(f"✅ {stats['levels_detected']} niveaux détectés")
        
        # Cartes des niveaux
        self._clear_level_cards()
        
        segments = stats.get('segments', {})
        for level in sorted(segments.keys()):
            card = LevelSegmentCard(level, segments[level])
            self.levels_layout.insertWidget(self.levels_layout.count() - 1, card)
        
        # Texte résumé
        text = f"""📊 RÉSULTATS
{'='*40}
• Total frames: {stats['total_frames']:,}
• Niveaux détectés: {stats['levels_detected']}
• Niveaux: {', '.join(stats['detected_levels'])}
• Classifications: {stats['classifications_count']}
• Couverture: {stats['coverage']}%
"""
        self.results_text.setPlainText(text)
    
    def _view_report(self):
        """Voir le rapport"""
        report_path = os.path.join(self.edit_output.text(), "segmentation_results.json")
        
        if not os.path.exists(report_path) and self.frames_dir:
            report_path = os.path.join(self.frames_dir, "segmentation_results.json")
        
        if not os.path.exists(report_path):
            QMessageBox.warning(self, "Rapport non trouvé", "Aucun rapport trouvé.")
            return
        
        try:
            with open(report_path, 'r') as f:
                report = json.load(f)
            
            dialog = QDialog(self)
            dialog.setWindowTitle("📄 Rapport de Segmentation")
            dialog.setMinimumSize(600, 500)
            
            layout = QVBoxLayout(dialog)
            
            text = QTextEdit()
            text.setReadOnly(True)
            text.setPlainText(json.dumps(report, indent=2, ensure_ascii=False))
            layout.addWidget(text)
            
            btn_close = QPushButton("Fermer")
            btn_close.clicked.connect(dialog.close)
            layout.addWidget(btn_close)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))