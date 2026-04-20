"""
Dataset Annotator Widget - Interface pour l'annotation manuelle YOLO
Affiche les classes avec images de référence et permet d'annoter les frames
"""

import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QGridLayout, QProgressBar, QLineEdit, QCheckBox, QComboBox,
    QTextEdit, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QSplitter, QListWidget, QListWidgetItem,
    QDialog, QDialogButtonBox, QSpinBox, QDoubleSpinBox, QSlider,
    QInputDialog, QMenu, QToolButton, QToolBar, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QRect, QPoint, QSize
from PyQt6.QtGui import (
    QFont, QPixmap, QImage, QPainter, QPen, QColor, QBrush,
    QMouseEvent, QKeyEvent, QShortcut, QKeySequence, QIcon, QAction
)

# Import du panneau des outils d'annotation
try:
    from ui.annotation_tools_panel import AnnotationToolsPanel
    TOOLS_PANEL_AVAILABLE = True
except ImportError:
    TOOLS_PANEL_AVAILABLE = False


class ImagePreviewDialog(QDialog):
    """Dialog pour afficher une image en grand format (style e-commerce)"""
    
    def __init__(self, image_path: str, title: str = "Aperçu", parent=None):
        super().__init__(parent)
        self.image_path = image_path
        self.setWindowTitle(f"🔍 {title}")
        self.setModal(True)
        
        # Taille adaptative selon l'écran
        screen = self.screen().availableGeometry()
        max_width = int(screen.width() * 0.8)
        max_height = int(screen.height() * 0.8)
        
        self._create_ui(max_width, max_height)
    
    def _create_ui(self, max_width: int, max_height: int):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Container pour l'image avec fond sombre
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-radius: 10px;
            }
        """)
        container_layout = QVBoxLayout(container)
        
        # Label pour l'image
        self.image_label = QLabel()
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        if os.path.exists(self.image_path):
            pixmap = QPixmap(self.image_path)
            
            # Redimensionner si nécessaire
            if pixmap.width() > max_width or pixmap.height() > max_height:
                pixmap = pixmap.scaled(
                    max_width - 40, max_height - 100,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
            
            self.image_label.setPixmap(pixmap)
            
            # Ajuster la taille du dialog
            self.resize(
                min(pixmap.width() + 40, max_width),
                min(pixmap.height() + 100, max_height)
            )
        else:
            self.image_label.setText("❌ Image non trouvée")
            self.image_label.setStyleSheet("color: white; font-size: 18px;")
            self.resize(400, 300)
        
        container_layout.addWidget(self.image_label)
        layout.addWidget(container)
        
        # Infos et bouton fermer
        bottom_layout = QHBoxLayout()
        
        # Infos sur l'image
        info_label = QLabel(f"📁 {os.path.basename(self.image_path)}")
        info_label.setStyleSheet("color: #666; font-size: 11px;")
        bottom_layout.addWidget(info_label)
        
        bottom_layout.addStretch()
        
        # Bouton fermer
        btn_close = QPushButton("✕ Fermer")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        btn_close.clicked.connect(self.close)
        bottom_layout.addWidget(btn_close)
        
        layout.addLayout(bottom_layout)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Fermer avec Escape ou Enter"""
        if event.key() in (Qt.Key.Key_Escape, Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.close()
        else:
            super().keyPressEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Fermer en cliquant n'importe où"""
        self.close()


class FullScreenAnnotationDialog(QDialog):
    """
    Fenêtre d'annotation en plein écran avec:
    - Panneau gauche: références cliquables
    - Centre: frame agrandi avec navigation
    - Bas: tableau des annotations
    """
    
    annotation_added = pyqtSignal(int, int, int, int, int)  # class_id, x, y, w, h
    annotation_removed = pyqtSignal(int)  # index
    frame_changed = pyqtSignal(int)  # new_index
    
    def __init__(self, task, current_index: int = 0, parent=None):
        super().__init__(parent)
        self.task = task
        self.current_index = current_index
        self.current_class_id = 0
        
        # État du dessin
        self.drawing = False
        self.start_point = None
        self.current_rect = None
        
        self.setWindowTitle("🎯 Annotation Plein Écran")
        self.setModal(True)
        
        # Plein écran ou grande taille
        screen = self.screen().availableGeometry()
        self.resize(int(screen.width() * 0.95), int(screen.height() * 0.9))
        
        self._create_ui()
        self._setup_shortcuts()
        self._display_frame()
    
    def _create_ui(self):
        """Créer l'interface"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Style sombre pour l'arrière-plan
        self.setStyleSheet("""
            QDialog {
                background-color: #2d2d2d;
            }
            QLabel {
                color: white;
            }
            QTableWidget {
                background-color: #3d3d3d;
                color: white;
                gridline-color: #555;
            }
            QHeaderView::section {
                background-color: #4d4d4d;
                color: white;
                padding: 5px;
                border: none;
            }
        """)
        
        # ===== ZONE PRINCIPALE =====
        content_layout = QHBoxLayout()
        
        # --- Panneau gauche: Références ---
        left_panel = self._create_references_panel()
        content_layout.addWidget(left_panel)
        
        # --- Zone centrale: Image + Navigation ---
        center_panel = self._create_center_panel()
        content_layout.addWidget(center_panel, stretch=1)
        
        main_layout.addLayout(content_layout, stretch=1)
        
        # ===== ZONE BAS: Annotations =====
        bottom_panel = self._create_annotations_panel()
        main_layout.addWidget(bottom_panel)
        
        # ===== Barre d'état =====
        status_layout = QHBoxLayout()
        
        self.status_label = QLabel("Cliquez sur une référence puis dessinez sur l'image")
        self.status_label.setStyleSheet("color: #aaa; font-style: italic;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # Bouton fermer
        btn_close = QPushButton("✕ Fermer (Echap)")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        btn_close.clicked.connect(self.close)
        status_layout.addWidget(btn_close)
        
        main_layout.addLayout(status_layout)
    
    def _create_references_panel(self) -> QWidget:
        """Créer le panneau des références"""
        panel = QFrame()
        panel.setFixedWidth(200)
        panel.setStyleSheet("""
            QFrame {
                background-color: #3d3d3d;
                border-radius: 10px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Titre
        title = QLabel("📚 Références")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #64b5f6;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        # Liste scrollable des références
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
        """)
        
        refs_widget = QWidget()
        self.refs_layout = QVBoxLayout(refs_widget)
        self.refs_layout.setSpacing(8)
        self.refs_layout.setContentsMargins(0, 0, 0, 0)
        
        # Ajouter les classes
        for cls in self.task.classes:
            ref_item = self._create_reference_item(cls)
            self.refs_layout.addWidget(ref_item)
        
        self.refs_layout.addStretch()
        scroll.setWidget(refs_widget)
        layout.addWidget(scroll)
        
        # Info raccourcis
        shortcut_info = QLabel("💡 Raccourcis: 1-9, 0, q-p, a-h")
        shortcut_info.setStyleSheet("color: #888; font-size: 10px;")
        shortcut_info.setWordWrap(True)
        layout.addWidget(shortcut_info)
        
        return panel
    
    def _create_reference_item(self, cls) -> QFrame:
        """Créer un item de référence cliquable"""
        frame = QFrame()
        frame.setStyleSheet(f"""
            QFrame {{
                background-color: #4d4d4d;
                border: 2px solid rgb{cls.color};
                border-radius: 5px;
            }}
            QFrame:hover {{
                background-color: #5d5d5d;
                border-width: 3px;
            }}
        """)
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        frame.setProperty("class_id", cls.id)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(3)
        
        # Image de référence
        img_label = QLabel()
        img_label.setFixedSize(80, 80)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setStyleSheet("background: #333; border-radius: 3px;")
        
        if cls.reference_image and os.path.exists(cls.reference_image):
            pixmap = QPixmap(cls.reference_image)
            pixmap = pixmap.scaled(76, 76, Qt.AspectRatioMode.KeepAspectRatio,
                                   Qt.TransformationMode.SmoothTransformation)
            img_label.setPixmap(pixmap)
        else:
            img_label.setText("?")
            img_label.setStyleSheet("background: #333; color: #888; font-size: 24px;")
        
        layout.addWidget(img_label, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Nom de la classe
        name_label = QLabel(cls.name)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        name_label.setStyleSheet(f"color: rgb{cls.color}; font-weight: bold; font-size: 11px;")
        name_label.setWordWrap(True)
        layout.addWidget(name_label)
        
        # Raccourci
        shortcut_label = QLabel(f"[{cls.shortcut.upper()}]")
        shortcut_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        shortcut_label.setStyleSheet("color: #888; font-size: 10px;")
        layout.addWidget(shortcut_label)
        
        # Clic pour sélectionner
        frame.mousePressEvent = lambda e, cid=cls.id: self._select_class(cid)
        
        return frame
    
    def _create_center_panel(self) -> QWidget:
        """Créer le panneau central avec l'image et la navigation"""
        panel = QWidget()
        layout = QHBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Bouton précédent (grand)
        btn_prev = QPushButton("◀")
        btn_prev.setFixedSize(50, 100)
        btn_prev.setFont(QFont("Segoe UI", 20))
        btn_prev.setStyleSheet("""
            QPushButton {
                background-color: #4d4d4d;
                color: white;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
            }
            QPushButton:pressed {
                background-color: #3d3d3d;
            }
        """)
        btn_prev.clicked.connect(self._prev_frame)
        btn_prev.setToolTip("Frame précédent (←)")
        layout.addWidget(btn_prev, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        # Zone image + navigation
        image_container = QFrame()
        image_container.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
                border-radius: 10px;
            }
        """)
        image_layout = QVBoxLayout(image_container)
        image_layout.setContentsMargins(10, 10, 10, 10)
        
        # Info du frame
        self.frame_info = QLabel()
        self.frame_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame_info.setStyleSheet("color: #64b5f6; font-size: 12px; font-weight: bold;")
        image_layout.addWidget(self.frame_info)
        
        # Canvas pour l'image
        self.image_canvas = AnnotationCanvasFullscreen(self)
        self.image_canvas.box_drawn.connect(self._on_box_drawn)
        self.image_canvas.setMinimumSize(600, 400)
        image_layout.addWidget(self.image_canvas, stretch=1)
        
        # ===== BARRE DE NAVIGATION COMPLÈTE =====
        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(10)
        
        # Style commun pour les boutons de navigation
        nav_btn_style = """
            QPushButton {
                background-color: #4d4d4d;
                color: white;
                border: none;
                padding: 8px 12px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
            }
            QPushButton:pressed {
                background-color: #3d3d3d;
            }
        """
        
        # Bouton premier
        btn_first = QPushButton("⏮")
        btn_first.setStyleSheet(nav_btn_style)
        btn_first.setToolTip("Premier frame")
        btn_first.clicked.connect(self._goto_first)
        nav_layout.addWidget(btn_first)
        
        # Bouton précédent (petit)
        btn_prev_small = QPushButton("◀ Précédent")
        btn_prev_small.setStyleSheet(nav_btn_style)
        btn_prev_small.clicked.connect(self._prev_frame)
        nav_layout.addWidget(btn_prev_small)
        
        # Slider
        self.nav_slider = QSlider(Qt.Orientation.Horizontal)
        self.nav_slider.setMinimum(0)
        self.nav_slider.setMaximum(max(0, len(self.task.images) - 1))
        self.nav_slider.setValue(self.current_index)
        self.nav_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #5d5d5d;
                height: 8px;
                background: #3d3d3d;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #64b5f6;
                border: none;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
            QSlider::handle:horizontal:hover {
                background: #90caf9;
            }
        """)
        self.nav_slider.valueChanged.connect(self._on_slider_changed)
        nav_layout.addWidget(self.nav_slider, stretch=1)
        
        # Bouton suivant (petit)
        btn_next_small = QPushButton("Suivant ▶")
        btn_next_small.setStyleSheet(nav_btn_style)
        btn_next_small.clicked.connect(self._next_frame)
        nav_layout.addWidget(btn_next_small)
        
        # Bouton dernier
        btn_last = QPushButton("⏭")
        btn_last.setStyleSheet(nav_btn_style)
        btn_last.setToolTip("Dernier frame")
        btn_last.clicked.connect(self._goto_last)
        nav_layout.addWidget(btn_last)
        
        # Séparateur visuel
        separator = QLabel("|")
        separator.setStyleSheet("color: #666; font-size: 16px;")
        nav_layout.addWidget(separator)
        
        # "Aller à"
        label_goto = QLabel("Aller à:")
        label_goto.setStyleSheet("color: #aaa;")
        nav_layout.addWidget(label_goto)
        
        self.goto_spinbox = QSpinBox()
        self.goto_spinbox.setMinimum(1)
        self.goto_spinbox.setMaximum(max(1, len(self.task.images)))
        self.goto_spinbox.setValue(self.current_index + 1)
        self.goto_spinbox.setStyleSheet("""
            QSpinBox {
                background-color: #4d4d4d;
                color: white;
                border: 1px solid #5d5d5d;
                border-radius: 3px;
                padding: 5px;
                min-width: 70px;
            }
        """)
        nav_layout.addWidget(self.goto_spinbox)
        
        btn_go = QPushButton("Go")
        btn_go.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        """)
        btn_go.clicked.connect(self._goto_frame)
        nav_layout.addWidget(btn_go)
        
        image_layout.addLayout(nav_layout)
        
        # Compteur de progression
        self.progress_label = QLabel()
        self.progress_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_label.setStyleSheet("color: #aaa; font-size: 11px;")
        image_layout.addWidget(self.progress_label)
        
        layout.addWidget(image_container, stretch=1)
        
        # Bouton suivant (grand)
        btn_next = QPushButton("▶")
        btn_next.setFixedSize(50, 100)
        btn_next.setFont(QFont("Segoe UI", 20))
        btn_next.setStyleSheet("""
            QPushButton {
                background-color: #4d4d4d;
                color: white;
                border: none;
                border-radius: 10px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
            }
            QPushButton:pressed {
                background-color: #3d3d3d;
            }
        """)
        btn_next.clicked.connect(self._next_frame)
        btn_next.setToolTip("Frame suivant (→)")
        layout.addWidget(btn_next, alignment=Qt.AlignmentFlag.AlignVCenter)
        
        return panel
    
    def _on_slider_changed(self, value: int):
        """Quand le slider change"""
        if value != self.current_index:
            self._save_current()
            self.current_index = value
            self._display_frame()
            self.frame_changed.emit(self.current_index)
    
    def _goto_first(self):
        """Aller au premier frame"""
        if self.current_index != 0:
            self._save_current()
            self.current_index = 0
            self._display_frame()
            self.frame_changed.emit(self.current_index)
    
    def _goto_last(self):
        """Aller au dernier frame"""
        last = len(self.task.images) - 1
        if self.current_index != last:
            self._save_current()
            self.current_index = last
            self._display_frame()
            self.frame_changed.emit(self.current_index)
    
    def _goto_frame(self):
        """Aller à un frame spécifique"""
        target = self.goto_spinbox.value() - 1  # Convertir en index 0-based
        if 0 <= target < len(self.task.images) and target != self.current_index:
            self._save_current()
            self.current_index = target
            self._display_frame()
            self.frame_changed.emit(self.current_index)
    
    def _create_annotations_panel(self) -> QWidget:
        """Créer le panneau des annotations"""
        panel = QFrame()
        panel.setFixedHeight(180)
        panel.setStyleSheet("""
            QFrame {
                background-color: #3d3d3d;
                border-radius: 10px;
            }
        """)
        
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # En-tête
        header = QHBoxLayout()
        
        title = QLabel("📝 Annotations de l'image")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #64b5f6;")
        header.addWidget(title)
        
        header.addStretch()
        
        # Boutons d'action
        btn_delete = QPushButton("🗑️ Supprimer sélection")
        btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """)
        btn_delete.clicked.connect(self._delete_selected_annotation)
        header.addWidget(btn_delete)
        
        btn_clear = QPushButton("🧹 Tout effacer")
        btn_clear.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                padding: 5px 15px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
        """)
        btn_clear.clicked.connect(self._clear_annotations)
        header.addWidget(btn_clear)
        
        layout.addLayout(header)
        
        # Tableau des annotations
        self.annotations_table = QTableWidget()
        self.annotations_table.setColumnCount(5)
        self.annotations_table.setHorizontalHeaderLabels(["Classe", "X", "Y", "Largeur", "Hauteur"])
        self.annotations_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.annotations_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.annotations_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.annotations_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.annotations_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.annotations_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.annotations_table.setAlternatingRowColors(True)
        self.annotations_table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #454545;
            }
        """)
        layout.addWidget(self.annotations_table)
        
        return panel
    
    def _setup_shortcuts(self):
        """Configurer les raccourcis clavier"""
        # Navigation
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, self._prev_frame)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, self._next_frame)
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, self._next_frame)
        QShortcut(QKeySequence(Qt.Key.Key_Home), self, self._goto_first)
        QShortcut(QKeySequence(Qt.Key.Key_End), self, self._goto_last)
        
        # Raccourcis pour les classes (1-9, 0, q-p, a-h)
        shortcuts = "1234567890qwertyuiopasdfgh"
        for i, key in enumerate(shortcuts):
            if i < len(self.task.classes):
                QShortcut(QKeySequence(key), self, 
                         lambda cid=i: self._select_class(cid))
        
        # Supprimer
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._delete_selected_annotation)
        
        # Annuler (Ctrl+Z)
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo_last_annotation)
        
        # Sauvegarder (Ctrl+S)
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_current)
    
    def _select_class(self, class_id: int):
        """Sélectionner une classe pour l'annotation"""
        if class_id < len(self.task.classes):
            self.current_class_id = class_id
            cls = self.task.classes[class_id]
            self.image_canvas.set_current_class(class_id, cls.color)
            self.status_label.setText(f"✅ Classe sélectionnée: {cls.name} [{cls.shortcut.upper()}] - Dessinez sur l'image")
            self.status_label.setStyleSheet(f"color: rgb{cls.color}; font-weight: bold;")
            
            # Mettre à jour visuellement les références
            self._highlight_selected_reference(class_id)
    
    def _highlight_selected_reference(self, class_id: int):
        """Mettre en surbrillance la référence sélectionnée"""
        for i in range(self.refs_layout.count()):
            item = self.refs_layout.itemAt(i)
            if item and item.widget():
                frame = item.widget()
                if isinstance(frame, QFrame):
                    cid = frame.property("class_id")
                    if cid == class_id:
                        # Sélectionné
                        frame.setStyleSheet(frame.styleSheet().replace(
                            "background-color: #4d4d4d", "background-color: #1976D2"
                        ))
                    else:
                        # Non sélectionné
                        frame.setStyleSheet(frame.styleSheet().replace(
                            "background-color: #1976D2", "background-color: #4d4d4d"
                        ))
    
    def _display_frame(self):
        """Afficher le frame courant"""
        if not self.task.images:
            return
        
        self.task.current_index = self.current_index
        img = self.task.get_current_image()
        
        if not img:
            return
        
        # Charger l'image
        pixmap = QPixmap(img.image_path)
        self.image_canvas.set_image(pixmap)
        
        # Afficher les boxes existantes
        boxes = []
        for box in img.boxes:
            cls = self.task.classes[box.class_id] if box.class_id < len(self.task.classes) else None
            color = cls.color if cls else (255, 255, 255)
            boxes.append((box.class_id, box.class_name, color, box.x, box.y, box.width, box.height))
        self.image_canvas.set_boxes(boxes)
        
        # Mettre à jour les infos
        self.frame_info.setText(f"📷 {img.image_name}  |  {img.width}x{img.height}")
        self.progress_label.setText(f"Frame {self.current_index + 1} / {len(self.task.images)}")
        
        # Synchroniser le slider et le spinbox
        if hasattr(self, 'nav_slider'):
            self.nav_slider.blockSignals(True)
            self.nav_slider.setValue(self.current_index)
            self.nav_slider.blockSignals(False)
        
        if hasattr(self, 'goto_spinbox'):
            self.goto_spinbox.blockSignals(True)
            self.goto_spinbox.setValue(self.current_index + 1)
            self.goto_spinbox.blockSignals(False)
        
        # Mettre à jour le tableau
        self._update_annotations_table()
    
    def _update_annotations_table(self):
        """Mettre à jour le tableau des annotations"""
        img = self.task.get_current_image()
        if not img:
            return
        
        self.annotations_table.setRowCount(len(img.boxes))
        
        for i, box in enumerate(img.boxes):
            cls = self.task.classes[box.class_id] if box.class_id < len(self.task.classes) else None
            color = cls.color if cls else (255, 255, 255)
            
            # Classe avec couleur
            class_item = QTableWidgetItem(box.class_name)
            class_item.setForeground(QColor(*color))
            self.annotations_table.setItem(i, 0, class_item)
            
            # Coordonnées
            self.annotations_table.setItem(i, 1, QTableWidgetItem(str(box.x)))
            self.annotations_table.setItem(i, 2, QTableWidgetItem(str(box.y)))
            self.annotations_table.setItem(i, 3, QTableWidgetItem(str(box.width)))
            self.annotations_table.setItem(i, 4, QTableWidgetItem(str(box.height)))
    
    def _prev_frame(self):
        """Aller au frame précédent"""
        if self.current_index > 0:
            self._save_current()
            self.current_index -= 1
            self._display_frame()
            self.frame_changed.emit(self.current_index)
    
    def _next_frame(self):
        """Aller au frame suivant"""
        if self.current_index < len(self.task.images) - 1:
            self._save_current()
            self.current_index += 1
            self._display_frame()
            self.frame_changed.emit(self.current_index)
    
    def _on_box_drawn(self, x: int, y: int, w: int, h: int):
        """Quand une box est dessinée"""
        if w < 5 or h < 5:
            return  # Trop petit
        
        # Ajouter l'annotation
        cls = self.task.classes[self.current_class_id] if self.current_class_id < len(self.task.classes) else None
        if cls:
            # Appeler add_annotation avec les bons arguments
            self.task.add_annotation(self.current_class_id, x, y, w, h)
            self.annotation_added.emit(self.current_class_id, x, y, w, h)
            
            # Rafraîchir
            self._display_frame()
            self.status_label.setText(f"✅ Annotation ajoutée: {cls.name}")
    
    def _delete_selected_annotation(self):
        """Supprimer l'annotation sélectionnée"""
        row = self.annotations_table.currentRow()
        if row >= 0:
            self.task.remove_annotation(row)
            self.annotation_removed.emit(row)
            self._display_frame()
    
    def _clear_annotations(self):
        """Effacer toutes les annotations de l'image courante"""
        reply = QMessageBox.question(
            self, "Confirmer",
            "Effacer toutes les annotations de cette image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.task.clear_annotations()
            self._display_frame()
    
    def _undo_last_annotation(self):
        """Annuler la dernière annotation"""
        img = self.task.get_current_image()
        if img and img.boxes:
            self.task.remove_annotation(len(img.boxes) - 1)
            self._display_frame()
    
    def _save_current(self):
        """Sauvegarder les annotations de l'image courante"""
        img = self.task.get_current_image()
        if img:
            img.save_yolo(self.task.config.output_dir if self.task.config else "")
    
    def keyPressEvent(self, event: QKeyEvent):
        """Gestion des touches"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Sauvegarder avant de fermer"""
        self._save_current()
        super().closeEvent(event)


class ClickableImageLabel(QLabel):
    """Label d'image cliquable avec effet de survol"""
    
    clicked = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._has_image = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("🔍 Cliquer pour agrandir")
    
    def set_has_image(self, has_image: bool):
        """Indiquer si le label contient une image"""
        self._has_image = has_image
        if has_image:
            self.setCursor(Qt.CursorShape.PointingHandCursor)
            self.setToolTip("🔍 Cliquer pour agrandir")
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
            self.setToolTip("")
    
    def enterEvent(self, event):
        """Effet de survol"""
        if self._has_image:
            self.setStyleSheet(self.styleSheet() + "border: 2px solid #1976D2;")
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Fin du survol"""
        if self._has_image:
            style = self.styleSheet().replace("border: 2px solid #1976D2;", "")
            self.setStyleSheet(style)
        super().leaveEvent(event)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Émettre le signal clicked"""
        if self._has_image and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class AnnotationCanvasFullscreen(QLabel):
    """Canvas pour dessiner des annotations en plein écran"""
    
    box_drawn = pyqtSignal(int, int, int, int)  # x, y, w, h (coordonnées image originale)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #1a1a1a;")
        self.setMouseTracking(True)
        
        self.original_pixmap = None
        self.display_pixmap = None
        self.scale_factor = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        self.boxes = []
        self.current_class_id = 0
        self.current_color = (255, 0, 0)
        
        # État du dessin
        self.drawing = False
        self.start_point = None
        self.current_rect = None
    
    def set_image(self, pixmap: QPixmap):
        """Définir l'image à afficher"""
        self.original_pixmap = pixmap
        self._update_display()
    
    def set_boxes(self, boxes: list):
        """Définir les boxes à afficher"""
        self.boxes = boxes
        self._update_display()
    
    def set_current_class(self, class_id: int, color: tuple):
        """Définir la classe courante"""
        self.current_class_id = class_id
        self.current_color = color
    
    def _update_display(self):
        """Mettre à jour l'affichage"""
        if not self.original_pixmap:
            return
        
        # Calculer l'échelle pour tenir dans le widget
        widget_size = self.size()
        img_size = self.original_pixmap.size()
        
        scale_w = (widget_size.width() - 20) / img_size.width()
        scale_h = (widget_size.height() - 20) / img_size.height()
        self.scale_factor = min(scale_w, scale_h, 1.0)  # Ne pas agrandir
        
        # Redimensionner l'image
        new_w = int(img_size.width() * self.scale_factor)
        new_h = int(img_size.height() * self.scale_factor)
        
        self.display_pixmap = self.original_pixmap.scaled(
            new_w, new_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # Calculer l'offset pour centrer
        self.offset_x = (widget_size.width() - self.display_pixmap.width()) // 2
        self.offset_y = (widget_size.height() - self.display_pixmap.height()) // 2
        
        self._draw()
    
    def _draw(self):
        """Dessiner l'image avec les boxes"""
        if not self.display_pixmap:
            return
        
        # Créer une copie pour dessiner
        result = QPixmap(self.size())
        result.fill(QColor("#1a1a1a"))
        
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Dessiner l'image centrée
        painter.drawPixmap(self.offset_x, self.offset_y, self.display_pixmap)
        
        # Dessiner les boxes existantes (avec protection)
        if hasattr(self, 'boxes') and self.boxes:
            for box in self.boxes:
                class_id, class_name, color, x, y, w, h = box
                
                # Convertir en coordonnées affichage
                dx = int(x * self.scale_factor) + self.offset_x
                dy = int(y * self.scale_factor) + self.offset_y
                dw = int(w * self.scale_factor)
                dh = int(h * self.scale_factor)
                
                # Rectangle
                pen = QPen(QColor(*color), 2)
                painter.setPen(pen)
                painter.setBrush(QBrush(QColor(color[0], color[1], color[2], 40)))
                painter.drawRect(dx, dy, dw, dh)
                
                # Label
                label_rect = QRect(dx, dy - 20, len(class_name) * 8 + 10, 18)
                painter.fillRect(label_rect, QColor(*color))
                painter.setPen(QPen(Qt.GlobalColor.white))
                painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, class_name)
        
        # Dessiner le rectangle en cours
        if hasattr(self, 'current_rect') and self.current_rect:
            pen = QPen(QColor(*self.current_color), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QBrush(QColor(self.current_color[0], self.current_color[1], 
                                          self.current_color[2], 60)))
            painter.drawRect(self.current_rect)
        
        painter.end()
        self.setPixmap(result)
    
    def resizeEvent(self, event):
        """Redimensionner l'affichage"""
        super().resizeEvent(event)
        self._update_display()
    
    def mousePressEvent(self, event: QMouseEvent):
        """Début du dessin"""
        if event.button() == Qt.MouseButton.LeftButton:
            pos = event.position().toPoint()
            
            # Vérifier si on est dans l'image
            if self._is_in_image(pos):
                self.drawing = True
                self.start_point = pos
                self.current_rect = QRect(pos, pos)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Pendant le dessin"""
        if not hasattr(self, 'drawing'):
            return
        if self.drawing and self.start_point:
            pos = event.position().toPoint()
            
            # Limiter à l'image
            pos = self._clamp_to_image(pos)
            
            self.current_rect = QRect(self.start_point, pos).normalized()
            self._draw()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Fin du dessin"""
        if not hasattr(self, 'drawing'):
            return
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            
            if self.current_rect and self.current_rect.width() > 5 and self.current_rect.height() > 5:
                # Convertir en coordonnées image originale
                x = int((self.current_rect.x() - self.offset_x) / self.scale_factor)
                y = int((self.current_rect.y() - self.offset_y) / self.scale_factor)
                w = int(self.current_rect.width() / self.scale_factor)
                h = int(self.current_rect.height() / self.scale_factor)
                
                # Émettre le signal
                self.box_drawn.emit(x, y, w, h)
            
            self.current_rect = None
            self.start_point = None
            self._draw()
    
    def _is_in_image(self, pos: QPoint) -> bool:
        """Vérifier si le point est dans l'image"""
        if not hasattr(self, 'display_pixmap') or not self.display_pixmap:
            return False
        
        return (self.offset_x <= pos.x() <= self.offset_x + self.display_pixmap.width() and
                self.offset_y <= pos.y() <= self.offset_y + self.display_pixmap.height())
    
    def _clamp_to_image(self, pos: QPoint) -> QPoint:
        """Limiter le point à l'intérieur de l'image"""
        if not hasattr(self, 'display_pixmap') or not self.display_pixmap:
            return pos
        
        x = max(self.offset_x, min(pos.x(), self.offset_x + self.display_pixmap.width()))
        y = max(self.offset_y, min(pos.y(), self.offset_y + self.display_pixmap.height()))
        return QPoint(x, y)


class ClassReferenceDialog(QDialog):
    """Dialog pour configurer les images de référence des classes"""
    
    def __init__(self, classes, references_dir="", parent=None):
        super().__init__(parent)
        self.classes = classes
        self.references_dir = references_dir
        self.reference_images = {cls.id: cls.reference_image for cls in classes}
        
        self.setWindowTitle("Configuration des Images de Référence")
        self.setMinimumSize(800, 600)
        self._create_ui()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        
        # Instructions
        info = QLabel(
            "📸 Associez une image de référence à chaque classe.\n"
            "Ces images aideront à identifier les éléments lors de l'annotation.\n"
            "💡 Cliquez sur une image pour l'agrandir."
        )
        info.setStyleSheet("color: #666; padding: 10px; background: #f5f5f5; border-radius: 5px;")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Liste des classes avec images
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        
        content = QWidget()
        self.grid = QGridLayout(content)
        self.grid.setSpacing(10)
        
        self.image_labels = {}
        self.image_paths = {}
        
        for i, cls in enumerate(self.classes):
            row = i // 4
            col = i % 4
            
            frame = QFrame()
            frame.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
            frame.setStyleSheet("QFrame { background: white; border-radius: 5px; }")
            
            frame_layout = QVBoxLayout(frame)
            frame_layout.setSpacing(5)
            
            # Nom de la classe
            name_label = QLabel(f"[{cls.shortcut}] {cls.name}")
            name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            name_label.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
            name_label.setStyleSheet(f"color: rgb{cls.color};")
            frame_layout.addWidget(name_label)
            
            # Image de référence (cliquable)
            img_label = ClickableImageLabel()
            img_label.setFixedSize(100, 100)
            img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            img_label.setStyleSheet("background: #eee; border: 1px dashed #ccc;")
            
            if cls.reference_image and os.path.exists(cls.reference_image):
                pixmap = QPixmap(cls.reference_image).scaled(
                    100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                img_label.setPixmap(pixmap)
                img_label.set_has_image(True)
                # Connecter le clic pour ouvrir l'aperçu
                img_label.clicked.connect(
                    lambda cid=cls.id, name=cls.name: self._show_image_preview(cid, name)
                )
            else:
                img_label.setText("Aucune\nimage")
                img_label.set_has_image(False)
            
            self.image_labels[cls.id] = img_label
            self.image_paths[cls.id] = cls.reference_image
            frame_layout.addWidget(img_label, alignment=Qt.AlignmentFlag.AlignCenter)
            
            # Bouton parcourir
            btn = QPushButton("📂 Choisir")
            btn.setProperty("class_id", cls.id)
            btn.clicked.connect(lambda checked, cid=cls.id: self._browse_image(cid))
            frame_layout.addWidget(btn)
            
            self.grid.addWidget(frame, row, col)
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Boutons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _browse_image(self, class_id):
        """Parcourir et sélectionner une image pour une classe"""
        class_name = self.classes[class_id].name
        file_path, _ = QFileDialog.getOpenFileName(
            self, f"Image pour {class_name}",
            "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.image_paths[class_id] = file_path
            pixmap = QPixmap(file_path).scaled(
                100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.image_labels[class_id].setPixmap(pixmap)
            self.image_labels[class_id].set_has_image(True)
            
            # Reconnecter le signal de clic
            try:
                self.image_labels[class_id].clicked.disconnect()
            except:
                pass
            self.image_labels[class_id].clicked.connect(
                lambda cid=class_id, name=class_name: self._show_image_preview(cid, name)
            )
    
    def _show_image_preview(self, class_id: int, class_name: str):
        """Afficher l'aperçu de l'image en grand"""
        image_path = self.image_paths.get(class_id, "")
        if image_path and os.path.exists(image_path):
            dialog = ImagePreviewDialog(image_path, f"Référence: {class_name}", self)
            dialog.exec()
    
    def get_references(self):
        return self.image_paths


class AddClassDialog(QDialog):
    """Dialog pour ajouter une nouvelle classe"""
    
    def __init__(self, existing_names, parent=None):
        super().__init__(parent)
        self.existing_names = [n.lower() for n in existing_names]
        self.setWindowTitle("Ajouter une Classe")
        self.setMinimumWidth(400)
        self._create_ui()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        
        # Nom
        layout.addWidget(QLabel("Nom de la classe:"))
        self.edit_name = QLineEdit()
        self.edit_name.setPlaceholderText("ex: bullet_bill")
        layout.addWidget(self.edit_name)
        
        # Image de référence
        layout.addWidget(QLabel("Image de référence (optionnel):"))
        
        img_layout = QHBoxLayout()
        self.edit_image = QLineEdit()
        self.edit_image.setReadOnly(True)
        img_layout.addWidget(self.edit_image)
        
        btn_browse = QPushButton("📂")
        btn_browse.clicked.connect(self._browse_image)
        img_layout.addWidget(btn_browse)
        
        layout.addLayout(img_layout)
        
        # Preview
        self.img_preview = QLabel()
        self.img_preview.setFixedSize(100, 100)
        self.img_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.img_preview.setStyleSheet("background: #eee; border: 1px dashed #ccc;")
        layout.addWidget(self.img_preview, alignment=Qt.AlignmentFlag.AlignCenter)
        
        # Boutons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._validate)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
    
    def _browse_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Image de référence", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.edit_image.setText(file_path)
            pixmap = QPixmap(file_path).scaled(
                100, 100, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.img_preview.setPixmap(pixmap)
    
    def _validate(self):
        name = self.edit_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Erreur", "Le nom est requis")
            return
        if name.lower() in self.existing_names:
            QMessageBox.warning(self, "Erreur", "Cette classe existe déjà")
            return
        self.accept()
    
    def get_data(self):
        return {
            "name": self.edit_name.text().strip(),
            "reference_image": self.edit_image.text()
        }


class AnnotationCanvas(QLabel):
    """Canvas pour dessiner les annotations"""
    
    annotation_added = pyqtSignal(int, int, int, int, int)  # class_id, x, y, w, h
    annotation_selected = pyqtSignal(int)  # box index
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(400, 400)  # Hauteur augmentée
        self.setStyleSheet("background: #1a1a1a; border: 2px solid #333;")
        
        # Image et annotations
        self.original_pixmap = None
        self.display_pixmap = None
        self.boxes = []  # Liste de tuples (class_id, class_name, color, x, y, w, h)
        self.current_class_id = 0
        self.current_class_color = (255, 0, 0)
        
        # État du dessin
        self.drawing = False
        self.start_point = None
        self.current_rect = None
        
        # Échelle
        self.scale = 1.0
        self.offset_x = 0
        self.offset_y = 0
        
        # Image dimensions
        self.img_width = 0
        self.img_height = 0
    
    def set_image(self, pixmap: QPixmap):
        """Définir l'image à annoter"""
        self.original_pixmap = pixmap
        self.img_width = pixmap.width()
        self.img_height = pixmap.height()
        self.boxes = []
        self._update_display()
    
    def set_boxes(self, boxes):
        """Définir les boxes existantes"""
        self.boxes = boxes
        self._update_display()
    
    def set_current_class(self, class_id: int, color: tuple):
        """Définir la classe courante pour l'annotation"""
        self.current_class_id = class_id
        self.current_class_color = color
    
    def _update_display(self):
        """Mettre à jour l'affichage"""
        if not self.original_pixmap:
            return
        
        # Calculer l'échelle
        widget_w = self.width() - 4
        widget_h = self.height() - 4
        
        scale_x = widget_w / self.img_width
        scale_y = widget_h / self.img_height
        self.scale = min(scale_x, scale_y)
        
        # Créer l'image affichée
        scaled_w = int(self.img_width * self.scale)
        scaled_h = int(self.img_height * self.scale)
        
        self.offset_x = (widget_w - scaled_w) // 2
        self.offset_y = (widget_h - scaled_h) // 2
        
        # Dessiner
        display = QPixmap(widget_w, widget_h)
        display.fill(QColor(26, 26, 26))
        
        painter = QPainter(display)
        
        # Image
        scaled_pixmap = self.original_pixmap.scaled(
            scaled_w, scaled_h,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        painter.drawPixmap(self.offset_x, self.offset_y, scaled_pixmap)
        
        # Boxes existantes
        for class_id, class_name, color, x, y, w, h in self.boxes:
            pen = QPen(QColor(*color), 2)
            painter.setPen(pen)
            
            sx = int(x * self.scale) + self.offset_x
            sy = int(y * self.scale) + self.offset_y
            sw = int(w * self.scale)
            sh = int(h * self.scale)
            
            painter.drawRect(sx, sy, sw, sh)
            
            # Label
            painter.fillRect(sx, sy - 18, len(class_name) * 8 + 10, 18, QColor(*color))
            painter.setPen(QColor(255, 255, 255))
            painter.drawText(sx + 5, sy - 4, class_name)
        
        # Rectangle en cours de dessin
        if self.drawing and self.start_point and self.current_rect:
            pen = QPen(QColor(*self.current_class_color), 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.drawRect(self.current_rect)
        
        painter.end()
        
        self.display_pixmap = display
        self.setPixmap(display)
    
    def _widget_to_image(self, x: int, y: int) -> tuple:
        """Convertir coordonnées widget vers image"""
        img_x = (x - self.offset_x) / self.scale
        img_y = (y - self.offset_y) / self.scale
        return int(img_x), int(img_y)
    
    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.original_pixmap:
            x, y = event.position().x(), event.position().y()
            img_x, img_y = self._widget_to_image(int(x), int(y))
            
            # Vérifier si dans l'image
            if 0 <= img_x < self.img_width and 0 <= img_y < self.img_height:
                self.drawing = True
                self.start_point = (int(x), int(y))
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if self.drawing and self.start_point:
            x, y = int(event.position().x()), int(event.position().y())
            
            x1, y1 = self.start_point
            self.current_rect = QRect(
                min(x1, x), min(y1, y),
                abs(x - x1), abs(y - y1)
            )
            self._update_display()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton and self.drawing:
            self.drawing = False
            
            if self.start_point and self.current_rect:
                # Convertir en coordonnées image
                x1, y1 = self._widget_to_image(self.current_rect.x(), self.current_rect.y())
                x2, y2 = self._widget_to_image(
                    self.current_rect.x() + self.current_rect.width(),
                    self.current_rect.y() + self.current_rect.height()
                )
                
                # Normaliser
                x = max(0, min(x1, x2))
                y = max(0, min(y1, y2))
                w = min(abs(x2 - x1), self.img_width - x)
                h = min(abs(y2 - y1), self.img_height - y)
                
                # Taille minimum
                if w > 5 and h > 5:
                    self.annotation_added.emit(self.current_class_id, x, y, w, h)
            
            self.start_point = None
            self.current_rect = None
            self._update_display()
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_display()


class ClassListWidget(QWidget):
    """Widget pour afficher la liste des classes avec leurs images de référence"""
    
    class_selected = pyqtSignal(int)  # class_id
    image_preview_requested = pyqtSignal(int, str, str)  # class_id, name, image_path
    rename_requested = pyqtSignal(int, str)  # class_id, current_name
    delete_requested = pyqtSignal(int, str)  # class_id, name
    change_image_requested = pyqtSignal(int, str)  # class_id, name
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.classes = []
        self._create_ui()
    
    def _create_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Titre
        title = QLabel("📋 Classes (clic droit pour options)")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet("color: #1976D2; padding: 5px;")
        title.setToolTip("Clic droit sur une classe pour la renommer, supprimer ou changer son image")
        layout.addWidget(title)
        
        # Liste scrollable
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        self.list_widget = QWidget()
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setSpacing(5)
        self.list_layout.addStretch()
        
        scroll.setWidget(self.list_widget)
        layout.addWidget(scroll)
        
        self.class_buttons = {}
        self.image_labels = {}
    
    def set_classes(self, classes):
        """Définir les classes à afficher"""
        self.classes = classes
        
        # Nettoyer
        for btn in self.class_buttons.values():
            btn.deleteLater()
        self.class_buttons = {}
        self.image_labels = {}
        
        # Recréer
        for cls in classes:
            self._add_class_item(cls)
    
    def _add_class_item(self, cls):
        """Ajouter un item de classe"""
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        frame.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 2px solid rgb{cls.color};
                border-radius: 5px;
            }}
            QFrame:hover {{
                background: #f0f0f0;
            }}
        """)
        frame.setCursor(Qt.CursorShape.PointingHandCursor)
        frame.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        frame.customContextMenuRequested.connect(
            lambda pos, cid=cls.id, name=cls.name: self._show_context_menu(pos, cid, name, frame)
        )
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(8)
        
        # Image de référence (cliquable pour zoom)
        img_label = ClickableImageLabel()
        img_label.setFixedSize(50, 50)
        img_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        img_label.setStyleSheet("background: #eee; border-radius: 3px;")
        
        if cls.reference_image and os.path.exists(cls.reference_image):
            pixmap = QPixmap(cls.reference_image).scaled(
                50, 50, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            img_label.setPixmap(pixmap)
            img_label.set_has_image(True)
            # Connecter pour ouvrir l'aperçu
            img_label.clicked.connect(
                lambda cid=cls.id, name=cls.name, path=cls.reference_image: 
                    self.image_preview_requested.emit(cid, name, path)
            )
        else:
            img_label.setText("?")
            img_label.set_has_image(False)
        
        self.image_labels[cls.id] = img_label
        layout.addWidget(img_label)
        
        # Infos
        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)
        
        name_label = QLabel(cls.name)
        name_label.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_label.setStyleSheet(f"color: rgb{cls.color};")
        info_layout.addWidget(name_label)
        
        shortcut_label = QLabel(f"Raccourci: [{cls.shortcut}]")
        shortcut_label.setStyleSheet("color: #666; font-size: 9px;")
        info_layout.addWidget(shortcut_label)
        
        count_label = QLabel(f"Annotations: {cls.count}")
        count_label.setStyleSheet("color: #999; font-size: 9px;")
        count_label.setObjectName(f"count_{cls.id}")
        info_layout.addWidget(count_label)
        
        layout.addLayout(info_layout)
        layout.addStretch()
        
        # Bouton zoom (pour mobile ou accessibilité)
        if cls.reference_image and os.path.exists(cls.reference_image):
            btn_zoom = QPushButton("🔍")
            btn_zoom.setFixedSize(25, 25)
            btn_zoom.setToolTip("Agrandir l'image")
            btn_zoom.setStyleSheet("""
                QPushButton {
                    background: #e3f2fd;
                    border: none;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background: #bbdefb;
                }
            """)
            btn_zoom.clicked.connect(
                lambda checked, cid=cls.id, name=cls.name, path=cls.reference_image: 
                    self.image_preview_requested.emit(cid, name, path)
            )
            layout.addWidget(btn_zoom)
        
        # Stocker et connecter la sélection de classe
        frame.setProperty("class_id", cls.id)
        frame.setProperty("reference_image", cls.reference_image)
        
        # Le clic sur le frame (hors image) sélectionne la classe
        original_mouse_press = frame.mousePressEvent
        def custom_mouse_press(event, cid=cls.id):
            # Vérifier si le clic est sur l'image de référence
            child = frame.childAt(event.position().toPoint())
            if not isinstance(child, ClickableImageLabel):
                self.class_selected.emit(cid)
        frame.mousePressEvent = custom_mouse_press
        
        self.class_buttons[cls.id] = frame
        self.list_layout.insertWidget(self.list_layout.count() - 1, frame)
    
    def _show_context_menu(self, pos, class_id: int, class_name: str, frame: QFrame):
        """Afficher le menu contextuel pour une classe"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #ccc;
                padding: 5px;
            }
            QMenu::item {
                padding: 8px 25px;
            }
            QMenu::item:selected {
                background-color: #e3f2fd;
            }
        """)
        
        # Action Renommer
        action_rename = menu.addAction("✏️ Renommer")
        action_rename.triggered.connect(
            lambda: self.rename_requested.emit(class_id, class_name)
        )
        
        # Action Changer l'image
        action_change_img = menu.addAction("🖼️ Changer l'image")
        action_change_img.triggered.connect(
            lambda: self.change_image_requested.emit(class_id, class_name)
        )
        
        menu.addSeparator()
        
        # Action Supprimer
        action_delete = menu.addAction("🗑️ Supprimer")
        action_delete.triggered.connect(
            lambda: self.delete_requested.emit(class_id, class_name)
        )
        
        menu.exec(frame.mapToGlobal(pos))
    
    def highlight_class(self, class_id: int):
        """Mettre en surbrillance la classe sélectionnée"""
        for cid, frame in self.class_buttons.items():
            if cid == class_id:
                frame.setStyleSheet(frame.styleSheet().replace(
                    "background: white", "background: #e3f2fd"
                ))
            else:
                frame.setStyleSheet(frame.styleSheet().replace(
                    "background: #e3f2fd", "background: white"
                ))
    
    def update_count(self, class_id: int, count: int):
        """Mettre à jour le compteur d'une classe"""
        if class_id in self.class_buttons:
            frame = self.class_buttons[class_id]
            count_label = frame.findChild(QLabel, f"count_{class_id}")
            if count_label:
                count_label.setText(f"Annotations: {count}")


class DatasetAnnotatorWidget(QWidget):
    """
    Widget principal pour l'annotation de dataset YOLO
    Interface avec liste des classes et canvas d'annotation
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        from tasks.dataset_annotator_task import DatasetAnnotatorTask, AnnotatorConfig
        
        self.task = DatasetAnnotatorTask()
        self.task.log_callback = self._log
        self.current_class_id = 0
        
        self._create_ui()
        self._setup_shortcuts()
    
    def _create_ui(self):
        """Créer l'interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Bannière
        layout.addWidget(self._create_banner())
        
        # Splitter principal
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # ===== PANNEAU GAUCHE (scrollable) =====
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setStyleSheet("""
            QScrollArea { 
                border: none; 
                background: transparent;
            }
            QScrollBar:vertical {
                width: 8px;
                background: #f0f0f0;
            }
            QScrollBar::handle:vertical {
                background: #c0c0c0;
                border-radius: 4px;
            }
        """)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(5, 5, 5, 5)
        left_layout.setSpacing(5)
        
        # Configuration
        left_layout.addWidget(self._create_config_group())
        
        # Liste des classes
        self.class_list = ClassListWidget()
        self.class_list.class_selected.connect(self._on_class_selected)
        self.class_list.image_preview_requested.connect(self._on_image_preview_requested)
        self.class_list.rename_requested.connect(self._on_rename_class)
        self.class_list.delete_requested.connect(self._on_delete_class)
        self.class_list.change_image_requested.connect(self._on_change_class_image)
        left_layout.addWidget(self.class_list)
        
        # Gestion des classes
        left_layout.addWidget(self._create_class_management())
        
        # Outils d'annotation avancés
        left_layout.addWidget(self._create_tools_group())
        
        # Ajouter un stretch pour pousser les éléments vers le haut
        left_layout.addStretch()
        
        left_scroll.setWidget(left_panel)
        left_scroll.setMinimumWidth(280)
        left_scroll.setMaximumWidth(400)
        main_splitter.addWidget(left_scroll)
        
        # ===== PANNEAU DROIT =====
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(5)
        
        # Info image courante
        right_layout.addWidget(self._create_image_info())
        
        # Splitter vertical pour canvas et annotations
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Canvas d'annotation (dans un widget container)
        canvas_container = QWidget()
        canvas_layout = QVBoxLayout(canvas_container)
        canvas_layout.setContentsMargins(0, 0, 0, 0)
        canvas_layout.setSpacing(5)
        
        # Barre d'outils du canvas
        canvas_toolbar = QHBoxLayout()
        canvas_toolbar.addStretch()
        
        btn_fullscreen = QPushButton("🔍 Annoter en Plein Écran")
        btn_fullscreen.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        """)
        btn_fullscreen.setToolTip("Ouvrir l'interface d'annotation plein écran (F11)")
        btn_fullscreen.clicked.connect(self._open_fullscreen_annotation)
        canvas_toolbar.addWidget(btn_fullscreen)
        
        canvas_layout.addLayout(canvas_toolbar)
        
        self.canvas = AnnotationCanvas()
        self.canvas.annotation_added.connect(self._on_annotation_added)
        self.canvas.setMinimumHeight(300)  # Hauteur minimum plus grande
        
        # Rendre le canvas cliquable pour ouvrir le plein écran
        self.canvas.setCursor(Qt.CursorShape.PointingHandCursor)
        self.canvas.mouseDoubleClickEvent = lambda e: self._open_fullscreen_annotation()
        
        canvas_layout.addWidget(self.canvas)
        
        right_splitter.addWidget(canvas_container)
        
        # Panneau inférieur (navigation + annotations)
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(5)
        
        bottom_layout.addWidget(self._create_navigation())
        bottom_layout.addWidget(self._create_annotations_list())
        
        right_splitter.addWidget(bottom_panel)
        
        # Proportions par défaut: 70% canvas, 30% navigation+annotations
        right_splitter.setSizes([500, 200])
        
        right_layout.addWidget(right_splitter)
        
        main_splitter.addWidget(right_panel)
        
        main_splitter.setSizes([300, 700])
        layout.addWidget(main_splitter)
        
        # Barre d'actions
        layout.addLayout(self._create_action_buttons())
        
        # Logs
        layout.addWidget(self._create_logs())
    
    def _create_banner(self):
        """Créer la bannière"""
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #7B1FA2, stop:1 #9C27B0);
                border-radius: 8px;
                padding: 10px;
            }
            QLabel { color: white; }
        """)
        
        layout = QVBoxLayout(banner)
        
        title = QLabel("🎮 Annotateur de Dataset YOLO")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Annotez manuellement vos frames pour créer un dataset d'entraînement YOLO.\n"
            "Gérez les classes, associez des images de référence, et exportez au format YOLOv8."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #E1BEE7; font-size: 10px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_config_group(self):
        """Créer le groupe configuration"""
        group = QGroupBox("⚙️ Configuration")
        group.setStyleSheet(self._get_group_style("#9C27B0"))
        
        layout = QGridLayout()
        
        # data.yaml
        layout.addWidget(QLabel("data.yaml:"), 0, 0)
        self.edit_yaml = QLineEdit()
        self.edit_yaml.setPlaceholderText("Fichier de configuration des classes...")
        layout.addWidget(self.edit_yaml, 0, 1)
        
        btn_yaml = QPushButton("📂")
        btn_yaml.setMaximumWidth(40)
        btn_yaml.clicked.connect(self._browse_yaml)
        layout.addWidget(btn_yaml, 0, 2)
        
        btn_load_yaml = QPushButton("Charger")
        btn_load_yaml.clicked.connect(self._load_yaml)
        layout.addWidget(btn_load_yaml, 0, 3)
        
        # Dossier frames
        layout.addWidget(QLabel("Dossier frames:"), 1, 0)
        self.edit_frames = QLineEdit()
        self.edit_frames.setPlaceholderText("Dossier contenant les images à annoter...")
        layout.addWidget(self.edit_frames, 1, 1)
        
        btn_frames = QPushButton("📂")
        btn_frames.setMaximumWidth(40)
        btn_frames.clicked.connect(self._browse_frames)
        layout.addWidget(btn_frames, 1, 2)
        
        btn_load_frames = QPushButton("Charger")
        btn_load_frames.clicked.connect(self._load_frames)
        layout.addWidget(btn_load_frames, 1, 3)
        
        # Dossier sortie
        layout.addWidget(QLabel("Dossier sortie:"), 2, 0)
        self.edit_output = QLineEdit()
        self.edit_output.setPlaceholderText("Dossier pour les annotations...")
        layout.addWidget(self.edit_output, 2, 1, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_class_management(self):
        """Créer les boutons de gestion des classes"""
        group = QGroupBox("🔧 Gestion des Classes")
        group.setStyleSheet(self._get_group_style("#673AB7"))
        
        layout = QHBoxLayout()
        
        btn_add = QPushButton("➕ Ajouter")
        btn_add.clicked.connect(self._add_class)
        layout.addWidget(btn_add)
        
        btn_references = QPushButton("🖼️ Références")
        btn_references.clicked.connect(self._configure_references)
        layout.addWidget(btn_references)
        
        btn_save_yaml = QPushButton("💾 Sauver YAML")
        btn_save_yaml.clicked.connect(self._save_yaml)
        layout.addWidget(btn_save_yaml)
        
        group.setLayout(layout)
        return group
    
    def _create_tools_group(self):
        """Créer le groupe des outils d'annotation avancés"""
        group = QGroupBox("🛠️ Outils d'annotation")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #00796B;
                border: 2px solid #00796B;
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
        
        layout = QGridLayout()
        layout.setSpacing(4)
        layout.setContentsMargins(8, 12, 8, 8)
        
        # Style commun pour les boutons compacts
        def create_tool_btn(text, tooltip, bg_color, hover_color):
            btn = QPushButton(text)
            btn.setMinimumHeight(26)
            btn.setToolTip(tooltip)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: white;
                    border: none;
                    padding: 4px 6px;
                    border-radius: 4px;
                    font-size: 9px;
                    font-weight: bold;
                }}
                QPushButton:hover {{ background-color: {hover_color}; }}
            """)
            return btn
        
        # Ligne 1: Échantillonnage + Pré-annotation
        btn_sampling = create_tool_btn("🎯 Échantillon.", 
            "Réduire le nombre de frames (1 sur N)\nGain: 10-20x", "#26a69a", "#00897b")
        btn_sampling.clicked.connect(self._open_sampling_tool)
        layout.addWidget(btn_sampling, 0, 0)
        
        btn_auto = create_tool_btn("🤖 Pré-annot.", 
            "Détecter avec modèle YOLO\nGain: 5-10x", "#5c6bc0", "#3f51b5")
        btn_auto.clicked.connect(self._open_auto_annotation_tool)
        layout.addWidget(btn_auto, 0, 1)
        
        # Ligne 2: Propagation + Interpolation
        btn_tracking = create_tool_btn("🎬 Propager", 
            "Suivi automatique des objets\nGain: 20-50x", "#7b1fa2", "#6a1b9a")
        btn_tracking.clicked.connect(self._open_tracking_tool)
        layout.addWidget(btn_tracking, 1, 0)
        
        btn_interpolation = create_tool_btn("📐 Interpoler", 
            "Interpoler entre 2 frames annotés\nIdéal pour SMB!", "#ff9800", "#f57c00")
        btn_interpolation.clicked.connect(self._open_interpolation_tool)
        layout.addWidget(btn_interpolation, 1, 1)
        
        # Ligne 3: Aide (centré)
        btn_help = create_tool_btn("❓ Aide", 
            "Informations sur les outils", "#757575", "#616161")
        btn_help.clicked.connect(self._show_tools_help)
        layout.addWidget(btn_help, 2, 0, 1, 2)  # Span 2 colonnes
        
        group.setLayout(layout)
        return group
    
    def _create_image_info(self):
        """Créer la barre d'info de l'image"""
        frame = QFrame()
        frame.setStyleSheet("background: #f5f5f5; border-radius: 5px; padding: 5px;")
        
        layout = QHBoxLayout(frame)
        layout.setContentsMargins(10, 5, 10, 5)
        
        self.label_image_name = QLabel("Aucune image")
        self.label_image_name.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        layout.addWidget(self.label_image_name)
        
        layout.addStretch()
        
        self.label_image_size = QLabel("")
        self.label_image_size.setStyleSheet("color: #666;")
        layout.addWidget(self.label_image_size)
        
        self.label_progress = QLabel("0/0")
        self.label_progress.setStyleSheet("color: #1976D2; font-weight: bold;")
        layout.addWidget(self.label_progress)
        
        return frame
    
    def _create_navigation(self):
        """Créer la barre de navigation"""
        frame = QFrame()
        layout = QHBoxLayout(frame)
        
        btn_first = QPushButton("⏮️")
        btn_first.clicked.connect(lambda: self._goto_image(0))
        layout.addWidget(btn_first)
        
        btn_prev = QPushButton("◀️ Précédent")
        btn_prev.clicked.connect(lambda: self._navigate(-1))
        layout.addWidget(btn_prev)
        
        self.slider_nav = QSlider(Qt.Orientation.Horizontal)
        self.slider_nav.setMinimum(0)
        self.slider_nav.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider_nav)
        
        btn_next = QPushButton("Suivant ▶️")
        btn_next.clicked.connect(lambda: self._navigate(1))
        layout.addWidget(btn_next)
        
        btn_last = QPushButton("⏭️")
        btn_last.clicked.connect(lambda: self._goto_image(-1))
        layout.addWidget(btn_last)
        
        # Aller à
        layout.addWidget(QLabel("Aller à:"))
        self.spin_goto = QSpinBox()
        self.spin_goto.setMinimum(1)
        layout.addWidget(self.spin_goto)
        
        btn_goto = QPushButton("Go")
        btn_goto.clicked.connect(self._goto_spin)
        layout.addWidget(btn_goto)
        
        return frame
    
    def _create_annotations_list(self):
        """Créer la liste des annotations de l'image courante"""
        group = QGroupBox("📦 Annotations de l'image")
        group.setStyleSheet(self._get_group_style("#FF5722"))
        # Pas de setMaximumHeight pour permettre le redimensionnement avec le splitter
        
        layout = QVBoxLayout()
        
        self.table_annotations = QTableWidget()
        self.table_annotations.setColumnCount(5)
        self.table_annotations.setHorizontalHeaderLabels(["Classe", "X", "Y", "L", "H"])
        self.table_annotations.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table_annotations.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table_annotations)
        
        btn_layout = QHBoxLayout()
        
        btn_delete = QPushButton("🗑️ Supprimer sélection")
        btn_delete.clicked.connect(self._delete_selected_annotation)
        btn_layout.addWidget(btn_delete)
        
        btn_clear = QPushButton("🧹 Tout effacer")
        btn_clear.clicked.connect(self._clear_annotations)
        btn_layout.addWidget(btn_clear)
        
        btn_layout.addStretch()
        
        layout.addLayout(btn_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_action_buttons(self):
        """Créer les boutons d'action"""
        layout = QHBoxLayout()
        
        btn_save = QPushButton("💾 Sauvegarder")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
        """)
        btn_save.clicked.connect(self._save_annotations)
        layout.addWidget(btn_save)
        
        btn_export = QPushButton("📤 Exporter Dataset")
        btn_export.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 10px 25px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        btn_export.clicked.connect(self._export_dataset)
        layout.addWidget(btn_export)
        
        layout.addStretch()
        
        btn_save_project = QPushButton("💼 Sauver Projet")
        btn_save_project.clicked.connect(self._save_project)
        layout.addWidget(btn_save_project)
        
        btn_load_project = QPushButton("📂 Charger Projet")
        btn_load_project.clicked.connect(self._load_project)
        layout.addWidget(btn_load_project)
        
        return layout
    
    def _create_logs(self):
        """Créer la zone de logs"""
        group = QGroupBox("📋 Logs")
        group.setMaximumHeight(100)
        
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("background: #1E1E1E; color: #D4D4D4;")
        layout.addWidget(self.log_text)
        
        group.setLayout(layout)
        return group
    
    def _get_group_style(self, color: str) -> str:
        return f"""
            QGroupBox {{
                font-weight: bold;
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 12px;
                padding-top: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: {color};
            }}
        """
    
    def _setup_shortcuts(self):
        """Configurer les raccourcis clavier"""
        # Navigation
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, lambda: self._navigate(-1))
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, lambda: self._navigate(1))
        QShortcut(QKeySequence(Qt.Key.Key_Space), self, lambda: self._navigate(1))
        
        # Actions
        QShortcut(QKeySequence("Ctrl+S"), self, self._save_annotations)
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, self._delete_selected_annotation)
        QShortcut(QKeySequence("Ctrl+Z"), self, self._undo_last_annotation)
        
        # Mode plein écran
        QShortcut(QKeySequence(Qt.Key.Key_F11), self, self._open_fullscreen_annotation)
        
        # Zoom interface
        QShortcut(QKeySequence("Ctrl++"), self, self._zoom_in)
        QShortcut(QKeySequence("Ctrl+="), self, self._zoom_in)  # Pour claviers sans pavé numérique
        QShortcut(QKeySequence("Ctrl+-"), self, self._zoom_out)
        QShortcut(QKeySequence("Ctrl+0"), self, self._zoom_reset)
    
    def _log(self, message: str):
        """Logger un message"""
        self.log_text.append(message)
    
    # ==================== ACTIONS ====================
    
    def _browse_yaml(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner data.yaml", "", "YAML (*.yaml *.yml)"
        )
        if file_path:
            self.edit_yaml.setText(file_path)
    
    def _browse_frames(self):
        folder = QFileDialog.getExistingDirectory(self, "Dossier des frames")
        if folder:
            self.edit_frames.setText(folder)
            if not self.edit_output.text():
                self.edit_output.setText(os.path.join(folder, "annotations"))
    
    def _load_yaml(self):
        yaml_path = self.edit_yaml.text().strip()
        if not yaml_path:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un fichier data.yaml")
            return
        
        if self.task.load_data_yaml(yaml_path):
            self.class_list.set_classes(self.task.classes)
            if self.task.classes:
                self._on_class_selected(0)
            self._log(f"✅ {len(self.task.classes)} classes chargées")
    
    def _load_frames(self):
        frames_dir = self.edit_frames.text().strip()
        if not frames_dir:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un dossier de frames")
            return
        
        from tasks.dataset_annotator_task import AnnotatorConfig
        
        output_dir = self.edit_output.text().strip() or os.path.join(frames_dir, "annotations")
        
        self.task.configure(AnnotatorConfig(
            frames_dir=frames_dir,
            output_dir=output_dir,
            references_dir=os.path.join(output_dir, "references")
        ))
        
        count = self.task.load_images(frames_dir)
        
        if count > 0:
            # Charger annotations existantes
            self.task.load_existing_annotations(os.path.join(output_dir, "labels"))
            
            self.slider_nav.setMaximum(count - 1)
            self.spin_goto.setMaximum(count)
            self._display_current_image()
            self._log(f"✅ {count} images chargées")
    
    def _add_class(self):
        existing = [cls.name for cls in self.task.classes]
        dialog = AddClassDialog(existing, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            data = dialog.get_data()
            new_class = self.task.add_class(data["name"], data["reference_image"])
            self.class_list.set_classes(self.task.classes)
    
    def _configure_references(self):
        if not self.task.classes:
            QMessageBox.warning(self, "Erreur", "Chargez d'abord les classes depuis data.yaml")
            return
        
        refs_dir = ""
        if self.task.config:
            refs_dir = self.task.config.references_dir
        
        dialog = ClassReferenceDialog(self.task.classes, refs_dir, self)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            references = dialog.get_references()
            modified = False
            
            for class_id, image_path in references.items():
                if image_path:
                    # auto_save=False pour éviter plusieurs sauvegardes
                    if self.task.set_reference_image(class_id, image_path, auto_save=False):
                        modified = True
            
            # Une seule sauvegarde à la fin
            if modified and self.task.current_yaml_path:
                self.task.save_references_config()
            
            self.class_list.set_classes(self.task.classes)
            self._log("✅ Images de référence mises à jour")
    
    def _save_yaml(self):
        yaml_path = self.edit_yaml.text().strip()
        if not yaml_path:
            yaml_path, _ = QFileDialog.getSaveFileName(
                self, "Sauvegarder data.yaml", "data.yaml", "YAML (*.yaml)"
            )
        
        if yaml_path:
            self.task.save_data_yaml(yaml_path)
            self.edit_yaml.setText(yaml_path)
    
    def _on_class_selected(self, class_id: int):
        """Quand une classe est sélectionnée"""
        self.current_class_id = class_id
        self.class_list.highlight_class(class_id)
        
        if class_id < len(self.task.classes):
            cls = self.task.classes[class_id]
            self.canvas.set_current_class(class_id, cls.color)
            self._log(f"Classe sélectionnée: {cls.name} [{cls.shortcut}]")
    
    def _on_image_preview_requested(self, class_id: int, class_name: str, image_path: str):
        """Quand on demande l'aperçu d'une image de référence"""
        if image_path and os.path.exists(image_path):
            dialog = ImagePreviewDialog(image_path, f"Référence: {class_name}", self)
            dialog.exec()
    
    def _on_rename_class(self, class_id: int, current_name: str):
        """Renommer une classe"""
        new_name, ok = QInputDialog.getText(
            self,
            "Renommer la classe",
            f"Nouveau nom pour '{current_name}':",
            QLineEdit.EchoMode.Normal,
            current_name
        )
        
        if ok and new_name.strip():
            new_name = new_name.strip()
            
            # Vérifier si le nom existe déjà
            existing_names = [cls.name.lower() for cls in self.task.classes if cls.id != class_id]
            if new_name.lower() in existing_names:
                QMessageBox.warning(self, "Erreur", f"Le nom '{new_name}' existe déjà!")
                return
            
            # Mettre à jour la classe
            if self.task.update_class(class_id, name=new_name):
                # Sauvegarder automatiquement dans data.yaml
                if self.task.current_yaml_path:
                    self.task.save_data_yaml(self.task.current_yaml_path)
                    self.task.save_references_config()
                
                # Rafraîchir l'affichage
                self.class_list.set_classes(self.task.classes)
                self._log(f"✅ Classe renommée: {current_name} → {new_name}")
    
    def _on_delete_class(self, class_id: int, class_name: str):
        """Supprimer une classe"""
        # Confirmation avec avertissement
        reply = QMessageBox.warning(
            self,
            "Confirmer la suppression",
            f"⚠️ Voulez-vous vraiment supprimer la classe '{class_name}'?\n\n"
            f"Cette action va:\n"
            f"• Supprimer la classe du data.yaml\n"
            f"• Supprimer l'image de référence associée\n"
            f"• Réindexer toutes les classes suivantes\n\n"
            f"Les annotations existantes avec cette classe deviendront invalides!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Supprimer la classe
            if self.task.remove_class(class_id):
                # Sauvegarder automatiquement
                if self.task.current_yaml_path:
                    self.task.save_data_yaml(self.task.current_yaml_path)
                    self.task.save_references_config()
                
                # Rafraîchir l'affichage
                self.class_list.set_classes(self.task.classes)
                
                # Réinitialiser la sélection si nécessaire
                if self.current_class_id >= len(self.task.classes):
                    self.current_class_id = max(0, len(self.task.classes) - 1)
                    if self.task.classes:
                        self._on_class_selected(self.current_class_id)
                
                self._log(f"🗑️ Classe supprimée: {class_name}")
    
    def _on_change_class_image(self, class_id: int, class_name: str):
        """Changer l'image de référence d'une classe"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Nouvelle image pour '{class_name}'",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        
        if file_path:
            if self.task.set_reference_image(class_id, file_path, auto_save=True):
                # Rafraîchir l'affichage
                self.class_list.set_classes(self.task.classes)
                self._log(f"🖼️ Image de référence changée pour: {class_name}")
    
    def _open_fullscreen_annotation(self):
        """Ouvrir l'interface d'annotation en plein écran"""
        if not self.task.images:
            QMessageBox.warning(self, "Erreur", "Chargez d'abord des frames à annoter")
            return
        
        if not self.task.classes:
            QMessageBox.warning(self, "Erreur", "Chargez d'abord les classes depuis data.yaml")
            return
        
        # Sauvegarder les annotations courantes
        self._save_annotations()
        
        # Ouvrir le dialogue plein écran
        dialog = FullScreenAnnotationDialog(self.task, self.task.current_index, self)
        
        # Connecter les signaux pour synchroniser
        dialog.frame_changed.connect(self._on_fullscreen_frame_changed)
        dialog.annotation_added.connect(lambda: self._display_current_image())
        dialog.annotation_removed.connect(lambda: self._display_current_image())
        
        dialog.exec()
        
        # Rafraîchir l'affichage après fermeture
        self._display_current_image()
        self._update_annotations_table()
        self._log("🔍 Mode plein écran fermé")
    
    def _on_fullscreen_frame_changed(self, new_index: int):
        """Quand le frame change dans le mode plein écran"""
        self.task.current_index = new_index
        self.slider_nav.blockSignals(True)
        self.slider_nav.setValue(new_index)
        self.slider_nav.blockSignals(False)
    
    def _display_current_image(self):
        """Afficher l'image courante"""
        img = self.task.get_current_image()
        if not img:
            return
        
        # Charger et afficher l'image
        pixmap = QPixmap(img.image_path)
        self.canvas.set_image(pixmap)
        
        # Afficher les boxes existantes
        boxes = []
        for box in img.boxes:
            cls = self.task.classes[box.class_id] if box.class_id < len(self.task.classes) else None
            color = cls.color if cls else (255, 255, 255)
            boxes.append((box.class_id, box.class_name, color, box.x, box.y, box.width, box.height))
        
        self.canvas.set_boxes(boxes)
        
        # Mettre à jour les infos
        self.label_image_name.setText(img.image_name)
        self.label_image_size.setText(f"{img.width}x{img.height}")
        self.label_progress.setText(f"{self.task.current_index + 1}/{len(self.task.images)}")
        
        self.slider_nav.blockSignals(True)
        self.slider_nav.setValue(self.task.current_index)
        self.slider_nav.blockSignals(False)
        
        # Mettre à jour le tableau des annotations
        self._update_annotations_table()
    
    def _update_annotations_table(self):
        """Mettre à jour le tableau des annotations"""
        img = self.task.get_current_image()
        if not img:
            self.table_annotations.setRowCount(0)
            return
        
        self.table_annotations.setRowCount(len(img.boxes))
        
        for i, box in enumerate(img.boxes):
            self.table_annotations.setItem(i, 0, QTableWidgetItem(box.class_name))
            self.table_annotations.setItem(i, 1, QTableWidgetItem(str(box.x)))
            self.table_annotations.setItem(i, 2, QTableWidgetItem(str(box.y)))
            self.table_annotations.setItem(i, 3, QTableWidgetItem(str(box.width)))
            self.table_annotations.setItem(i, 4, QTableWidgetItem(str(box.height)))
    
    def _navigate(self, direction: int):
        """Naviguer dans les images"""
        self.task.navigate(direction)
        self._display_current_image()
    
    def _goto_image(self, index: int):
        """Aller à une image"""
        if index == -1:
            index = len(self.task.images) - 1
        self.task.goto_image(index)
        self._display_current_image()
    
    def _on_slider_changed(self, value: int):
        """Quand le slider change"""
        self.task.goto_image(value)
        self._display_current_image()
    
    def _goto_spin(self):
        """Aller à l'image du spinbox"""
        index = self.spin_goto.value() - 1
        self._goto_image(index)
    
    def _on_annotation_added(self, class_id: int, x: int, y: int, w: int, h: int):
        """Quand une annotation est ajoutée"""
        if self.task.add_annotation(class_id, x, y, w, h):
            self._display_current_image()
            
            # Mettre à jour le compteur
            if class_id < len(self.task.classes):
                self.class_list.update_count(class_id, self.task.classes[class_id].count)
    
    def _delete_selected_annotation(self):
        """Supprimer l'annotation sélectionnée"""
        row = self.table_annotations.currentRow()
        if row >= 0:
            self.task.remove_annotation(row)
            self._display_current_image()
    
    def _undo_last_annotation(self):
        """Annuler la dernière annotation"""
        img = self.task.get_current_image()
        if img and img.boxes:
            self.task.remove_annotation(len(img.boxes) - 1)
            self._display_current_image()
    
    def _clear_annotations(self):
        """Effacer toutes les annotations de l'image"""
        reply = QMessageBox.question(
            self, "Confirmer",
            "Effacer toutes les annotations de cette image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.task.clear_annotations()
            self._display_current_image()
    
    def _save_annotations(self):
        """Sauvegarder les annotations courantes"""
        if self.task.save_current_annotations():
            self._log("💾 Annotations sauvegardées")
    
    def _export_dataset(self):
        """Exporter le dataset complet"""
        output_dir = QFileDialog.getExistingDirectory(
            self, "Dossier d'export du dataset"
        )
        
        if output_dir:
            result = self.task.export_yolo_dataset(output_dir)
            
            if result["success"]:
                QMessageBox.information(
                    self, "Export réussi",
                    f"✅ Dataset exporté!\n\n"
                    f"📊 Total: {result['total']} images\n"
                    f"🎯 Train: {result['train']}\n"
                    f"📋 Val: {result['val']}\n"
                    f"🧪 Test: {result['test']}\n\n"
                    f"📁 Dossier: {output_dir}"
                )
            else:
                QMessageBox.warning(self, "Erreur", "Échec de l'export")
    
    def _save_project(self):
        """Sauvegarder le projet"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder le projet",
            "annotation_project.json",
            "JSON (*.json)"
        )
        
        if file_path:
            self.task.save_project(file_path)
    
    def _load_project(self):
        """Charger un projet"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Charger un projet",
            "", "JSON (*.json)"
        )
        
        if file_path:
            if self.task.load_project(file_path):
                self.class_list.set_classes(self.task.classes)
                if self.task.classes:
                    self._on_class_selected(0)
                
                if self.task.images:
                    self.slider_nav.setMaximum(len(self.task.images) - 1)
                    self.spin_goto.setMaximum(len(self.task.images))
                    self._display_current_image()
                
                # Restaurer les chemins dans l'UI
                if self.task.config:
                    self.edit_frames.setText(self.task.config.frames_dir)
                    self.edit_output.setText(self.task.config.output_dir)
    
    # ==================== OUTILS D'ANNOTATION AVANCÉS ====================
    
    def _open_sampling_tool(self):
        """Ouvrir l'outil d'échantillonnage"""
        if not self.task.images:
            QMessageBox.warning(self, "Erreur", "Chargez d'abord des images.")
            return
        
        if not TOOLS_PANEL_AVAILABLE:
            QMessageBox.warning(self, "Non disponible", 
                "Le module annotation_tools_panel n'est pas disponible.\n"
                "Vérifiez que le fichier ui/annotation_tools_panel.py existe.")
            return
        
        try:
            from tasks.annotation_helpers import SamplingHelper
            from ui.annotation_tools_panel import SamplingConfigDialog
            
            dialog = SamplingConfigDialog(len(self.task.images), self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                config = dialog.get_config()
                
                helper = SamplingHelper()
                helper.log_callback = self._log
                helper.configure(self.task, **config)
                result = helper.execute()
                
                if result.success:
                    reply = QMessageBox.question(
                        self, "Échantillonnage terminé",
                        f"✅ {result.processed} frames sélectionnés sur {len(self.task.images)}.\n\n"
                        f"Réduction: {100 - (result.processed / len(self.task.images) * 100):.1f}%\n\n"
                        f"Indices sélectionnés sauvegardés.\n"
                        f"Voulez-vous voir les détails?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    )
                    
                    if reply == QMessageBox.StandardButton.Yes:
                        indices = result.details.get('selected_indices', [])
                        QMessageBox.information(self, "Frames sélectionnés",
                            f"Méthode: {config['method']}\n"
                            f"Frames: {len(indices)}\n\n"
                            f"Premiers indices: {indices[:20]}...")
                    
                    self._log(f"✅ Échantillonnage: {result.processed} frames sélectionnés")
                else:
                    QMessageBox.warning(self, "Erreur", result.message)
                    
        except ImportError as e:
            QMessageBox.warning(self, "Module manquant", 
                f"Erreur d'import: {e}\n\n"
                "Vérifiez que les fichiers annotation_helpers sont présents.")
    
    def _open_auto_annotation_tool(self):
        """Ouvrir l'outil de pré-annotation YOLO"""
        if not self.task.images:
            QMessageBox.warning(self, "Erreur", "Chargez d'abord des images.")
            return
        
        if not TOOLS_PANEL_AVAILABLE:
            QMessageBox.warning(self, "Non disponible", 
                "Le module annotation_tools_panel n'est pas disponible.")
            return
        
        try:
            from tasks.annotation_helpers import AutoAnnotationHelper
            
            if not AutoAnnotationHelper.is_available():
                QMessageBox.warning(self, "Non disponible",
                    "La bibliothèque 'ultralytics' n'est pas installée.\n\n"
                    "Installez-la avec:\npip install ultralytics")
                return
            
            from ui.annotation_tools_panel import AutoAnnotationConfigDialog
            
            dialog = AutoAnnotationConfigDialog(self.task.classes, self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                config = dialog.get_config()
                
                if not config['model_path']:
                    QMessageBox.warning(self, "Erreur", "Sélectionnez un modèle YOLO (.pt)")
                    return
                
                helper = AutoAnnotationHelper()
                helper.log_callback = self._log
                helper.configure(self.task, **config)
                
                self._log(f"🤖 Chargement du modèle: {config['model_path']}")
                
                if not helper.load_model():
                    QMessageBox.warning(self, "Erreur", "Impossible de charger le modèle.")
                    return
                
                # Mapping automatique
                helper.auto_map_classes()
                
                self._log("🤖 Pré-annotation en cours...")
                result = helper.execute()
                
                self._display_current_image()
                
                QMessageBox.information(self, "Pré-annotation terminée",
                    f"✅ {result.message}\n\n"
                    f"• Frames traités: {result.processed}\n"
                    f"• Frames ignorés: {result.skipped}\n"
                    f"• Erreurs: {result.errors}\n\n"
                    f"• Détections: {result.details.get('total_detections', 0)}")
                
        except ImportError as e:
            QMessageBox.warning(self, "Module manquant", f"Erreur d'import: {e}")
    
    def _open_tracking_tool(self):
        """Ouvrir l'outil de propagation avec tracking"""
        if not self.task.images:
            QMessageBox.warning(self, "Erreur", "Chargez d'abord des images.")
            return
        
        # Vérifier qu'il y a des annotations sur l'image courante
        img = self.task.get_current_image()
        if not img or not img.boxes:
            QMessageBox.warning(self, "Erreur",
                "Annotez d'abord l'image courante.\n\n"
                "Le tracking propage les annotations de l'image actuelle "
                "aux images suivantes.")
            return
        
        if not TOOLS_PANEL_AVAILABLE:
            QMessageBox.warning(self, "Non disponible", 
                "Le module annotation_tools_panel n'est pas disponible.")
            return
        
        try:
            from tasks.annotation_helpers import TrackingHelper
            
            if not TrackingHelper.is_available():
                QMessageBox.warning(self, "Non disponible",
                    "Les trackers OpenCV ne sont pas disponibles.\n\n"
                    "Installez opencv-contrib-python:\n\n"
                    "pip uninstall opencv-python opencv-python-headless\n"
                    "pip install opencv-contrib-python\n\n"
                    "La version 'contrib' inclut les trackers (KCF, CSRT, etc.)")
                return
            
            from ui.annotation_tools_panel import TrackingConfigDialog
            
            remaining = len(self.task.images) - self.task.current_index - 1
            if remaining <= 0:
                QMessageBox.warning(self, "Erreur", "Pas de frames suivants.")
                return
            
            dialog = TrackingConfigDialog(remaining, len(img.boxes), self)
            if dialog.exec() == QDialog.DialogCode.Accepted:
                config = dialog.get_config()
                
                helper = TrackingHelper()
                helper.log_callback = self._log
                helper.configure(self.task, **config)
                
                self._log(f"🎬 Propagation avec {config['tracker_type']}...")
                result = helper.execute()
                
                self._display_current_image()
                
                if result.success:
                    QMessageBox.information(self, "Propagation terminée",
                        f"✅ {result.message}\n\n"
                        f"• Frames propagés: {result.processed}\n"
                        f"• Frames ignorés: {result.skipped}\n\n"
                        f"• Objets suivis: {result.details.get('objects_tracked', 0)}\n"
                        f"• Objets perdus: {result.details.get('objects_lost', 0)}")
                else:
                    QMessageBox.warning(self, "Erreur de propagation", result.message)
                
        except ImportError as e:
            QMessageBox.warning(self, "Module manquant", f"Erreur d'import: {e}")
    
    def _open_interpolation_tool(self):
        """Ouvrir l'outil d'interpolation simple entre deux frames"""
        if not self.task.images:
            QMessageBox.warning(self, "Erreur", "Chargez d'abord des images.")
            return
        
        # Vérifier qu'il y a des annotations sur l'image courante
        img = self.task.get_current_image()
        if not img or not img.boxes:
            QMessageBox.warning(self, "Erreur",
                "Annotez d'abord le frame de DÉPART.\n\n"
                "L'interpolation fonctionne ainsi:\n"
                "1. Annotez le frame actuel (tous les objets)\n"
                "2. Naviguez vers un frame plus loin\n"
                "3. Annotez ce frame (les mêmes objets, qui ont bougé)\n"
                "4. Lancez l'interpolation")
            return
        
        remaining = len(self.task.images) - self.task.current_index - 1
        if remaining <= 0:
            QMessageBox.warning(self, "Erreur", "Pas de frames suivants.")
            return
        
        start_frame = self.task.current_index
        start_boxes = [(b.class_id, b.class_name, b.x, b.y, b.width, b.height) for b in img.boxes]
        start_count = len(start_boxes)
        
        # Dialogue simplifié
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
        
        # Info
        info_label = QLabel(
            f"<b style='color:#ff9800;'>Frame de DÉBUT:</b> #{start_frame} ({start_count} objets)<br><br>"
            "<b>Instructions:</b><br>"
            "1. Allez au frame de fin et annotez les <b>mêmes objets</b><br>"
            "2. Le système interpole automatiquement les positions<br><br>"
            "<span style='color:#4caf50;'>💡 Astuce: Annotez les objets dans le même ordre!</span>"
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
        
        btn_goto = QPushButton("📍 Aller au frame de fin")
        btn_goto.setStyleSheet("background-color: #ff9800; color: white; padding: 8px;")
        frame_layout.addWidget(btn_goto, 1, 0, 1, 2)
        
        status_label = QLabel("⏳ En attente d'annotation...")
        status_label.setStyleSheet("color: #888;")
        frame_layout.addWidget(status_label, 2, 0, 1, 2)
        
        layout.addWidget(frame_group)
        
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
        
        def goto_end():
            target = spin_end.value()
            self.task.current_index = target
            self._display_current_image()
            
            end_img = self.task.images[target]
            if end_img.boxes:
                status_label.setText(f"✅ Frame #{target}: {len(end_img.boxes)} objets annotés")
                status_label.setStyleSheet("color: #4caf50;")
            else:
                status_label.setText(f"⚠️ Frame #{target}: pas encore annoté!")
                status_label.setStyleSheet("color: #f44336;")
        
        btn_goto.clicked.connect(goto_end)
        
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
            
            for i, box in enumerate(start_boxes):
                cls = box[1]  # class_name
                if cls not in start_by_class:
                    start_by_class[cls] = []
                start_by_class[cls].append((i, box))
            
            for i, box in enumerate(end_boxes):
                cls = box[1]
                if cls not in end_by_class:
                    end_by_class[cls] = []
                end_by_class[cls].append((i, box))
            
            # Matcher les objets communs (présents début ET fin)
            matches_full = []  # (start_box, end_box) - interpolation complète
            
            for cls in start_by_class:
                if cls not in end_by_class:
                    continue
                
                starts = sorted(start_by_class[cls], key=lambda x: (x[1][3], x[1][2]))
                ends = sorted(end_by_class[cls], key=lambda x: (x[1][3], x[1][2]))
                
                for j in range(min(len(starts), len(ends))):
                    matches_full.append((starts[j][1], ends[j][1], cls))
            
            # Identifier les objets qui APPARAISSENT (dans fin mais pas assez dans début)
            appearing_objects = []
            
            for cls in end_by_class:
                end_count = len(end_by_class[cls])
                start_count = len(start_by_class.get(cls, []))
                
                if end_count > start_count:
                    # Il y a des objets supplémentaires de cette classe
                    ends = sorted(end_by_class[cls], key=lambda x: (x[1][3], x[1][2]))
                    # Les objets supplémentaires sont ceux après le start_count
                    for j in range(start_count, end_count):
                        appearing_objects.append((ends[j][1], cls))
            
            total_matches = len(matches_full) + len(appearing_objects)
            
            if total_matches == 0:
                QMessageBox.warning(dialog, "Erreur",
                    "Aucun objet à interpoler!\n"
                    "Vérifiez que les mêmes classes sont annotées dans les deux frames.")
                return
            
            # S'il y a des objets qui apparaissent, demander confirmation
            if appearing_objects:
                appear_names = [obj[1] for obj in appearing_objects]
                appear_frame = (start_frame + end_frame) // 2  # Par défaut: milieu
                
                reply = QMessageBox.question(dialog, "Objets supplémentaires détectés",
                    f"Le frame de fin a {len(appearing_objects)} objet(s) supplémentaire(s):\n"
                    f"• {', '.join(appear_names)}\n\n"
                    f"Ces objets apparaîtront à partir du frame #{appear_frame}\n"
                    f"(milieu de l'intervalle).\n\n"
                    f"Continuer?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                
                if reply != QMessageBox.StandardButton.Yes:
                    return
            
            dialog.accept()
            
            # Interpoler
            total_frames = end_frame - start_frame - 1
            middle_frame = (start_frame + end_frame) // 2
            
            self._log(f"📐 Interpolation de {len(matches_full)} objets complets + {len(appearing_objects)} objets apparaissant")
            
            for frame_offset in range(1, total_frames + 1):
                frame_idx = start_frame + frame_offset
                progress = frame_offset / (total_frames + 1)
                
                self.task.current_index = frame_idx
                
                if check_overwrite.isChecked():
                    self.task.clear_annotations()
                
                # 1. Objets présents du début à la fin (interpolation complète)
                for start_box, end_box, cls in matches_full:
                    x = int(start_box[2] + (end_box[2] - start_box[2]) * progress)
                    y = int(start_box[3] + (end_box[3] - start_box[3]) * progress)
                    w = int(start_box[4] + (end_box[4] - start_box[4]) * progress)
                    h = int(start_box[5] + (end_box[5] - start_box[5]) * progress)
                    
                    if w > 5 and h > 5:
                        self.task.add_annotation(start_box[0], x, y, w, h)
                
                # 2. Objets qui apparaissent (à partir du milieu)
                if frame_idx >= middle_frame and appearing_objects:
                    # Calculer le scrolling par frame basé sur les objets communs
                    if matches_full:
                        # Utiliser le premier objet commun pour estimer le scrolling
                        first_match = matches_full[0]
                        total_scroll_x = first_match[0][2] - first_match[1][2]  # start_x - end_x
                        scroll_per_frame = total_scroll_x / (total_frames + 1) if total_frames > 0 else 0
                    else:
                        scroll_per_frame = 0
                    
                    # Progression depuis le milieu jusqu'à la fin
                    frames_from_middle = frame_idx - middle_frame
                    frames_middle_to_end = end_frame - middle_frame
                    
                    for end_box, cls in appearing_objects:
                        # Position finale (au frame de fin)
                        final_x, final_y = end_box[2], end_box[3]
                        w, h = end_box[4], end_box[5]
                        
                        # Calculer la position à ce frame en appliquant le scrolling inverse
                        frames_to_end = end_frame - frame_idx
                        x = int(final_x + scroll_per_frame * frames_to_end)
                        y = final_y  # Y ne change pas (pas de scrolling vertical)
                        
                        if w > 5 and h > 5:
                            self.task.add_annotation(end_box[0], x, y, w, h)
                
                self.task.save_current_annotations()
            
            # Revenir au début
            self.task.current_index = start_frame
            self._display_current_image()
            
            msg = f"✅ {total_frames} frames annotés!\n\n"
            msg += f"• Objets interpolés: {len(matches_full)}\n"
            if appearing_objects:
                msg += f"• Objets apparaissant: {len(appearing_objects)}\n"
            msg += f"• Du frame #{start_frame} au frame #{end_frame}"
            
            QMessageBox.information(self, "Interpolation terminée", msg)
        
        btn_interpolate.clicked.connect(do_interpolate)
        
        dialog.exec()
    
    def _show_tools_help(self):
        """Afficher l'aide sur les outils"""
        help_text = """
<h2>🛠️ Outils d'annotation avancés</h2>

<p>Ces outils vous aident à annoter plus rapidement vos frames.</p>

<h3>🎯 Échantillonnage</h3>
<p>Réduit le nombre de frames à annoter en sélectionnant un sous-ensemble représentatif.</p>
<ul>
<li><b>Intervalle</b>: 1 frame sur N (ex: 1 sur 10 = 200 frames au lieu de 2000)</li>
<li><b>Aléatoire</b>: Sélection aléatoire de N frames</li>
<li><b>Keyframe</b>: Détecte les changements de scène</li>
<li><b>Diversité</b>: Sélectionne les frames les plus différents</li>
</ul>
<p><b>Gain estimé:</b> 10-20x plus rapide</p>

<h3>🤖 Pré-annotation YOLO</h3>
<p>Utilise un modèle YOLO existant pour détecter automatiquement les objets.</p>
<ul>
<li>Chargez un modèle .pt (pré-entraîné ou personnalisé)</li>
<li>Le système détecte les objets automatiquement</li>
<li>Vous n'avez qu'à corriger les erreurs</li>
</ul>
<p><b>Gain estimé:</b> 5-10x plus rapide</p>

<h3>🎬 Propagation (Tracking)</h3>
<p>Propage les annotations d'un frame aux frames suivants avec suivi d'objets.</p>
<ul>
<li>Annotez un frame de référence</li>
<li>Le système suit les objets automatiquement</li>
<li>Arrêt automatique sur changement de scène</li>
</ul>
<p><b>Gain estimé:</b> 20-50x plus rapide</p>

<h3>📐 Interpolation (RECOMMANDÉ pour SMB)</h3>
<p>Interpole automatiquement les positions entre deux frames annotés.</p>
<ul>
<li><b>Plus fiable</b> que le tracking pour les jeux 2D avec scrolling</li>
<li>Annotez le frame de début et le frame de fin</li>
<li>Le système calcule les positions intermédiaires automatiquement</li>
<li>Idéal pour <b>Super Mario Bros</b> et jeux similaires</li>
</ul>
<p><b>Gain estimé:</b> 10-30x plus rapide</p>

<hr>
<h3>💡 Recommandations pour Super Mario Bros</h3>
<ol>
<li><b>Échantillonnage</b>: 1 frame sur 10 → réduit à ~160 frames</li>
<li><b>Interpolation</b>: Annotez frame 1 et frame 30, interpolez le reste</li>
<li><b>Propagation</b>: Pour Mario et ennemis (objets dynamiques)</li>
</ol>

<h3>🚀 Workflow optimal</h3>
<ol>
<li>Divisez en segments de 30-50 frames</li>
<li>Annotez le premier et dernier frame de chaque segment</li>
<li>Utilisez <b>📐 Interpoler</b> pour les frames intermédiaires</li>
<li>Corrigez manuellement si nécessaire</li>
</ol>
"""
        
        dialog = QDialog(self)
        dialog.setWindowTitle("❓ Aide - Outils d'annotation")
        dialog.setMinimumSize(500, 600)
        
        layout = QVBoxLayout(dialog)
        
        text = QTextEdit()
        text.setReadOnly(True)
        text.setHtml(help_text)
        layout.addWidget(text)
        
        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close)
        
        dialog.exec()
    
    # ==================== ZOOM INTERFACE ====================
    
    def _zoom_in(self):
        """Augmenter la taille de l'interface (Ctrl++)"""
        if not hasattr(self, '_zoom_level'):
            self._zoom_level = 100
        
        if self._zoom_level < 150:
            self._zoom_level += 10
            self._apply_zoom()
            self._log(f"🔍 Zoom: {self._zoom_level}%")
    
    def _zoom_out(self):
        """Réduire la taille de l'interface (Ctrl+-)"""
        if not hasattr(self, '_zoom_level'):
            self._zoom_level = 100
        
        if self._zoom_level > 70:
            self._zoom_level -= 10
            self._apply_zoom()
            self._log(f"🔍 Zoom: {self._zoom_level}%")
    
    def _zoom_reset(self):
        """Réinitialiser le zoom (Ctrl+0)"""
        self._zoom_level = 100
        self._apply_zoom()
        self._log("🔍 Zoom réinitialisé à 100%")
    
    def _apply_zoom(self):
        """Appliquer le niveau de zoom à l'interface"""
        # Calculer le facteur d'échelle
        scale = self._zoom_level / 100.0
        
        # Appliquer via une transformation CSS sur le widget principal
        # Méthode alternative: ajuster la taille de police
        base_font_size = int(9 * scale)
        
        # Créer une feuille de style avec la taille de police ajustée
        zoom_style = f"""
            QWidget {{
                font-size: {base_font_size}pt;
            }}
            QLabel {{
                font-size: {base_font_size}pt;
            }}
            QPushButton {{
                font-size: {base_font_size}pt;
                padding: {int(5 * scale)}px {int(10 * scale)}px;
            }}
            QLineEdit, QComboBox, QSpinBox {{
                font-size: {base_font_size}pt;
                padding: {int(3 * scale)}px;
            }}
            QGroupBox {{
                font-size: {int(10 * scale)}pt;
            }}
            QTableWidget {{
                font-size: {base_font_size}pt;
            }}
        """
        
        # Note: L'application complète du zoom nécessiterait de modifier
        # la feuille de style du widget parent (MainWindow)
        # Pour l'instant, on affiche juste un message
        
        # Alternative: Utiliser QApplication.setFont()
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFont
        
        app = QApplication.instance()
        if app:
            font = app.font()
            font.setPointSize(base_font_size)
            app.setFont(font)
    
    def keyPressEvent(self, event: QKeyEvent):
        """Gérer les raccourcis clavier pour les classes"""
        key = event.text().lower()
        
        # Vérifier si c'est un raccourci de classe
        cls = self.task.get_class_by_shortcut(key)
        if cls:
            self._on_class_selected(cls.id)
            return
        
        super().keyPressEvent(event)