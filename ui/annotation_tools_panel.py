"""
Annotation Tools Panel - Panneau UI pour les outils d'annotation avancés

Ce panneau affiche les différentes fonctionnalités d'assistance à l'annotation
et permet à l'utilisateur de les configurer et les utiliser.
"""

import os
from typing import Dict, List, Optional, Callable
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFrame, QScrollArea, QDialog, QDialogButtonBox,
    QSpinBox, QDoubleSpinBox, QComboBox, QCheckBox, QLineEdit,
    QFileDialog, QMessageBox, QProgressBar, QTextEdit, QTabWidget,
    QGridLayout, QSizePolicy, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QIcon

# Import des helpers
try:
    from tasks.annotation_helpers import (
        SamplingHelper, AutoAnnotationHelper, TrackingHelper,
        HelperInfo, HelperResult
    )
    HELPERS_AVAILABLE = True
except ImportError:
    HELPERS_AVAILABLE = False


class ToolCard(QFrame):
    """Carte représentant un outil d'annotation"""
    
    clicked = pyqtSignal(str)  # tool_id
    info_requested = pyqtSignal(str)  # tool_id
    
    def __init__(self, info: 'HelperInfo', parent=None):
        super().__init__(parent)
        self.info = info
        self._setup_ui()
    
    def _setup_ui(self):
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Raised)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            ToolCard {
                background-color: #3d3d3d;
                border: 2px solid #5d5d5d;
                border-radius: 10px;
                padding: 10px;
            }
            ToolCard:hover {
                border-color: #64b5f6;
                background-color: #454545;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        
        # En-tête avec icône et nom
        header = QHBoxLayout()
        
        icon_label = QLabel(self.info.icon)
        icon_label.setFont(QFont("Segoe UI Emoji", 24))
        header.addWidget(icon_label)
        
        title = QLabel(self.info.name)
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet("color: #64b5f6;")
        header.addWidget(title, stretch=1)
        
        # Bouton info
        btn_info = QPushButton("ℹ️")
        btn_info.setFixedSize(30, 30)
        btn_info.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #5d5d5d;
                border-radius: 15px;
            }
        """)
        btn_info.setToolTip("Plus d'informations")
        btn_info.clicked.connect(lambda: self.info_requested.emit(self.info.id))
        header.addWidget(btn_info)
        
        layout.addLayout(header)
        
        # Description courte
        desc = QLabel(self.info.short_description)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #aaa; font-size: 11px;")
        layout.addWidget(desc)
        
        # Speedup estimé
        if self.info.estimated_speedup:
            speedup = QLabel(f"⚡ {self.info.estimated_speedup}")
            speedup.setStyleSheet("color: #4caf50; font-size: 10px; font-weight: bold;")
            layout.addWidget(speedup)
        
        # Bouton utiliser
        btn_use = QPushButton("▶️ Utiliser")
        btn_use.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border: none;
                padding: 8px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        """)
        btn_use.clicked.connect(lambda: self.clicked.emit(self.info.id))
        layout.addWidget(btn_use)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.info.id)
        super().mousePressEvent(event)


