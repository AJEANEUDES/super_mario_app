"""
Frame Viewer Window - Fenêtre de visualisation des frames extraits
Permet de prévisualiser un échantillon des frames pour vérification
"""

import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QGridLayout, QMessageBox, QSlider,
    QGroupBox, QSizePolicy, QFileDialog, QSpinBox, QComboBox
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QPixmap, QImage, QFont


class FrameViewerWindow(QDialog):
    """
    Fenêtre de visualisation des frames extraits
    Affiche une grille de miniatures avec possibilité de zoom
    """
    
    def __init__(self, frames_dir: str, parent=None):
        super().__init__(parent)
        
        self.frames_dir = Path(frames_dir)
        self.frame_files = []
        self.current_page = 0
        self.frames_per_page = 20  # Nombre de frames par page
        self.thumbnail_size = 150  # Taille des miniatures
        self.selected_frame_index = None
        
        # Configuration fenêtre
        self.setWindowTitle(f"🖼️ Visualisation des Frames - {self.frames_dir.name}")
        self.setGeometry(100, 100, 1200, 800)
        self.setMinimumSize(900, 600)
        
        # Charger la liste des frames
        self._load_frame_list()
        
        # Créer l'interface
        self._create_ui()
        
        # Afficher la première page
        self._display_current_page()
    
    def _load_frame_list(self):
        """Charger la liste des fichiers frames"""
        if not self.frames_dir.exists():
            return
        
        # Extensions d'images supportées
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        
        # Lister tous les fichiers images
        self.frame_files = sorted([
            f for f in self.frames_dir.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ])
    
    def _create_ui(self):
        """Créer l'interface utilisateur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header avec informations
        header = self._create_header()
        layout.addWidget(header)
        
        # Contrôles de navigation et options
        controls = self._create_controls()
        layout.addLayout(controls)
        
        # Zone de scroll pour les miniatures
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 2px solid #9C27B0;
                border-radius: 8px;
                background-color: #1E1E1E;
            }
        """)
        
        # Widget contenant la grille de miniatures
        self.grid_widget = QWidget()
        self.grid_widget.setStyleSheet("background-color: #1E1E1E;")
        self.grid_layout = QGridLayout(self.grid_widget)
        self.grid_layout.setSpacing(10)
        self.grid_layout.setContentsMargins(10, 10, 10, 10)
        
        scroll_area.setWidget(self.grid_widget)
        layout.addWidget(scroll_area)
        
        # Zone de prévisualisation agrandie
        self.preview_group = self._create_preview_area()
        layout.addWidget(self.preview_group)
        
        # Boutons d'action
        buttons = self._create_buttons()
        layout.addLayout(buttons)
    
    def _create_header(self):
        """Créer le header avec informations"""
        header = QLabel()
        
        total_frames = len(self.frame_files)
        folder_name = self.frames_dir.name
        parent_folder = self.frames_dir.parent.name
        
        # Calculer la taille totale
        total_size = sum(f.stat().st_size for f in self.frame_files) if self.frame_files else 0
        size_mb = total_size / (1024 * 1024)
        
        header_text = f"""
        <h2>🖼️ Visualisation des Frames</h2>
        <p><b>Dossier:</b> {parent_folder}/{folder_name}</p>
        <p><b>Total frames:</b> {total_frames:,} | <b>Taille:</b> {size_mb:.1f} MB</p>
        """
        
        header.setText(header_text)
        header.setStyleSheet("""
            QLabel {
                padding: 15px;
                background-color: #EDE7F6;
                border: 2px solid #9C27B0;
                border-radius: 8px;
                color: #4A148C;
            }
        """)
        
        return header
    
    def _create_controls(self):
        """Créer les contrôles de navigation"""
        layout = QHBoxLayout()
        
        # Navigation pages
        self.prev_btn = QPushButton("◀ Précédent")
        self.prev_btn.setStyleSheet(self._get_button_style("#9C27B0"))
        self.prev_btn.clicked.connect(self._prev_page)
        layout.addWidget(self.prev_btn)
        
        # Label page actuelle
        self.page_label = QLabel("Page 1 / 1")
        self.page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_label.setStyleSheet("font-weight: bold; font-size: 14px; padding: 5px;")
        layout.addWidget(self.page_label)
        
        self.next_btn = QPushButton("Suivant ▶")
        self.next_btn.setStyleSheet(self._get_button_style("#9C27B0"))
        self.next_btn.clicked.connect(self._next_page)
        layout.addWidget(self.next_btn)
        
        layout.addSpacing(20)
        
        # Taille des miniatures
        layout.addWidget(QLabel("Taille:"))
        self.size_combo = QComboBox()
        self.size_combo.addItems(["Petite (100px)", "Moyenne (150px)", "Grande (200px)", "Très grande (250px)"])
        self.size_combo.setCurrentIndex(1)  # Moyenne par défaut
        self.size_combo.currentIndexChanged.connect(self._change_thumbnail_size)
        layout.addWidget(self.size_combo)
        
        layout.addSpacing(20)
        
        # Frames par page
        layout.addWidget(QLabel("Par page:"))
        self.per_page_spin = QSpinBox()
        self.per_page_spin.setMinimum(10)
        self.per_page_spin.setMaximum(100)
        self.per_page_spin.setValue(20)
        self.per_page_spin.valueChanged.connect(self._change_frames_per_page)
        layout.addWidget(self.per_page_spin)
        
        layout.addStretch()
        
        # Aller à un frame spécifique
        layout.addWidget(QLabel("Aller au frame:"))
        self.goto_spin = QSpinBox()
        self.goto_spin.setMinimum(0)
        self.goto_spin.setMaximum(max(0, len(self.frame_files) - 1))
        layout.addWidget(self.goto_spin)
        
        goto_btn = QPushButton("Aller")
        goto_btn.setStyleSheet(self._get_button_style("#673AB7"))
        goto_btn.clicked.connect(self._goto_frame)
        layout.addWidget(goto_btn)
        
        return layout
    
    def _create_preview_area(self):
        """Créer la zone de prévisualisation agrandie"""
        group = QGroupBox("🔍 Prévisualisation")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #673AB7;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QHBoxLayout()
        
        # Image de prévisualisation
        self.preview_label = QLabel("Cliquez sur une miniature pour prévisualiser")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(400, 250)
        self.preview_label.setMaximumHeight(300)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #2D2D30;
                border: 1px solid #3E3E42;
                border-radius: 4px;
                color: #888;
            }
        """)
        layout.addWidget(self.preview_label, 2)
        
        # Informations sur le frame sélectionné
        info_layout = QVBoxLayout()
        
        self.frame_info_label = QLabel("Aucun frame sélectionné")
        self.frame_info_label.setWordWrap(True)
        self.frame_info_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
        """)
        info_layout.addWidget(self.frame_info_label)
        
        # Bouton ouvrir dans l'explorateur
        open_folder_btn = QPushButton("📁 Ouvrir le dossier")
        open_folder_btn.setStyleSheet(self._get_button_style("#4CAF50"))
        open_folder_btn.clicked.connect(self._open_folder)
        info_layout.addWidget(open_folder_btn)
        
        info_layout.addStretch()
        
        layout.addLayout(info_layout, 1)
        
        group.setLayout(layout)
        return group
    
    def _create_buttons(self):
        """Créer les boutons d'action"""
        layout = QHBoxLayout()
        layout.addStretch()
        
        # Bouton rafraîchir
        refresh_btn = QPushButton("🔄 Rafraîchir")
        refresh_btn.setStyleSheet(self._get_button_style("#FF9800"))
        refresh_btn.clicked.connect(self._refresh)
        layout.addWidget(refresh_btn)
        
        # Bouton fermer
        close_btn = QPushButton("❌ Fermer")
        close_btn.setStyleSheet(self._get_button_style("#757575"))
        close_btn.clicked.connect(self.close)
        layout.addWidget(close_btn)
        
        return layout
    
    def _get_button_style(self, color: str) -> str:
        """Obtenir le style CSS pour un bouton"""
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
    
    def _display_current_page(self):
        """Afficher la page actuelle de miniatures"""
        # Vider la grille
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if not self.frame_files:
            no_frames_label = QLabel("Aucun frame trouvé dans ce dossier")
            no_frames_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_frames_label.setStyleSheet("color: #888; font-size: 16px; padding: 50px;")
            self.grid_layout.addWidget(no_frames_label, 0, 0)
            return
        
        # Calculer les indices de début et fin
        start_idx = self.current_page * self.frames_per_page
        end_idx = min(start_idx + self.frames_per_page, len(self.frame_files))
        
        # Nombre de colonnes selon la taille des miniatures
        columns = max(1, 800 // (self.thumbnail_size + 20))
        
        # Afficher les miniatures
        for i, frame_idx in enumerate(range(start_idx, end_idx)):
            frame_path = self.frame_files[frame_idx]
            
            # Créer le widget de miniature
            thumb_widget = self._create_thumbnail_widget(frame_path, frame_idx)
            
            row = i // columns
            col = i % columns
            self.grid_layout.addWidget(thumb_widget, row, col)
        
        # Mettre à jour la navigation
        total_pages = (len(self.frame_files) + self.frames_per_page - 1) // self.frames_per_page
        self.page_label.setText(f"Page {self.current_page + 1} / {total_pages}")
        
        self.prev_btn.setEnabled(self.current_page > 0)
        self.next_btn.setEnabled(self.current_page < total_pages - 1)
    
    def _create_thumbnail_widget(self, frame_path: Path, frame_idx: int):
        """Créer un widget de miniature cliquable"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background-color: #2D2D30;
                border: 2px solid #3E3E42;
                border-radius: 4px;
            }
            QWidget:hover {
                border: 2px solid #9C27B0;
            }
        """)
        widget.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)
        
        # Image
        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        image_label.setFixedSize(self.thumbnail_size, self.thumbnail_size)
        
        # Charger et redimensionner l'image
        pixmap = QPixmap(str(frame_path))
        if not pixmap.isNull():
            scaled_pixmap = pixmap.scaled(
                self.thumbnail_size, self.thumbnail_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            image_label.setPixmap(scaled_pixmap)
        else:
            image_label.setText("Erreur")
            image_label.setStyleSheet("color: red;")
        
        layout.addWidget(image_label)
        
        # Nom du fichier
        name_label = QLabel(frame_path.name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet("color: #CCC; font-size: 10px;")
        name_label.setMaximumWidth(self.thumbnail_size)
        layout.addWidget(name_label)
        
        # Stocker les données pour le clic
        widget.frame_path = frame_path
        widget.frame_idx = frame_idx
        
        # Gérer le clic
        widget.mousePressEvent = lambda event, fp=frame_path, fi=frame_idx: self._on_thumbnail_click(fp, fi)
        
        return widget
    
    def _on_thumbnail_click(self, frame_path: Path, frame_idx: int):
        """Gérer le clic sur une miniature"""
        self.selected_frame_index = frame_idx
        
        # Afficher la prévisualisation
        pixmap = QPixmap(str(frame_path))
        if not pixmap.isNull():
            # Redimensionner pour la prévisualisation
            scaled = pixmap.scaled(
                self.preview_label.width() - 20,
                self.preview_label.height() - 20,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.preview_label.setPixmap(scaled)
        
        # Afficher les informations
        file_size = frame_path.stat().st_size / 1024  # KB
        
        info_text = f"""
<b>📄 Fichier:</b> {frame_path.name}<br>
<b>📊 Index:</b> {frame_idx} / {len(self.frame_files) - 1}<br>
<b>💾 Taille:</b> {file_size:.1f} KB<br>
<b>📐 Dimensions:</b> {pixmap.width()} x {pixmap.height()} px
        """
        self.frame_info_label.setText(info_text)
    
    def _prev_page(self):
        """Page précédente"""
        if self.current_page > 0:
            self.current_page -= 1
            self._display_current_page()
    
    def _next_page(self):
        """Page suivante"""
        total_pages = (len(self.frame_files) + self.frames_per_page - 1) // self.frames_per_page
        if self.current_page < total_pages - 1:
            self.current_page += 1
            self._display_current_page()
    
    def _change_thumbnail_size(self, index):
        """Changer la taille des miniatures"""
        sizes = [100, 150, 200, 250]
        self.thumbnail_size = sizes[index]
        self._display_current_page()
    
    def _change_frames_per_page(self, value):
        """Changer le nombre de frames par page"""
        self.frames_per_page = value
        self.current_page = 0
        self._display_current_page()
    
    def _goto_frame(self):
        """Aller à un frame spécifique"""
        frame_idx = self.goto_spin.value()
        if 0 <= frame_idx < len(self.frame_files):
            # Calculer la page
            self.current_page = frame_idx // self.frames_per_page
            self._display_current_page()
            
            # Sélectionner le frame
            frame_path = self.frame_files[frame_idx]
            self._on_thumbnail_click(frame_path, frame_idx)
    
    def _open_folder(self):
        """Ouvrir le dossier dans l'explorateur"""
        import subprocess
        import platform
        
        try:
            if platform.system() == "Windows":
                os.startfile(str(self.frames_dir))
            elif platform.system() == "Darwin":  # macOS
                subprocess.run(["open", str(self.frames_dir)])
            else:  # Linux
                subprocess.run(["xdg-open", str(self.frames_dir)])
        except Exception as e:
            QMessageBox.warning(self, "Erreur", f"Impossible d'ouvrir le dossier:\n{str(e)}")
    
    def _refresh(self):
        """Rafraîchir la liste des frames"""
        self._load_frame_list()
        self.current_page = 0
        self.goto_spin.setMaximum(max(0, len(self.frame_files) - 1))
        self._display_current_page()
        
        QMessageBox.information(
            self,
            "Rafraîchi",
            f"Liste mise à jour: {len(self.frame_files):,} frames trouvés"
        )