"""
YOLO Training Widget - Interface pour l'entraînement de modèles YOLO
Version améliorée avec pause/reprise, arrêt réel, logs temps réel et accès aux résultats
"""

import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QGridLayout, QProgressBar, QLineEdit, QSpinBox, QCheckBox,
    QTextEdit, QComboBox, QSizePolicy, QTabWidget, QListWidget,
    QListWidgetItem, QDialog, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QColor

# Import conditionnel
try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False


class TrainingThread(QThread):
    """Thread pour l'entraînement en arrière-plan"""
    
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, dict)
    finished_signal = pyqtSignal(object)
    
    def __init__(self, task, resume_path=None, parent=None):
        super().__init__(parent)
        self.task = task
        self.resume_path = resume_path
    
    def run(self):
        """Exécuter l'entraînement"""
        # Configurer les callbacks
        self.task.log_callback = self._log
        self.task.status_callback = self._status
        self.task.progress_callback = self._progress
        
        if self.resume_path:
            result = self.task.resume(self.resume_path)
        else:
            result = self.task.execute()
        
        self.finished_signal.emit(result)
    
    def _log(self, message: str):
        self.log_signal.emit(message)
    
    def _status(self, status: str):
        self.status_signal.emit(status)
    
    def _progress(self, current: int, total: int, metrics: dict):
        self.progress_signal.emit(current, total, metrics)