class ToolInfoDialog(QDialog):
    """Dialogue affichant les informations détaillées d'un outil"""
    
    def __init__(self, info: 'HelperInfo', parent=None):
        super().__init__(parent)
        self.info = info
        self.setWindowTitle(f"{info.icon} {info.name}")
        self.setMinimumSize(500, 600)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #2d2d2d;
            }
            QLabel {
                color: white;
            }
            QGroupBox {
                color: #64b5f6;
                font-weight: bold;
                border: 1px solid #5d5d5d;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # En-tête
        header = QHBoxLayout()
        
        icon = QLabel(self.info.icon)
        icon.setFont(QFont("Segoe UI Emoji", 48))
        header.addWidget(icon)
        
        title_layout = QVBoxLayout()
        title = QLabel(self.info.name)
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #64b5f6;")
        title_layout.addWidget(title)
        
        if self.info.estimated_speedup:
            speedup = QLabel(f"⚡ {self.info.estimated_speedup}")
            speedup.setStyleSheet("color: #4caf50; font-size: 14px;")
            title_layout.addWidget(speedup)
        
        header.addLayout(title_layout, stretch=1)
        layout.addLayout(header)
        
        # Scroll area pour le contenu
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)
        
        # Description longue
        desc_group = QGroupBox("📖 Description")
        desc_layout = QVBoxLayout(desc_group)
        desc = QLabel(self.info.long_description)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #ddd; line-height: 1.4;")
        desc_layout.addWidget(desc)
        content_layout.addWidget(desc_group)
        
        # Idéal pour
        if self.info.best_for:
            best_group = QGroupBox("✅ Idéal pour")
            best_layout = QVBoxLayout(best_group)
            for item in self.info.best_for:
                lbl = QLabel(f"• {item}")
                lbl.setStyleSheet("color: #4caf50;")
                best_layout.addWidget(lbl)
            content_layout.addWidget(best_group)
        
        # Limitations
        if self.info.limitations:
            limit_group = QGroupBox("⚠️ Limitations")
            limit_layout = QVBoxLayout(limit_group)
            for item in self.info.limitations:
                lbl = QLabel(f"• {item}")
                lbl.setStyleSheet("color: #ff9800;")
                limit_layout.addWidget(lbl)
            content_layout.addWidget(limit_group)
        
        # Prérequis
        if self.info.requirements:
            req_group = QGroupBox("📦 Prérequis")
            req_layout = QVBoxLayout(req_group)
            for item in self.info.requirements:
                lbl = QLabel(f"• {item}")
                lbl.setStyleSheet("color: #f44336;")
                req_layout.addWidget(lbl)
            content_layout.addWidget(req_group)
        
        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll)
        
        # Bouton fermer
        btn_close = QPushButton("Fermer")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #5d5d5d;
                color: white;
                border: none;
                padding: 10px 30px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #6d6d6d;
            }
        """)
        btn_close.clicked.connect(self.close)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignCenter)


class SamplingConfigDialog(QDialog):
    """Dialogue de configuration de l'échantillonnage"""
    
    def __init__(self, total_frames: int, parent=None):
        super().__init__(parent)
        self.total_frames = total_frames
        self.setWindowTitle("🎯 Configuration de l'échantillonnage")
        self.setMinimumWidth(450)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #2d2d2d; }
            QLabel { color: white; }
            QGroupBox { color: #64b5f6; border: 1px solid #5d5d5d; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
            QSpinBox, QDoubleSpinBox, QComboBox { background-color: #3d3d3d; color: white; border: 1px solid #5d5d5d; padding: 5px; }
            QCheckBox { color: white; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Info
        info = QLabel(f"📊 Total: {self.total_frames} frames")
        info.setStyleSheet("color: #64b5f6; font-size: 12px;")
        layout.addWidget(info)
        
        # Méthode
        method_group = QGroupBox("Méthode d'échantillonnage")
        method_layout = QVBoxLayout(method_group)
        
        self.combo_method = QComboBox()
        self.combo_method.addItems([
            "Intervalle régulier (1 sur N)",
            "Sélection aléatoire",
            "Détection de keyframes",
            "Diversité maximale"
        ])
        self.combo_method.currentIndexChanged.connect(self._on_method_changed)
        method_layout.addWidget(self.combo_method)
        
        # Stack pour les options spécifiques
        self.options_stack = QStackedWidget()
        
        # Options intervalle
        interval_widget = QWidget()
        interval_layout = QHBoxLayout(interval_widget)
        interval_layout.addWidget(QLabel("1 frame sur:"))
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(2, 100)
        self.spin_interval.setValue(10)
        self.spin_interval.valueChanged.connect(self._update_preview)
        interval_layout.addWidget(self.spin_interval)
        self.options_stack.addWidget(interval_widget)
        
        # Options random
        random_widget = QWidget()
        random_layout = QHBoxLayout(random_widget)
        random_layout.addWidget(QLabel("Nombre de frames:"))
        self.spin_count = QSpinBox()
        self.spin_count.setRange(10, self.total_frames)
        self.spin_count.setValue(min(100, self.total_frames))
        self.spin_count.valueChanged.connect(self._update_preview)
        random_layout.addWidget(self.spin_count)
        self.options_stack.addWidget(random_widget)
        
        # Options keyframe
        keyframe_widget = QWidget()
        keyframe_layout = QHBoxLayout(keyframe_widget)
        keyframe_layout.addWidget(QLabel("Seuil de changement:"))
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0.1, 0.9)
        self.spin_threshold.setValue(0.3)
        self.spin_threshold.setSingleStep(0.05)
        keyframe_layout.addWidget(self.spin_threshold)
        self.options_stack.addWidget(keyframe_widget)
        
        # Options diversité
        diversity_widget = QWidget()
        diversity_layout = QHBoxLayout(diversity_widget)
        diversity_layout.addWidget(QLabel("Nombre de frames:"))
        self.spin_diversity = QSpinBox()
        self.spin_diversity.setRange(10, self.total_frames)
        self.spin_diversity.setValue(min(100, self.total_frames))
        diversity_layout.addWidget(self.spin_diversity)
        self.options_stack.addWidget(diversity_widget)
        
        method_layout.addWidget(self.options_stack)
        layout.addWidget(method_group)
        
        # Options communes
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        self.check_first = QCheckBox("Inclure le premier frame")
        self.check_first.setChecked(True)
        options_layout.addWidget(self.check_first)
        
        self.check_last = QCheckBox("Inclure le dernier frame")
        self.check_last.setChecked(True)
        options_layout.addWidget(self.check_last)
        
        layout.addWidget(options_group)
        
        # Aperçu
        self.preview_label = QLabel()
        self.preview_label.setStyleSheet("color: #4caf50; font-weight: bold;")
        layout.addWidget(self.preview_label)
        self._update_preview()
        
        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setStyleSheet("background-color: #666; color: white; padding: 8px 20px; border: none; border-radius: 4px;")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_ok = QPushButton("🎯 Appliquer")
        btn_ok.setStyleSheet("background-color: #1976D2; color: white; padding: 8px 20px; border: none; border-radius: 4px; font-weight: bold;")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        
        layout.addLayout(btn_layout)
    
    def _on_method_changed(self, index):
        self.options_stack.setCurrentIndex(index)
        self._update_preview()
    
    def _update_preview(self):
        method = self.combo_method.currentIndex()
        
        if method == 0:  # Interval
            count = self.total_frames // self.spin_interval.value()
        elif method == 1:  # Random
            count = self.spin_count.value()
        elif method == 2:  # Keyframe
            count = "~variable"
        else:  # Diversity
            count = self.spin_diversity.value()
        
        self.preview_label.setText(f"📊 Estimation: {count} frames à annoter")
    
    def get_config(self) -> Dict:
        methods = ["interval", "random", "keyframe", "diversity"]
        method = methods[self.combo_method.currentIndex()]
        
        return {
            'method': method,
            'interval': self.spin_interval.value(),
            'count': self.spin_count.value() if method == "random" else self.spin_diversity.value(),
            'threshold': self.spin_threshold.value(),
            'include_first': self.check_first.isChecked(),
            'include_last': self.check_last.isChecked()
        }


class AutoAnnotationConfigDialog(QDialog):
    """Dialogue de configuration de la pré-annotation YOLO"""
    
    def __init__(self, task_classes: List, parent=None):
        super().__init__(parent)
        self.task_classes = task_classes
        self.model_path = ""
        self.setWindowTitle("🤖 Configuration de la pré-annotation")
        self.setMinimumWidth(500)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #2d2d2d; }
            QLabel { color: white; }
            QGroupBox { color: #64b5f6; border: 1px solid #5d5d5d; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
            QLineEdit, QSpinBox, QDoubleSpinBox { background-color: #3d3d3d; color: white; border: 1px solid #5d5d5d; padding: 5px; }
            QCheckBox { color: white; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # Modèle
        model_group = QGroupBox("Modèle YOLO")
        model_layout = QHBoxLayout(model_group)
        
        self.edit_model = QLineEdit()
        self.edit_model.setPlaceholderText("Chemin vers le modèle .pt")
        model_layout.addWidget(self.edit_model)
        
        btn_browse = QPushButton("📂")
        btn_browse.setFixedWidth(40)
        btn_browse.clicked.connect(self._browse_model)
        model_layout.addWidget(btn_browse)
        
        layout.addWidget(model_group)
        
        # Paramètres
        params_group = QGroupBox("Paramètres de détection")
        params_layout = QGridLayout(params_group)
        
        params_layout.addWidget(QLabel("Confiance minimum:"), 0, 0)
        self.spin_conf = QDoubleSpinBox()
        self.spin_conf.setRange(0.01, 0.99)
        self.spin_conf.setValue(0.25)
        self.spin_conf.setSingleStep(0.05)
        params_layout.addWidget(self.spin_conf, 0, 1)
        
        params_layout.addWidget(QLabel("Seuil IoU:"), 1, 0)
        self.spin_iou = QDoubleSpinBox()
        self.spin_iou.setRange(0.1, 0.9)
        self.spin_iou.setValue(0.45)
        self.spin_iou.setSingleStep(0.05)
        params_layout.addWidget(self.spin_iou, 1, 1)
        
        layout.addWidget(params_group)
        
        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)
        
        self.check_overwrite = QCheckBox("Écraser les annotations existantes")
        options_layout.addWidget(self.check_overwrite)
        
        self.check_save = QCheckBox("Sauvegarder après chaque frame")
        self.check_save.setChecked(True)
        options_layout.addWidget(self.check_save)
        
        layout.addWidget(options_group)
        
        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setStyleSheet("background-color: #666; color: white; padding: 8px 20px; border: none; border-radius: 4px;")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_ok = QPushButton("🤖 Lancer")
        btn_ok.setStyleSheet("background-color: #1976D2; color: white; padding: 8px 20px; border: none; border-radius: 4px; font-weight: bold;")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        
        layout.addLayout(btn_layout)
    
    def _browse_model(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Sélectionner le modèle YOLO", "",
            "Modèle PyTorch (*.pt);;Tous (*.*)"
        )
        if path:
            self.edit_model.setText(path)
            self.model_path = path
    
    def get_config(self) -> Dict:
        return {
            'model_path': self.edit_model.text(),
            'confidence': self.spin_conf.value(),
            'iou_threshold': self.spin_iou.value(),
            'overwrite_existing': self.check_overwrite.isChecked(),
            'save_after_each': self.check_save.isChecked()
        }


class TrackingConfigDialog(QDialog):
    """Dialogue de configuration du tracking avec compensation de scrolling"""
    
    def __init__(self, remaining_frames: int, num_objects: int, parent=None):
        super().__init__(parent)
        self.remaining_frames = remaining_frames
        self.num_objects = num_objects
        self.setWindowTitle("🎬 Configuration de la propagation")
        self.setMinimumWidth(520)
        self._setup_ui()
    
    def _setup_ui(self):
        self.setStyleSheet("""
            QDialog { background-color: #2d2d2d; }
            QLabel { color: white; }
            QGroupBox { color: #64b5f6; border: 1px solid #5d5d5d; border-radius: 5px; margin-top: 10px; padding-top: 10px; }
            QSpinBox, QDoubleSpinBox, QComboBox { background-color: #3d3d3d; color: white; border: 1px solid #5d5d5d; padding: 5px; }
            QCheckBox { color: white; }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Info
        info = QLabel(f"📊 {self.num_objects} objets à suivre | {self.remaining_frames} frames disponibles")
        info.setStyleSheet("color: #64b5f6; font-size: 12px;")
        layout.addWidget(info)
        
        # Mode de propagation
        mode_group = QGroupBox("🎮 Mode de propagation")
        mode_layout = QVBoxLayout(mode_group)
        
        self.combo_mode = QComboBox()
        self.combo_mode.addItems([
            "📐 Décalage manuel (recommandé pour SMB)",
            "🔄 Compensation auto de scrolling",
            "🎯 Tracking classique (vidéos)",
            "📦 Décalage global uniquement"
        ])
        mode_layout.addWidget(self.combo_mode)
        
        # Description du mode
        self.mode_desc = QLabel("Spécifiez le décalage en pixels par frame. Idéal pour Super Mario Bros.")
        self.mode_desc.setStyleSheet("color: #4caf50; font-size: 10px; font-style: italic;")
        self.mode_desc.setWordWrap(True)
        mode_layout.addWidget(self.mode_desc)
        
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        
        layout.addWidget(mode_group)
        
        # Paramètres de décalage manuel (NOUVEAU)
        self.offset_group = QGroupBox("📐 Décalage manuel (pixels/frame)")
        offset_layout = QGridLayout(self.offset_group)
        
        offset_layout.addWidget(QLabel("Décalage horizontal:"), 0, 0)
        self.spin_offset_x = QDoubleSpinBox()
        self.spin_offset_x.setRange(-50.0, 50.0)
        self.spin_offset_x.setValue(4.0)  # Valeur typique pour SMB
        self.spin_offset_x.setSingleStep(0.5)
        self.spin_offset_x.setSuffix(" px")
        self.spin_offset_x.setToolTip("Positif = scroll vers la droite (Mario avance)\nNégatif = scroll vers la gauche")
        offset_layout.addWidget(self.spin_offset_x, 0, 1)
        
        offset_layout.addWidget(QLabel("Décalage vertical:"), 1, 0)
        self.spin_offset_y = QDoubleSpinBox()
        self.spin_offset_y.setRange(-50.0, 50.0)
        self.spin_offset_y.setValue(0.0)
        self.spin_offset_y.setSingleStep(0.5)
        self.spin_offset_y.setSuffix(" px")
        offset_layout.addWidget(self.spin_offset_y, 1, 1)
        
        # Aide pour estimer le décalage
        help_label = QLabel("💡 Astuce: Pour SMB NES, essayez 3-5 px/frame. Ajustez si les objets dérivent.")
        help_label.setStyleSheet("color: #888; font-size: 9px;")
        help_label.setWordWrap(True)
        offset_layout.addWidget(help_label, 2, 0, 1, 2)
        
        layout.addWidget(self.offset_group)
        
        # Algorithme de tracking
        self.algo_group = QGroupBox("⚙️ Algorithme de tracking")
        algo_layout = QVBoxLayout(self.algo_group)
        
        self.combo_tracker = QComboBox()
        self.combo_tracker.addItems(["KCF (Recommandé)", "CSRT (Plus précis)", "MOSSE (Plus rapide)", "MIL"])
        algo_layout.addWidget(self.combo_tracker)
        
        layout.addWidget(self.algo_group)
        
        # Paramètres généraux
        params_group = QGroupBox("📐 Paramètres")
        params_layout = QGridLayout(params_group)
        
        params_layout.addWidget(QLabel("Nombre max de frames:"), 0, 0)
        self.spin_max = QSpinBox()
        self.spin_max.setRange(1, self.remaining_frames)
        self.spin_max.setValue(min(100, self.remaining_frames))
        params_layout.addWidget(self.spin_max, 0, 1)
        
        params_layout.addWidget(QLabel("Réinit. trackers tous les:"), 1, 0)
        self.spin_reinit = QSpinBox()
        self.spin_reinit.setRange(5, 100)
        self.spin_reinit.setValue(10)
        self.spin_reinit.setSuffix(" frames")
        params_layout.addWidget(self.spin_reinit, 1, 1)
        
        params_layout.addWidget(QLabel("Seuil changement scène:"), 2, 0)
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0.1, 0.9)
        self.spin_threshold.setValue(0.3)
        self.spin_threshold.setSingleStep(0.05)
        params_layout.addWidget(self.spin_threshold, 2, 1)
        
        layout.addWidget(params_group)
        
        # Options
        options_group = QGroupBox("✓ Options")
        options_layout = QVBoxLayout(options_group)
        
        self.check_scene = QCheckBox("Arrêter sur changement de scène")
        self.check_scene.setChecked(True)
        options_layout.addWidget(self.check_scene)
        
        self.check_save = QCheckBox("Sauvegarder après chaque frame")
        self.check_save.setChecked(True)
        options_layout.addWidget(self.check_save)
        
        layout.addWidget(options_group)
        
        # Boutons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Annuler")
        btn_cancel.setStyleSheet("background-color: #666; color: white; padding: 8px 20px; border: none; border-radius: 4px;")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_ok = QPushButton("🎬 Propager")
        btn_ok.setStyleSheet("background-color: #1976D2; color: white; padding: 8px 20px; border: none; border-radius: 4px; font-weight: bold;")
        btn_ok.clicked.connect(self.accept)
        btn_layout.addWidget(btn_ok)
        
        layout.addLayout(btn_layout)
        
        # Initialiser l'état des widgets
        self._on_mode_changed(0)
    
    def _on_mode_changed(self, index):
        """Mettre à jour l'interface selon le mode"""
        descriptions = [
            "Spécifiez le décalage en pixels par frame. Idéal pour Super Mario Bros.",
            "Détecte automatiquement le scrolling. Peut être imprécis.",
            "Suit chaque objet individuellement. Pour vidéos sans scrolling.",
            "Tous les objets se déplacent du même montant."
        ]
        colors = ["#4caf50", "#ff9800", "#2196f3", "#9c27b0"]
        
        self.mode_desc.setText(descriptions[index])
        self.mode_desc.setStyleSheet(f"color: {colors[index]}; font-size: 10px; font-style: italic;")
        
        # Afficher/masquer les options selon le mode
        is_manual = (index == 0)
        is_tracking = (index == 2)
        
        self.offset_group.setVisible(is_manual or index == 3)
        self.algo_group.setVisible(is_tracking or index == 1)
    
    def get_config(self) -> Dict:
        modes = ["manual_offset", "scroll_compensation", "pure_tracking", "static_only"]
        trackers = ["KCF", "CSRT", "MOSSE", "MIL"]
        
        mode_index = self.combo_mode.currentIndex()
        
        return {
            'mode': modes[mode_index],
            'tracker_type': trackers[self.combo_tracker.currentIndex()],
            'max_frames': self.spin_max.value(),
            'reinit_every_n_frames': self.spin_reinit.value(),
            'scene_change_threshold': self.spin_threshold.value(),
            'manual_offset_x': self.spin_offset_x.value(),
            'manual_offset_y': self.spin_offset_y.value(),
            'use_manual_offset': (mode_index == 0),
            'use_scroll_compensation': (mode_index == 1),
            'stop_on_scene_change': self.check_scene.isChecked(),
            'save_after_each': self.check_save.isChecked()
        }


class AnnotationToolsPanel(QWidget):
    """
    Panneau principal des outils d'annotation.
    
    Affiche les différentes fonctionnalités disponibles et permet
    à l'utilisateur de les configurer et les utiliser.
    """
    
    tool_executed = pyqtSignal(str, dict)  # tool_id, result
    
    def __init__(self, task=None, parent=None):
        super().__init__(parent)
        self.task = task
        self.helpers = {}
        self._init_helpers()
        self._setup_ui()
    
    def _init_helpers(self):
        """Initialiser les helpers"""
        if not HELPERS_AVAILABLE:
            return
        
        self.helpers = {
            'sampling': SamplingHelper(),
            'auto_annotation': AutoAnnotationHelper(),
            'tracking': TrackingHelper()
        }
    
    def set_task(self, task):
        """Définir le task à utiliser"""
        self.task = task
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        
        # Titre
        title_layout = QHBoxLayout()
        
        title = QLabel("🛠️ Outils d'annotation")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: #64b5f6;")
        title_layout.addWidget(title)
        
        title_layout.addStretch()
        
        # Bouton aide
        btn_help = QPushButton("❓")
        btn_help.setFixedSize(30, 30)
        btn_help.setStyleSheet("""
            QPushButton {
                background-color: #5d5d5d;
                color: white;
                border: none;
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: #6d6d6d;
            }
        """)
        btn_help.setToolTip("Aide sur les outils")
        btn_help.clicked.connect(self._show_help)
        title_layout.addWidget(btn_help)
        
        layout.addLayout(title_layout)
        
        # Description
        desc = QLabel("Sélectionnez un outil pour accélérer votre annotation:")
        desc.setStyleSheet("color: #aaa; font-size: 11px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)
        
        # Cartes des outils
        if HELPERS_AVAILABLE:
            for helper_id, helper in self.helpers.items():
                info = helper.get_info()
                card = ToolCard(info)
                card.clicked.connect(self._on_tool_clicked)
                card.info_requested.connect(self._show_tool_info)
                layout.addWidget(card)
        else:
            no_helpers = QLabel("⚠️ Module annotation_helpers non disponible")
            no_helpers.setStyleSheet("color: #ff9800;")
            layout.addWidget(no_helpers)
        
        layout.addStretch()
    
    def _show_help(self):
        """Afficher l'aide générale"""
        QMessageBox.information(
            self, "Aide - Outils d'annotation",
            "🛠️ **Outils d'annotation avancés**\n\n"
            "Ces outils vous aident à annoter plus rapidement:\n\n"
            "• **Échantillonnage**: Réduire le nombre de frames\n"
            "• **Pré-annotation**: Détection automatique YOLO\n"
            "• **Tracking**: Suivi automatique des objets\n\n"
            "Cliquez sur ℹ️ pour plus de détails sur chaque outil."
        )
    
    def _show_tool_info(self, tool_id: str):
        """Afficher les infos détaillées d'un outil"""
        if tool_id in self.helpers:
            info = self.helpers[tool_id].get_info()
            dialog = ToolInfoDialog(info, self)
            dialog.exec()
    
    def _on_tool_clicked(self, tool_id: str):
        """Quand un outil est cliqué"""
        if not self.task:
            QMessageBox.warning(self, "Erreur", "Chargez d'abord des images.")
            return
        
        if tool_id == "sampling":
            self._run_sampling()
        elif tool_id == "auto_annotation":
            self._run_auto_annotation()
        elif tool_id == "tracking":
            self._run_tracking()
    
    def _run_sampling(self):
        """Exécuter l'échantillonnage"""
        if not self.task.images:
            QMessageBox.warning(self, "Erreur", "Aucune image chargée.")
            return
        
        dialog = SamplingConfigDialog(len(self.task.images), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            
            helper = self.helpers['sampling']
            helper.configure(self.task, **config)
            result = helper.execute()
            
            if result.success:
                # Demander si on veut appliquer le filtre
                reply = QMessageBox.question(
                    self, "Échantillonnage terminé",
                    f"✅ {result.processed} frames sélectionnés.\n\n"
                    f"Voulez-vous masquer les autres frames?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    helper.apply_filter()
                
                self.tool_executed.emit('sampling', result.to_dict())
            else:
                QMessageBox.warning(self, "Erreur", result.message)
    
    def _run_auto_annotation(self):
        """Exécuter la pré-annotation"""
        if not AutoAnnotationHelper.is_available():
            QMessageBox.warning(
                self, "Non disponible",
                "La bibliothèque 'ultralytics' n'est pas installée.\n\n"
                "Installez-la avec: pip install ultralytics"
            )
            return
        
        dialog = AutoAnnotationConfigDialog(self.task.classes, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            
            if not config['model_path']:
                QMessageBox.warning(self, "Erreur", "Sélectionnez un modèle YOLO.")
                return
            
            helper = self.helpers['auto_annotation']
            helper.configure(self.task, **config)
            
            if not helper.load_model():
                QMessageBox.warning(self, "Erreur", "Impossible de charger le modèle.")
                return
            
            # Tenter le mapping automatique
            helper.auto_map_classes()
            
            # Exécuter
            result = helper.execute()
            
            QMessageBox.information(
                self, "Pré-annotation terminée",
                f"✅ {result.message}\n\n"
                f"• Frames traités: {result.processed}\n"
                f"• Frames ignorés: {result.skipped}\n"
                f"• Erreurs: {result.errors}"
            )
            
            self.tool_executed.emit('auto_annotation', result.to_dict())
    
    def _run_tracking(self):
        """Exécuter le tracking"""
        if not TrackingHelper.is_available():
            QMessageBox.warning(
                self, "Non disponible",
                "OpenCV n'est pas installé correctement.\n\n"
                "Installez-le avec: pip install opencv-python"
            )
            return
        
        # Vérifier qu'il y a des annotations
        img = self.task.get_current_image()
        if not img or not img.boxes:
            QMessageBox.warning(
                self, "Erreur",
                "Annotez d'abord le frame courant avant de propager."
            )
            return
        
        remaining = len(self.task.images) - self.task.current_index - 1
        if remaining <= 0:
            QMessageBox.warning(self, "Erreur", "Pas de frames suivants.")
            return
        
        dialog = TrackingConfigDialog(remaining, len(img.boxes), self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            config = dialog.get_config()
            
            helper = self.helpers['tracking']
            helper.configure(self.task, **config)
            result = helper.execute()
            
            QMessageBox.information(
                self, "Propagation terminée",
                f"✅ {result.message}\n\n"
                f"• Frames propagés: {result.processed}\n"
                f"• Frames ignorés: {result.skipped}"
            )
            
            self.tool_executed.emit('tracking', result.to_dict())