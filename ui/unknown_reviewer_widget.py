"""
Unknown Reviewer Widget - Interface pour la révision manuelle des images non classifiées
"""

import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QGridLayout, QProgressBar, QLineEdit, QSpinBox, QCheckBox,
    QTextEdit, QComboBox, QSizePolicy, QSlider, QListWidget,
    QListWidgetItem, QDialog, QDialogButtonBox, QSplitter,
    QRadioButton, QButtonGroup
)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer
from PyQt6.QtGui import QFont, QPixmap, QImage, QTextCursor, QKeySequence, QShortcut


class UnknownReviewerWidget(QWidget):
    """
    Widget pour la révision manuelle des images non classifiées
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.task = None
        self.current_pixmap = None
        
        self._create_ui()
        self._setup_shortcuts()
    
    def _create_ui(self):
        """Créer l'interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Panneau gauche (configuration + actions)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 5, 0)
        
        left_layout.addWidget(self._create_banner())
        left_layout.addWidget(self._create_config_group())
        left_layout.addWidget(self._create_classification_group())
        left_layout.addWidget(self._create_bulk_actions_group())
        left_layout.addWidget(self._create_stats_group())
        left_layout.addStretch()
        
        splitter.addWidget(left_panel)
        
        # Panneau droit (visualisation)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 0, 0, 0)
        
        right_layout.addWidget(self._create_viewer_group())
        right_layout.addWidget(self._create_navigation_group())
        right_layout.addWidget(self._create_logs_group())
        
        splitter.addWidget(right_panel)
        
        # Proportions
        splitter.setSizes([350, 650])
        
        layout.addWidget(splitter)
    
    def _create_banner(self):
        """Créer la bannière"""
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #E65100, stop:1 #F57C00);
                border-radius: 8px;
                padding: 10px;
            }
            QLabel { color: white; }
        """)
        
        layout = QVBoxLayout(banner)
        
        title = QLabel("🔍 Révision Images Unknown")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Révisez manuellement les images non classifiées.\n"
            "Classez-les dans le bon niveau ou supprimez-les."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #FFE0B2; font-size: 10px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_config_group(self):
        """Créer le groupe configuration"""
        group = QGroupBox("📁 Configuration")
        group.setStyleSheet(self._get_group_style("#2196F3"))
        
        layout = QGridLayout()
        
        # Dossier unknown
        layout.addWidget(QLabel("Dossier unknown:"), 0, 0)
        self.edit_unknown = QLineEdit()
        self.edit_unknown.setPlaceholderText("classified_levels/unknown")
        layout.addWidget(self.edit_unknown, 0, 1)
        
        btn_browse_unknown = QPushButton("📂")
        btn_browse_unknown.setFixedWidth(40)
        btn_browse_unknown.clicked.connect(self._browse_unknown)
        layout.addWidget(btn_browse_unknown, 0, 2)
        
        # Dossier base niveaux
        layout.addWidget(QLabel("Dossier niveaux:"), 1, 0)
        self.edit_levels = QLineEdit()
        self.edit_levels.setPlaceholderText("classified_levels")
        layout.addWidget(self.edit_levels, 1, 1)
        
        btn_browse_levels = QPushButton("📂")
        btn_browse_levels.setFixedWidth(40)
        btn_browse_levels.clicked.connect(self._browse_levels)
        layout.addWidget(btn_browse_levels, 1, 2)
        
        # Bouton charger
        btn_layout = QHBoxLayout()
        
        self.btn_load = QPushButton("🔄 Charger")
        self.btn_load.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        self.btn_load.clicked.connect(self._load_images)
        btn_layout.addWidget(self.btn_load)
        
        self.btn_resume = QPushButton("↩️ Reprendre")
        self.btn_resume.setToolTip("Reprendre depuis la dernière session")
        self.btn_resume.clicked.connect(self._resume_session)
        self.btn_resume.setEnabled(False)
        btn_layout.addWidget(self.btn_resume)
        
        layout.addLayout(btn_layout, 2, 0, 1, 3)
        
        # Info
        self.label_info = QLabel("")
        self.label_info.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.label_info, 3, 0, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_classification_group(self):
        """Créer le groupe classification"""
        group = QGroupBox("🎯 Classification Manuelle")
        group.setStyleSheet(self._get_group_style("#4CAF50"))
        
        layout = QVBoxLayout()
        
        # Liste des niveaux
        layout.addWidget(QLabel("Sélectionner le niveau:"))
        
        self.combo_levels = QComboBox()
        self.combo_levels.setMinimumHeight(35)
        self.combo_levels.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.combo_levels)
        
        # Boutons d'action
        btn_layout = QGridLayout()
        
        self.btn_move = QPushButton("✅ Classer dans ce niveau")
        self.btn_move.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #9E9E9E; }
        """)
        self.btn_move.clicked.connect(self._move_to_level)
        self.btn_move.setEnabled(False)
        btn_layout.addWidget(self.btn_move, 0, 0, 1, 2)
        
        self.btn_delete = QPushButton("🗑️ Supprimer")
        self.btn_delete.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #d32f2f; }
            QPushButton:disabled { background-color: #9E9E9E; }
        """)
        self.btn_delete.clicked.connect(self._delete_current)
        self.btn_delete.setEnabled(False)
        btn_layout.addWidget(self.btn_delete, 1, 0)
        
        self.btn_skip = QPushButton("⏭️ Ignorer")
        self.btn_skip.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 5px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #F57C00; }
            QPushButton:disabled { background-color: #9E9E9E; }
        """)
        self.btn_skip.clicked.connect(self._skip_current)
        self.btn_skip.setEnabled(False)
        btn_layout.addWidget(self.btn_skip, 1, 1)
        
        layout.addLayout(btn_layout)
        
        # Raccourcis clavier info
        shortcuts_label = QLabel(
            "⌨️ Raccourcis: Entrée=Classer, Suppr=Supprimer, Espace=Ignorer, ←→=Navigation"
        )
        shortcuts_label.setStyleSheet("color: #666; font-size: 9px;")
        shortcuts_label.setWordWrap(True)
        layout.addWidget(shortcuts_label)
        
        group.setLayout(layout)
        return group
    
    def _create_bulk_actions_group(self):
        """Créer le groupe actions en masse"""
        group = QGroupBox("💥 Actions en Masse")
        group.setStyleSheet(self._get_group_style("#9C27B0"))
        
        layout = QVBoxLayout()
        
        # Suppression restantes
        self.btn_delete_all = QPushButton("🗑️ Supprimer toutes les restantes")
        self.btn_delete_all.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                border: none;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #7B1FA2; }
            QPushButton:disabled { background-color: #9E9E9E; }
        """)
        self.btn_delete_all.clicked.connect(self._delete_all_remaining)
        self.btn_delete_all.setEnabled(False)
        layout.addWidget(self.btn_delete_all)
        
        # Suppression par motif
        pattern_layout = QHBoxLayout()
        
        self.edit_pattern = QLineEdit()
        self.edit_pattern.setPlaceholderText("Motif (ex: frame_00)")
        pattern_layout.addWidget(self.edit_pattern)
        
        self.btn_delete_pattern = QPushButton("🔍 Supprimer par motif")
        self.btn_delete_pattern.clicked.connect(self._delete_by_pattern)
        self.btn_delete_pattern.setEnabled(False)
        pattern_layout.addWidget(self.btn_delete_pattern)
        
        layout.addLayout(pattern_layout)
        
        # Options
        self.check_backup = QCheckBox("Créer sauvegarde avant suppression")
        self.check_backup.setChecked(True)
        layout.addWidget(self.check_backup)
        
        group.setLayout(layout)
        return group
    
    def _create_stats_group(self):
        """Créer le groupe statistiques"""
        group = QGroupBox("📊 Statistiques")
        group.setStyleSheet(self._get_group_style("#607D8B"))
        
        layout = QGridLayout()
        
        self.label_stat_total = QLabel("Total: -")
        layout.addWidget(self.label_stat_total, 0, 0)
        
        self.label_stat_remaining = QLabel("Restantes: -")
        layout.addWidget(self.label_stat_remaining, 0, 1)
        
        self.label_stat_moved = QLabel("Déplacées: 0")
        layout.addWidget(self.label_stat_moved, 1, 0)
        
        self.label_stat_deleted = QLabel("Supprimées: 0")
        layout.addWidget(self.label_stat_deleted, 1, 1)
        
        # Bouton sauvegarder
        btn_layout = QHBoxLayout()
        
        self.btn_save = QPushButton("💾 Sauvegarder progrès")
        self.btn_save.clicked.connect(self._save_progress)
        self.btn_save.setEnabled(False)
        btn_layout.addWidget(self.btn_save)
        
        self.btn_summary = QPushButton("📊 Résumé")
        self.btn_summary.clicked.connect(self._show_summary)
        self.btn_summary.setEnabled(False)
        btn_layout.addWidget(self.btn_summary)
        
        layout.addLayout(btn_layout, 2, 0, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def _create_viewer_group(self):
        """Créer le groupe visualisation"""
        group = QGroupBox("🖼️ Image")
        group.setStyleSheet(self._get_group_style("#009688"))
        
        layout = QVBoxLayout()
        
        # Info image
        self.label_image_info = QLabel("Aucune image chargée")
        self.label_image_info.setStyleSheet("font-weight: bold; color: #009688;")
        layout.addWidget(self.label_image_info)
        
        # Zone d'affichage image
        self.image_label = QLabel()
        self.image_label.setMinimumSize(400, 300)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setStyleSheet("""
            QLabel {
                background-color: #1E1E1E;
                border: 2px solid #333;
                border-radius: 5px;
            }
        """)
        self.image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.image_label)
        
        # Détails
        self.label_details = QLabel("")
        self.label_details.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.label_details)
        
        group.setLayout(layout)
        return group
    
    def _create_navigation_group(self):
        """Créer le groupe navigation"""
        group = QGroupBox("🧭 Navigation")
        group.setStyleSheet(self._get_group_style("#FF5722"))
        
        layout = QVBoxLayout()
        
        # Barre de navigation
        nav_layout = QHBoxLayout()
        
        self.btn_prev = QPushButton("◀ Précédent")
        self.btn_prev.clicked.connect(self._go_previous)
        self.btn_prev.setEnabled(False)
        nav_layout.addWidget(self.btn_prev)
        
        self.label_position = QLabel("0 / 0")
        self.label_position.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label_position.setStyleSheet("font-weight: bold; font-size: 14px;")
        nav_layout.addWidget(self.label_position)
        
        self.btn_next = QPushButton("Suivant ▶")
        self.btn_next.clicked.connect(self._go_next)
        self.btn_next.setEnabled(False)
        nav_layout.addWidget(self.btn_next)
        
        layout.addLayout(nav_layout)
        
        # Slider
        slider_layout = QHBoxLayout()
        
        self.slider_position = QSlider(Qt.Orientation.Horizontal)
        self.slider_position.setMinimum(0)
        self.slider_position.setMaximum(0)
        self.slider_position.valueChanged.connect(self._on_slider_changed)
        slider_layout.addWidget(self.slider_position)
        
        self.spin_goto = QSpinBox()
        self.spin_goto.setMinimum(1)
        self.spin_goto.setMaximum(1)
        self.spin_goto.setFixedWidth(70)
        slider_layout.addWidget(self.spin_goto)
        
        btn_goto = QPushButton("Aller")
        btn_goto.clicked.connect(self._go_to_position)
        btn_goto.setFixedWidth(50)
        slider_layout.addWidget(btn_goto)
        
        layout.addLayout(slider_layout)
        
        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        layout.addWidget(self.progress_bar)
        
        group.setLayout(layout)
        return group
    
    def _create_logs_group(self):
        """Créer le groupe logs"""
        group = QGroupBox("📋 Logs")
        group.setStyleSheet(self._get_group_style("#795548"))
        
        layout = QVBoxLayout()
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setFont(QFont("Consolas", 9))
        self.log_text.setMaximumHeight(120)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #333;
            }
        """)
        layout.addWidget(self.log_text)
        
        group.setLayout(layout)
        return group
    
    def _setup_shortcuts(self):
        """Configurer les raccourcis clavier"""
        # Entrée = Classer
        shortcut_enter = QShortcut(QKeySequence(Qt.Key.Key_Return), self)
        shortcut_enter.activated.connect(self._move_to_level)
        
        # Suppr = Supprimer
        shortcut_delete = QShortcut(QKeySequence(Qt.Key.Key_Delete), self)
        shortcut_delete.activated.connect(self._delete_current)
        
        # Espace = Ignorer
        shortcut_space = QShortcut(QKeySequence(Qt.Key.Key_Space), self)
        shortcut_space.activated.connect(self._skip_current)
        
        # Flèche gauche = Précédent
        shortcut_left = QShortcut(QKeySequence(Qt.Key.Key_Left), self)
        shortcut_left.activated.connect(self._go_previous)
        
        # Flèche droite = Suivant
        shortcut_right = QShortcut(QKeySequence(Qt.Key.Key_Right), self)
        shortcut_right.activated.connect(self._go_next)
    
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
    
    def _log(self, message: str):
        """Ajouter un message au log"""
        self.log_text.append(message)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
    
    def _browse_unknown(self):
        """Parcourir pour sélectionner le dossier unknown"""
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier unknown")
        if folder:
            self.edit_unknown.setText(folder)
            
            # Auto-détecter le dossier parent comme base
            parent = str(Path(folder).parent)
            self.edit_levels.setText(parent)
    
    def _browse_levels(self):
        """Parcourir pour sélectionner le dossier de base des niveaux"""
        folder = QFileDialog.getExistingDirectory(self, "Sélectionner le dossier des niveaux")
        if folder:
            self.edit_levels.setText(folder)
    
    def _load_images(self):
        """Charger les images unknown"""
        unknown_dir = self.edit_unknown.text().strip()
        levels_dir = self.edit_levels.text().strip()
        
        if not unknown_dir or not os.path.exists(unknown_dir):
            QMessageBox.warning(self, "Erreur", "Dossier unknown invalide")
            return
        
        if not levels_dir or not os.path.exists(levels_dir):
            QMessageBox.warning(self, "Erreur", "Dossier niveaux invalide")
            return
        
        # Créer la tâche
        from tasks.unknown_reviewer_task import UnknownReviewerTask, ReviewerConfig
        
        config = ReviewerConfig(
            unknown_dir=unknown_dir,
            levels_base_dir=levels_dir
        )
        
        self.task = UnknownReviewerTask()
        self.task.configure(config, log_callback=self._log)
        
        # Mettre à jour l'interface
        self._update_levels_combo()
        self._update_ui_state()
        self._display_current_image()
        
        # Vérifier s'il y a un progrès à reprendre
        if self.task.has_saved_progress():
            self.btn_resume.setEnabled(True)
            self._log("💡 Session précédente détectée - Cliquez sur 'Reprendre' pour continuer")
        
        self._log(f"✅ {len(self.task.unknown_images)} images chargées")
        self._log(f"🎯 {len(self.task.available_levels)} niveaux disponibles")
    
    def _resume_session(self):
        """Reprendre la session précédente"""
        if self.task and self.task.load_progress():
            self._display_current_image()
            self._update_stats_display()
            self._log("↩️ Session reprise avec succès")
    
    def _update_levels_combo(self):
        """Mettre à jour la liste des niveaux"""
        self.combo_levels.clear()
        
        if self.task:
            for level in self.task.available_levels:
                self.combo_levels.addItem(f"level_{level}", level)
    
    def _update_ui_state(self):
        """Mettre à jour l'état des boutons"""
        has_task = self.task is not None
        has_images = has_task and len(self.task.unknown_images) > 0
        
        self.btn_move.setEnabled(has_images)
        self.btn_delete.setEnabled(has_images)
        self.btn_skip.setEnabled(has_images)
        self.btn_delete_all.setEnabled(has_images)
        self.btn_delete_pattern.setEnabled(has_images)
        self.btn_save.setEnabled(has_task)
        self.btn_summary.setEnabled(has_task)
        self.btn_prev.setEnabled(has_images)
        self.btn_next.setEnabled(has_images)
        
        if has_images:
            self.slider_position.setMaximum(len(self.task.unknown_images) - 1)
            self.spin_goto.setMaximum(len(self.task.unknown_images))
        
        self._update_stats_display()
    
    def _update_stats_display(self):
        """Mettre à jour l'affichage des statistiques"""
        if not self.task:
            return
        
        total = self.task.stats.total_images
        remaining = len(self.task.unknown_images)
        moved = self.task.stats.moved
        deleted = self.task.stats.deleted + self.task.stats.bulk_deleted
        
        self.label_stat_total.setText(f"Total: {total}")
        self.label_stat_remaining.setText(f"Restantes: {remaining}")
        self.label_stat_moved.setText(f"Déplacées: {moved}")
        self.label_stat_deleted.setText(f"Supprimées: {deleted}")
        
        # Progress bar
        if total > 0:
            progress = int(((total - remaining) / total) * 100)
            self.progress_bar.setValue(progress)
    
    def _display_current_image(self):
        """Afficher l'image courante"""
        if not self.task or len(self.task.unknown_images) == 0:
            self.image_label.clear()
            self.image_label.setText("Aucune image")
            self.label_image_info.setText("Aucune image à afficher")
            self.label_details.setText("")
            self.label_position.setText("0 / 0")
            return
        
        # Position
        pos = self.task.current_index + 1
        total = len(self.task.unknown_images)
        self.label_position.setText(f"{pos} / {total}")
        self.slider_position.blockSignals(True)
        self.slider_position.setValue(self.task.current_index)
        self.slider_position.blockSignals(False)
        self.spin_goto.setValue(pos)
        
        # Info image
        info = self.task.get_image_info()
        if info:
            self.label_image_info.setText(f"📄 {info.filename}")
            
            details = f"Taille: {info.size_bytes / 1024:.1f} KB"
            if info.width > 0:
                details += f" | Dimensions: {info.width}x{info.height}"
            if info.frame_number:
                details += f" | Frame: {info.frame_number}"
            self.label_details.setText(details)
            
            # Charger et afficher l'image
            self._load_and_display_image(info.filepath)
    
    def _load_and_display_image(self, filepath: str):
        """Charger et afficher une image"""
        pixmap = QPixmap(filepath)
        
        if pixmap.isNull():
            self.image_label.setText("❌ Impossible de charger l'image")
            return
        
        # Redimensionner pour s'adapter
        label_size = self.image_label.size()
        scaled_pixmap = pixmap.scaled(
            label_size.width() - 10,
            label_size.height() - 10,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.image_label.setPixmap(scaled_pixmap)
        self.current_pixmap = pixmap
    
    def _go_previous(self):
        """Aller à l'image précédente"""
        if self.task and self.task.navigate(-1):
            self._display_current_image()
    
    def _go_next(self):
        """Aller à l'image suivante"""
        if self.task and self.task.navigate(1):
            self._display_current_image()
    
    def _on_slider_changed(self, value):
        """Quand le slider change"""
        if self.task and self.task.go_to_index(value):
            self._display_current_image()
    
    def _go_to_position(self):
        """Aller à une position spécifique"""
        if self.task:
            index = self.spin_goto.value() - 1
            if self.task.go_to_index(index):
                self._display_current_image()
    
    def _move_to_level(self):
        """Déplacer l'image vers le niveau sélectionné"""
        if not self.task or self.combo_levels.currentIndex() < 0:
            return
        
        level = self.combo_levels.currentData()
        
        if self.task.move_to_level(level):
            self._update_ui_state()
            self._display_current_image()
    
    def _delete_current(self):
        """Supprimer l'image courante"""
        if not self.task:
            return
        
        reply = QMessageBox.question(
            self,
            "Confirmer la suppression",
            "Supprimer cette image?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.task.delete_current():
                self._update_ui_state()
                self._display_current_image()
    
    def _skip_current(self):
        """Ignorer l'image courante"""
        if self.task:
            self.task.skip_current()
            self._update_stats_display()
            self._display_current_image()
    
    def _delete_all_remaining(self):
        """Supprimer toutes les images restantes"""
        if not self.task:
            return
        
        remaining = len(self.task.unknown_images) - self.task.current_index
        
        reply = QMessageBox.warning(
            self,
            "⚠️ Suppression massive",
            f"Voulez-vous supprimer les {remaining} images restantes?\n\n"
            f"Cette action est IRRÉVERSIBLE!",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Double confirmation
        confirm = QMessageBox.critical(
            self,
            "🛑 Dernière confirmation",
            f"DERNIÈRE CHANCE!\n\n"
            f"Supprimer définitivement {remaining} images?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if confirm == QMessageBox.StandardButton.Yes:
            result = self.task.delete_all_remaining(
                create_backup=self.check_backup.isChecked()
            )
            
            if result['success']:
                QMessageBox.information(
                    self,
                    "Suppression terminée",
                    f"✅ {result['deleted']} images supprimées"
                )
                self._update_ui_state()
                self._display_current_image()
    
    def _delete_by_pattern(self):
        """Supprimer par motif"""
        if not self.task:
            return
        
        pattern = self.edit_pattern.text().strip()
        if not pattern:
            QMessageBox.warning(self, "Erreur", "Entrez un motif de recherche")
            return
        
        # Trouver les correspondances d'abord
        result = self.task.delete_by_pattern(pattern, "name")
        
        if result['matching'] == 0:
            QMessageBox.information(
                self,
                "Aucune correspondance",
                f"Aucune image ne correspond au motif '{pattern}'"
            )
            return
        
        # Le delete_by_pattern a déjà supprimé, mais on pourrait ajouter une confirmation
        self._update_ui_state()
        self._display_current_image()
        
        QMessageBox.information(
            self,
            "Suppression terminée",
            f"✅ {result['deleted']} images supprimées (motif: '{pattern}')"
        )
    
    def _save_progress(self):
        """Sauvegarder le progrès"""
        if self.task and self.task.save_progress():
            QMessageBox.information(
                self,
                "Progrès sauvegardé",
                "💾 Votre progrès a été sauvegardé.\n"
                "Vous pourrez reprendre plus tard."
            )
    
    def _show_summary(self):
        """Afficher le résumé"""
        if not self.task:
            return
        
        summary = self.task.get_stats_summary()
        
        dialog = QDialog(self)
        dialog.setWindowTitle("📊 Résumé de la session")
        dialog.setMinimumSize(400, 300)
        
        layout = QVBoxLayout(dialog)
        
        text = QTextEdit()
        text.setReadOnly(True)
        text.setFont(QFont("Consolas", 10))
        text.setText(summary)
        layout.addWidget(text)
        
        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(dialog.close)
        layout.addWidget(btn_close)
        
        dialog.exec()
    
    def resizeEvent(self, event):
        """Quand le widget est redimensionné"""
        super().resizeEvent(event)
        
        # Re-afficher l'image pour l'adapter à la nouvelle taille
        if self.task and self.current_pixmap:
            img_path = self.task.get_current_image_path()
            if img_path:
                QTimer.singleShot(100, lambda: self._load_and_display_image(img_path))