class ExistingResultsDialog(QDialog):
    """Dialogue pour sélectionner un résultat existant"""
    
    def __init__(self, results: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Résultats d'entraînement existants")
        self.setMinimumSize(600, 400)
        self.selected_result = None
        
        layout = QVBoxLayout(self)
        
        # Instructions
        info = QLabel("Sélectionnez un entraînement précédent pour voir les résultats ou reprendre:")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # Liste des résultats
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget::item { padding: 10px; }
            QListWidget::item:selected { background-color: #1565C0; color: white; }
        """)
        
        self.results_data = {}
        for r in results:
            item_text = f"📁 {r['name']} - {r['date']}"
            if r.get('has_best'):
                item_text += " ✅ best.pt"
            if r.get('has_last'):
                item_text += " 💾 last.pt"
            
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, r)
            self.list_widget.addItem(item)
            self.results_data[r['name']] = r
        
        self.list_widget.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.list_widget)
        
        # Boutons
        btn_layout = QHBoxLayout()
        
        self.btn_open = QPushButton("📂 Ouvrir le dossier")
        self.btn_open.clicked.connect(self._open_folder)
        btn_layout.addWidget(self.btn_open)
        
        self.btn_resume = QPushButton("▶️ Reprendre l'entraînement")
        self.btn_resume.clicked.connect(self._resume)
        self.btn_resume.setEnabled(False)
        btn_layout.addWidget(self.btn_resume)
        
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Fermer")
        self.btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
    
    def _on_selection_changed(self, current, previous):
        if current:
            r = current.data(Qt.ItemDataRole.UserRole)
            self.btn_resume.setEnabled(r.get('has_last', False))
    
    def _on_double_click(self, item):
        self._open_folder()
    
    def _open_folder(self):
        current = self.list_widget.currentItem()
        if current:
            r = current.data(Qt.ItemDataRole.UserRole)
            path = r.get('path')
            if path and os.path.exists(path):
                import subprocess
                import sys
                if sys.platform == 'win32':
                    subprocess.run(['explorer', path])
                elif sys.platform == 'darwin':
                    subprocess.run(['open', path])
                else:
                    subprocess.run(['xdg-open', path])
    
    def _resume(self):
        current = self.list_widget.currentItem()
        if current:
            r = current.data(Qt.ItemDataRole.UserRole)
            if r.get('has_last'):
                self.selected_result = r
                self.accept()


class YOLOTrainingWidget(QWidget):
    """
    Widget pour l'entraînement de modèles YOLO
    Interface complète avec configuration, logs temps réel, pause/reprise et résultats
    """
    
    task_requested = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.data_path = None
        self.training_thread = None
        self.current_task = None
        self.is_training = False
        self.is_paused = False
        self.last_checkpoint = None
        self.last_result_dir = None
        
        self._create_ui()
        self._check_dependencies()
    
    def _create_ui(self):
        """Créer l'interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(15)
        
        # 1. Bannière
        content_layout.addWidget(self._create_banner())
        
        # 2. Statut système
        content_layout.addWidget(self._create_system_group())
        
        # 3. Dataset
        content_layout.addWidget(self._create_dataset_group())
        
        # 4. Configuration
        content_layout.addWidget(self._create_config_group())
        
        # 5. Logs et résultats (tabs)
        content_layout.addWidget(self._create_output_group())
        
        content_layout.addStretch()
        
        # 6. Boutons
        content_layout.addLayout(self._create_action_buttons())
        
        scroll.setWidget(content)
        layout.addWidget(scroll)
    
    def _create_banner(self):
        """Créer la bannière d'information"""
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #1565C0, stop:1 #0D47A1);
                border-radius: 8px;
                padding: 15px;
            }
            QLabel { color: white; }
        """)
        
        layout = QVBoxLayout(banner)
        
        title = QLabel("🤖 Entraînement YOLO")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Entraînez un modèle YOLO sur votre dataset Mario.\n"
            "Le système détecte automatiquement votre GPU et optimise les paramètres.\n"
            "Vous pouvez mettre en pause et reprendre l'entraînement à tout moment."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #E3F2FD; font-size: 11px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_system_group(self):
        """Créer le groupe statut système"""
        group = QGroupBox("💻 Statut Système")
        group.setStyleSheet(self._get_group_style("#607D8B"))
        
        layout = QGridLayout()
        
        # PyTorch
        layout.addWidget(QLabel("PyTorch:"), 0, 0)
        self.label_pytorch = QLabel("Vérification...")
        layout.addWidget(self.label_pytorch, 0, 1)
        
        # Ultralytics
        layout.addWidget(QLabel("Ultralytics:"), 0, 2)
        self.label_ultralytics = QLabel("Vérification...")
        layout.addWidget(self.label_ultralytics, 0, 3)
        
        # GPU
        layout.addWidget(QLabel("GPU:"), 1, 0)
        self.label_gpu = QLabel("Vérification...")
        layout.addWidget(self.label_gpu, 1, 1, 1, 3)
        
        # Mémoire
        layout.addWidget(QLabel("VRAM:"), 2, 0)
        self.label_vram = QLabel("Vérification...")
        layout.addWidget(self.label_vram, 2, 1)
        
        # Batch recommandé
        layout.addWidget(QLabel("Batch recommandé:"), 2, 2)
        self.label_batch_rec = QLabel("-")
        layout.addWidget(self.label_batch_rec, 2, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_dataset_group(self):
        """Créer le groupe sélection dataset"""
        group = QGroupBox("📁 Dataset YOLO")
        group.setStyleSheet(self._get_group_style("#4CAF50"))
        
        layout = QGridLayout()
        
        # Fichier data.yaml
        layout.addWidget(QLabel("Fichier data.yaml:"), 0, 0)
        
        self.edit_data_path = QLineEdit()
        self.edit_data_path.setPlaceholderText("Chemin vers data.yaml...")
        self.edit_data_path.textChanged.connect(self._on_data_path_changed)
        layout.addWidget(self.edit_data_path, 0, 1)
        
        btn_browse = QPushButton("📂 Parcourir")
        btn_browse.clicked.connect(self._browse_data_file)
        layout.addWidget(btn_browse, 0, 2)
        
        # Info dataset
        self.label_dataset_info = QLabel("")
        self.label_dataset_info.setStyleSheet("color: #666; font-size: 10px;")
        self.label_dataset_info.setWordWrap(True)
        layout.addWidget(self.label_dataset_info, 1, 0, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_config_group(self):
        """Créer le groupe configuration"""
        group = QGroupBox("⚙️ Configuration")
        group.setStyleSheet(self._get_group_style("#FF9800"))
        
        layout = QGridLayout()
        
        # Preset
        layout.addWidget(QLabel("Preset:"), 0, 0)
        self.combo_preset = QComboBox()
        self.combo_preset.addItem("🧪 Test Rapide (5 epochs)", "quick_test")
        self.combo_preset.addItem("⚡ Court (25 epochs)", "short")
        self.combo_preset.addItem("📊 Standard (100 epochs)", "standard")
        self.combo_preset.addItem("🔬 Étendu (200 epochs)", "extended")
        self.combo_preset.addItem("💻 CPU Sécurisé (50 epochs)", "cpu_safe")
        self.combo_preset.addItem("🔧 Personnalisé", "custom")
        self.combo_preset.setCurrentIndex(2)  # Standard par défaut
        self.combo_preset.currentIndexChanged.connect(self._on_preset_changed)
        layout.addWidget(self.combo_preset, 0, 1)
        
        # Modèle
        layout.addWidget(QLabel("Modèle:"), 0, 2)
        self.combo_model = QComboBox()
        self.combo_model.addItem("YOLOv8n (Nano - Rapide)", "yolov8n.pt")
        self.combo_model.addItem("YOLOv8s (Small - Équilibré)", "yolov8s.pt")
        self.combo_model.addItem("YOLOv8m (Medium - Précis)", "yolov8m.pt")
        self.combo_model.addItem("YOLOv8l (Large - Très précis)", "yolov8l.pt")
        self.combo_model.addItem("YOLOv8x (XLarge - Maximum)", "yolov8x.pt")
        layout.addWidget(self.combo_model, 0, 3)
        
        # Epochs
        layout.addWidget(QLabel("Epochs:"), 1, 0)
        self.spin_epochs = QSpinBox()
        self.spin_epochs.setRange(1, 1000)
        self.spin_epochs.setValue(100)
        layout.addWidget(self.spin_epochs, 1, 1)
        
        # Batch size
        layout.addWidget(QLabel("Batch Size:"), 1, 2)
        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(1, 128)
        self.spin_batch.setValue(8)
        self.spin_batch.setSpecialValueText("Auto")
        layout.addWidget(self.spin_batch, 1, 3)
        
        # Device
        layout.addWidget(QLabel("Device:"), 2, 0)
        self.combo_device = QComboBox()
        self.combo_device.addItem("🔥 Auto (GPU si disponible)", "auto")
        self.combo_device.addItem("🎮 GPU (CUDA)", "cuda")
        self.combo_device.addItem("💻 CPU", "cpu")
        layout.addWidget(self.combo_device, 2, 1)
        
        # Workers
        layout.addWidget(QLabel("Workers:"), 2, 2)
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(0, 16)
        self.spin_workers.setValue(0)
        self.spin_workers.setToolTip("0 = désactivé (recommandé pour Windows)")
        layout.addWidget(self.spin_workers, 2, 3)
        
        # Options avancées
        layout.addWidget(QLabel("Options:"), 3, 0)
        
        options_layout = QHBoxLayout()
        
        self.check_amp = QCheckBox("Mixed Precision (AMP)")
        self.check_amp.setChecked(True)
        self.check_amp.setToolTip("Accélère l'entraînement et réduit la mémoire")
        options_layout.addWidget(self.check_amp)
        
        self.check_cache = QCheckBox("Cache images")
        self.check_cache.setChecked(False)
        self.check_cache.setToolTip("Cache en RAM - nécessite beaucoup de mémoire")
        options_layout.addWidget(self.check_cache)
        
        options_layout.addStretch()
        
        layout.addLayout(options_layout, 3, 1, 1, 3)
        
        # Patience et Save Period
        layout.addWidget(QLabel("Patience:"), 4, 0)
        self.spin_patience = QSpinBox()
        self.spin_patience.setRange(10, 200)
        self.spin_patience.setValue(50)
        self.spin_patience.setToolTip("Arrêt si pas d'amélioration après N epochs")
        layout.addWidget(self.spin_patience, 4, 1)
        
        layout.addWidget(QLabel("Save Period:"), 4, 2)
        self.spin_save_period = QSpinBox()
        self.spin_save_period.setRange(1, 50)
        self.spin_save_period.setValue(10)
        self.spin_save_period.setToolTip("Sauvegarder tous les N epochs")
        layout.addWidget(self.spin_save_period, 4, 3)
        
        # Nom du projet
        layout.addWidget(QLabel("Nom projet:"), 5, 0)
        self.edit_project_name = QLineEdit("mario_yolo")
        layout.addWidget(self.edit_project_name, 5, 1, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_output_group(self):
        """Créer le groupe logs/résultats"""
        group = QGroupBox("📋 Logs & Résultats")
        group.setStyleSheet(self._get_group_style("#9C27B0"))
        
        layout = QVBoxLayout()
        
        # Progress bar et epoch
        progress_layout = QHBoxLayout()
        
        self.label_epoch = QLabel("Epoch: -/-")
        self.label_epoch.setStyleSheet("font-weight: bold;")
        progress_layout.addWidget(self.label_epoch)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        
        # Tabs
        tabs = QTabWidget()
        
        # Tab Logs
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #333;
            }
        """)
        self.log_text.setMinimumHeight(250)
        log_layout.addWidget(self.log_text)
        
        # Boutons log
        log_btn_layout = QHBoxLayout()
        
        btn_clear_log = QPushButton("🗑️ Effacer")
        btn_clear_log.clicked.connect(self.log_text.clear)
        log_btn_layout.addWidget(btn_clear_log)
        
        btn_copy_log = QPushButton("📋 Copier")
        btn_copy_log.clicked.connect(self._copy_log)
        log_btn_layout.addWidget(btn_copy_log)
        
        self.check_autoscroll = QCheckBox("Auto-scroll")
        self.check_autoscroll.setChecked(True)
        log_btn_layout.addWidget(self.check_autoscroll)
        
        log_btn_layout.addStretch()
        log_layout.addLayout(log_btn_layout)
        
        tabs.addTab(log_widget, "📋 Logs")
        
        # Tab Résultats
        result_widget = QWidget()
        result_layout = QVBoxLayout(result_widget)
        
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setMinimumHeight(200)
        self.result_text.setPlaceholderText(
            "Les résultats de l'entraînement s'afficheront ici.\n\n"
            "Vous pouvez aussi accéder aux entraînements précédents\n"
            "via le bouton 'Voir les résultats existants'."
        )
        result_layout.addWidget(self.result_text)
        
        # Boutons résultats
        result_btn_layout = QHBoxLayout()
        
        self.btn_open_results = QPushButton("📂 Ouvrir le dossier des résultats")
        self.btn_open_results.clicked.connect(self._open_results_dir)
        result_btn_layout.addWidget(self.btn_open_results)
        
        self.btn_existing_results = QPushButton("📚 Voir les résultats existants")
        self.btn_existing_results.clicked.connect(self._show_existing_results)
        result_btn_layout.addWidget(self.btn_existing_results)
        
        result_btn_layout.addStretch()
        result_layout.addLayout(result_btn_layout)
        
        tabs.addTab(result_widget, "📊 Résultats")
        
        layout.addWidget(tabs)
        
        # Status
        self.status_label = QLabel("En attente...")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)
        
        group.setLayout(layout)
        return group
    
    def _create_action_buttons(self):
        """Créer les boutons d'action"""
        layout = QHBoxLayout()
        
        self.btn_start = QPushButton("🚀 Démarrer l'Entraînement")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #9E9E9E; }
        """)
        self.btn_start.clicked.connect(self._start_training)
        self.btn_start.setEnabled(False)
        layout.addWidget(self.btn_start)
        
        self.btn_pause = QPushButton("⏸️ Pause")
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: #9E9E9E; }
        """)
        self.btn_pause.clicked.connect(self._pause_training)
        self.btn_pause.setEnabled(False)
        layout.addWidget(self.btn_pause)
        
        self.btn_resume = QPushButton("▶️ Reprendre")
        self.btn_resume.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
            QPushButton:disabled { background-color: #9E9E9E; }
        """)
        self.btn_resume.clicked.connect(self._resume_training)
        self.btn_resume.setEnabled(False)
        layout.addWidget(self.btn_resume)
        
        self.btn_stop = QPushButton("⏹️ Arrêter")
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 12px 25px;
                border-radius: 6px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d32f2f; }
            QPushButton:disabled { background-color: #9E9E9E; }
        """)
        self.btn_stop.clicked.connect(self._stop_training)
        self.btn_stop.setEnabled(False)
        layout.addWidget(self.btn_stop)
        
        layout.addStretch()
        
        return layout
    
    def _get_group_style(self, color: str) -> str:
        """Style pour les groupes"""
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
    
    def _check_dependencies(self):
        """Vérifier les dépendances"""
        from tasks.yolo_training_task import YOLOTrainingTask
        
        deps = YOLOTrainingTask.check_dependencies()
        gpu_info = YOLOTrainingTask.get_gpu_info()
        
        # PyTorch
        if deps["torch"]:
            import torch
            self.label_pytorch.setText(f"✅ v{torch.__version__}")
            self.label_pytorch.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.label_pytorch.setText("❌ Non installé")
            self.label_pytorch.setStyleSheet("color: #f44336; font-weight: bold;")
        
        # Ultralytics
        if deps["ultralytics"]:
            self.label_ultralytics.setText("✅ Installé")
            self.label_ultralytics.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            self.label_ultralytics.setText("❌ Non installé")
            self.label_ultralytics.setStyleSheet("color: #f44336; font-weight: bold;")
        
        # GPU
        if gpu_info["available"]:
            self.label_gpu.setText(f"✅ {gpu_info['name']}")
            self.label_gpu.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.label_vram.setText(f"{gpu_info['memory_gb']:.1f} GB")
            
            # Batch recommandé
            if gpu_info['memory_gb'] < 4:
                rec_batch = 2
            elif gpu_info['memory_gb'] < 6:
                rec_batch = 4
            elif gpu_info['memory_gb'] < 8:
                rec_batch = 8
            else:
                rec_batch = 16
            
            self.label_batch_rec.setText(str(rec_batch))
            self.spin_batch.setValue(rec_batch)
        else:
            self.label_gpu.setText("❌ Non disponible (mode CPU)")
            self.label_gpu.setStyleSheet("color: #FF9800; font-weight: bold;")
            self.label_vram.setText("N/A")
            self.label_batch_rec.setText("2-4")
            self.spin_batch.setValue(2)
            self.combo_device.setCurrentIndex(2)  # CPU
    
    def _browse_data_file(self):
        """Parcourir pour data.yaml"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner data.yaml",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)"
        )
        
        if file_path:
            self.edit_data_path.setText(file_path)
    
    def _on_data_path_changed(self, path: str):
        """Quand le chemin change"""
        if os.path.exists(path) and path.endswith(('.yaml', '.yml')):
            self.data_path = path
            self._analyze_dataset(path)
            self.btn_start.setEnabled(True)
        else:
            self.data_path = None
            self.label_dataset_info.setText("⚠️ Fichier data.yaml invalide ou inexistant")
            self.btn_start.setEnabled(False)
    
    def _analyze_dataset(self, path: str):
        """Analyser le dataset"""
        try:
            import yaml
            
            with open(path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            info_parts = []
            
            # Classes
            if 'names' in data:
                names = data['names']
                if isinstance(names, dict):
                    num_classes = len(names)
                    class_list = list(names.values())[:5]
                else:
                    num_classes = len(names)
                    class_list = names[:5]
                
                info_parts.append(f"📦 {num_classes} classes: {', '.join(str(c) for c in class_list)}")
                if num_classes > 5:
                    info_parts[-1] += "..."
            
            # Paths
            base_dir = Path(path).parent
            for split in ['train', 'val', 'test']:
                if split in data:
                    split_path = base_dir / data[split] / "images"
                    if split_path.exists():
                        count = len(list(split_path.glob("*")))
                        info_parts.append(f"  {split}: {count} images")
            
            self.label_dataset_info.setText(" | ".join(info_parts))
            self.label_dataset_info.setStyleSheet("color: #4CAF50; font-size: 10px;")
            
        except Exception as e:
            self.label_dataset_info.setText(f"⚠️ Erreur lecture: {e}")
            self.label_dataset_info.setStyleSheet("color: #f44336; font-size: 10px;")
    
    def _on_preset_changed(self, index: int):
        """Quand le preset change"""
        from tasks.yolo_training_task import YOLOTrainingTask
        
        preset_key = self.combo_preset.currentData()
        
        if preset_key == "custom":
            return
        
        if preset_key in YOLOTrainingTask.TRAINING_PRESETS:
            preset = YOLOTrainingTask.TRAINING_PRESETS[preset_key]
            
            self.spin_epochs.setValue(preset["epochs"])
            
            if preset.get("batch_size"):
                self.spin_batch.setValue(preset["batch_size"])
            
            if preset.get("device") == "cpu":
                self.combo_device.setCurrentIndex(2)
            else:
                self.combo_device.setCurrentIndex(0)
    
    def _start_training(self):
        """Démarrer l'entraînement"""
        if not self.data_path:
            QMessageBox.warning(self, "Erreur", "Sélectionnez un fichier data.yaml")
            return
        
        if self.is_training:
            QMessageBox.warning(self, "Entraînement en cours", 
                              "Un entraînement est déjà en cours.\n"
                              "Arrêtez-le ou mettez-le en pause avant d'en lancer un nouveau.")
            return
        
        reply = QMessageBox.question(
            self,
            "Démarrer l'entraînement",
            f"Lancer l'entraînement avec {self.spin_epochs.value()} epochs?\n\n"
            f"Modèle: {self.combo_model.currentData()}\n"
            f"Batch: {self.spin_batch.value()}\n"
            f"Device: {self.combo_device.currentData()}\n\n"
            f"Vous pourrez mettre en pause ou arrêter à tout moment.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        self._launch_training()
    
    def _launch_training(self, resume_path: str = None):
        """Lancer l'entraînement (nouveau ou reprise)"""
        try:
            from tasks.yolo_training_task import YOLOTrainingTask, TrainingConfig
            
            # Configuration
            device = self.combo_device.currentData()
            if device == "auto":
                device = None
            
            batch = self.spin_batch.value()
            if batch == 0:
                batch = None
            
            config = TrainingConfig(
                data_path=self.data_path,
                model_name=self.combo_model.currentData(),
                epochs=self.spin_epochs.value(),
                batch_size=batch,
                device=device,
                workers=self.spin_workers.value(),
                patience=self.spin_patience.value(),
                save_period=self.spin_save_period.value(),
                cache=self.check_cache.isChecked(),
                amp=self.check_amp.isChecked(),
                name=self.edit_project_name.text() or "mario_yolo",
                resume_from=resume_path
            )
            
            # Créer la tâche
            self.current_task = YOLOTrainingTask()
            self.current_task.configure(config)
            
            # Thread d'entraînement
            self.training_thread = TrainingThread(self.current_task, resume_path, self)
            self.training_thread.log_signal.connect(self._on_log)
            self.training_thread.status_signal.connect(self._on_status)
            self.training_thread.progress_signal.connect(self._on_progress)
            self.training_thread.finished_signal.connect(self._on_training_finished)
            
            # UI
            self.is_training = True
            self.is_paused = False
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_resume.setEnabled(False)
            self.btn_stop.setEnabled(True)
            
            if not resume_path:
                self.log_text.clear()
            
            self.status_label.setText("🚀 Démarrage...")
            self.progress_bar.setValue(0)
            
            # Lancer
            self.training_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
            self._reset_ui_state()
    
    def _pause_training(self):
        """Mettre en pause l'entraînement"""
        if not self.is_training or not self.current_task:
            return
        
        reply = QMessageBox.question(
            self,
            "Pause",
            "Mettre l'entraînement en pause?\n\n"
            "Le modèle sera sauvegardé et vous pourrez reprendre plus tard.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._on_log("\n⏸️ Mise en pause demandée...")
            self.status_label.setText("⏸️ Mise en pause...")
            
            # Mettre en pause
            checkpoint = self.current_task.pause()
            self.last_checkpoint = checkpoint
            self.is_paused = True
    
    def _resume_training(self):
        """Reprendre l'entraînement"""
        if not self.last_checkpoint or not os.path.exists(self.last_checkpoint):
            QMessageBox.warning(self, "Erreur", "Aucun checkpoint disponible pour reprendre.")
            return
        
        if self.is_training:
            QMessageBox.warning(self, "Erreur", "Un entraînement est déjà en cours.")
            return
        
        reply = QMessageBox.question(
            self,
            "Reprendre",
            f"Reprendre l'entraînement depuis:\n{self.last_checkpoint}",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._on_log(f"\n▶️ Reprise depuis: {self.last_checkpoint}")
            self._launch_training(self.last_checkpoint)
    
    def _stop_training(self):
        """Arrêter l'entraînement"""
        if not self.is_training or not self.current_task:
            return
        
        reply = QMessageBox.question(
            self,
            "Arrêter",
            "Êtes-vous sûr de vouloir arrêter l'entraînement?\n\n"
            "Le modèle actuel sera sauvegardé et vous pourrez le reprendre plus tard.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._on_log("\n⏹️ Arrêt demandé...")
            self.status_label.setText("⏹️ Arrêt en cours...")
            self.btn_stop.setEnabled(False)
            self.btn_pause.setEnabled(False)
            
            # Arrêter
            self.current_task.stop()
    
    def _on_log(self, message: str):
        """Recevoir un log"""
        self.log_text.append(message)
        
        # Auto-scroll
        if self.check_autoscroll.isChecked():
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)
    
    def _on_status(self, status: str):
        """Recevoir un statut"""
        self.status_label.setText(status)
    
    def _on_progress(self, current: int, total: int, metrics: dict):
        """Recevoir la progression"""
        self.label_epoch.setText(f"Epoch: {current}/{total}")
        
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            self.progress_bar.setFormat(f"{percent}% ({current}/{total})")
    
    def _on_training_finished(self, result):
        """Quand l'entraînement est terminé"""
        self.is_training = False
        self._reset_ui_state()
        
        if result.was_paused:
            self.status_label.setText("⏸️ Entraînement en pause")
            self.status_label.setStyleSheet("color: #FF9800; font-weight: bold;")
            self.btn_resume.setEnabled(True)
            
            if result.last_model:
                self.last_checkpoint = result.last_model
            
            QMessageBox.information(
                self,
                "Pause",
                f"Entraînement mis en pause.\n\n"
                f"Checkpoint: {result.last_model}\n\n"
                f"Cliquez sur 'Reprendre' pour continuer."
            )
            
        elif result.was_stopped:
            self.status_label.setText("⏹️ Entraînement arrêté")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            
            if result.last_model:
                self.last_checkpoint = result.last_model
                self.btn_resume.setEnabled(True)
            
            self._show_result_info(result, "Arrêté")
            
        elif result.success:
            self.status_label.setText("✅ Entraînement terminé avec succès!")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            self._show_result_info(result, "Succès")
            
            if result.save_dir:
                self.last_result_dir = result.save_dir
            
            QMessageBox.information(
                self,
                "Entraînement terminé",
                f"✅ Modèle entraîné avec succès!\n\n"
                f"Résultats: {result.save_dir}"
            )
        else:
            self.status_label.setText("❌ Échec de l'entraînement")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            
            self.result_text.setText(f"❌ Erreur: {result.error_message}")
            
            QMessageBox.warning(
                self,
                "Échec",
                f"L'entraînement a échoué:\n\n{result.error_message}"
            )
    
    def _show_result_info(self, result, status: str):
        """Afficher les informations de résultat"""
        result_text = f"""
{'='*50}
🎉 ENTRAÎNEMENT {status.upper()}
{'='*50}

📂 Dossier: {result.save_dir}
🏆 Meilleur modèle: {result.best_model or 'N/A'}
💾 Dernier checkpoint: {result.last_model or 'N/A'}

Pour utiliser le modèle:
────────────────────────────────────────────────
from ultralytics import YOLO
model = YOLO("{result.best_model or result.last_model}")
results = model.predict("votre_image.jpg")
────────────────────────────────────────────────
"""
        self.result_text.setText(result_text)
        
        if result.save_dir:
            self.last_result_dir = result.save_dir
    
    def _reset_ui_state(self):
        """Réinitialiser l'état de l'UI"""
        self.btn_start.setEnabled(self.data_path is not None)
        self.btn_pause.setEnabled(False)
        self.btn_stop.setEnabled(False)
    
    def _copy_log(self):
        """Copier les logs"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.log_text.toPlainText())
        
        self.status_label.setText("📋 Logs copiés!")
        QTimer.singleShot(2000, lambda: self.status_label.setText(""))
    
    def _open_results_dir(self):
        """Ouvrir le dossier des résultats"""
        if self.is_training:
            QMessageBox.information(
                self,
                "Entraînement en cours",
                "Un entraînement est en cours.\n"
                "Attendez la fin ou arrêtez-le pour accéder aux résultats."
            )
            return
        
        # Essayer d'ouvrir le dernier dossier de résultats
        if self.last_result_dir and os.path.exists(self.last_result_dir):
            self._open_folder(self.last_result_dir)
        else:
            # Proposer de parcourir
            folder = QFileDialog.getExistingDirectory(
                self,
                "Sélectionner le dossier des résultats",
                "runs/train"
            )
            if folder:
                self._open_folder(folder)
    
    def _open_folder(self, path: str):
        """Ouvrir un dossier dans l'explorateur"""
        import subprocess
        import sys
        
        if sys.platform == 'win32':
            subprocess.run(['explorer', path])
        elif sys.platform == 'darwin':
            subprocess.run(['open', path])
        else:
            subprocess.run(['xdg-open', path])
    
    def _show_existing_results(self):
        """Afficher les résultats d'entraînement existants"""
        if self.is_training:
            QMessageBox.information(
                self,
                "Entraînement en cours",
                "Un entraînement est en cours.\n"
                "Attendez la fin ou arrêtez-le pour accéder aux résultats existants."
            )
            return
        
        from tasks.yolo_training_task import YOLOTrainingTask
        
        results = YOLOTrainingTask.find_existing_results("runs/train")
        
        if not results:
            # Proposer de parcourir manuellement
            reply = QMessageBox.question(
                self,
                "Aucun résultat",
                "Aucun résultat trouvé dans 'runs/train'.\n\n"
                "Voulez-vous parcourir un autre dossier?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                folder = QFileDialog.getExistingDirectory(
                    self,
                    "Sélectionner le dossier contenant les résultats",
                    ""
                )
                if folder:
                    results = YOLOTrainingTask.find_existing_results(folder)
        
        if results:
            dialog = ExistingResultsDialog(results, self)
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_result:
                # Reprendre l'entraînement
                checkpoint = dialog.selected_result.get('last_path')
                if checkpoint:
                    self.last_checkpoint = checkpoint
                    self._resume_training()
        else:
            QMessageBox.information(
                self,
                "Aucun résultat",
                "Aucun résultat d'entraînement trouvé."
            )