"""
Level Splitter Widget - Interface pour la classification automatique par niveau Mario
"""

import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QGridLayout, QProgressBar, QLineEdit, QSpinBox, QCheckBox,
    QTextEdit, QComboBox, QSizePolicy, QDoubleSpinBox, QListWidget,
    QListWidgetItem, QDialog, QDialogButtonBox, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QColor


class ClassificationThread(QThread):
    """Thread pour la classification en arrière-plan"""
    
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, str)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(object)
    paused_signal = pyqtSignal()  # Signal quand mis en pause
    
    def __init__(self, task, preview_only=False, sample_size=10, resume_mode=False, parent=None):
        super().__init__(parent)
        self.task = task
        self.preview_only = preview_only
        self.sample_size = sample_size
        self.resume_mode = resume_mode
    
    def run(self):
        """Exécuter la classification"""
        self.task.log_callback = self._log
        self.task.progress_callback = self._progress
        self.task.status_callback = self._status
        
        if self.preview_only:
            results = self.task.preview_classification(self.sample_size)
            # Créer un résultat factice pour le preview
            from tasks.level_splitter_task import SplitterResult
            result = SplitterResult()
            result.success = True
            result.total_images = len(results)
            result.classified_images = sum(1 for r in results if r.status == 'classified')
            self.finished_signal.emit(result)
        else:
            result = self.task.execute(resume_from_state=self.resume_mode)
            
            # Vérifier si c'est une pause
            if self.task.is_paused:
                self.paused_signal.emit()
            
            self.finished_signal.emit(result)
    
    def _log(self, message: str):
        self.log_signal.emit(message)
    
    def _progress(self, current: int, total: int, filename: str):
        self.progress_signal.emit(current, total, filename)
    
    def _status(self, status: str):
        self.status_signal.emit(status)


