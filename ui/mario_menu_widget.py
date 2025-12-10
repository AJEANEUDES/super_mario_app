"""
Mario Menu Widget - Interface utilisateur pour la détection de l'écran WORLD 1-1
Widget séparé pour trouver le début du jeu Super Mario Bros
"""

import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QGridLayout, QProgressBar, QCheckBox, QDoubleSpinBox,
    QDialog, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QRadioButton, QButtonGroup, QSlider, QSpinBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage


class CandidateCard(QFrame):
    """Widget carte pour afficher un candidat détecté"""
    
    selected = pyqtSignal(int)  # Signal avec la position
    
    def __init__(self, position: int, filename: str, score: float, 
                 black_ratio: float, text_ratio: float, parent=None):
        super().__init__(parent)
        
        self.position = position
        
        # Couleur selon le score
        if score >= 0.8:
            color = "#4CAF50"  # Vert - excellent
            bg_color = "#E8F5E9"
        elif score >= 0.7:
            color = "#FF9800"  # Orange - bon
            bg_color = "#FFF3E0"
        else:
            color = "#2196F3"  # Bleu - acceptable
            bg_color = "#E3F2FD"
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 2px solid {color};
                border-radius: 8px;
                padding: 8px;
            }}
            QFrame:hover {{
                border-width: 3px;
            }}
        """)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        
        # Position et fichier
        header = QLabel(f"#{position} - {filename}")
        header.setStyleSheet(f"font-weight: bold; color: {color};")
        layout.addWidget(header)
        
        # Score
        score_label = QLabel(f"Score: {score*100:.1f}%")
        score_label.setStyleSheet("font-size: 12px;")
        layout.addWidget(score_label)
        
        # Détails
        details = QLabel(f"Noir: {black_ratio*100:.1f}% | Texte: {text_ratio*100:.1f}%")
        details.setStyleSheet("font-size: 10px; color: #666;")
        layout.addWidget(details)
    
    def mousePressEvent(self, event):
        """Émettre le signal quand cliqué"""
        self.selected.emit(self.position)
        super().mousePressEvent(event)


class MarioMenuWidget(QWidget):
    """
    Widget pour la détection de l'écran WORLD 1-1 de Super Mario Bros
    """
    
    task_requested = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.frames_dir = None
        self.output_dir = None
        self.last_candidates = []
        self.preview_image = None
        
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
        
        # 3. Configuration de la détection
        config_group = self._create_config_group()
        content_layout.addWidget(config_group)
        
        # 4. Mode d'exécution
        mode_group = self._create_mode_group()
        content_layout.addWidget(mode_group)
        
        # 5. Prévisualisation et résultats
        preview_group = self._create_preview_group()
        content_layout.addWidget(preview_group)
        
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
                background-color: #FCE4EC;
                border: 2px solid #E91E63;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(banner)
        
        title = QLabel("🎮 Détecteur d'Écran WORLD 1-1")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #C2185B;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Détecte automatiquement l'écran de début de niveau de Super Mario Bros.\n\n"
            "<b>Critères de détection:</b>\n"
            "• Fond noir ≥75% des pixels\n"
            "• Texte blanc >2% (affichage WORLD 1-1, score, etc.)\n"
            "• Luminosité moyenne <80\n\n"
            "<b>Résultat:</b> Crée un nouveau dossier avec uniquement les frames de gameplay."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #AD1457; font-size: 11px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_folder_selection(self):
        """Créer la section de sélection du dossier"""
        group = QGroupBox("📁 Dossier de Frames")
        group.setStyleSheet(self._get_group_style("#2196F3"))
        
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Dossier source
        layout.addWidget(QLabel("Dossier source:"), 0, 0)
        
        self.folder_label = QLabel("Non sélectionné")
        self.folder_label.setStyleSheet(self._get_folder_label_style(False))
        layout.addWidget(self.folder_label, 0, 1)
        
        btn_browse = QPushButton("📂 Parcourir")
        btn_browse.setStyleSheet(self._get_button_style("#2196F3"))
        btn_browse.clicked.connect(self._browse_folder)
        layout.addWidget(btn_browse, 0, 2)
        
        # Info
        self.folder_info = QLabel("")
        self.folder_info.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.folder_info, 1, 1, 1, 2)
        
        # Dossier de sortie
        layout.addWidget(QLabel("Dossier sortie:"), 2, 0)
        
        self.output_label = QLabel("Automatique (_cleaned)")
        self.output_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.output_label, 2, 1, 1, 2)
        
        group.setLayout(layout)
        return group
    
    def _create_config_group(self):
        """Créer les options de configuration"""
        group = QGroupBox("⚙️ Paramètres de Détection")
        group.setStyleSheet(self._get_group_style("#FF9800"))
        group.setCheckable(True)
        group.setChecked(False)
        
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Seuil de score
        layout.addWidget(QLabel("Seuil de score:"), 0, 0)
        
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0.40, 0.95)
        self.spin_threshold.setValue(0.75)
        self.spin_threshold.setSingleStep(0.05)
        self.spin_threshold.setDecimals(2)
        self.spin_threshold.setSuffix(" (75%)")
        self.spin_threshold.valueChanged.connect(self._on_threshold_changed)
        layout.addWidget(self.spin_threshold, 0, 1)
        
        self.threshold_desc = QLabel("Recommandé - Détection fiable")
        self.threshold_desc.setStyleSheet("color: #4CAF50; font-size: 10px;")
        layout.addWidget(self.threshold_desc, 0, 2)
        
        # Slider visuel
        self.slider_threshold = QSlider(Qt.Orientation.Horizontal)
        self.slider_threshold.setRange(40, 95)
        self.slider_threshold.setValue(75)
        self.slider_threshold.valueChanged.connect(self._on_slider_changed)
        layout.addWidget(self.slider_threshold, 1, 0, 1, 3)
        
        # Seuils avancés
        advanced_layout = QHBoxLayout()
        
        advanced_layout.addWidget(QLabel("Noir min:"))
        self.spin_black = QSpinBox()
        self.spin_black.setRange(50, 90)
        self.spin_black.setValue(75)
        self.spin_black.setSuffix("%")
        advanced_layout.addWidget(self.spin_black)
        
        advanced_layout.addSpacing(20)
        
        advanced_layout.addWidget(QLabel("Texte min:"))
        self.spin_text = QSpinBox()
        self.spin_text.setRange(1, 10)
        self.spin_text.setValue(2)
        self.spin_text.setSuffix("%")
        advanced_layout.addWidget(self.spin_text)
        
        advanced_layout.addStretch()
        
        layout.addLayout(advanced_layout, 2, 0, 1, 3)
        
        # Presets
        presets_layout = QHBoxLayout()
        
        btn_strict = QPushButton("🔒 Strict (0.85)")
        btn_strict.clicked.connect(lambda: self._set_threshold(0.85))
        presets_layout.addWidget(btn_strict)
        
        btn_normal = QPushButton("⚖️ Normal (0.75)")
        btn_normal.clicked.connect(lambda: self._set_threshold(0.75))
        presets_layout.addWidget(btn_normal)
        
        btn_tolerant = QPushButton("🔓 Tolérant (0.60)")
        btn_tolerant.clicked.connect(lambda: self._set_threshold(0.60))
        presets_layout.addWidget(btn_tolerant)
        
        layout.addLayout(presets_layout, 3, 0, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_mode_group(self):
        """Créer le groupe de sélection du mode"""
        group = QGroupBox("🎯 Mode d'Exécution")
        group.setStyleSheet(self._get_group_style("#9C27B0"))
        
        layout = QVBoxLayout()
        
        # Boutons radio
        self.btn_group = QButtonGroup(self)
        
        self.radio_dryrun = QRadioButton("🔍 Simulation (Dry Run) - Analyse uniquement, aucun fichier modifié")
        self.radio_dryrun.setChecked(True)
        self.radio_dryrun.setStyleSheet("font-weight: bold;")
        self.btn_group.addButton(self.radio_dryrun, 0)
        layout.addWidget(self.radio_dryrun)
        
        self.radio_execute = QRadioButton("📁 Exécution - Créer le dataset nettoyé")
        self.radio_execute.setStyleSheet("font-weight: bold; color: #E91E63;")
        self.btn_group.addButton(self.radio_execute, 1)
        layout.addWidget(self.radio_execute)
        
        # Warning
        self.warning_label = QLabel(
            "⚠️ L'exécution créera un nouveau dossier avec les frames de gameplay uniquement.\n"
            "Les fichiers originaux ne seront PAS modifiés."
        )
        self.warning_label.setStyleSheet("color: #666; font-size: 10px; margin-left: 20px;")
        layout.addWidget(self.warning_label)
        
        # Option écraser
        self.check_overwrite = QCheckBox("Écraser le dossier de sortie s'il existe")
        self.check_overwrite.setStyleSheet("margin-left: 20px;")
        layout.addWidget(self.check_overwrite)
        
        group.setLayout(layout)
        return group
    
    def _create_preview_group(self):
        """Créer la section de prévisualisation"""
        group = QGroupBox("👁️ Résultats et Prévisualisation")
        group.setStyleSheet(self._get_group_style("#4CAF50"))
        
        layout = QVBoxLayout()
        
        # Zone des candidats
        candidates_layout = QHBoxLayout()
        
        # Liste des candidats (scrollable)
        self.candidates_scroll = QScrollArea()
        self.candidates_scroll.setWidgetResizable(True)
        self.candidates_scroll.setMaximumHeight(150)
        self.candidates_scroll.setStyleSheet("QScrollArea { border: 1px solid #E0E0E0; }")
        
        self.candidates_container = QWidget()
        self.candidates_layout = QHBoxLayout(self.candidates_container)
        self.candidates_layout.setSpacing(10)
        self.candidates_layout.addStretch()
        
        self.candidates_scroll.setWidget(self.candidates_container)
        candidates_layout.addWidget(self.candidates_scroll)
        
        layout.addLayout(candidates_layout)
        
        # Zone de preview d'image
        preview_layout = QHBoxLayout()
        
        self.preview_label = QLabel("Sélectionnez un candidat pour prévisualiser")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(320, 180)
        self.preview_label.setStyleSheet("""
            QLabel {
                background-color: #2D2D2D;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                color: #888;
            }
        """)
        preview_layout.addWidget(self.preview_label)
        
        # Infos du candidat sélectionné
        info_layout = QVBoxLayout()
        
        self.selected_info = QLabel("Aucun candidat sélectionné")
        self.selected_info.setStyleSheet("font-size: 12px;")
        info_layout.addWidget(self.selected_info)
        
        self.stats_label = QLabel("")
        self.stats_label.setStyleSheet("font-size: 11px; color: #666;")
        info_layout.addWidget(self.stats_label)
        
        info_layout.addStretch()
        
        preview_layout.addLayout(info_layout)
        
        layout.addLayout(preview_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_action_buttons(self):
        """Créer les boutons d'action"""
        layout = QHBoxLayout()
        
        self.btn_view_report = QPushButton("📄 Voir Dernier Rapport")
        self.btn_view_report.setStyleSheet(self._get_button_style("#607D8B"))
        self.btn_view_report.clicked.connect(self._view_last_report)
        self.btn_view_report.setEnabled(False)
        layout.addWidget(self.btn_view_report)
        
        layout.addStretch()
        
        self.btn_start = QPushButton("🎮 Lancer la Détection")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #E91E63;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 15px 30px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #C2185B;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.btn_start.clicked.connect(self._start_detection)
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
    
    def _get_folder_label_style(self, selected: bool) -> str:
        """Style pour les labels de dossier"""
        if selected:
            return """
                QLabel {
                    padding: 8px;
                    background-color: #E3F2FD;
                    border: 1px solid #2196F3;
                    border-radius: 4px;
                    color: #1565C0;
                    font-weight: bold;
                }
            """
        else:
            return """
                QLabel {
                    padding: 8px;
                    background-color: #FAFAFA;
                    border: 1px solid #E0E0E0;
                    border-radius: 4px;
                    color: #757575;
                }
            """
    
    def _browse_folder(self):
        """Parcourir pour le dossier de frames"""
        folder = QFileDialog.getExistingDirectory(
            self, "Sélectionner le dossier de frames", "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self.frames_dir = folder
            self.output_dir = f"{folder}_cleaned"
            
            folder_name = os.path.basename(folder)
            self.folder_label.setText(f"📁 {folder_name}")
            self.folder_label.setToolTip(folder)
            self.folder_label.setStyleSheet(self._get_folder_label_style(True))
            
            self.output_label.setText(f"📁 {folder_name}_cleaned")
            
            # Analyser le dossier
            info = self._analyze_folder(folder)
            self.folder_info.setText(f"📷 {info['count']:,} images | 💾 {info['size_mb']:.1f} MB")
            
            # Vérifier rapport existant
            report_path = os.path.join(folder, "mario_menu_report.json")
            self.btn_view_report.setEnabled(os.path.exists(report_path))
            
            self.btn_start.setEnabled(info['count'] > 0)
            
            # Charger une image de prévisualisation
            self._load_preview_sample(folder)
    
    def _analyze_folder(self, folder: str) -> dict:
        """Analyser un dossier"""
        extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        count = 0
        total_size = 0
        
        for f in os.listdir(folder):
            filepath = os.path.join(folder, f)
            if os.path.isfile(filepath) and os.path.splitext(f)[1].lower() in extensions:
                count += 1
                total_size += os.path.getsize(filepath)
        
        return {'count': count, 'size_mb': total_size / (1024 * 1024)}
    
    def _load_preview_sample(self, folder: str):
        """Charger une image sample pour prévisualisation"""
        extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        
        for f in sorted(os.listdir(folder)):
            if os.path.splitext(f)[1].lower() in extensions:
                image_path = os.path.join(folder, f)
                self._show_preview_image(image_path)
                break
    
    def _show_preview_image(self, image_path: str):
        """Afficher une image de prévisualisation"""
        try:
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    320, 180,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                self.preview_label.setPixmap(scaled)
        except Exception as e:
            self.preview_label.setText(f"Erreur: {e}")
    
    def _on_threshold_changed(self, value):
        """Quand le seuil change"""
        self.spin_threshold.setSuffix(f" ({value*100:.0f}%)")
        self.slider_threshold.blockSignals(True)
        self.slider_threshold.setValue(int(value * 100))
        self.slider_threshold.blockSignals(False)
        
        # Description
        if value >= 0.85:
            self.threshold_desc.setText("Très strict - Peu de faux positifs")
            self.threshold_desc.setStyleSheet("color: #F44336; font-size: 10px;")
        elif value >= 0.75:
            self.threshold_desc.setText("Recommandé - Détection fiable")
            self.threshold_desc.setStyleSheet("color: #4CAF50; font-size: 10px;")
        elif value >= 0.65:
            self.threshold_desc.setText("Tolérant - Plus de candidats")
            self.threshold_desc.setStyleSheet("color: #FF9800; font-size: 10px;")
        else:
            self.threshold_desc.setText("Très tolérant - Risque de faux positifs")
            self.threshold_desc.setStyleSheet("color: #9C27B0; font-size: 10px;")
    
    def _on_slider_changed(self, value):
        """Quand le slider change"""
        self.spin_threshold.setValue(value / 100.0)
    
    def _set_threshold(self, value):
        """Définir le seuil via preset"""
        self.spin_threshold.setValue(value)
    
    def _on_candidate_selected(self, position: int):
        """Quand un candidat est sélectionné"""
        # Trouver le candidat
        for candidate in self.last_candidates:
            if candidate.get('position') == position:
                # Afficher l'image
                filepath = candidate.get('filepath')
                if filepath and os.path.exists(filepath):
                    self._show_preview_image(filepath)
                
                # Afficher les infos
                self.selected_info.setText(
                    f"<b>Position #{position}</b> - {candidate.get('filename', '?')}<br>"
                    f"Score: <b>{candidate.get('final_score', 0)*100:.1f}%</b>"
                )
                
                self.stats_label.setText(
                    f"Noir: {candidate.get('black_ratio', 0)*100:.1f}% | "
                    f"Texte: {candidate.get('text_ratio', 0)*100:.1f}% | "
                    f"Luminosité: {candidate.get('mean_brightness', 0):.1f}"
                )
                break
    
    def _update_candidates_display(self, candidates: list):
        """Mettre à jour l'affichage des candidats"""
        # Nettoyer l'ancien affichage
        while self.candidates_layout.count() > 1:  # Garder le stretch
            item = self.candidates_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.last_candidates = candidates
        
        # Ajouter les nouveaux candidats
        for candidate in candidates[:20]:  # Max 20 candidats
            card = CandidateCard(
                position=candidate.get('position', 0),
                filename=candidate.get('filename', '?'),
                score=candidate.get('final_score', 0),
                black_ratio=candidate.get('black_ratio', 0),
                text_ratio=candidate.get('text_ratio', 0)
            )
            card.selected.connect(self._on_candidate_selected)
            self.candidates_layout.insertWidget(self.candidates_layout.count() - 1, card)
    
    def _view_last_report(self):
        """Voir le dernier rapport"""
        if not self.frames_dir:
            return
        
        report_path = os.path.join(self.frames_dir, "mario_menu_report.json")
        
        if not os.path.exists(report_path):
            QMessageBox.warning(self, "Rapport non trouvé", "Aucun rapport trouvé.")
            return
        
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            # Mettre à jour les candidats
            candidates = report.get('all_candidates', [])
            if candidates:
                self._update_candidates_display(candidates)
            
            # Afficher le dialogue
            dialog = QDialog(self)
            dialog.setWindowTitle("📄 Rapport de Détection Mario")
            dialog.setMinimumSize(600, 500)
            
            layout = QVBoxLayout(dialog)
            
            text = QTextEdit()
            text.setReadOnly(True)
            
            stats = report.get('statistics', {})
            info = report.get('analysis_info', {})
            
            content = f"""🎮 RAPPORT DE DÉTECTION MARIO MENU
{'='*50}

📁 Dossier source: {info.get('frames_dir', '?')}
📁 Dossier sortie: {info.get('output_dir', '?')}
🕐 Date: {info.get('timestamp', '?')}

📈 RÉSULTATS
{'-'*30}
• Total frames analysées: {stats.get('total_frames', 0):,}
• Candidats trouvés: {stats.get('candidates_found', 0)}
• Seuil utilisé: {stats.get('threshold_used', 0)*100:.0f}%
• Détection réussie: {'✅ Oui' if stats.get('detection_successful') else '❌ Non'}
"""
            
            if stats.get('detection_successful'):
                content += f"""
🎯 MEILLEUR CANDIDAT
{'-'*30}
• Position: #{stats.get('start_position', '?')}
• Frames à ignorer: {stats.get('files_to_skip', 0):,} ({stats.get('cleanup_percentage', 0):.1f}%)
• Frames de gameplay: {stats.get('files_to_copy', 0):,}
• Mode: {'Simulation' if stats.get('dry_run') else 'Exécuté'}
"""
                if not stats.get('dry_run') and stats.get('files_copied'):
                    content += f"• Fichiers copiés: {stats.get('files_copied', 0):,}\n"
            
            text.setPlainText(content)
            layout.addWidget(text)
            
            close_btn = QPushButton("Fermer")
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lecture rapport:\n{str(e)}")
    
    def _start_detection(self):
        """Démarrer la détection"""
        if not self.frames_dir:
            QMessageBox.warning(self, "Dossier requis", "Sélectionnez un dossier de frames.")
            return
        
        dry_run = self.radio_dryrun.isChecked()
        
        # Confirmation si exécution réelle
        if not dry_run:
            reply = QMessageBox.question(
                self,
                "Confirmation",
                f"Voulez-vous créer le dataset nettoyé ?\n\n"
                f"Un nouveau dossier sera créé:\n{self.output_dir}\n\n"
                "Les fichiers originaux ne seront PAS modifiés.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            from tasks.mario_menu_task import MarioMenuTask, MarioMenuConfig
            
            config = MarioMenuConfig(
                score_threshold=self.spin_threshold.value(),
                black_threshold=self.spin_black.value() / 100.0,
                text_threshold=self.spin_text.value() / 100.0,
                overwrite_existing=self.check_overwrite.isChecked()
            )
            
            task = MarioMenuTask()
            task.configure(
                frames_dir=self.frames_dir,
                output_dir=self.output_dir,
                score_threshold=self.spin_threshold.value(),
                dry_run=dry_run,
                config=config
            )
            
            self.task_requested.emit(task)
            
            mode = "simulation" if dry_run else "exécution"
            QMessageBox.information(
                self,
                "Tâche ajoutée",
                f"✅ La tâche de détection Mario a été ajoutée.\n\n"
                f"Dossier: {os.path.basename(self.frames_dir)}\n"
                f"Seuil: {self.spin_threshold.value()*100:.0f}%\n"
                f"Mode: {mode}\n\n"
                "Cliquez sur 'Démarrer Pipeline' pour lancer."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{str(e)}")