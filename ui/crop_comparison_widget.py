"""
Crop Comparison Widget - Interface utilisateur pour l'analyse de comparaison crop
Widget séparé pour comparer dossiers original et croppé
"""

import os
import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QGridLayout, QProgressBar, QCheckBox, QSpinBox,
    QDialog, QTextEdit, QTableWidget, QTableWidgetItem, QHeaderView,
    QTabWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor


class StatCard(QFrame):
    """Widget carte pour afficher une statistique"""
    
    def __init__(self, title: str, value: str, color: str, icon: str = "", parent=None):
        super().__init__(parent)
        
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {color}20;
                border: 2px solid {color};
                border-radius: 8px;
                padding: 10px;
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        title_label = QLabel(f"{icon} {title}")
        title_label.setStyleSheet(f"color: {color}; font-size: 11px; font-weight: bold;")
        layout.addWidget(title_label)
        
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(f"color: {color}; font-size: 18px; font-weight: bold;")
        layout.addWidget(self.value_label)
    
    def set_value(self, value: str):
        """Mettre à jour la valeur"""
        self.value_label.setText(value)


class CropComparisonWidget(QWidget):
    """
    Widget pour l'analyse de comparaison entre dossiers original et croppé
    """
    
    task_requested = pyqtSignal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.original_dir = None
        self.cropped_dir = None
        self.last_stats = None
        
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
        
        # 2. Sélection des dossiers
        folders_group = self._create_folders_selection()
        content_layout.addWidget(folders_group)
        
        # 3. Options
        options_group = self._create_options_group()
        content_layout.addWidget(options_group)
        
        # 4. Résultats (cartes de statistiques)
        results_group = self._create_results_group()
        content_layout.addWidget(results_group)
        
        # 5. Détails (tableau)
        details_group = self._create_details_group()
        content_layout.addWidget(details_group)
        
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
                background-color: #E8F5E9;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(banner)
        
        title = QLabel("📊 Analyseur de Comparaison Crop")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #2E7D32;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Compare le dossier original avec le dossier croppé pour identifier les modifications.\n\n"
            "• <b>Croppés</b>: Fichiers dont la taille a diminué (crop appliqué)\n"
            "• <b>Copiés</b>: Fichiers de taille identique (non modifiés)\n"
            "• <b>Manquants</b>: Fichiers absents du dossier croppé\n"
            "• <b>Erreur</b>: Fichiers dont la taille a augmenté (anormal)"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #388E3C; font-size: 11px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_folders_selection(self):
        """Créer la section de sélection des dossiers"""
        group = QGroupBox("📁 Sélection des Dossiers")
        group.setStyleSheet(self._get_group_style("#2196F3"))
        
        layout = QGridLayout()
        layout.setSpacing(10)
        
        # Dossier original
        layout.addWidget(QLabel("Dossier Original:"), 0, 0)
        
        self.original_label = QLabel("Non sélectionné")
        self.original_label.setStyleSheet(self._get_folder_label_style(False))
        layout.addWidget(self.original_label, 0, 1)
        
        btn_original = QPushButton("📂 Parcourir")
        btn_original.setStyleSheet(self._get_button_style("#2196F3"))
        btn_original.clicked.connect(self._browse_original)
        layout.addWidget(btn_original, 0, 2)
        
        # Info original
        self.original_info = QLabel("")
        self.original_info.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.original_info, 1, 1, 1, 2)
        
        # Dossier croppé
        layout.addWidget(QLabel("Dossier Croppé:"), 2, 0)
        
        self.cropped_label = QLabel("Non sélectionné")
        self.cropped_label.setStyleSheet(self._get_folder_label_style(False))
        layout.addWidget(self.cropped_label, 2, 1)
        
        btn_cropped = QPushButton("📂 Parcourir")
        btn_cropped.setStyleSheet(self._get_button_style("#FF9800"))
        btn_cropped.clicked.connect(self._browse_cropped)
        layout.addWidget(btn_cropped, 2, 2)
        
        # Info croppé
        self.cropped_info = QLabel("")
        self.cropped_info.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.cropped_info, 3, 1, 1, 2)
        
        # Bouton auto-detect
        btn_auto = QPushButton("🔍 Auto-détecter le dossier croppé")
        btn_auto.setToolTip("Cherche automatiquement un dossier _cropped correspondant")
        btn_auto.clicked.connect(self._auto_detect_cropped)
        layout.addWidget(btn_auto, 4, 0, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_options_group(self):
        """Créer les options d'analyse"""
        group = QGroupBox("⚙️ Options d'Analyse")
        group.setStyleSheet(self._get_group_style("#607D8B"))
        group.setCheckable(True)
        group.setChecked(False)
        
        layout = QHBoxLayout()
        
        layout.addWidget(QLabel("Seuil de différence:"))
        self.spin_threshold = QSpinBox()
        self.spin_threshold.setRange(100, 10000)
        self.spin_threshold.setValue(1024)
        self.spin_threshold.setSuffix(" bytes")
        self.spin_threshold.setToolTip("Différence de taille minimum pour considérer qu'un fichier a été croppé")
        layout.addWidget(self.spin_threshold)
        
        layout.addSpacing(20)
        
        self.check_export = QCheckBox("Exporter les listes de fichiers (.txt)")
        self.check_export.setChecked(True)
        layout.addWidget(self.check_export)
        
        layout.addStretch()
        
        group.setLayout(layout)
        return group
    
    def _create_results_group(self):
        """Créer la section des résultats"""
        group = QGroupBox("📈 Résultats de l'Analyse")
        group.setStyleSheet(self._get_group_style("#9C27B0"))
        
        layout = QVBoxLayout()
        
        # Cartes de statistiques
        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(10)
        
        self.card_total = StatCard("Total Analysés", "-", "#2196F3", "📁")
        cards_layout.addWidget(self.card_total)
        
        self.card_cropped = StatCard("Croppés", "-", "#4CAF50", "✂️")
        cards_layout.addWidget(self.card_cropped)
        
        self.card_copied = StatCard("Copiés", "-", "#FF9800", "📋")
        cards_layout.addWidget(self.card_copied)
        
        self.card_missing = StatCard("Manquants", "-", "#F44336", "❌")
        cards_layout.addWidget(self.card_missing)
        
        self.card_space = StatCard("Espace Économisé", "-", "#673AB7", "💾")
        cards_layout.addWidget(self.card_space)
        
        layout.addLayout(cards_layout)
        
        # Barres de progression visuelles
        bars_layout = QGridLayout()
        bars_layout.setSpacing(5)
        
        bars_layout.addWidget(QLabel("Croppés:"), 0, 0)
        self.progress_cropped = QProgressBar()
        self.progress_cropped.setStyleSheet(self._get_progress_style("#4CAF50"))
        self.progress_cropped.setTextVisible(True)
        self.progress_cropped.setFormat("%v%")
        bars_layout.addWidget(self.progress_cropped, 0, 1)
        
        bars_layout.addWidget(QLabel("Copiés:"), 1, 0)
        self.progress_copied = QProgressBar()
        self.progress_copied.setStyleSheet(self._get_progress_style("#FF9800"))
        self.progress_copied.setTextVisible(True)
        self.progress_copied.setFormat("%v%")
        bars_layout.addWidget(self.progress_copied, 1, 1)
        
        bars_layout.addWidget(QLabel("Manquants:"), 2, 0)
        self.progress_missing = QProgressBar()
        self.progress_missing.setStyleSheet(self._get_progress_style("#F44336"))
        self.progress_missing.setTextVisible(True)
        self.progress_missing.setFormat("%v%")
        bars_layout.addWidget(self.progress_missing, 2, 1)
        
        layout.addLayout(bars_layout)
        
        group.setLayout(layout)
        return group
    
    def _create_details_group(self):
        """Créer la section des détails"""
        group = QGroupBox("📋 Détails par Catégorie")
        group.setStyleSheet(self._get_group_style("#795548"))
        group.setCheckable(True)
        group.setChecked(False)
        
        layout = QVBoxLayout()
        
        # Onglets pour les différentes listes
        self.tabs_details = QTabWidget()
        
        # Table des fichiers croppés
        self.table_cropped = QTableWidget()
        self.table_cropped.setColumnCount(3)
        self.table_cropped.setHorizontalHeaderLabels(["Fichier", "Original", "Croppé"])
        self.table_cropped.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabs_details.addTab(self.table_cropped, "✂️ Croppés")
        
        # Table des fichiers copiés
        self.table_copied = QTableWidget()
        self.table_copied.setColumnCount(2)
        self.table_copied.setHorizontalHeaderLabels(["Fichier", "Taille"])
        self.table_copied.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabs_details.addTab(self.table_copied, "📋 Copiés")
        
        # Table des fichiers manquants
        self.table_missing = QTableWidget()
        self.table_missing.setColumnCount(2)
        self.table_missing.setHorizontalHeaderLabels(["Fichier", "Taille Originale"])
        self.table_missing.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabs_details.addTab(self.table_missing, "❌ Manquants")
        
        layout.addWidget(self.tabs_details)
        
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
        
        self.btn_analyze = QPushButton("🔍 Lancer l'Analyse")
        self.btn_analyze.setStyleSheet("""
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
                background-color: #388E3C;
            }
            QPushButton:disabled {
                background-color: #BDBDBD;
            }
        """)
        self.btn_analyze.clicked.connect(self._start_analysis)
        self.btn_analyze.setEnabled(False)
        layout.addWidget(self.btn_analyze)
        
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
    
    def _get_progress_style(self, color: str) -> str:
        """Style pour les barres de progression"""
        return f"""
            QProgressBar {{
                border: 1px solid #DDD;
                border-radius: 4px;
                text-align: center;
                background-color: #F5F5F5;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """
    
    def _browse_original(self):
        """Parcourir pour le dossier original"""
        folder = QFileDialog.getExistingDirectory(
            self, "Sélectionner le dossier original", "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self.original_dir = folder
            folder_name = os.path.basename(folder)
            self.original_label.setText(f"📁 {folder_name}")
            self.original_label.setToolTip(folder)
            self.original_label.setStyleSheet(self._get_folder_label_style(True))
            
            # Analyser le dossier
            info = self._analyze_folder(folder)
            self.original_info.setText(f"📷 {info['count']:,} images | 💾 {info['size_mb']:.1f} MB")
            
            self._check_ready()
    
    def _browse_cropped(self):
        """Parcourir pour le dossier croppé"""
        folder = QFileDialog.getExistingDirectory(
            self, "Sélectionner le dossier croppé", "",
            QFileDialog.Option.ShowDirsOnly
        )
        
        if folder:
            self.cropped_dir = folder
            folder_name = os.path.basename(folder)
            self.cropped_label.setText(f"📁 {folder_name}")
            self.cropped_label.setToolTip(folder)
            self.cropped_label.setStyleSheet(self._get_folder_label_style(True))
            
            # Analyser le dossier
            info = self._analyze_folder(folder)
            self.cropped_info.setText(f"📷 {info['count']:,} images | 💾 {info['size_mb']:.1f} MB")
            
            # Vérifier rapport existant
            report_path = os.path.join(folder, "crop_comparison_report.json")
            self.btn_view_report.setEnabled(os.path.exists(report_path))
            
            self._check_ready()
    
    def _auto_detect_cropped(self):
        """Auto-détecter le dossier croppé"""
        if not self.original_dir:
            QMessageBox.warning(self, "Dossier manquant", "Sélectionnez d'abord le dossier original.")
            return
        
        # Chercher un dossier _cropped
        parent_dir = os.path.dirname(self.original_dir)
        original_name = os.path.basename(self.original_dir)
        
        possible_names = [
            f"{original_name}_cropped",
            f"{original_name}-cropped",
            f"{original_name}_crop",
            "cropped",
            "frames_cropped"
        ]
        
        for name in possible_names:
            cropped_path = os.path.join(parent_dir, name)
            if os.path.exists(cropped_path) and os.path.isdir(cropped_path):
                self.cropped_dir = cropped_path
                self.cropped_label.setText(f"📁 {name}")
                self.cropped_label.setToolTip(cropped_path)
                self.cropped_label.setStyleSheet(self._get_folder_label_style(True))
                
                info = self._analyze_folder(cropped_path)
                self.cropped_info.setText(f"📷 {info['count']:,} images | 💾 {info['size_mb']:.1f} MB")
                
                report_path = os.path.join(cropped_path, "crop_comparison_report.json")
                self.btn_view_report.setEnabled(os.path.exists(report_path))
                
                self._check_ready()
                
                QMessageBox.information(self, "Trouvé!", f"Dossier croppé détecté:\n{cropped_path}")
                return
        
        QMessageBox.warning(self, "Non trouvé", "Aucun dossier croppé trouvé automatiquement.\nSélectionnez-le manuellement.")
    
    def _analyze_folder(self, folder: str) -> dict:
        """Analyser un dossier (nombre d'images et taille)"""
        extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        count = 0
        total_size = 0
        
        for f in os.listdir(folder):
            filepath = os.path.join(folder, f)
            if os.path.isfile(filepath) and os.path.splitext(f)[1].lower() in extensions:
                count += 1
                total_size += os.path.getsize(filepath)
        
        return {
            'count': count,
            'size_mb': total_size / (1024 * 1024)
        }
    
    def _check_ready(self):
        """Vérifier si prêt pour l'analyse"""
        ready = self.original_dir is not None and self.cropped_dir is not None
        self.btn_analyze.setEnabled(ready)
    
    def _update_results(self, stats: dict):
        """Mettre à jour l'affichage des résultats"""
        self.last_stats = stats
        
        totals = stats['totals']
        pcts = stats['percentages']
        space = stats['space']
        
        # Cartes
        self.card_total.set_value(f"{totals['total_files']:,}")
        self.card_cropped.set_value(f"{totals['files_cropped']:,}")
        self.card_copied.set_value(f"{totals['files_copied']:,}")
        self.card_missing.set_value(f"{totals['files_missing']:,}")
        self.card_space.set_value(f"{space['reduction_mb']:.1f} MB")
        
        # Barres de progression
        self.progress_cropped.setValue(int(pcts['cropped']))
        self.progress_copied.setValue(int(pcts['copied']))
        self.progress_missing.setValue(int(pcts['missing']))
        
        # Tables (échantillons)
        file_lists = stats.get('file_lists', {})
        
        # Table croppés
        cropped_files = file_lists.get('cropped', [])[:100]
        self.table_cropped.setRowCount(len(cropped_files))
        for i, filename in enumerate(cropped_files):
            self.table_cropped.setItem(i, 0, QTableWidgetItem(filename))
            self.table_cropped.setItem(i, 1, QTableWidgetItem("-"))
            self.table_cropped.setItem(i, 2, QTableWidgetItem("-"))
        
        # Table copiés
        copied_files = file_lists.get('copied', [])[:100]
        self.table_copied.setRowCount(len(copied_files))
        for i, filename in enumerate(copied_files):
            self.table_copied.setItem(i, 0, QTableWidgetItem(filename))
            self.table_copied.setItem(i, 1, QTableWidgetItem("-"))
        
        # Table manquants
        missing_files = file_lists.get('missing', [])[:100]
        self.table_missing.setRowCount(len(missing_files))
        for i, filename in enumerate(missing_files):
            self.table_missing.setItem(i, 0, QTableWidgetItem(filename))
            self.table_missing.setItem(i, 1, QTableWidgetItem("-"))
    
    def _view_last_report(self):
        """Voir le dernier rapport"""
        if not self.cropped_dir:
            return
        
        report_path = os.path.join(self.cropped_dir, "crop_comparison_report.json")
        
        if not os.path.exists(report_path):
            QMessageBox.warning(self, "Rapport non trouvé", "Aucun rapport trouvé.")
            return
        
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report = json.load(f)
            
            # Mettre à jour l'affichage avec les stats du rapport
            if 'statistics' in report:
                self._update_results(report['statistics'])
            
            # Afficher le dialogue
            dialog = QDialog(self)
            dialog.setWindowTitle("📄 Rapport de Comparaison")
            dialog.setMinimumSize(600, 500)
            
            layout = QVBoxLayout(dialog)
            
            text = QTextEdit()
            text.setReadOnly(True)
            
            stats = report.get('statistics', {})
            info = report.get('analysis_info', {})
            
            content = f"""📊 RAPPORT DE COMPARAISON CROP
{'='*50}

📁 Dossier original: {info.get('original_directory', '?')}
📁 Dossier croppé: {info.get('cropped_directory', '?')}
🕐 Date: {info.get('timestamp', '?')}

📈 STATISTIQUES
{'-'*30}
• Total analysés: {stats.get('totals', {}).get('total_files', 0):,}
• Croppés: {stats.get('totals', {}).get('files_cropped', 0):,} ({stats.get('percentages', {}).get('cropped', 0):.1f}%)
• Copiés: {stats.get('totals', {}).get('files_copied', 0):,} ({stats.get('percentages', {}).get('copied', 0):.1f}%)
• Manquants: {stats.get('totals', {}).get('files_missing', 0):,} ({stats.get('percentages', {}).get('missing', 0):.1f}%)

💾 ESPACE
{'-'*30}
• Taille originale: {stats.get('space', {}).get('original_mb', 0):.1f} MB
• Taille croppée: {stats.get('space', {}).get('cropped_mb', 0):.1f} MB
• Économie: {stats.get('space', {}).get('reduction_mb', 0):.1f} MB ({stats.get('space', {}).get('reduction_pct', 0):.1f}%)
"""
            
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
        if not self.original_dir or not self.cropped_dir:
            QMessageBox.warning(self, "Dossiers requis", "Sélectionnez les deux dossiers.")
            return
        
        try:
            from tasks.crop_comparison_task import CropComparisonTask
            
            task = CropComparisonTask()
            task.configure(
                original_dir=self.original_dir,
                cropped_dir=self.cropped_dir,
                size_threshold=self.spin_threshold.value(),
                export_lists=self.check_export.isChecked()
            )
            
            self.task_requested.emit(task)
            
            QMessageBox.information(
                self,
                "Tâche ajoutée",
                f"✅ La tâche d'analyse de comparaison a été ajoutée.\n\n"
                f"Original: {os.path.basename(self.original_dir)}\n"
                f"Croppé: {os.path.basename(self.cropped_dir)}\n\n"
                "Cliquez sur 'Démarrer Pipeline' pour lancer."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Erreur:\n{str(e)}")