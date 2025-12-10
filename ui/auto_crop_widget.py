"""
Auto Crop Widget - Interface utilisateur pour le crop automatique
Widget séparé avec prévisualisation visuelle
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSpinBox, QFileDialog, QMessageBox, QFrame,
    QScrollArea, QGridLayout, QSlider, QCheckBox, QSplitter,
    QDialog, QTextEdit, QLineEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ImagePreviewLabel(QLabel):
    """Label personnalisé pour afficher l'image avec les zones de crop"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 300)
        self.setStyleSheet("""
            QLabel {
                background-color: #2D2D2D;
                border: 2px solid #555;
                border-radius: 4px;
            }
        """)
        
        self.original_pixmap = None
        self.crop_left = 0
        self.crop_right = 0
        self.crop_top = 0
        self.crop_bottom = 0
        self.image_width = 0
        self.image_height = 0
        self.scale_factor = 1.0
        self._image_path = None
    
    def set_image(self, image_path: str):
        """Charger une image"""
        if not os.path.exists(image_path):
            self.setText("Image non trouvée")
            return
        
        try:
            self._image_path = image_path
            pixmap = QPixmap(image_path)
            if pixmap.isNull():
                self.setText("Erreur chargement image")
                return
            
            self.image_width = pixmap.width()
            self.image_height = pixmap.height()
            
            # Redimensionner pour l'affichage
            scaled = pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            
            self.scale_factor = scaled.width() / pixmap.width() if pixmap.width() > 0 else 1.0
            self.original_pixmap = scaled
            self._update_display()
            
        except Exception as e:
            self.setText(f"Erreur: {str(e)}")
    
    def set_crop_values(self, left: int, right: int, top: int, bottom: int):
        """Définir les valeurs de crop"""
        self.crop_left = left
        self.crop_right = right
        self.crop_top = top
        self.crop_bottom = bottom
        self._update_display()
    
    def _update_display(self):
        """Mettre à jour l'affichage avec les zones de crop"""
        if self.original_pixmap is None:
            return
        
        # Créer une copie du pixmap
        display_pixmap = self.original_pixmap.copy()
        
        # Dessiner les zones de crop
        painter = QPainter(display_pixmap)
        
        # Zone de crop semi-transparente (rouge)
        crop_color = QColor(255, 0, 0, 100)
        painter.setBrush(crop_color)
        painter.setPen(Qt.PenStyle.NoPen)
        
        w = display_pixmap.width()
        h = display_pixmap.height()
        
        # Calculer les positions avec le facteur d'échelle
        left_px = int(self.crop_left * self.scale_factor)
        right_px = int(self.crop_right * self.scale_factor)
        top_px = int(self.crop_top * self.scale_factor)
        bottom_px = int(self.crop_bottom * self.scale_factor)
        
        # Dessiner les zones à supprimer
        if left_px > 0:
            painter.drawRect(0, 0, left_px, h)
        if right_px > 0:
            painter.drawRect(w - right_px, 0, right_px, h)
        if top_px > 0:
            painter.drawRect(left_px, 0, w - left_px - right_px, top_px)
        if bottom_px > 0:
            painter.drawRect(left_px, h - bottom_px, w - left_px - right_px, bottom_px)
        
        # Bordure de la zone conservée (vert)
        if left_px > 0 or right_px > 0 or top_px > 0 or bottom_px > 0:
            pen = QPen(QColor(0, 255, 0), 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(left_px, top_px, w - left_px - right_px, h - top_px - bottom_px)
        
        painter.end()
        
        self.setPixmap(display_pixmap)
    
    def resizeEvent(self, event):
        """Redimensionner l'image quand le widget est redimensionné"""
        super().resizeEvent(event)
        if self._image_path:
            self.set_image(self._image_path)


class AutoCropWidget(QWidget):
    """
    Widget pour le crop automatique des frames
    Interface avec prévisualisation visuelle
    """
    
    task_requested = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.frames_dir = None
        self.sample_image_path = None
        self.image_width = 0
        self.image_height = 0
        
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
        
        # 3. Splitter pour prévisualisation et contrôles
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panneau de prévisualisation
        preview_widget = self._create_preview_panel()
        splitter.addWidget(preview_widget)
        
        # Panneau de contrôles
        controls_widget = self._create_controls_panel()
        splitter.addWidget(controls_widget)
        
        splitter.setSizes([500, 300])
        content_layout.addWidget(splitter, 1)
        
        # 4. Options avancées
        options_group = self._create_options_group()
        content_layout.addWidget(options_group)
        
        # 5. Boutons d'action
        buttons = self._create_action_buttons()
        content_layout.addLayout(buttons)
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
    
    def _create_info_banner(self):
        """Créer la bannière d'information"""
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
        
        title = QLabel("✂️ Système de Crop Automatique")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #E65100;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Supprimez les bordures indésirables de toutes vos frames en une seule opération.\n\n"
            "• Définissez les pixels à enlever de chaque côté (gauche, droite, haut, bas)\n"
            "• Prévisualisez le résultat en temps réel (zone rouge = supprimée, vert = conservée)\n"
            "• Les images seront sauvées dans un nouveau dossier (original conservé)"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #F57C00; font-size: 11px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_folder_selection(self):
        """Créer la section de sélection du dossier"""
        group = QGroupBox("📁 Dossier de Frames")
        group.setStyleSheet(self._get_group_style("#2196F3"))
        
        layout = QVBoxLayout()
        
        select_layout = QHBoxLayout()
        
        self.folder_label = QLabel("Aucun dossier sélectionné")
        self.folder_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                background-color: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
                color: #757575;
            }
        """)
        select_layout.addWidget(self.folder_label, 1)
        
        browse_btn = QPushButton("📂 Parcourir")
        browse_btn.setStyleSheet(self._get_button_style("#2196F3"))
        browse_btn.clicked.connect(self._browse_folder)
        select_layout.addWidget(browse_btn)
        
        layout.addLayout(select_layout)
        
        self.folder_info = QLabel("")
        self.folder_info.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        layout.addWidget(self.folder_info)
        
        group.setLayout(layout)
        return group
    
    def _create_preview_panel(self):
        """Créer le panneau de prévisualisation"""
        group = QGroupBox("👁️ Prévisualisation")
        group.setStyleSheet(self._get_group_style("#4CAF50"))
        
        layout = QVBoxLayout()
        
        # Label d'image
        self.preview_label = ImagePreviewLabel()
        self.preview_label.setText("Sélectionnez un dossier pour prévisualiser")
        layout.addWidget(self.preview_label, 1)
        
        # Informations sur l'image
        info_layout = QHBoxLayout()
        
        self.original_size_label = QLabel("Original: -")
        self.original_size_label.setStyleSheet("color: #666;")
        info_layout.addWidget(self.original_size_label)
        
        info_layout.addStretch()
        
        self.final_size_label = QLabel("Final: -")
        self.final_size_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        info_layout.addWidget(self.final_size_label)
        
        layout.addLayout(info_layout)
        
        # Bouton pour changer d'image sample
        change_btn = QPushButton("🔄 Autre image")
        change_btn.clicked.connect(self._change_sample_image)
        layout.addWidget(change_btn)
        
        group.setLayout(layout)
        return group
    
    def _create_controls_panel(self):
        """Créer le panneau de contrôles de crop"""
        group = QGroupBox("✂️ Paramètres de Crop")
        group.setStyleSheet(self._get_group_style("#FF5722"))
        
        layout = QVBoxLayout()
        
        # Grille de contrôles
        grid = QGridLayout()
        grid.setSpacing(10)
        
        # Crop Haut
        grid.addWidget(QLabel("⬆️ Haut:"), 0, 0)
        self.spin_top = QSpinBox()
        self.spin_top.setRange(0, 2000)
        self.spin_top.setValue(0)
        self.spin_top.setSuffix(" px")
        self.spin_top.valueChanged.connect(self._update_preview)
        grid.addWidget(self.spin_top, 0, 1)
        
        self.slider_top = QSlider(Qt.Orientation.Horizontal)
        self.slider_top.setRange(0, 500)
        self.slider_top.valueChanged.connect(lambda v: self.spin_top.setValue(v))
        self.spin_top.valueChanged.connect(lambda v: self.slider_top.setValue(min(v, 500)))
        grid.addWidget(self.slider_top, 0, 2)
        
        # Crop Bas
        grid.addWidget(QLabel("⬇️ Bas:"), 1, 0)
        self.spin_bottom = QSpinBox()
        self.spin_bottom.setRange(0, 2000)
        self.spin_bottom.setValue(0)
        self.spin_bottom.setSuffix(" px")
        self.spin_bottom.valueChanged.connect(self._update_preview)
        grid.addWidget(self.spin_bottom, 1, 1)
        
        self.slider_bottom = QSlider(Qt.Orientation.Horizontal)
        self.slider_bottom.setRange(0, 500)
        self.slider_bottom.valueChanged.connect(lambda v: self.spin_bottom.setValue(v))
        self.spin_bottom.valueChanged.connect(lambda v: self.slider_bottom.setValue(min(v, 500)))
        grid.addWidget(self.slider_bottom, 1, 2)
        
        # Crop Gauche
        grid.addWidget(QLabel("⬅️ Gauche:"), 2, 0)
        self.spin_left = QSpinBox()
        self.spin_left.setRange(0, 2000)
        self.spin_left.setValue(0)
        self.spin_left.setSuffix(" px")
        self.spin_left.valueChanged.connect(self._update_preview)
        grid.addWidget(self.spin_left, 2, 1)
        
        self.slider_left = QSlider(Qt.Orientation.Horizontal)
        self.slider_left.setRange(0, 500)
        self.slider_left.valueChanged.connect(lambda v: self.spin_left.setValue(v))
        self.spin_left.valueChanged.connect(lambda v: self.slider_left.setValue(min(v, 500)))
        grid.addWidget(self.slider_left, 2, 2)
        
        # Crop Droite
        grid.addWidget(QLabel("➡️ Droite:"), 3, 0)
        self.spin_right = QSpinBox()
        self.spin_right.setRange(0, 2000)
        self.spin_right.setValue(0)
        self.spin_right.setSuffix(" px")
        self.spin_right.valueChanged.connect(self._update_preview)
        grid.addWidget(self.spin_right, 3, 1)
        
        self.slider_right = QSlider(Qt.Orientation.Horizontal)
        self.slider_right.setRange(0, 500)
        self.slider_right.valueChanged.connect(lambda v: self.spin_right.setValue(v))
        self.spin_right.valueChanged.connect(lambda v: self.slider_right.setValue(min(v, 500)))
        grid.addWidget(self.slider_right, 3, 2)
        
        layout.addLayout(grid)
        
        # Presets
        layout.addWidget(QLabel("📋 Presets rapides:"))
        
        presets_layout = QGridLayout()
        
        preset_reset = QPushButton("🔄 Reset (0)")
        preset_reset.clicked.connect(lambda: self._apply_preset(0, 0, 0, 0))
        presets_layout.addWidget(preset_reset, 0, 0)
        
        preset_small = QPushButton("Petit (10px)")
        preset_small.clicked.connect(lambda: self._apply_preset(10, 10, 10, 10))
        presets_layout.addWidget(preset_small, 0, 1)
        
        preset_medium = QPushButton("Moyen (50px)")
        preset_medium.clicked.connect(lambda: self._apply_preset(50, 50, 50, 50))
        presets_layout.addWidget(preset_medium, 1, 0)
        
        preset_large = QPushButton("Grand (100px)")
        preset_large.clicked.connect(lambda: self._apply_preset(100, 100, 100, 100))
        presets_layout.addWidget(preset_large, 1, 1)
        
        preset_left_only = QPushButton("Gauche seul (100)")
        preset_left_only.clicked.connect(lambda: self._apply_preset(100, 0, 0, 0))
        presets_layout.addWidget(preset_left_only, 2, 0)
        
        preset_top_bottom = QPushButton("Haut+Bas (50)")
        preset_top_bottom.clicked.connect(lambda: self._apply_preset(0, 0, 50, 50))
        presets_layout.addWidget(preset_top_bottom, 2, 1)
        
        layout.addLayout(presets_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_options_group(self):
        """Créer les options avancées"""
        group = QGroupBox("⚙️ Options Avancées")
        group.setStyleSheet(self._get_group_style("#607D8B"))
        group.setCheckable(True)
        group.setChecked(False)
        
        layout = QGridLayout()
        
        # Qualité JPEG
        layout.addWidget(QLabel("Qualité JPEG:"), 0, 0)
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(50, 100)
        self.spin_quality.setValue(95)
        self.spin_quality.setSuffix(" %")
        layout.addWidget(self.spin_quality, 0, 1)
        
        # Dimensions minimales
        layout.addWidget(QLabel("Largeur min:"), 1, 0)
        self.spin_min_width = QSpinBox()
        self.spin_min_width.setRange(10, 1000)
        self.spin_min_width.setValue(100)
        self.spin_min_width.setSuffix(" px")
        layout.addWidget(self.spin_min_width, 1, 1)
        
        layout.addWidget(QLabel("Hauteur min:"), 1, 2)
        self.spin_min_height = QSpinBox()
        self.spin_min_height.setRange(10, 1000)
        self.spin_min_height.setValue(100)
        self.spin_min_height.setSuffix(" px")
        layout.addWidget(self.spin_min_height, 1, 3)
        
        # Suffixe de sortie
        layout.addWidget(QLabel("Suffixe dossier:"), 2, 0)
        self.edit_suffix = QLineEdit("_cropped")
        layout.addWidget(self.edit_suffix, 2, 1)
        
        # Écraser originaux
        self.check_overwrite = QCheckBox("⚠️ Écraser les fichiers originaux (dangereux)")
        self.check_overwrite.setStyleSheet("color: #D32F2F;")
        layout.addWidget(self.check_overwrite, 3, 0, 1, 4)
        
        group.setLayout(layout)
        return group
    
    def _create_action_buttons(self):
        """Créer les boutons d'action"""
        layout = QHBoxLayout()
        
        self.btn_view_report = QPushButton("📊 Voir Dernier Rapport")
        self.btn_view_report.setStyleSheet(self._get_button_style("#607D8B"))
        self.btn_view_report.clicked.connect(self._view_last_report)
        self.btn_view_report.setEnabled(False)
        layout.addWidget(self.btn_view_report)
        
        layout.addStretch()
        
        self.btn_start = QPushButton("✂️ Lancer le Crop")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 15px 30px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.btn_start.clicked.connect(self._start_crop)
        self.btn_start.setEnabled(False)
        layout.addWidget(self.btn_start)
        
        return layout
    
    def _get_group_style(self, color: str) -> str:
        """Style CSS pour les groupes"""
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
        """Style CSS pour les boutons"""
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
    
    def _browse_folder(self):
        """Parcourir pour sélectionner un dossier"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner le dossier de frames",
            "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self.frames_dir = folder
            folder_name = os.path.basename(folder)
            self.folder_label.setText(f"📁 {folder_name}")
            self.folder_label.setToolTip(folder)
            self.folder_label.setStyleSheet("""
                QLabel {
                    padding: 10px;
                    background-color: #E3F2FD;
                    border: 1px solid #2196F3;
                    border-radius: 4px;
                    color: #1565C0;
                    font-weight: bold;
                }
            """)
            
            self._analyze_folder(folder)
            self._load_sample_image()
            
            # Activer le bouton
            self.btn_start.setEnabled(True)
            
            # Vérifier rapport existant
            report_path = os.path.join(folder + "_cropped", "crop_report.json")
            self.btn_view_report.setEnabled(os.path.exists(report_path))
    
    def _analyze_folder(self, folder: str):
        """Analyser le contenu du dossier"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        
        image_count = 0
        total_size = 0
        
        for f in os.listdir(folder):
            filepath = os.path.join(folder, f)
            if os.path.isfile(filepath) and f.lower().endswith(tuple(image_extensions)):
                image_count += 1
                total_size += os.path.getsize(filepath)
        
        size_mb = total_size / (1024 * 1024)
        self.folder_info.setText(f"📷 {image_count:,} images | 💾 {size_mb:.1f} MB")
    
    def _load_sample_image(self):
        """Charger une image d'exemple pour la prévisualisation"""
        if not self.frames_dir:
            return
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        
        for f in sorted(os.listdir(self.frames_dir)):
            if f.lower().endswith(tuple(image_extensions)):
                self.sample_image_path = os.path.join(self.frames_dir, f)
                break
        
        if self.sample_image_path and os.path.exists(self.sample_image_path):
            self.preview_label.set_image(self.sample_image_path)
            
            # Obtenir les dimensions
            if PIL_AVAILABLE:
                with Image.open(self.sample_image_path) as img:
                    self.image_width, self.image_height = img.size
            else:
                # Fallback avec QPixmap
                pixmap = QPixmap(self.sample_image_path)
                self.image_width = pixmap.width()
                self.image_height = pixmap.height()
            
            self.original_size_label.setText(f"Original: {self.image_width}x{self.image_height}px")
            self._update_preview()
    
    def _change_sample_image(self):
        """Changer l'image d'exemple"""
        if not self.frames_dir:
            return
        
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner une image",
            self.frames_dir,
            "Images (*.jpg *.jpeg *.png *.bmp *.tiff)"
        )
        
        if filepath:
            self.sample_image_path = filepath
            self.preview_label.set_image(filepath)
            
            if PIL_AVAILABLE:
                with Image.open(filepath) as img:
                    self.image_width, self.image_height = img.size
            else:
                pixmap = QPixmap(filepath)
                self.image_width = pixmap.width()
                self.image_height = pixmap.height()
            
            self.original_size_label.setText(f"Original: {self.image_width}x{self.image_height}px")
            self._update_preview()
    
    def _apply_preset(self, left: int, right: int, top: int, bottom: int):
        """Appliquer un preset"""
        self.spin_left.setValue(left)
        self.spin_right.setValue(right)
        self.spin_top.setValue(top)
        self.spin_bottom.setValue(bottom)
    
    def _update_preview(self):
        """Mettre à jour la prévisualisation"""
        left = self.spin_left.value()
        right = self.spin_right.value()
        top = self.spin_top.value()
        bottom = self.spin_bottom.value()
        
        # Mettre à jour l'affichage
        self.preview_label.set_crop_values(left, right, top, bottom)
        
        # Calculer les dimensions finales
        if self.image_width > 0 and self.image_height > 0:
            final_w = self.image_width - left - right
            final_h = self.image_height - top - bottom
            
            if final_w > 0 and final_h > 0:
                self.final_size_label.setText(f"Final: {final_w}x{final_h}px")
                self.final_size_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            else:
                self.final_size_label.setText("⚠️ Dimensions invalides!")
                self.final_size_label.setStyleSheet("color: #D32F2F; font-weight: bold;")
    
    def _view_last_report(self):
        """Voir le dernier rapport"""
        if not self.frames_dir:
            return
        
        suffix = self.edit_suffix.text() if hasattr(self, 'edit_suffix') else "_cropped"
        report_path = os.path.join(self.frames_dir + suffix, "crop_report.json")
        
        if not os.path.exists(report_path):
            QMessageBox.warning(self, "Rapport non trouvé", "Aucun rapport trouvé.")
            return
        
        try:
            import json
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            dialog = QDialog(self)
            dialog.setWindowTitle("📊 Rapport de Crop")
            dialog.setMinimumSize(500, 400)
            
            layout = QVBoxLayout(dialog)
            
            text = QTextEdit()
            text.setReadOnly(True)
            
            orig_size = report.get('original_size', [0, 0])
            final_size = report.get('final_size', [0, 0])
            
            content = f"""📊 RAPPORT DE CROP
{'='*40}

✅ Images traitées: {report.get('total_cropped', 0):,}/{report.get('total_processed', 0):,}
📊 Taux de réussite: {report.get('success_rate', 0):.1f}%
⏱️ Temps: {report.get('processing_time', 0):.1f}s
🚀 Vitesse: {report.get('fps', 0):.1f} img/s

📐 DIMENSIONS:
• Original: {orig_size[0]}x{orig_size[1]}px
• Final: {final_size[0]}x{final_size[1]}px

📁 Sortie: {report.get('output_directory', '?')}
"""
            
            text.setPlainText(content)
            layout.addWidget(text)
            
            close_btn = QPushButton("Fermer")
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lecture rapport:\n{str(e)}")
    
    def _start_crop(self):
        """Démarrer le crop"""
        if not self.frames_dir:
            QMessageBox.warning(self, "Dossier requis", "Veuillez sélectionner un dossier.")
            return
        
        left = self.spin_left.value()
        right = self.spin_right.value()
        top = self.spin_top.value()
        bottom = self.spin_bottom.value()
        
        if left == 0 and right == 0 and top == 0 and bottom == 0:
            QMessageBox.warning(self, "Aucun crop", "Veuillez définir au moins une valeur de crop.")
            return
        
        # Vérifier les dimensions finales
        final_w = self.image_width - left - right
        final_h = self.image_height - top - bottom
        min_w = self.spin_min_width.value()
        min_h = self.spin_min_height.value()
        
        if final_w < min_w or final_h < min_h:
            QMessageBox.warning(
                self, 
                "Dimensions invalides",
                f"Les dimensions finales ({final_w}x{final_h}px) sont inférieures au minimum ({min_w}x{min_h}px)."
            )
            return
        
        # Confirmation si écrasement
        overwrite = self.check_overwrite.isChecked()
        if overwrite:
            reply = QMessageBox.warning(
                self,
                "⚠️ Attention",
                "Vous allez ÉCRASER les fichiers originaux!\n\n"
                "Cette action est IRRÉVERSIBLE.\n\nContinuer?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            from tasks.auto_crop_task import AutoCropTask
            
            task = AutoCropTask()
            task.configure(
                frames_dir=self.frames_dir,
                crop_left=left,
                crop_right=right,
                crop_top=top,
                crop_bottom=bottom,
                min_remaining_width=min_w,
                min_remaining_height=min_h,
                jpeg_quality=self.spin_quality.value(),
                output_suffix=self.edit_suffix.text(),
                overwrite_originals=overwrite
            )
            
            self.task_requested.emit(task)
            
            QMessageBox.information(
                self,
                "Tâche ajoutée",
                f"✅ La tâche de crop a été ajoutée.\n\n"
                f"Crop: G={left}, D={right}, H={top}, B={bottom}\n"
                f"Dimensions finales: {final_w}x{final_h}px\n\n"
                "Cliquez sur 'Démarrer Pipeline' pour lancer."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{str(e)}")