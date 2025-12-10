"""
Segment Transition Widget - Interface utilisateur pour la segmentation par dichotomie
Widget interactif pour détecter les transitions visuelles entre deux états
"""

import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QGridLayout, QProgressBar, QLineEdit, QSpinBox,
    QDialog, QTextEdit, QSplitter, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QImage

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


class ROISelector(QLabel):
    """Widget pour sélectionner une région d'intérêt (ROI) sur une image"""
    
    roi_selected = pyqtSignal(tuple)  # (x1, y1, x2, y2)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.original_pixmap = None
        self.scale_factor = 1.0
        self.image_offset = QPoint(0, 0)
        
        self.drawing = False
        self.start_point = None
        self.end_point = None
        self.roi_rect = None  # En coordonnées image originale
        
        # Taille FIXE pour éviter l'expansion infinie
        self.setFixedHeight(300)
        self.setMinimumWidth(400)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("background-color: #2D2D2D; border: 2px solid #4CAF50;")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("Chargez une image pour définir la ROI")
    
    def set_image(self, image_path: str):
        """Charger une image"""
        pixmap = QPixmap(image_path)
        if not pixmap.isNull():
            self.original_pixmap = pixmap
            self._update_display()
    
    def set_pixmap_direct(self, pixmap: QPixmap):
        """Définir directement un pixmap"""
        if not pixmap.isNull():
            self.original_pixmap = pixmap
            self._update_display()
    
    def _update_display(self):
        """Mettre à jour l'affichage"""
        if self.original_pixmap is None:
            return
        
        # Calculer le facteur d'échelle
        available_width = self.width() - 4
        available_height = self.height() - 4
        
        scale_w = available_width / self.original_pixmap.width()
        scale_h = available_height / self.original_pixmap.height()
        self.scale_factor = min(scale_w, scale_h, 1.0)
        
        # Redimensionner
        scaled = self.original_pixmap.scaled(
            int(self.original_pixmap.width() * self.scale_factor),
            int(self.original_pixmap.height() * self.scale_factor),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Calculer l'offset pour centrer
        self.image_offset = QPoint(
            (self.width() - scaled.width()) // 2,
            (self.height() - scaled.height()) // 2
        )
        
        # Dessiner avec ROI
        display = QPixmap(self.size())
        display.fill(QColor("#2D2D2D"))
        
        painter = QPainter(display)
        painter.drawPixmap(self.image_offset, scaled)
        
        # Dessiner la ROI si définie
        if self.roi_rect:
            pen = QPen(QColor(255, 0, 0, 200), 3)
            painter.setPen(pen)
            
            # Convertir ROI en coordonnées écran
            x1 = int(self.roi_rect[0] * self.scale_factor) + self.image_offset.x()
            y1 = int(self.roi_rect[1] * self.scale_factor) + self.image_offset.y()
            x2 = int(self.roi_rect[2] * self.scale_factor) + self.image_offset.x()
            y2 = int(self.roi_rect[3] * self.scale_factor) + self.image_offset.y()
            
            painter.drawRect(x1, y1, x2 - x1, y2 - y1)
        
        # Dessiner le rectangle en cours
        if self.drawing and self.start_point and self.end_point:
            pen = QPen(QColor(0, 255, 0, 200), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            rect = QRect(self.start_point, self.end_point).normalized()
            painter.drawRect(rect)
        
        painter.end()
        super().setPixmap(display)
    
    def mousePressEvent(self, event):
        """Début du dessin"""
        if event.button() == Qt.MouseButton.LeftButton and self.original_pixmap:
            self.drawing = True
            self.start_point = event.pos()
            self.end_point = event.pos()
    
    def mouseMoveEvent(self, event):
        """Pendant le dessin"""
        if self.drawing:
            self.end_point = event.pos()
            self._update_display()
    
    def mouseReleaseEvent(self, event):
        """Fin du dessin"""
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            self.end_point = event.pos()
            
            if self.start_point and self.end_point:
                # Convertir en coordonnées image
                x1 = (self.start_point.x() - self.image_offset.x()) / self.scale_factor
                y1 = (self.start_point.y() - self.image_offset.y()) / self.scale_factor
                x2 = (self.end_point.x() - self.image_offset.x()) / self.scale_factor
                y2 = (self.end_point.y() - self.image_offset.y()) / self.scale_factor
                
                # Normaliser
                x1, x2 = min(x1, x2), max(x1, x2)
                y1, y2 = min(y1, y2), max(y1, y2)
                
                # Valider
                if x2 - x1 > 10 and y2 - y1 > 10:
                    self.roi_rect = (int(x1), int(y1), int(x2), int(y2))
                    self._update_display()
                    self.roi_selected.emit(self.roi_rect)
    
    def resizeEvent(self, event):
        """Redimensionnement"""
        super().resizeEvent(event)
        self._update_display()
    
    def get_roi(self):
        """Retourner la ROI actuelle"""
        return self.roi_rect
    
    def clear_roi(self):
        """Effacer la ROI"""
        self.roi_rect = None
        self._update_display()


class ClassificationDialog(QDialog):
    """Dialogue de classification d'une frame"""
    
    def __init__(self, frame_info, roi_coords, label_a: str, label_b: str, parent=None):
        super().__init__(parent)
        
        self.frame_info = frame_info
        self.roi_coords = roi_coords
        self.result = None
        
        self.setWindowTitle(f"Classification - {frame_info.filename}")
        self.setMinimumSize(700, 500)
        self.setModal(True)
        
        self._create_ui(label_a, label_b)
        self._load_image()
    
    def _create_ui(self, label_a: str, label_b: str):
        """Créer l'interface"""
        layout = QVBoxLayout(self)
        
        # Info frame
        info_label = QLabel(f"<b>Frame:</b> {self.frame_info.filename} (#{self.frame_info.frame_number})")
        info_label.setStyleSheet("font-size: 12px; padding: 5px;")
        layout.addWidget(info_label)
        
        # Image
        self.image_label = QLabel("Chargement...")
        self.image_label.setMinimumSize(640, 360)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("background-color: #1E1E1E; border: 2px solid #666;")
        layout.addWidget(self.image_label)
        
        # Question
        question = QLabel("Comment classifiez-vous cette frame ?")
        question.setStyleSheet("font-size: 14px; font-weight: bold; padding: 10px;")
        question.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(question)
        
        # Boutons de classification
        buttons_layout = QHBoxLayout()
        
        self.btn_a = QPushButton(f"🅰️ {label_a}")
        self.btn_a.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 20px 40px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.btn_a.clicked.connect(lambda: self._classify('a'))
        buttons_layout.addWidget(self.btn_a)
        
        buttons_layout.addSpacing(50)
        
        self.btn_b = QPushButton(f"🅱️ {label_b}")
        self.btn_b.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 16px;
                font-weight: bold;
                padding: 20px 40px;
                border: none;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        self.btn_b.clicked.connect(lambda: self._classify('b'))
        buttons_layout.addWidget(self.btn_b)
        
        layout.addLayout(buttons_layout)
        
        # Raccourcis clavier
        shortcut_label = QLabel("Raccourcis: [A] ou [1] = État A | [B] ou [2] = État B | [Échap] = Annuler")
        shortcut_label.setStyleSheet("color: #888; font-size: 10px;")
        shortcut_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(shortcut_label)
    
    def _load_image(self):
        """Charger et afficher l'image"""
        try:
            if CV2_AVAILABLE:
                img = cv2.imread(self.frame_info.filepath)
                if img is not None:
                    # Dessiner la ROI si définie
                    if self.roi_coords:
                        x1, y1, x2, y2 = self.roi_coords
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 3)
                    
                    # Convertir BGR -> RGB
                    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w, ch = img_rgb.shape
                    
                    # Créer QImage
                    qimg = QImage(img_rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(qimg)
                    
                    # Redimensionner
                    scaled = pixmap.scaled(
                        640, 360,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    self.image_label.setPixmap(scaled)
                    return
            
            # Fallback sans OpenCV
            pixmap = QPixmap(self.frame_info.filepath)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    640, 360,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.image_label.setPixmap(scaled)
        except Exception as e:
            self.image_label.setText(f"Erreur: {e}")
    
    def _classify(self, classification: str):
        """Enregistrer la classification"""
        self.result = classification
        self.accept()
    
    def keyPressEvent(self, event):
        """Gestion des raccourcis clavier"""
        key = event.key()
        
        if key in (Qt.Key.Key_A, Qt.Key.Key_1):
            self._classify('a')
        elif key in (Qt.Key.Key_B, Qt.Key.Key_2):
            self._classify('b')
        elif key == Qt.Key.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(event)


class SegmentTransitionWidget(QWidget):
    """
    Widget pour la segmentation par détection de transition
    """
    
    task_requested = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.frames_dir = None
        self.all_frames = []
        self.roi_coords = None
        self.current_task = None
        self.last_results = None
        
        # Conserver les classifications entre les exécutions
        self.saved_classifications = {}
        self.analysis_completed = False
        
        self._create_ui()
    
    def _create_ui(self):
        """Créer l'interface utilisateur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        
        # 1. Bannière d'info
        info_banner = self._create_info_banner()
        content_layout.addWidget(info_banner)
        
        # 2. Sélection du dossier
        folder_group = self._create_folder_selection()
        content_layout.addWidget(folder_group)
        
        # 3. Configuration ROI + Labels
        config_group = self._create_config_group()
        content_layout.addWidget(config_group)
        
        # 4. Paramètres avancés
        params_group = self._create_params_group()
        content_layout.addWidget(params_group)
        
        # 5. Résultats
        results_group = self._create_results_group()
        content_layout.addWidget(results_group)
        
        content_layout.addStretch()
        
        # 6. Boutons d'action
        buttons = self._create_action_buttons()
        content_layout.addLayout(buttons)
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
    
    def _create_info_banner(self):
        """Créer la bannière d'information"""
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background-color: #E8EAF6;
                border: 2px solid #3F51B5;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(banner)
        
        title = QLabel("🔄 Détection de Transition par Dichotomie")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #303F9F;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Détecte automatiquement le point de transition entre deux états visuels.\n\n"
            "<b>Algorithme:</b> Recherche par intervalles + dichotomie (O(log n))\n"
            "<b>Processus:</b>\n"
            "1. Définissez une ROI (zone d'intérêt) pour guider l'analyse\n"
            "2. Classifiez quelques frames interactivement (A ou B)\n"
            "3. L'algorithme trouve le point exact de transition\n\n"
            "<b>Exemple:</b> Trouver la transition WORLD 1-1 → WORLD ★1-1"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #3F51B5; font-size: 11px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_folder_selection(self):
        """Créer la section de sélection du dossier"""
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
    
    def _create_config_group(self):
        """Créer la configuration ROI et labels"""
        group = QGroupBox("🎯 Configuration de la Détection")
        group.setStyleSheet(self._get_group_style("#4CAF50"))
        
        layout = QVBoxLayout()
        
        # Labels des états
        labels_layout = QHBoxLayout()
        
        labels_layout.addWidget(QLabel("État A:"))
        self.edit_label_a = QLineEdit("Normal")
        self.edit_label_a.setPlaceholderText("Ex: WORLD 1-1")
        labels_layout.addWidget(self.edit_label_a)
        
        labels_layout.addSpacing(20)
        
        labels_layout.addWidget(QLabel("État B:"))
        self.edit_label_b = QLineEdit("Star")
        self.edit_label_b.setPlaceholderText("Ex: WORLD ★1-1")
        labels_layout.addWidget(self.edit_label_b)
        
        layout.addLayout(labels_layout)
        
        # ROI Selector
        roi_layout = QHBoxLayout()
        
        roi_label = QLabel("ROI (Zone d'analyse):")
        roi_label.setStyleSheet("font-weight: bold;")
        roi_layout.addWidget(roi_label)
        
        self.roi_info = QLabel("Non définie - Dessinez un rectangle sur l'image")
        self.roi_info.setStyleSheet("color: #F44336;")
        roi_layout.addWidget(self.roi_info)
        
        roi_layout.addStretch()
        
        btn_clear_roi = QPushButton("🗑️ Effacer ROI")
        btn_clear_roi.clicked.connect(self._clear_roi)
        roi_layout.addWidget(btn_clear_roi)
        
        layout.addLayout(roi_layout)
        
        # Sélecteur ROI visuel
        self.roi_selector = ROISelector()
        # La hauteur est déjà fixée dans la classe ROISelector
        self.roi_selector.roi_selected.connect(self._on_roi_selected)
        layout.addWidget(self.roi_selector)
        
        group.setLayout(layout)
        return group
    
    def _create_params_group(self):
        """Créer les paramètres avancés"""
        group = QGroupBox("⚙️ Paramètres Avancés")
        group.setStyleSheet(self._get_group_style("#FF9800"))
        group.setCheckable(True)
        group.setChecked(False)
        
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("Taille d'intervalle:"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(100, 10000)
        self.spin_interval.setValue(1500)
        self.spin_interval.setSuffix(" frames")
        self.spin_interval.setToolTip("Plus grand = moins de classifications, mais moins précis initialement")
        layout.addWidget(self.spin_interval)
        
        layout.addSpacing(20)
        
        layout.addWidget(QLabel("Dossier sortie:"))
        self.edit_output = QLineEdit("segmented_output")
        layout.addWidget(self.edit_output)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def _create_results_group(self):
        """Créer la section des résultats"""
        group = QGroupBox("📊 Résultats")
        group.setStyleSheet(self._get_group_style("#9C27B0"))
        
        layout = QVBoxLayout()
        
        # Barre de progression
        self.progress_bar = QProgressBar()
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%v%")
        layout.addWidget(self.progress_bar)
        
        # Status
        self.status_label = QLabel("En attente...")
        self.status_label.setStyleSheet("font-size: 12px; padding: 5px;")
        layout.addWidget(self.status_label)
        
        # Résultats détaillés
        self.results_text = QTextEdit()
        self.results_text.setReadOnly(True)
        self.results_text.setMaximumHeight(150)
        self.results_text.setPlaceholderText("Les résultats apparaîtront ici...")
        layout.addWidget(self.results_text)
        
        group.setLayout(layout)
        return group
    
    def _create_action_buttons(self):
        """Créer les boutons d'action"""
        layout = QHBoxLayout()
        
        self.btn_view_report = QPushButton("📄 Voir Rapport")
        self.btn_view_report.setStyleSheet(self._get_button_style("#607D8B"))
        self.btn_view_report.clicked.connect(self._view_report)
        self.btn_view_report.setEnabled(False)
        layout.addWidget(self.btn_view_report)
        
        self.btn_reset = QPushButton("🔄 Réinitialiser")
        self.btn_reset.setStyleSheet(self._get_button_style("#FF5722"))
        self.btn_reset.clicked.connect(self._reset_analysis)
        self.btn_reset.setEnabled(False)
        self.btn_reset.setToolTip("Effacer les classifications et recommencer")
        layout.addWidget(self.btn_reset)
        
        layout.addStretch()
        
        self.btn_start = QPushButton("🔄 Lancer la Segmentation")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #3F51B5;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 15px 30px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #303F9F;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.btn_start.clicked.connect(self._start_segmentation)
        self.btn_start.setEnabled(False)
        layout.addWidget(self.btn_start)
        
        return layout
    
    def _get_group_style(self, color: str) -> str:
        return f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 13px;
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
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
            QPushButton:hover {{
                background-color: {color}CC;
            }}
        """
    
    def _get_label_style(self, selected: bool) -> str:
        if selected:
            return "padding: 8px; background-color: #E3F2FD; border: 1px solid #2196F3; border-radius: 4px; color: #1565C0; font-weight: bold;"
        return "padding: 8px; background-color: #FAFAFA; border: 1px solid #E0E0E0; border-radius: 4px; color: #757575;"
    
    def _browse_folder(self):
        """Parcourir pour le dossier"""
        folder = QFileDialog.getExistingDirectory(
            self, "Sélectionner le dossier de frames", "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            # Si on change de dossier, réinitialiser l'état
            if self.frames_dir and self.frames_dir != folder:
                self.saved_classifications = {}
                self.analysis_completed = False
                self.last_results = None
                self.progress_bar.setValue(0)
                self.status_label.setText("En attente...")
                self.results_text.clear()
                self.btn_reset.setEnabled(False)
            
            self.frames_dir = folder
            self.folder_label.setText(f"📁 {os.path.basename(folder)}")
            self.folder_label.setToolTip(folder)
            self.folder_label.setStyleSheet(self._get_label_style(True))
            
            # Analyser
            info = self._analyze_folder(folder)
            self.folder_info.setText(f"📷 {info['count']:,} images")
            
            # Charger une image sample pour la ROI
            self._load_sample_image(folder)
            
            # Vérifier rapport
            report_path = os.path.join(folder, "segmentation_report.json")
            self.btn_view_report.setEnabled(os.path.exists(report_path))
            
            # Réactiver le bouton de démarrage
            self.btn_start.setEnabled(True)
            self.btn_start.setText("🔄 Lancer la Segmentation")
            
            self._check_ready()
    
    def _analyze_folder(self, folder: str) -> dict:
        """Analyser le dossier"""
        extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        count = 0
        for f in os.listdir(folder):
            if os.path.splitext(f)[1].lower() in extensions:
                count += 1
        return {'count': count}
    
    def _load_sample_image(self, folder: str):
        """Charger une image sample"""
        extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        files = sorted([f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in extensions])
        
        if files:
            # Prendre l'image du milieu
            middle = len(files) // 2
            image_path = os.path.join(folder, files[middle])
            self.roi_selector.set_image(image_path)
    
    def _on_roi_selected(self, roi: tuple):
        """Quand une ROI est sélectionnée"""
        self.roi_coords = roi
        self.roi_info.setText(f"✅ ROI: ({roi[0]}, {roi[1]}) → ({roi[2]}, {roi[3]})")
        self.roi_info.setStyleSheet("color: #4CAF50; font-weight: bold;")
        self._check_ready()
    
    def _clear_roi(self):
        """Effacer la ROI"""
        self.roi_coords = None
        self.roi_selector.clear_roi()
        self.roi_info.setText("Non définie - Dessinez un rectangle sur l'image")
        self.roi_info.setStyleSheet("color: #F44336;")
        self._check_ready()
    
    def _check_ready(self):
        """Vérifier si prêt"""
        ready = self.frames_dir is not None
        self.btn_start.setEnabled(ready)
    
    def _classification_callback(self, frame_info, roi_coords):
        """Callback de classification interactive"""
        dialog = ClassificationDialog(
            frame_info,
            roi_coords,
            self.edit_label_a.text() or "État A",
            self.edit_label_b.text() or "État B",
            self
        )
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.result
        return None
    
    def _reset_analysis(self):
        """Réinitialiser l'analyse pour recommencer"""
        reply = QMessageBox.question(
            self,
            "Réinitialiser",
            "Voulez-vous effacer les classifications et recommencer ?\n\n"
            f"Classifications actuelles: {len(self.saved_classifications)}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.saved_classifications = {}
            self.analysis_completed = False
            self.last_results = None
            self.current_task = None
            
            # Réinitialiser l'interface
            self.progress_bar.setValue(0)
            self.status_label.setText("En attente...")
            self.results_text.clear()
            
            # Réactiver le bouton
            self.btn_start.setEnabled(True)
            self.btn_start.setText("🔄 Lancer la Segmentation")
            self.btn_reset.setEnabled(False)
            
            QMessageBox.information(self, "Réinitialisé", "✅ Analyse réinitialisée. Vous pouvez recommencer.")
    
    def _start_segmentation(self):
        """Démarrer la segmentation interactive"""
        if not self.frames_dir:
            QMessageBox.warning(self, "Dossier requis", "Sélectionnez un dossier.")
            return
        
        # Vérifier si une analyse a déjà été faite
        if self.analysis_completed:
            reply = QMessageBox.question(
                self,
                "Analyse déjà effectuée",
                "Une analyse a déjà été effectuée.\n\n"
                f"Résultat: {'Transition trouvée' if self.last_results and self.last_results.get('transition_found') else 'Dataset homogène'}\n"
                f"Classifications: {len(self.saved_classifications)}\n\n"
                "Voulez-vous utiliser les classifications existantes et relancer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Confirmation initiale
        if not self.analysis_completed:
            reply = QMessageBox.question(
                self,
                "Lancer la segmentation",
                "La segmentation va démarrer.\n\n"
                "Vous devrez classifier quelques frames interactivement.\n"
                "L'algorithme utilisera la dichotomie pour minimiser le nombre de classifications.\n\n"
                "Continuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            from tasks.segment_transition_task import SegmentTransitionTask, SegmentConfig
            
            config = SegmentConfig(
                interval_size=self.spin_interval.value(),
                label_state_a=self.edit_label_a.text() or "État A",
                label_state_b=self.edit_label_b.text() or "État B",
                roi_coords=self.roi_coords,
                output_dir=self.edit_output.text() or "segmented_output"
            )
            
            task = SegmentTransitionTask()
            task.configure(
                frames_dir=self.frames_dir,
                config=config,
                classification_callback=self._classification_callback
            )
            
            # Restaurer les classifications existantes
            if self.saved_classifications:
                task.classifications = self.saved_classifications.copy()
            
            self.current_task = task
            
            # Désactiver le bouton pendant l'exécution
            self.btn_start.setEnabled(False)
            self.btn_start.setText("⏳ Analyse en cours...")
            
            # Exécuter directement (pas via pipeline car interactif)
            self.status_label.setText("🔄 Segmentation en cours...")
            self.progress_bar.setValue(0)
            
            # Exécuter
            success = task.execute()
            
            # Sauvegarder les classifications
            self.saved_classifications = task.classifications.copy()
            
            if success:
                self.last_results = task.stats
                self.analysis_completed = True
                self._display_results(task.stats)
                self.btn_view_report.setEnabled(True)
                self.btn_reset.setEnabled(True)
                
                # Changer le texte du bouton
                self.btn_start.setText("✅ Analyse terminée")
                
                # Proposer de créer le dataset
                if task.stats.get('transition_found'):
                    self._propose_create_dataset(task)
                else:
                    QMessageBox.information(
                        self,
                        "Analyse terminée",
                        f"✅ Analyse terminée!\n\n"
                        f"Résultat: Dataset homogène (type: {task.stats.get('global_type', '?')})\n"
                        f"Aucune transition détectée.\n\n"
                        f"Total frames: {task.stats.get('total_frames', 0):,}\n"
                        f"Classifications effectuées: {task.stats.get('classifications_count', 0)}\n\n"
                        "Utilisez 'Réinitialiser' si vous voulez recommencer avec des paramètres différents."
                    )
            else:
                self.status_label.setText("❌ Segmentation échouée ou annulée")
                self.btn_start.setEnabled(True)
                self.btn_start.setText("🔄 Relancer la Segmentation")
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{str(e)}")
            self.status_label.setText(f"❌ Erreur: {str(e)}")
            self.btn_start.setEnabled(True)
            self.btn_start.setText("🔄 Relancer la Segmentation")
    
    def _display_results(self, stats: dict):
        """Afficher les résultats"""
        self.progress_bar.setValue(100)
        
        if stats.get('transition_found'):
            self.status_label.setText("✅ Transition trouvée!")
            
            text = f"""🔄 RÉSULTATS DE SEGMENTATION
{'='*40}

✅ Transition détectée!

📍 Point de transition:
   • Index: #{stats['transition_index']}
   • Fichier: {stats['transition_frame']}
   • Frame #: {stats['transition_frame_number']}

📊 Distribution:
   • État A: {stats['state_a_frames']:,} frames
   • État B: {stats['state_b_frames']:,} frames
   • Total: {stats['total_frames']:,} frames

🎯 Efficacité:
   • Classifications effectuées: {stats['classifications_count']}
   • Ratio: {stats['classifications_count']}/{stats['total_frames']} ({stats['classifications_count']/stats['total_frames']*100:.2f}%)
"""
        else:
            self.status_label.setText("ℹ️ Dataset homogène (pas de transition)")
            
            text = f"""🔄 RÉSULTATS DE SEGMENTATION
{'='*40}

ℹ️ Dataset homogène

• Type global: {stats.get('global_type', '?')}
• Total frames: {stats['total_frames']:,}
• Classifications: {stats['classifications_count']}
"""
        
        self.results_text.setPlainText(text)
    
    def _propose_create_dataset(self, task):
        """Proposer de créer le dataset segmenté"""
        reply = QMessageBox.question(
            self,
            "Créer le dataset",
            f"Transition trouvée à la frame #{task.stats['transition_index']}!\n\n"
            f"Voulez-vous créer le dataset segmenté ?\n"
            f"• État A: {task.stats['state_a_frames']:,} frames\n"
            f"• État B: {task.stats['state_b_frames']:,} frames",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            result = task.create_segmented_dataset(task.stats, dry_run=False)
            
            QMessageBox.information(
                self,
                "Dataset créé",
                f"✅ Dataset segmenté créé!\n\n"
                f"État A: {result.get('state_a_count', 0):,} frames\n"
                f"État B: {result.get('state_b_count', 0):,} frames"
            )
    
    def _view_report(self):
        """Voir le rapport"""
        if not self.frames_dir:
            return
        
        report_path = os.path.join(self.frames_dir, "segmentation_report.json")
        
        if not os.path.exists(report_path):
            QMessageBox.warning(self, "Rapport non trouvé", "Aucun rapport trouvé.")
            return
        
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            dialog = QDialog(self)
            dialog.setWindowTitle("📄 Rapport de Segmentation")
            dialog.setMinimumSize(500, 400)
            
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
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{str(e)}")