class ModelSelectionDialog(QDialog):
    """Dialogue pour sélectionner un modèle YOLO"""
    
    def __init__(self, models: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Sélectionner un modèle YOLO")
        self.setMinimumSize(600, 400)
        self.selected_model = None
        
        layout = QVBoxLayout(self)
        
        # Info
        info = QLabel("Sélectionnez le modèle YOLO à utiliser pour la classification:")
        layout.addWidget(info)
        
        # Table des modèles
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Nom", "Type", "Date", "Chemin"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        
        self.table.setRowCount(len(models))
        for i, model in enumerate(models):
            self.table.setItem(i, 0, QTableWidgetItem(model['folder']))
            
            type_item = QTableWidgetItem(model['type'])
            if model['type'] == 'best':
                type_item.setForeground(QColor("#4CAF50"))
            self.table.setItem(i, 1, type_item)
            
            self.table.setItem(i, 2, QTableWidgetItem(model['date']))
            self.table.setItem(i, 3, QTableWidgetItem(model['path']))
        
        self.table.itemDoubleClicked.connect(self._on_double_click)
        layout.addWidget(self.table)
        
        self.models = models
        
        # Boutons
        btn_layout = QHBoxLayout()
        
        btn_browse = QPushButton("📂 Parcourir...")
        btn_browse.clicked.connect(self._browse)
        btn_layout.addWidget(btn_browse)
        
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("Annuler")
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        
        btn_select = QPushButton("✅ Sélectionner")
        btn_select.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        btn_select.clicked.connect(self._select)
        btn_layout.addWidget(btn_select)
        
        layout.addLayout(btn_layout)
    
    def _on_double_click(self, item):
        self._select()
    
    def _select(self):
        row = self.table.currentRow()
        if row >= 0:
            self.selected_model = self.models[row]['path']
            self.accept()
    
    def _browse(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un modèle YOLO",
            "runs/train",
            "PyTorch Model (*.pt)"
        )
        if file_path:
            self.selected_model = file_path
            self.accept()


class LevelSplitterWidget(QWidget):
    """
    Widget pour la classification automatique des images par niveau Mario
    """
    
    task_requested = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.model_path = None
        self.source_dir = None
        self.classification_thread = None
        self.current_task = None
        self.is_running = False
        self.is_paused = False  # État de pause
        
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
        content_layout.addWidget(self._create_banner())
        
        # 2. Sélection modèle
        content_layout.addWidget(self._create_model_group())
        
        # 3. Sélection source
        content_layout.addWidget(self._create_source_group())
        
        # 4. Configuration
        content_layout.addWidget(self._create_config_group())
        
        # 5. Logs et résultats
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
                    stop:0 #7B1FA2, stop:1 #512DA8);
                border-radius: 8px;
                padding: 15px;
            }
            QLabel { color: white; }
        """)
        
        layout = QVBoxLayout(banner)
        
        title = QLabel("🎮 Classification par Niveau Mario")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Utilisez votre modèle YOLO entraîné pour classifier automatiquement\n"
            "les images par niveau détecté (1-1, 1-2, 2-1, etc.).\n"
            "Les images seront organisées dans des dossiers par niveau."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #E1BEE7; font-size: 11px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_model_group(self):
        """Créer le groupe sélection modèle"""
        group = QGroupBox("🤖 Modèle YOLO")
        group.setStyleSheet(self._get_group_style("#4CAF50"))
        
        layout = QGridLayout()
        
        layout.addWidget(QLabel("Modèle:"), 0, 0)
        
        self.edit_model = QLineEdit()
        self.edit_model.setPlaceholderText("Chemin vers best.pt ou last.pt...")
        self.edit_model.setReadOnly(True)
        layout.addWidget(self.edit_model, 0, 1)
        
        btn_browse = QPushButton("📂 Parcourir")
        btn_browse.clicked.connect(self._browse_model)
        layout.addWidget(btn_browse, 0, 2)
        
        btn_find = QPushButton("🔍 Trouver")
        btn_find.setToolTip("Rechercher les modèles dans runs/train")
        btn_find.clicked.connect(self._find_models)
        layout.addWidget(btn_find, 0, 3)
        
        self.label_model_info = QLabel("")
        self.label_model_info.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.label_model_info, 1, 0, 1, 4)
        
        group.setLayout(layout)
        return group
    
    def _create_source_group(self):
        """Créer le groupe sélection source"""
        group = QGroupBox("📁 Dossier Source")
        group.setStyleSheet(self._get_group_style("#2196F3"))
        
        layout = QGridLayout()
        
        layout.addWidget(QLabel("Dossier:"), 0, 0)
        
        self.edit_source = QLineEdit()
        self.edit_source.setPlaceholderText("Dossier contenant les images à classifier...")
        self.edit_source.textChanged.connect(self._on_source_changed)
        layout.addWidget(self.edit_source, 0, 1)
        
        btn_browse = QPushButton("📂 Parcourir")
        btn_browse.clicked.connect(self._browse_source)
        layout.addWidget(btn_browse, 0, 2)
        
        self.label_source_info = QLabel("")
        self.label_source_info.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.label_source_info, 1, 0, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_config_group(self):
        """Créer le groupe configuration"""
        group = QGroupBox("⚙️ Configuration")
        group.setStyleSheet(self._get_group_style("#FF9800"))
        
        layout = QGridLayout()
        
        # Seuil de confiance
        layout.addWidget(QLabel("Seuil de confiance:"), 0, 0)
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0.1, 1.0)
        self.spin_threshold.setSingleStep(0.05)
        self.spin_threshold.setValue(0.5)
        self.spin_threshold.setToolTip("Confiance minimum pour classifier (0.5 = 50%)")
        layout.addWidget(self.spin_threshold, 0, 1)
        
        # Dossier de sortie
        layout.addWidget(QLabel("Dossier sortie:"), 0, 2)
        self.edit_output = QLineEdit("classified_levels")
        layout.addWidget(self.edit_output, 0, 3)
        
        # Options
        layout.addWidget(QLabel("Options:"), 1, 0)
        
        options_layout = QHBoxLayout()
        
        self.check_save_unknown = QCheckBox("Sauvegarder les non-classifiées")
        self.check_save_unknown.setChecked(True)
        self.check_save_unknown.setToolTip("Sauvegarder les images non détectées dans 'unknown/'")
        options_layout.addWidget(self.check_save_unknown)
        
        self.check_copy = QCheckBox("Copier (au lieu de déplacer)")
        self.check_copy.setChecked(True)
        self.check_copy.setToolTip("Copier les fichiers au lieu de les déplacer")
        options_layout.addWidget(self.check_copy)
        
        options_layout.addStretch()
        
        layout.addLayout(options_layout, 1, 1, 1, 3)
        
        # Taille échantillon test
        layout.addWidget(QLabel("Taille test:"), 2, 0)
        self.spin_sample = QSpinBox()
        self.spin_sample.setRange(5, 100)
        self.spin_sample.setValue(10)
        self.spin_sample.setToolTip("Nombre d'images pour le test rapide")
        layout.addWidget(self.spin_sample, 2, 1)
        
        group.setLayout(layout)
        return group
    
    def _create_output_group(self):
        """Créer le groupe logs/résultats"""
        group = QGroupBox("📋 Logs & Résultats")
        group.setStyleSheet(self._get_group_style("#9C27B0"))
        
        layout = QVBoxLayout()
        
        # Progress
        progress_layout = QHBoxLayout()
        
        self.label_progress = QLabel("En attente...")
        self.label_progress.setStyleSheet("font-weight: bold;")
        progress_layout.addWidget(self.label_progress)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        
        # Logs
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
        layout.addWidget(self.log_text)
        
        # Boutons logs
        log_btn_layout = QHBoxLayout()
        
        btn_clear = QPushButton("🗑️ Effacer")
        btn_clear.clicked.connect(self.log_text.clear)
        log_btn_layout.addWidget(btn_clear)
        
        btn_copy = QPushButton("📋 Copier")
        btn_copy.clicked.connect(self._copy_log)
        log_btn_layout.addWidget(btn_copy)
        
        log_btn_layout.addStretch()
        
        self.btn_open_output = QPushButton("📂 Ouvrir dossier résultats")
        self.btn_open_output.clicked.connect(self._open_output_dir)
        self.btn_open_output.setEnabled(False)
        log_btn_layout.addWidget(self.btn_open_output)
        
        self.btn_report = QPushButton("📊 Voir rapport")
        self.btn_report.clicked.connect(self._view_report)
        self.btn_report.setEnabled(False)
        log_btn_layout.addWidget(self.btn_report)
        
        layout.addLayout(log_btn_layout)
        
        # Status
        self.status_label = QLabel("Configurez le modèle et le dossier source")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)
        
        group.setLayout(layout)
        return group
    
    def _create_action_buttons(self):
        """Créer les boutons d'action"""
        layout = QHBoxLayout()
        
        self.btn_test = QPushButton("🔍 Test Rapide")
        self.btn_test.setStyleSheet("""
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
        self.btn_test.clicked.connect(self._run_test)
        self.btn_test.setEnabled(False)
        self.btn_test.setToolTip("Tester la classification sur un échantillon")
        layout.addWidget(self.btn_test)
        
        self.btn_start = QPushButton("🚀 Lancer la Classification")
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
        self.btn_start.clicked.connect(self._start_classification)
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
        self.btn_pause.clicked.connect(self._pause_classification)
        self.btn_pause.setEnabled(False)
        self.btn_pause.setToolTip("Mettre en pause la classification")
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
        self.btn_resume.clicked.connect(self._resume_classification)
        self.btn_resume.setEnabled(False)
        self.btn_resume.setToolTip("Reprendre la classification")
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
        self.btn_stop.clicked.connect(self._stop_classification)
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
    
    def _browse_model(self):
        """Parcourir pour sélectionner un modèle"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un modèle YOLO",
            "runs/train",
            "PyTorch Model (*.pt)"
        )
        if file_path:
            self._set_model(file_path)
    
    def _find_models(self):
        """Rechercher les modèles disponibles"""
        from tasks.level_splitter_task import LevelSplitterTask
        
        models = LevelSplitterTask.find_yolo_models("runs/train")
        
        if not models:
            QMessageBox.information(
                self,
                "Aucun modèle",
                "Aucun modèle trouvé dans 'runs/train/'.\n\n"
                "Entraînez d'abord un modèle YOLO dans l'onglet YOLO Training,\n"
                "ou utilisez 'Parcourir' pour sélectionner un modèle existant."
            )
            return
        
        dialog = ModelSelectionDialog(models, self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_model:
            self._set_model(dialog.selected_model)
    
    def _set_model(self, model_path: str):
        """Définir le modèle sélectionné"""
        self.model_path = model_path
        self.edit_model.setText(model_path)
        
        # Analyser le modèle
        try:
            from ultralytics import YOLO
            model = YOLO(model_path)
            num_classes = len(model.names)
            class_names = list(model.names.values())[:5]
            
            info = f"✅ {num_classes} classes: {', '.join(str(c) for c in class_names)}"
            if num_classes > 5:
                info += "..."
            
            self.label_model_info.setText(info)
            self.label_model_info.setStyleSheet("color: #4CAF50; font-size: 10px;")
            
            # Libérer le modèle
            del model
            
        except Exception as e:
            self.label_model_info.setText(f"⚠️ Erreur: {e}")
            self.label_model_info.setStyleSheet("color: #f44336; font-size: 10px;")
        
        self._check_ready()
    
    def _browse_source(self):
        """Parcourir pour sélectionner le dossier source"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner le dossier d'images",
            ""
        )
        if folder:
            self.edit_source.setText(folder)
    
    def _on_source_changed(self, path: str):
        """Quand le dossier source change"""
        if os.path.exists(path) and os.path.isdir(path):
            self.source_dir = path
            
            # Compter les images
            extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
            count = sum(1 for f in os.listdir(path) 
                       if os.path.splitext(f)[1].lower() in extensions)
            
            self.label_source_info.setText(f"📷 {count:,} images trouvées")
            self.label_source_info.setStyleSheet("color: #4CAF50; font-size: 10px;")
        else:
            self.source_dir = None
            self.label_source_info.setText("⚠️ Dossier invalide")
            self.label_source_info.setStyleSheet("color: #f44336; font-size: 10px;")
        
        self._check_ready()
    
    def _check_ready(self):
        """Vérifier si prêt à lancer"""
        ready = self.model_path is not None and self.source_dir is not None
        self.btn_test.setEnabled(ready)
        self.btn_start.setEnabled(ready)
    
    def _run_test(self):
        """Lancer le test rapide"""
        self._launch_classification(preview_only=True)
    
    def _start_classification(self):
        """Lancer la classification complète"""
        # Confirmation
        extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        count = sum(1 for f in os.listdir(self.source_dir) 
                   if os.path.splitext(f)[1].lower() in extensions)
        
        reply = QMessageBox.question(
            self,
            "Lancer la classification",
            f"Classifier {count:,} images?\n\n"
            f"Modèle: {os.path.basename(self.model_path)}\n"
            f"Seuil: {self.spin_threshold.value()}\n"
            f"Sortie: {self.edit_output.text()}/\n\n"
            f"{'Copier' if self.check_copy.isChecked() else 'Déplacer'} les fichiers.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._launch_classification(preview_only=False)
    
    def _launch_classification(self, preview_only: bool = False, resume_mode: bool = False):
        """Lancer la classification"""
        try:
            from tasks.level_splitter_task import LevelSplitterTask, SplitterConfig
            
            # En mode reprise, réutiliser la tâche existante
            if resume_mode and self.current_task and self.current_task.resume():
                task = self.current_task
                resume_info = task.get_resume_info()
                self._on_log(f"\n▶️ Reprise de la classification...")
                self._on_log(f"📍 Déjà traité: {resume_info['processed']:,} images")
                self._on_log(f"📊 Restant: {resume_info['remaining']:,} images")
            else:
                config = SplitterConfig(
                    model_path=self.model_path,
                    source_dir=self.source_dir,
                    output_dir=self.edit_output.text(),
                    confidence_threshold=self.spin_threshold.value(),
                    save_unknown=self.check_save_unknown.isChecked(),
                    copy_files=self.check_copy.isChecked()
                )
                
                task = LevelSplitterTask()
                task.configure(config)
                self.current_task = task
            
            # Thread
            self.classification_thread = ClassificationThread(
                task,
                preview_only=preview_only,
                sample_size=self.spin_sample.value(),
                resume_mode=resume_mode,
                parent=self
            )
            self.classification_thread.log_signal.connect(self._on_log)
            self.classification_thread.progress_signal.connect(self._on_progress)
            self.classification_thread.status_signal.connect(self._on_status)
            self.classification_thread.finished_signal.connect(self._on_finished)
            self.classification_thread.paused_signal.connect(self._on_paused)
            
            # UI
            self.is_running = True
            self.is_paused = False
            self.btn_test.setEnabled(False)
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_resume.setEnabled(False)
            self.btn_stop.setEnabled(True)
            
            if not resume_mode:
                self.log_text.clear()
                self.progress_bar.setValue(0)
            
            if preview_only:
                self.status_label.setText("🔍 Test en cours...")
            elif resume_mode:
                self.status_label.setText("▶️ Reprise de la classification...")
            else:
                self.status_label.setText("🚀 Classification en cours...")
            
            self.classification_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))
    
    def _stop_classification(self):
        """Arrêter la classification avec confirmation"""
        if self.current_task:
            reply = QMessageBox.question(
                self,
                "Confirmer l'arrêt",
                "⚠️ Voulez-vous vraiment arrêter la classification?\n\n"
                "Cette action est définitive et vous devrez recommencer depuis le début.\n\n"
                "💡 Conseil: Utilisez 'Pause' si vous souhaitez reprendre plus tard.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No  # Bouton par défaut = Non
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.current_task.stop()
                self.current_task.clear_resume_state()  # Effacer l'état de reprise
                self.btn_stop.setEnabled(False)
                self.btn_pause.setEnabled(False)
                self._on_log("⏹️ Classification arrêtée par l'utilisateur")
            # Si Non, on ne fait rien et la classification continue
    
    def _pause_classification(self):
        """Mettre en pause la classification"""
        if self.current_task:
            self.current_task.pause()
            self.btn_pause.setEnabled(False)
            self.status_label.setText("⏸️ Mise en pause...")
    
    def _resume_classification(self):
        """Reprendre la classification"""
        if self.current_task and self.current_task.resume():
            self._launch_classification(preview_only=False, resume_mode=True)
        else:
            QMessageBox.warning(
                self,
                "Impossible de reprendre",
                "Aucune classification en pause à reprendre."
            )
    
    def _on_paused(self):
        """Quand la classification est mise en pause"""
        self.is_paused = True
        self.is_running = False
        
        self.btn_test.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(True)
        self.btn_stop.setEnabled(False)
        
        self.status_label.setText("⏸️ En pause")
        self.status_label.setStyleSheet("color: #FF9800; font-weight: bold;")
        
        if self.current_task:
            resume_info = self.current_task.get_resume_info()
            QMessageBox.information(
                self,
                "Classification en pause",
                f"⏸️ Classification mise en pause\n\n"
                f"📊 Images traitées: {resume_info['processed']:,}\n"
                f"📊 Images restantes: {resume_info['remaining']:,}\n\n"
                f"Cliquez sur '▶️ Reprendre' pour continuer."
            )
    
    def _on_log(self, message: str):
        """Recevoir un log"""
        self.log_text.append(message)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
    
    def _on_progress(self, current: int, total: int, filename: str):
        """Recevoir la progression"""
        if total > 0:
            percent = int((current / total) * 100)
            self.progress_bar.setValue(percent)
            self.label_progress.setText(f"{current:,}/{total:,} ({percent}%)")
    
    def _on_status(self, status: str):
        """Recevoir le statut"""
        self.status_label.setText(status)
    
    def _on_finished(self, result):
        """Quand la classification est terminée"""
        self.is_running = False
        
        # Si c'était une pause, ne pas réinitialiser tout
        if self.is_paused:
            return
        
        self.btn_test.setEnabled(True)
        self.btn_start.setEnabled(True)
        self.btn_pause.setEnabled(False)
        self.btn_resume.setEnabled(False)
        self.btn_stop.setEnabled(False)
        
        # Nettoyer l'état de reprise si terminé avec succès
        if result.success and result.report_path and self.current_task:
            self.current_task.clear_resume_state()
        
        if result.success:
            self.status_label.setText("✅ Terminé!")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            
            if result.output_dir:
                self.btn_open_output.setEnabled(True)
                self.last_output_dir = result.output_dir
            
            if result.report_path:
                self.btn_report.setEnabled(True)
                self.last_report_path = result.report_path
            
            if result.total_images > 0 and result.classified_images > 0:
                QMessageBox.information(
                    self,
                    "Classification terminée",
                    f"✅ Classification réussie!\n\n"
                    f"📊 Images traitées: {result.total_images:,}\n"
                    f"✅ Classifiées: {result.classified_images:,} ({result.classification_rate}%)\n"
                    f"🎯 Niveaux détectés: {result.levels_detected}"
                )
        else:
            self.status_label.setText("❌ Erreur")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            
            if result.error_message:
                QMessageBox.warning(self, "Erreur", result.error_message)
    
    def _copy_log(self):
        """Copier les logs"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.log_text.toPlainText())
        self.status_label.setText("📋 Logs copiés!")
        QTimer.singleShot(2000, lambda: self.status_label.setText(""))
    
    def _open_output_dir(self):
        """Ouvrir le dossier de sortie"""
        if hasattr(self, 'last_output_dir') and os.path.exists(self.last_output_dir):
            import subprocess
            import sys
            if sys.platform == 'win32':
                subprocess.run(['explorer', self.last_output_dir])
            elif sys.platform == 'darwin':
                subprocess.run(['open', self.last_output_dir])
            else:
                subprocess.run(['xdg-open', self.last_output_dir])
    
    def _view_report(self):
        """Afficher le rapport"""
        if hasattr(self, 'last_report_path') and os.path.exists(self.last_report_path):
            try:
                with open(self.last_report_path, 'r', encoding='utf-8') as f:
                    report = json.load(f)
                
                # Créer un dialogue avec le rapport
                dialog = QDialog(self)
                dialog.setWindowTitle("Rapport de Classification")
                dialog.setMinimumSize(600, 500)
                
                layout = QVBoxLayout(dialog)
                
                text = QTextEdit()
                text.setReadOnly(True)
                text.setFont(QFont("Consolas", 10))
                text.setText(json.dumps(report, indent=2, ensure_ascii=False))
                layout.addWidget(text)
                
                btn_close = QPushButton("Fermer")
                btn_close.clicked.connect(dialog.close)
                layout.addWidget(btn_close)
                
                dialog.exec()
                
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Impossible de lire le rapport: {e}")