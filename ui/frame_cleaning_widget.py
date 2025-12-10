"""
Frame Cleaning Widget - Interface utilisateur pour le nettoyage des frames
Widget séparé pour une meilleure organisation du code
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSpinBox, QDoubleSpinBox, QCheckBox, QFileDialog,
    QMessageBox, QComboBox, QFrame, QScrollArea, QGridLayout,
    QProgressBar, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class FrameCleaningWidget(QWidget):
    """
    Widget complet pour la configuration et le lancement du nettoyage de frames
    Conçu pour être intégré comme onglet dans MainWindow
    """
    
    # Signal émis quand une tâche doit être ajoutée
    task_requested = pyqtSignal(object)  # Émet la tâche configurée
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.frames_dir = None
        self.last_stats = None
        
        self._create_ui()
    
    def _create_ui(self):
        """Créer l'interface utilisateur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Scroll area pour tout le contenu
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        
        # 1. Bannière d'information (optionnel)
        info_banner = self._create_info_banner()
        content_layout.addWidget(info_banner)
        
        # 2. Sélection du dossier
        folder_group = self._create_folder_selection()
        content_layout.addWidget(folder_group)
        
        # 3. Options de détection
        detection_group = self._create_detection_options()
        content_layout.addWidget(detection_group)
        
        # 4. Seuils avancés (collapsible)
        thresholds_group = self._create_thresholds_section()
        content_layout.addWidget(thresholds_group)
        
        # 5. Options de performance
        performance_group = self._create_performance_options()
        content_layout.addWidget(performance_group)
        
        # 6. Mode d'exécution
        mode_group = self._create_mode_selection()
        content_layout.addWidget(mode_group)
        
        content_layout.addStretch()
        
        # 7. Boutons d'action
        buttons_layout = self._create_action_buttons()
        content_layout.addLayout(buttons_layout)
        
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
        
        # Titre
        title = QLabel("⚠️ Étape Optionnelle - Nettoyage des Frames")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #E65100;")
        layout.addWidget(title)
        
        # Description
        desc = QLabel(
            "Cette fonctionnalité est <b>optionnelle</b>. Elle permet de supprimer automatiquement "
            "les frames de mauvaise qualité (floues, trop sombres, uniformes, etc.) pour améliorer "
            "la qualité de votre dataset.\n\n"
            "💡 <b>Conseil:</b> Commencez par une analyse (mode simulation) pour voir combien de frames "
            "seraient supprimées avant de lancer la suppression réelle."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #5D4037; font-size: 12px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_folder_selection(self):
        """Créer la section de sélection du dossier"""
        group = QGroupBox("📁 Dossier de Frames")
        group.setStyleSheet(self._get_group_style("#FF5722"))
        
        layout = QVBoxLayout()
        
        # Ligne de sélection
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
        browse_btn.setStyleSheet(self._get_button_style("#FF5722"))
        browse_btn.clicked.connect(self._browse_folder)
        select_layout.addWidget(browse_btn)
        
        layout.addLayout(select_layout)
        
        # Info sur le dossier
        self.folder_info = QLabel("")
        self.folder_info.setStyleSheet("color: #666; font-size: 11px; padding: 5px;")
        layout.addWidget(self.folder_info)
        
        group.setLayout(layout)
        return group
    
    def _create_detection_options(self):
        """Créer les options de détection"""
        group = QGroupBox("🔍 Types de Frames à Détecter")
        group.setStyleSheet(self._get_group_style("#9C27B0"))
        
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Checkboxes pour chaque type
        self.check_black = QCheckBox("Frames trop sombres")
        self.check_black.setChecked(True)
        self.check_black.setToolTip("Détecte les frames presque noires (écrans de chargement, transitions)")
        layout.addWidget(self.check_black, 0, 0)
        
        self.check_blurry = QCheckBox("Frames floues")
        self.check_blurry.setChecked(True)
        self.check_blurry.setToolTip("Détecte les frames avec peu de détails (motion blur, défocus)")
        layout.addWidget(self.check_blurry, 0, 1)
        
        self.check_uniform = QCheckBox("Frames uniformes")
        self.check_uniform.setChecked(True)
        self.check_uniform.setToolTip("Détecte les frames avec peu de variation de couleur")
        layout.addWidget(self.check_uniform, 1, 0)
        
        self.check_low_content = QCheckBox("Faible contenu")
        self.check_low_content.setChecked(True)
        self.check_low_content.setToolTip("Détecte les frames avec peu de contours/détails")
        layout.addWidget(self.check_low_content, 1, 1)
        
        self.check_small = QCheckBox("Résolution insuffisante")
        self.check_small.setChecked(True)
        self.check_small.setToolTip("Détecte les frames trop petites")
        layout.addWidget(self.check_small, 2, 0)
        
        # Bouton tout sélectionner/désélectionner
        toggle_btn = QPushButton("Tout sélectionner/désélectionner")
        toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: #E1BEE7;
                color: #4A148C;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #CE93D8;
            }
        """)
        toggle_btn.clicked.connect(self._toggle_all_checks)
        layout.addWidget(toggle_btn, 2, 1)
        
        group.setLayout(layout)
        return group
    
    def _create_thresholds_section(self):
        """Créer la section des seuils avancés"""
        group = QGroupBox("⚙️ Seuils Avancés (Optionnel)")
        group.setStyleSheet(self._get_group_style("#607D8B"))
        group.setCheckable(True)
        group.setChecked(False)  # Replié par défaut
        
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Seuil de noir
        layout.addWidget(QLabel("Seuil noir:"), 0, 0)
        self.spin_black = QDoubleSpinBox()
        self.spin_black.setRange(0.01, 0.5)
        self.spin_black.setSingleStep(0.01)
        self.spin_black.setValue(0.08)
        self.spin_black.setToolTip("Luminosité max pour considérer une frame comme noire (0-1)")
        layout.addWidget(self.spin_black, 0, 1)
        
        # Seuil de flou
        layout.addWidget(QLabel("Seuil flou:"), 0, 2)
        self.spin_blur = QDoubleSpinBox()
        self.spin_blur.setRange(0.0001, 0.01)
        self.spin_blur.setSingleStep(0.0001)
        self.spin_blur.setDecimals(4)
        self.spin_blur.setValue(0.0015)
        self.spin_blur.setToolTip("Variance Laplacian min pour considérer une frame comme nette")
        layout.addWidget(self.spin_blur, 0, 3)
        
        # Seuil uniformité
        layout.addWidget(QLabel("Seuil uniforme:"), 1, 0)
        self.spin_uniform = QDoubleSpinBox()
        self.spin_uniform.setRange(0.001, 0.1)
        self.spin_uniform.setSingleStep(0.001)
        self.spin_uniform.setDecimals(3)
        self.spin_uniform.setValue(0.008)
        self.spin_uniform.setToolTip("Variance couleur min pour considérer une frame comme variée")
        layout.addWidget(self.spin_uniform, 1, 1)
        
        # Seuil contenu
        layout.addWidget(QLabel("Seuil contenu:"), 1, 2)
        self.spin_edge = QDoubleSpinBox()
        self.spin_edge.setRange(0.001, 0.1)
        self.spin_edge.setSingleStep(0.001)
        self.spin_edge.setDecimals(3)
        self.spin_edge.setValue(0.005)
        self.spin_edge.setToolTip("Ratio de contours min pour considérer une frame comme ayant du contenu")
        layout.addWidget(self.spin_edge, 1, 3)
        
        # Taille minimale
        layout.addWidget(QLabel("Largeur min:"), 2, 0)
        self.spin_min_width = QSpinBox()
        self.spin_min_width.setRange(50, 1920)
        self.spin_min_width.setValue(200)
        layout.addWidget(self.spin_min_width, 2, 1)
        
        layout.addWidget(QLabel("Hauteur min:"), 2, 2)
        self.spin_min_height = QSpinBox()
        self.spin_min_height.setRange(50, 1080)
        self.spin_min_height.setValue(150)
        layout.addWidget(self.spin_min_height, 2, 3)
        
        # Bouton reset
        reset_btn = QPushButton("🔄 Réinitialiser les seuils")
        reset_btn.clicked.connect(self._reset_thresholds)
        layout.addWidget(reset_btn, 3, 0, 1, 4)
        
        group.setLayout(layout)
        return group
    
    def _create_performance_options(self):
        """Créer les options de performance"""
        group = QGroupBox("🚀 Performance")
        group.setStyleSheet(self._get_group_style("#4CAF50"))
        
        layout = QHBoxLayout()
        
        # Mode GPU/CPU
        layout.addWidget(QLabel("Mode:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Auto (GPU si disponible)", "GPU uniquement", "CPU uniquement"])
        self.combo_mode.setToolTip("GPU est plus rapide mais nécessite PyTorch avec CUDA")
        layout.addWidget(self.combo_mode)
        
        layout.addSpacing(20)
        
        # Batch size
        layout.addWidget(QLabel("Batch size:"))
        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(8, 128)
        self.spin_batch.setValue(32)
        self.spin_batch.setToolTip("Nombre d'images traitées simultanément (GPU)")
        layout.addWidget(self.spin_batch)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def _create_mode_selection(self):
        """Créer la sélection du mode d'exécution"""
        group = QGroupBox("🎯 Mode d'Exécution")
        group.setStyleSheet(self._get_group_style("#2196F3"))
        
        layout = QVBoxLayout()
        
        # Radio buttons simulés avec des boutons
        mode_layout = QHBoxLayout()
        
        self.btn_analyze = QPushButton("🔍 Analyse Seulement\n(Simulation)")
        self.btn_analyze.setCheckable(True)
        self.btn_analyze.setChecked(True)
        self.btn_analyze.setStyleSheet(self._get_mode_button_style(True))
        self.btn_analyze.clicked.connect(lambda: self._select_mode(True))
        mode_layout.addWidget(self.btn_analyze)
        
        self.btn_delete = QPushButton("🗑️ Analyse + Suppression\n(Irréversible)")
        self.btn_delete.setCheckable(True)
        self.btn_delete.setChecked(False)
        self.btn_delete.setStyleSheet(self._get_mode_button_style(False))
        self.btn_delete.clicked.connect(lambda: self._select_mode(False))
        mode_layout.addWidget(self.btn_delete)
        
        layout.addLayout(mode_layout)
        
        # Avertissement pour le mode suppression
        self.warning_label = QLabel(
            "⚠️ Le mode suppression est <b>irréversible</b>. "
            "Les frames détectées comme invalides seront définitivement supprimées."
        )
        self.warning_label.setWordWrap(True)
        self.warning_label.setStyleSheet("""
            QLabel {
                color: #D32F2F;
                background-color: #FFEBEE;
                padding: 10px;
                border-radius: 4px;
                font-size: 11px;
            }
        """)
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)
        
        group.setLayout(layout)
        return group
    
    def _create_action_buttons(self):
        """Créer les boutons d'action"""
        layout = QHBoxLayout()
        
        # Bouton visualiser les résultats précédents
        self.btn_view_report = QPushButton("📊 Voir Dernier Rapport")
        self.btn_view_report.setStyleSheet(self._get_button_style("#607D8B"))
        self.btn_view_report.clicked.connect(self._view_last_report)
        self.btn_view_report.setEnabled(False)
        layout.addWidget(self.btn_view_report)
        
        layout.addStretch()
        
        # Bouton lancer
        self.btn_start = QPushButton("▶️ Lancer le Nettoyage")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 15px 30px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #43A047;
            }
            QPushButton:pressed {
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.btn_start.clicked.connect(self._start_cleaning)
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
    
    def _get_mode_button_style(self, selected: bool) -> str:
        """Style pour les boutons de mode"""
        if selected:
            return """
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    font-weight: bold;
                    padding: 15px;
                    border: 3px solid #1565C0;
                    border-radius: 8px;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #E3F2FD;
                    color: #1565C0;
                    font-weight: bold;
                    padding: 15px;
                    border: 2px solid #90CAF9;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #BBDEFB;
                }
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
                    background-color: #E8F5E9;
                    border: 1px solid #4CAF50;
                    border-radius: 4px;
                    color: #2E7D32;
                    font-weight: bold;
                }
            """)
            
            # Compter les images
            self._analyze_folder(folder)
            
            # Vérifier s'il y a un rapport existant
            report_path = os.path.join(folder, "cleaning_report.json")
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
        self.folder_info.setText(f"📷 {image_count:,} images trouvées | 💾 {size_mb:.1f} MB")
    
    def _toggle_all_checks(self):
        """Basculer toutes les checkboxes"""
        # Vérifier l'état actuel
        all_checked = all([
            self.check_black.isChecked(),
            self.check_blurry.isChecked(),
            self.check_uniform.isChecked(),
            self.check_low_content.isChecked(),
            self.check_small.isChecked()
        ])
        
        # Inverser
        new_state = not all_checked
        self.check_black.setChecked(new_state)
        self.check_blurry.setChecked(new_state)
        self.check_uniform.setChecked(new_state)
        self.check_low_content.setChecked(new_state)
        self.check_small.setChecked(new_state)
    
    def _reset_thresholds(self):
        """Réinitialiser les seuils aux valeurs par défaut"""
        self.spin_black.setValue(0.08)
        self.spin_blur.setValue(0.0015)
        self.spin_uniform.setValue(0.008)
        self.spin_edge.setValue(0.005)
        self.spin_min_width.setValue(200)
        self.spin_min_height.setValue(150)
    
    def _select_mode(self, analyze_only: bool):
        """Sélectionner le mode d'exécution"""
        self.btn_analyze.setChecked(analyze_only)
        self.btn_delete.setChecked(not analyze_only)
        
        self.btn_analyze.setStyleSheet(self._get_mode_button_style(analyze_only))
        self.btn_delete.setStyleSheet(self._get_mode_button_style(not analyze_only))
        
        # Afficher/masquer l'avertissement
        self.warning_label.setVisible(not analyze_only)
        
        # Changer le texte du bouton
        if analyze_only:
            self.btn_start.setText("▶️ Lancer l'Analyse")
            self.btn_start.setStyleSheet(self._get_button_style("#4CAF50").replace("padding: 8px 15px;", "padding: 15px 30px; font-size: 14px;"))
        else:
            self.btn_start.setText("🗑️ Lancer le Nettoyage")
            self.btn_start.setStyleSheet("""
                QPushButton {
                    background-color: #F44336;
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 15px 30px;
                    border: none;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
            """)
    
    def _view_last_report(self):
        """Voir le dernier rapport de nettoyage"""
        if not self.frames_dir:
            return
        
        report_path = os.path.join(self.frames_dir, "cleaning_report.json")
        
        if not os.path.exists(report_path):
            QMessageBox.warning(self, "Rapport non trouvé", "Aucun rapport de nettoyage trouvé dans ce dossier.")
            return
        
        try:
            import json
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            # Afficher dans une boîte de dialogue
            dialog = QDialog(self)
            dialog.setWindowTitle("📊 Rapport de Nettoyage")
            dialog.setMinimumSize(500, 400)
            
            layout = QVBoxLayout(dialog)
            
            text = QTextEdit()
            text.setReadOnly(True)
            
            # Formater le rapport
            content = f"""📊 RAPPORT DE NETTOYAGE
{'='*50}

📁 Dossier: {self.frames_dir}
🖥️ Device: {report.get('device', 'N/A')}
🔄 Mode: {'Analyse seulement' if report.get('dry_run', True) else 'Suppression'}

📈 STATISTIQUES
{'-'*30}
• Total frames: {report.get('total_frames', 0):,}
• Frames valides: {report.get('valid_frames', 0):,} ({report.get('valid_percentage', 0):.1f}%)
• Frames invalides: {report.get('invalid_frames', 0):,}
• Espace total: {report.get('total_size_mb', 0):.1f} MB
• Espace économisé: {report.get('savings_mb', 0):.1f} MB

🔍 PROBLÈMES DÉTECTÉS
{'-'*30}"""
            
            issues = report.get('issues_breakdown', {})
            if issues:
                for issue, count in sorted(issues.items(), key=lambda x: x[1], reverse=True):
                    percentage = (count / report.get('total_frames', 1)) * 100
                    content += f"\n• {issue}: {count:,} ({percentage:.1f}%)"
            else:
                content += "\nAucun problème détecté"
            
            text.setPlainText(content)
            layout.addWidget(text)
            
            close_btn = QPushButton("Fermer")
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lors de la lecture du rapport:\n{str(e)}")
    
    def _start_cleaning(self):
        """Démarrer le nettoyage"""
        # Vérifications
        if not self.frames_dir:
            QMessageBox.warning(
                self,
                "Dossier requis",
                "Veuillez sélectionner un dossier de frames à analyser."
            )
            return
        
        # Confirmation pour le mode suppression
        dry_run = self.btn_analyze.isChecked()
        
        if not dry_run:
            reply = QMessageBox.warning(
                self,
                "⚠️ Confirmation de Suppression",
                "Vous êtes sur le point de supprimer définitivement les frames invalides.\n\n"
                "Cette action est IRRÉVERSIBLE.\n\n"
                "Êtes-vous sûr de vouloir continuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        # Créer la tâche
        try:
            from tasks.frame_cleaning_task import FrameCleaningTask, TORCH_AVAILABLE
            
            # Déterminer le mode GPU/CPU
            mode_idx = self.combo_mode.currentIndex()
            if mode_idx == 0:  # Auto
                use_gpu = TORCH_AVAILABLE
            elif mode_idx == 1:  # GPU only
                use_gpu = True
                if not TORCH_AVAILABLE:
                    QMessageBox.warning(
                        self,
                        "GPU non disponible",
                        "PyTorch n'est pas installé. Le mode CPU sera utilisé.\n\n"
                        "Pour utiliser le GPU, installez: pip install torch torchvision"
                    )
                    use_gpu = False
            else:  # CPU only
                use_gpu = False
            
            task = FrameCleaningTask()
            task.configure(
                frames_dir=self.frames_dir,
                dry_run=dry_run,
                # Seuils
                black_threshold=self.spin_black.value(),
                blur_threshold=self.spin_blur.value(),
                uniform_threshold=self.spin_uniform.value(),
                edge_threshold=self.spin_edge.value(),
                min_width=self.spin_min_width.value(),
                min_height=self.spin_min_height.value(),
                # Options
                remove_black=self.check_black.isChecked(),
                remove_blurry=self.check_blurry.isChecked(),
                remove_uniform=self.check_uniform.isChecked(),
                remove_low_content=self.check_low_content.isChecked(),
                remove_small=self.check_small.isChecked(),
                # Performance
                batch_size=self.spin_batch.value(),
                use_gpu=use_gpu
            )
            
            # Émettre le signal
            self.task_requested.emit(task)
            
            mode_str = "Analyse" if dry_run else "Nettoyage"
            QMessageBox.information(
                self,
                "Tâche ajoutée",
                f"✅ La tâche de {mode_str.lower()} a été ajoutée à la queue.\n\n"
                "Cliquez sur 'Démarrer Pipeline' pour lancer l'exécution."
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Erreur",
                f"Erreur lors de la création de la tâche:\n{str(e)}"
            )
    
    def get_task(self):
        """
        Méthode alternative pour obtenir une tâche configurée
        Utilisée si le signal n'est pas connecté
        """
        if not self.frames_dir:
            return None
        
        from tasks.frame_cleaning_task import FrameCleaningTask, TORCH_AVAILABLE
        
        mode_idx = self.combo_mode.currentIndex()
        use_gpu = TORCH_AVAILABLE if mode_idx == 0 else (mode_idx == 1)
        
        task = FrameCleaningTask()
        task.configure(
            frames_dir=self.frames_dir,
            dry_run=self.btn_analyze.isChecked(),
            black_threshold=self.spin_black.value(),
            blur_threshold=self.spin_blur.value(),
            uniform_threshold=self.spin_uniform.value(),
            edge_threshold=self.spin_edge.value(),
            min_width=self.spin_min_width.value(),
            min_height=self.spin_min_height.value(),
            remove_black=self.check_black.isChecked(),
            remove_blurry=self.check_blurry.isChecked(),
            remove_uniform=self.check_uniform.isChecked(),
            remove_low_content=self.check_low_content.isChecked(),
            remove_small=self.check_small.isChecked(),
            batch_size=self.spin_batch.value(),
            use_gpu=use_gpu
        )
        
        return task