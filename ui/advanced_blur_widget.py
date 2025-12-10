"""
Advanced Blur Widget - Interface utilisateur pour la détection avancée de flou
Widget séparé pour une meilleure organisation du code
"""

import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QSpinBox, QDoubleSpinBox, QCheckBox, QFileDialog,
    QMessageBox, QComboBox, QFrame, QScrollArea, QGridLayout,
    QSlider, QDialog, QTextEdit, QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor


class AdvancedBlurWidget(QWidget):
    """
    Widget pour la détection avancée de frames floues
    Analyse multi-critères sophistiquée
    """
    
    # Signal émis quand une tâche doit être ajoutée
    task_requested = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.frames_dir = None
        
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
        
        # 3. Région de gameplay
        region_group = self._create_region_settings()
        content_layout.addWidget(region_group)
        
        # 4. Seuils de détection (tabs)
        thresholds_group = self._create_thresholds_tabs()
        content_layout.addWidget(thresholds_group)
        
        # 5. Options de décision
        decision_group = self._create_decision_options()
        content_layout.addWidget(decision_group)
        
        # 6. Performance
        perf_group = self._create_performance_options()
        content_layout.addWidget(perf_group)
        
        # 7. Mode d'exécution
        mode_group = self._create_mode_selection()
        content_layout.addWidget(mode_group)
        
        content_layout.addStretch()
        
        # 8. Boutons
        buttons = self._create_action_buttons()
        content_layout.addLayout(buttons)
        
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
    
    def _create_info_banner(self):
        """Créer la bannière d'information"""
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background-color: #E3F2FD;
                border: 2px solid #2196F3;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(banner)
        
        title = QLabel("🔬 Détection Avancée de Frames Floues")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1565C0;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Cette fonctionnalité utilise <b>7 méthodes d'analyse</b> pour détecter les frames de mauvaise qualité:\n\n"
            "• <b>Laplacian & Sobel</b> - Détection de flou classique\n"
            "• <b>FFT</b> - Analyse fréquentielle (hautes fréquences = netteté)\n"
            "• <b>Pixelisation</b> - Détection de blocs uniformes\n"
            "• <b>Texture (LBP)</b> - Analyse des patterns locaux\n"
            "• <b>Transitions</b> - Écrans de chargement/uniformes\n"
            "• <b>Zones noires</b> - Régions trop sombres\n\n"
            "💡 <b>Conseil:</b> Vous pouvez définir une région de gameplay pour ignorer les bordures/UI."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #1976D2; font-size: 11px;")
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
    
    def _create_region_settings(self):
        """Créer les paramètres de région de gameplay"""
        group = QGroupBox("🎮 Région de Gameplay (Optionnel)")
        group.setStyleSheet(self._get_group_style("#4CAF50"))
        group.setCheckable(True)
        group.setChecked(False)
        
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Explication
        info = QLabel(
            "Définissez une région spécifique pour l'analyse. "
            "Utile pour ignorer les bordures noires ou l'interface du jeu."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(info, 0, 0, 1, 4)
        
        # Position X
        layout.addWidget(QLabel("Position X:"), 1, 0)
        self.spin_region_x = QDoubleSpinBox()
        self.spin_region_x.setRange(0.0, 0.9)
        self.spin_region_x.setSingleStep(0.05)
        self.spin_region_x.setValue(0.0)
        self.spin_region_x.setToolTip("Position X relative (0.0 = gauche, 1.0 = droite)")
        layout.addWidget(self.spin_region_x, 1, 1)
        
        # Position Y
        layout.addWidget(QLabel("Position Y:"), 1, 2)
        self.spin_region_y = QDoubleSpinBox()
        self.spin_region_y.setRange(0.0, 0.9)
        self.spin_region_y.setSingleStep(0.05)
        self.spin_region_y.setValue(0.0)
        self.spin_region_y.setToolTip("Position Y relative (0.0 = haut, 1.0 = bas)")
        layout.addWidget(self.spin_region_y, 1, 3)
        
        # Largeur
        layout.addWidget(QLabel("Largeur:"), 2, 0)
        self.spin_region_w = QDoubleSpinBox()
        self.spin_region_w.setRange(0.1, 1.0)
        self.spin_region_w.setSingleStep(0.05)
        self.spin_region_w.setValue(1.0)
        self.spin_region_w.setToolTip("Largeur relative de la région")
        layout.addWidget(self.spin_region_w, 2, 1)
        
        # Hauteur
        layout.addWidget(QLabel("Hauteur:"), 2, 2)
        self.spin_region_h = QDoubleSpinBox()
        self.spin_region_h.setRange(0.1, 1.0)
        self.spin_region_h.setSingleStep(0.05)
        self.spin_region_h.setValue(1.0)
        self.spin_region_h.setToolTip("Hauteur relative de la région")
        layout.addWidget(self.spin_region_h, 2, 3)
        
        # Presets
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Presets:"))
        
        preset_full = QPushButton("Image complète")
        preset_full.clicked.connect(lambda: self._set_region_preset(0.0, 0.0, 1.0, 1.0))
        preset_layout.addWidget(preset_full)
        
        preset_mario = QPushButton("Mario classique")
        preset_mario.clicked.connect(lambda: self._set_region_preset(0.05, 0.1, 0.9, 0.8))
        preset_layout.addWidget(preset_mario)
        
        preset_center = QPushButton("Centre 60%")
        preset_center.clicked.connect(lambda: self._set_region_preset(0.2, 0.2, 0.6, 0.6))
        preset_layout.addWidget(preset_center)
        
        layout.addLayout(preset_layout, 3, 0, 1, 4)
        
        group.setLayout(layout)
        return group
    
    def _create_thresholds_tabs(self):
        """Créer les onglets de seuils"""
        group = QGroupBox("⚙️ Seuils de Détection")
        group.setStyleSheet(self._get_group_style("#FF9800"))
        group.setCheckable(True)
        group.setChecked(False)
        
        layout = QVBoxLayout()
        
        tabs = QTabWidget()
        
        # Tab 1: Flou
        blur_tab = QWidget()
        blur_layout = QGridLayout(blur_tab)
        
        blur_layout.addWidget(QLabel("Seuil Laplacian:"), 0, 0)
        self.spin_laplacian = QDoubleSpinBox()
        self.spin_laplacian.setRange(0.0001, 0.1)
        self.spin_laplacian.setDecimals(4)
        self.spin_laplacian.setSingleStep(0.0005)
        self.spin_laplacian.setValue(0.002)
        self.spin_laplacian.setToolTip("Variance Laplacian min (plus bas = plus strict)")
        blur_layout.addWidget(self.spin_laplacian, 0, 1)
        
        blur_layout.addWidget(QLabel("Seuil Sobel:"), 0, 2)
        self.spin_sobel = QDoubleSpinBox()
        self.spin_sobel.setRange(0.01, 0.5)
        self.spin_sobel.setDecimals(3)
        self.spin_sobel.setSingleStep(0.01)
        self.spin_sobel.setValue(0.05)
        self.spin_sobel.setToolTip("Gradient Sobel moyen min")
        blur_layout.addWidget(self.spin_sobel, 0, 3)
        
        blur_layout.addWidget(QLabel("Seuil FFT:"), 1, 0)
        self.spin_fft = QDoubleSpinBox()
        self.spin_fft.setRange(0.01, 0.5)
        self.spin_fft.setDecimals(3)
        self.spin_fft.setSingleStep(0.01)
        self.spin_fft.setValue(0.12)
        self.spin_fft.setToolTip("Ratio hautes fréquences min")
        blur_layout.addWidget(self.spin_fft, 1, 1)
        
        tabs.addTab(blur_tab, "🔍 Flou")
        
        # Tab 2: Texture/Pixel
        texture_tab = QWidget()
        texture_layout = QGridLayout(texture_tab)
        
        texture_layout.addWidget(QLabel("Seuil Texture:"), 0, 0)
        self.spin_texture = QDoubleSpinBox()
        self.spin_texture.setRange(1.0, 100.0)
        self.spin_texture.setDecimals(1)
        self.spin_texture.setSingleStep(1.0)
        self.spin_texture.setValue(20.0)
        self.spin_texture.setToolTip("Variance texture min (LBP)")
        texture_layout.addWidget(self.spin_texture, 0, 1)
        
        texture_layout.addWidget(QLabel("Seuil Pixelisation:"), 0, 2)
        self.spin_pixelation = QDoubleSpinBox()
        self.spin_pixelation.setRange(0.05, 0.9)
        self.spin_pixelation.setDecimals(2)
        self.spin_pixelation.setSingleStep(0.05)
        self.spin_pixelation.setValue(0.25)
        self.spin_pixelation.setToolTip("Ratio de blocs uniformes max")
        texture_layout.addWidget(self.spin_pixelation, 0, 3)
        
        tabs.addTab(texture_tab, "🎨 Texture")
        
        # Tab 3: Transitions
        trans_tab = QWidget()
        trans_layout = QGridLayout(trans_tab)
        
        trans_layout.addWidget(QLabel("Seuil Uniformité:"), 0, 0)
        self.spin_uniformity = QDoubleSpinBox()
        self.spin_uniformity.setRange(0.005, 0.2)
        self.spin_uniformity.setDecimals(3)
        self.spin_uniformity.setSingleStep(0.005)
        self.spin_uniformity.setValue(0.02)
        self.spin_uniformity.setToolTip("Variance couleur max pour transition")
        trans_layout.addWidget(self.spin_uniformity, 0, 1)
        
        trans_layout.addWidget(QLabel("Seuil Noir:"), 0, 2)
        self.spin_black = QDoubleSpinBox()
        self.spin_black.setRange(0.1, 0.9)
        self.spin_black.setDecimals(2)
        self.spin_black.setSingleStep(0.05)
        self.spin_black.setValue(0.4)
        self.spin_black.setToolTip("Ratio de pixels noirs max")
        trans_layout.addWidget(self.spin_black, 0, 3)
        
        tabs.addTab(trans_tab, "📺 Transitions")
        
        layout.addWidget(tabs)
        
        # Bouton reset
        reset_btn = QPushButton("🔄 Réinitialiser tous les seuils")
        reset_btn.clicked.connect(self._reset_thresholds)
        layout.addWidget(reset_btn)
        
        group.setLayout(layout)
        return group
    
    def _create_decision_options(self):
        """Créer les options de décision"""
        group = QGroupBox("🎯 Critères de Décision")
        group.setStyleSheet(self._get_group_style("#9C27B0"))
        
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("Nombre minimum de problèmes pour marquer comme flou:"))
        
        self.spin_issues = QSpinBox()
        self.spin_issues.setRange(1, 7)
        self.spin_issues.setValue(2)
        self.spin_issues.setToolTip(
            "1 = Très strict (un seul problème suffit)\n"
            "2 = Équilibré (recommandé)\n"
            "3+ = Tolérant (plusieurs problèmes nécessaires)"
        )
        layout.addWidget(self.spin_issues)
        
        layout.addSpacing(20)
        
        # Indication
        self.issues_label = QLabel("(2 = Recommandé)")
        self.issues_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.issues_label)
        
        self.spin_issues.valueChanged.connect(self._update_issues_label)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def _create_performance_options(self):
        """Créer les options de performance"""
        group = QGroupBox("🚀 Performance")
        group.setStyleSheet(self._get_group_style("#00BCD4"))
        
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("Mode:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItems(["Auto (GPU si disponible)", "GPU uniquement", "CPU uniquement"])
        layout.addWidget(self.combo_mode)
        
        layout.addSpacing(20)
        
        layout.addWidget(QLabel("Batch size:"))
        self.spin_batch = QSpinBox()
        self.spin_batch.setRange(8, 128)
        self.spin_batch.setValue(32)
        layout.addWidget(self.spin_batch)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def _create_mode_selection(self):
        """Créer la sélection du mode"""
        group = QGroupBox("🎬 Mode d'Exécution")
        group.setStyleSheet(self._get_group_style("#673AB7"))
        
        layout = QVBoxLayout()
        
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
        
        self.warning_label = QLabel(
            "⚠️ Le mode suppression est <b>irréversible</b>."
        )
        self.warning_label.setStyleSheet("""
            QLabel {
                color: #D32F2F;
                background-color: #FFEBEE;
                padding: 10px;
                border-radius: 4px;
            }
        """)
        self.warning_label.setVisible(False)
        layout.addWidget(self.warning_label)
        
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
        
        self.btn_start = QPushButton("▶️ Lancer l'Analyse Avancée")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 15px 30px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        self.btn_start.clicked.connect(self._start_analysis)
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
                    background-color: #673AB7;
                    color: white;
                    font-weight: bold;
                    padding: 15px;
                    border: 3px solid #4527A0;
                    border-radius: 8px;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #EDE7F6;
                    color: #4527A0;
                    font-weight: bold;
                    padding: 15px;
                    border: 2px solid #B39DDB;
                    border-radius: 8px;
                }
                QPushButton:hover {
                    background-color: #D1C4E9;
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
                    background-color: #E3F2FD;
                    border: 1px solid #2196F3;
                    border-radius: 4px;
                    color: #1565C0;
                    font-weight: bold;
                }
            """)
            
            self._analyze_folder(folder)
            
            report_path = os.path.join(folder, "advanced_blur_report.json")
            self.btn_view_report.setEnabled(os.path.exists(report_path))
    
    def _analyze_folder(self, folder: str):
        """Analyser le contenu du dossier"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        
        image_count = 0
        total_size = 0
        
        for f in os.listdir(folder):
            filepath = os.path.join(folder, f)
            if os.path.isfile(filepath) and f.lower().endswith(tuple(image_extensions)):
                image_count += 1
                total_size += os.path.getsize(filepath)
        
        size_mb = total_size / (1024 * 1024)
        self.folder_info.setText(f"📷 {image_count:,} images | 💾 {size_mb:.1f} MB")
    
    def _set_region_preset(self, x, y, w, h):
        """Appliquer un preset de région"""
        self.spin_region_x.setValue(x)
        self.spin_region_y.setValue(y)
        self.spin_region_w.setValue(w)
        self.spin_region_h.setValue(h)
    
    def _reset_thresholds(self):
        """Réinitialiser les seuils"""
        self.spin_laplacian.setValue(0.002)
        self.spin_sobel.setValue(0.05)
        self.spin_fft.setValue(0.12)
        self.spin_texture.setValue(20.0)
        self.spin_pixelation.setValue(0.25)
        self.spin_uniformity.setValue(0.02)
        self.spin_black.setValue(0.4)
        self.spin_issues.setValue(2)
    
    def _update_issues_label(self, value):
        """Mettre à jour le label du nombre de problèmes"""
        labels = {
            1: "(1 = Très strict)",
            2: "(2 = Recommandé)",
            3: "(3 = Équilibré)",
            4: "(4 = Tolérant)",
            5: "(5 = Très tolérant)",
            6: "(6 = Minimal)",
            7: "(7 = Extrêmement tolérant)"
        }
        self.issues_label.setText(labels.get(value, ""))
    
    def _select_mode(self, analyze_only: bool):
        """Sélectionner le mode"""
        self.btn_analyze.setChecked(analyze_only)
        self.btn_delete.setChecked(not analyze_only)
        
        self.btn_analyze.setStyleSheet(self._get_mode_button_style(analyze_only))
        self.btn_delete.setStyleSheet(self._get_mode_button_style(not analyze_only))
        
        self.warning_label.setVisible(not analyze_only)
        
        if analyze_only:
            self.btn_start.setText("▶️ Lancer l'Analyse Avancée")
            self.btn_start.setStyleSheet(self._get_button_style("#2196F3").replace("padding: 8px 15px;", "padding: 15px 30px; font-size: 14px;"))
        else:
            self.btn_start.setText("🗑️ Lancer le Nettoyage Avancé")
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
        """Voir le dernier rapport"""
        if not self.frames_dir:
            return
        
        report_path = os.path.join(self.frames_dir, "advanced_blur_report.json")
        
        if not os.path.exists(report_path):
            QMessageBox.warning(self, "Rapport non trouvé", "Aucun rapport trouvé.")
            return
        
        try:
            import json
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            dialog = QDialog(self)
            dialog.setWindowTitle("📊 Rapport d'Analyse Avancée")
            dialog.setMinimumSize(600, 500)
            
            layout = QVBoxLayout(dialog)
            
            text = QTextEdit()
            text.setReadOnly(True)
            
            content = f"""📊 RAPPORT D'ANALYSE AVANCÉE DE FLOU
{'='*50}

📁 Dossier: {self.frames_dir}
🖥️ Device: {report.get('device', 'N/A')}

📈 STATISTIQUES
{'-'*30}
• Total frames: {report.get('total_frames', 0):,}
• Frames nettes: {report.get('sharp_frames', 0):,} ({report.get('sharp_percentage', 0):.1f}%)
• Frames floues: {report.get('blurry_frames', 0):,}

🔍 PROBLÈMES DÉTECTÉS
{'-'*30}"""
            
            issues = report.get('issues_breakdown', {})
            if issues:
                for issue, count in sorted(issues.items(), key=lambda x: x[1], reverse=True):
                    pct = (count / report.get('total_frames', 1)) * 100
                    content += f"\n• {issue}: {count:,} ({pct:.1f}%)"
            else:
                content += "\nAucun problème détecté"
            
            if report.get('quality_metrics'):
                content += f"\n\n📊 MÉTRIQUES QUALITÉ (frames nettes)\n{'-'*30}"
                for metric, value in report['quality_metrics'].items():
                    content += f"\n• {metric}: {value:.4f}"
            
            text.setPlainText(content)
            layout.addWidget(text)
            
            close_btn = QPushButton("Fermer")
            close_btn.clicked.connect(dialog.close)
            layout.addWidget(close_btn)
            
            dialog.exec()
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur lecture rapport:\n{str(e)}")
    
    def _start_analysis(self):
        """Démarrer l'analyse"""
        if not self.frames_dir:
            QMessageBox.warning(self, "Dossier requis", "Veuillez sélectionner un dossier.")
            return
        
        dry_run = self.btn_analyze.isChecked()
        
        if not dry_run:
            reply = QMessageBox.warning(
                self,
                "⚠️ Confirmation",
                "Vous allez supprimer définitivement les frames détectées comme floues.\n\n"
                "Cette action est IRRÉVERSIBLE.\n\nContinuer ?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        try:
            from tasks.advanced_blur_task import AdvancedBlurTask, TORCH_AVAILABLE
            
            mode_idx = self.combo_mode.currentIndex()
            if mode_idx == 0:
                use_gpu = TORCH_AVAILABLE
            elif mode_idx == 1:
                use_gpu = True
                if not TORCH_AVAILABLE:
                    QMessageBox.warning(self, "GPU non disponible", "PyTorch non installé. Mode CPU utilisé.")
                    use_gpu = False
            else:
                use_gpu = False
            
            task = AdvancedBlurTask()
            task.configure(
                frames_dir=self.frames_dir,
                dry_run=dry_run,
                # Région
                region_x=self.spin_region_x.value(),
                region_y=self.spin_region_y.value(),
                region_w=self.spin_region_w.value(),
                region_h=self.spin_region_h.value(),
                # Seuils
                laplacian_threshold=self.spin_laplacian.value(),
                sobel_threshold=self.spin_sobel.value(),
                fft_threshold=self.spin_fft.value(),
                texture_threshold=self.spin_texture.value(),
                pixelation_threshold=self.spin_pixelation.value(),
                uniformity_threshold=self.spin_uniformity.value(),
                black_ratio_threshold=self.spin_black.value(),
                # Décision
                num_issues_threshold=self.spin_issues.value(),
                # Performance
                batch_size=self.spin_batch.value(),
                use_gpu=use_gpu
            )
            
            self.task_requested.emit(task)
            
            mode_str = "Analyse" if dry_run else "Nettoyage"
            QMessageBox.information(
                self,
                "Tâche ajoutée",
                f"✅ La tâche de {mode_str.lower()} avancé a été ajoutée.\n\n"
                "Cliquez sur 'Démarrer Pipeline' pour lancer."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{str(e)}")