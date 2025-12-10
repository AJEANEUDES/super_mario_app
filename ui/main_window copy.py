"""
Main Window - Fenêtre principale de l'application Pipeline Manager
"""

import sys
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
    QPushButton, QLabel, QTextEdit, QTableWidget, QTableWidgetItem,
    QProgressBar, QGroupBox, QSplitter, QMessageBox, QHeaderView,
    QTabWidget, QLineEdit, QSpinBox, QFormLayout, QComboBox, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor
import pandas as pd

from pipeline_manager import PipelineManager
from tasks.base_task import TaskStatus
from tasks.scraper_task import ScraperTask, SCRAPER_AVAILABLE

class MainWindow(QMainWindow):
    """Fenêtre principale de l'application"""
    
    # Signaux pour thread-safety
    task_started_signal = pyqtSignal(object)
    task_completed_signal = pyqtSignal(object)
    task_progress_signal = pyqtSignal(object, int, str)
    pipeline_completed_signal = pyqtSignal(dict)
    
    def __init__(self):
        super().__init__()
        
        # Initialiser le pipeline manager
        self.pipeline_manager = PipelineManager()
        self._setup_pipeline_callbacks()
        
        # Thème (par défaut: clair)
        self.current_theme = "light"
        
        # UI
        self.setWindowTitle("🎮 Speedrun Pipeline Manager - Extraction & Analysis")
        self.setGeometry(100, 100, 1400, 900)
        self.setMinimumSize(1200, 700)
        
        # Connecter les signaux
        self.task_started_signal.connect(self._on_task_started_ui)
        self.task_completed_signal.connect(self._on_task_completed_ui)
        self.task_progress_signal.connect(self._on_task_progress_ui)
        self.pipeline_completed_signal.connect(self._on_pipeline_completed_ui)
        
        # Créer l'interface
        self._create_ui()
        
        # Appliquer le thème clair par défaut
        self._apply_light_theme()
        
        # Timer pour refresh UI
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self._refresh_ui)
        self.refresh_timer.start(500)  # Refresh toutes les 500ms
        
        # Afficher statut initial
        self._update_status_display()
    
    def _create_ui(self):
        """Créer l'interface utilisateur"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Header
        self._create_header(main_layout)
        
        # Splitter principal (gauche/droite)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        main_layout.addWidget(splitter)
        
        # Panel gauche - Configuration
        left_panel = self._create_left_panel()
        splitter.addWidget(left_panel)
        
        # Panel droit - Monitoring
        right_panel = self._create_right_panel()
        splitter.addWidget(right_panel)
        
        # Proportions du splitter
        splitter.setSizes([500, 900])
        
        # Status bar
        self._create_status_bar(main_layout)
    
    def _create_header(self, layout):
        """Créer le header de l'application"""
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 5, 10, 5)
        
        # Titre
        title_label = QLabel("🎮 Speedrun Pipeline Manager")
        title_font = QFont("Arial", 18, QFont.Weight.Bold)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        # Bouton de thème
        self.theme_button = QPushButton("🌙 Mode Sombre")
        self.theme_button.setMaximumWidth(150)
        self.theme_button.setMinimumHeight(30)
        self.theme_button.clicked.connect(self._toggle_theme)
        header_layout.addWidget(self.theme_button)
        
        # Version et status
        version_label = QLabel("v2.2.0 - UI Complete")
        version_label.setStyleSheet("color: gray; font-size: 11px;")
        header_layout.addWidget(version_label)
        
        layout.addWidget(header_widget)
    
    def _create_left_panel(self):
        """Créer le panel de configuration (gauche)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Titre du panel
        title_label = QLabel("⚙️ Configuration des Tâches")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title_label)
        
        # Tabs pour différents types de tâches
        tabs = QTabWidget()
        layout.addWidget(tabs)
        
        # Tab 1: Extraction Speedrun
        if SCRAPER_AVAILABLE:
            scraper_tab = self._create_scraper_config_tab()
            tabs.addTab(scraper_tab, "📊 Extraction Speedrun")
        else:
            error_tab = QLabel("❌ Module scraper.py non disponible\n\n"
                             "Placez scraper.py dans le dossier de l'application")
            error_tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            error_tab.setStyleSheet("color: red; padding: 20px;")
            tabs.addTab(error_tab, "❌ Extraction")
        
        # Tab 2: Téléchargement
        try:
            from tasks.download_task import YT_DLP_AVAILABLE
            if YT_DLP_AVAILABLE:
                download_tab = self._create_download_config_tab()
                tabs.addTab(download_tab, "⬇️ Téléchargement")
            else:
                error_tab = QLabel("❌ Module yt-dlp non disponible\n\n"
                                 "Installez-le avec:\npip install yt-dlp --break-system-packages")
                error_tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
                error_tab.setStyleSheet("color: red; padding: 20px;")
                tabs.addTab(error_tab, "❌ Téléchargement")
        except ImportError:
            error_tab = QLabel("❌ Module de téléchargement non disponible")
            error_tab.setAlignment(Qt.AlignmentFlag.AlignCenter)
            tabs.addTab(error_tab, "⬇️ Téléchargement")
        
        # Tab 3: Visualisation
        viewer_tab = self._create_viewer_config_tab()
        tabs.addTab(viewer_tab, "👁️ Visualisation")
        
        # Tab 4: Métriques
        metrics_tab = self._create_metrics_config_tab()
        tabs.addTab(metrics_tab, "📈 Métriques")
        
        return panel
    
    def _create_scraper_config_tab(self):
        """Créer le tab de configuration du scraper"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Form layout
        form_group = QGroupBox("Paramètres d'extraction")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # URL Speedrun
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("https://www.speedrun.com/smb1?h=Any-NTSC")
        self.url_input.setMinimumHeight(30)
        form_layout.addRow("URL Speedrun.com:", self.url_input)
        
        # Page de départ
        self.start_page_input = QSpinBox()
        self.start_page_input.setMinimum(1)
        self.start_page_input.setMaximum(100)
        self.start_page_input.setValue(1)
        self.start_page_input.setMinimumHeight(30)
        form_layout.addRow("Page de départ:", self.start_page_input)
        
        # Page de fin
        self.end_page_input = QSpinBox()
        self.end_page_input.setMinimum(1)
        self.end_page_input.setMaximum(100)
        self.end_page_input.setValue(3)
        self.end_page_input.setMinimumHeight(30)
        form_layout.addRow("Page de fin:", self.end_page_input)
        
        # Nom du projet
        self.project_name_input = QLineEdit()
        self.project_name_input.setPlaceholderText("SMB_speedruns")
        self.project_name_input.setText("SMB_speedruns")
        self.project_name_input.setMinimumHeight(30)
        form_layout.addRow("Nom du projet:", self.project_name_input)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Info box améliorée avec meilleur style
        self.info_label = QLabel(
            "<b>💡 Astuces d'utilisation</b><br><br>"
            "• <b>~25 runs</b> par page<br>"
            "• Pages 1-3 = <b>Top 75 runs</b><br>"
            "• Maximum <b>50 pages</b> par extraction<br>"
            "• <b>2 secondes</b> de délai entre pages"
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        layout.addStretch()
        
        # Bouton ajouter à la queue
        add_button = QPushButton("➕ Ajouter à la Queue")
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 12px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
        """)
        add_button.clicked.connect(self._add_scraper_task)
        layout.addWidget(add_button)
        
        return tab
    
    def _create_download_config_tab(self):
        """Créer le tab de configuration du téléchargement"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Form layout
        form_group = QGroupBox("Paramètres de téléchargement")
        form_layout = QFormLayout()
        form_layout.setSpacing(10)
        
        # Sélection du fichier CSV avec bouton Parcourir
        csv_layout = QHBoxLayout()
        
        self.csv_path_label = QLabel("Aucun fichier sélectionné")
        self.csv_path_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
        """)
        self.csv_path_label.setWordWrap(True)
        csv_layout.addWidget(self.csv_path_label, 1)
        
        browse_btn = QPushButton("📁 Parcourir...")
        browse_btn.setMinimumWidth(120)
        browse_btn.setMinimumHeight(35)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        browse_btn.clicked.connect(self._browse_csv_file)
        csv_layout.addWidget(browse_btn)
        
        form_layout.addRow("Fichier CSV:", csv_layout)
        
        # Stocker le chemin du fichier sélectionné
        self.selected_csv_path = None
        
        # Nom du jeu
        self.game_name_input = QLineEdit()
        self.game_name_input.setPlaceholderText("SMB")
        self.game_name_input.setText("SMB")
        self.game_name_input.setMinimumHeight(30)
        form_layout.addRow("Nom du jeu:", self.game_name_input)
        
        # Format vidéo
        self.video_format_combo = QComboBox()
        self.video_format_combo.addItems([
            "best",
            "bestvideo+bestaudio/best",
            "best[height<=720]",
            "best[height<=1080]"
        ])
        self.video_format_combo.setCurrentIndex(1)  # bestvideo+bestaudio par défaut
        self.video_format_combo.setMinimumHeight(30)
        form_layout.addRow("Format vidéo:", self.video_format_combo)
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Info CSV
        info_group = QGroupBox("Informations CSV")
        info_layout = QVBoxLayout()
        
        self.csv_info_label = QLabel("Aucun fichier sélectionné")
        self.csv_info_label.setWordWrap(True)
        self.csv_info_label.setStyleSheet("padding: 10px; background-color: #F5F5F5; border-radius: 4px;")
        info_layout.addWidget(self.csv_info_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Info box
        self.download_info_label = QLabel(
            "<b>💡 Astuces de téléchargement</b><br><br>"
            "• Utilise <b>yt-dlp</b> pour télécharger<br>"
            "• Organisé par <b>joueur</b><br>"
            "• Délai de <b>2 secondes</b> entre vidéos<br>"
            "• Supporte <b>YouTube, Twitch, etc.</b>"
        )
        self.download_info_label.setWordWrap(True)
        layout.addWidget(self.download_info_label)
        
        layout.addStretch()
        
        # Bouton ajouter à la queue
        add_button = QPushButton("➕ Ajouter à la Queue")
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 12px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:pressed {
                background-color: #E65100;
            }
        """)
        add_button.clicked.connect(self._add_download_task)
        layout.addWidget(add_button)
        
        return tab
    
    def _browse_csv_file(self):
        """Ouvrir un dialogue pour sélectionner un fichier CSV"""
        # Ouvrir le dialogue de sélection de fichier
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier CSV",
            "",  # Dossier de départ (vide = dossier courant)
            "Fichiers CSV (*.csv);;Tous les fichiers (*.*)"
        )
        
        if file_path:
            self.selected_csv_path = file_path
            
            # Afficher le nom du fichier (pas le chemin complet)
            filename = os.path.basename(file_path)
            self.csv_path_label.setText(filename)
            self.csv_path_label.setToolTip(file_path)  # Le chemin complet en tooltip
            
            # Analyser et afficher les infos du CSV
            self._analyze_selected_csv(file_path)
    
    def _analyze_selected_csv(self, csv_path):
        """Analyser le CSV sélectionné et afficher les informations"""
        if not os.path.exists(csv_path):
            self.csv_info_label.setText("❌ Fichier introuvable")
            return
        
        try:
            # Lire le CSV
            df = pd.read_csv(csv_path)
            
            # Compter vidéos valides
            valid_videos = df[(df['video_url'].notna()) & (df['video_url'] != '')]
            total_runs = len(df)
            videos_count = len(valid_videos)
            
            # Extraire catégorie si disponible
            category = df['category'].iloc[0] if 'category' in df.columns and len(df) > 0 else "N/A"
            
            # Afficher les infos
            info_text = f"""
<b>📊 Informations du fichier</b><br><br>
<b>Fichier:</b> {os.path.basename(csv_path)}<br>
<b>Total runs:</b> {total_runs}<br>
<b>Vidéos disponibles:</b> {videos_count}<br>
<b>Catégorie:</b> {category}<br>
<b>Taille:</b> {os.path.getsize(csv_path) / 1024:.1f} KB
            """
            
            self.csv_info_label.setText(info_text.strip())
            
        except Exception as e:
            self.csv_info_label.setText(f"❌ Erreur lecture: {str(e)[:50]}")
    
    def _add_download_task(self):
        """Ajouter une tâche de téléchargement"""
        # Vérifier qu'un fichier est sélectionné
        if not self.selected_csv_path:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un fichier CSV")
            return
        
        csv_path = self.selected_csv_path
        
        if not os.path.exists(csv_path):
            QMessageBox.warning(self, "Erreur", "Fichier CSV introuvable")
            return
        
        # Récupérer paramètres
        game_name = self.game_name_input.text().strip()
        if not game_name:
            game_name = "game"
        
        video_format = self.video_format_combo.currentText()
        
        # Importer DownloadTask
        try:
            from tasks.download_task import DownloadTask
        except ImportError:
            QMessageBox.critical(self, "Erreur", "Module de téléchargement non disponible")
            return
        
        # Créer la tâche
        task = DownloadTask(
            csv_file=csv_path,
            game_name=game_name,
            video_format=video_format
        )
        
        # Configurer callback de log
        task.set_log_callback(self._on_task_log)
        
        # Ajouter au pipeline
        self.pipeline_manager.add_task(task)
        
        # Log
        self._add_log(f"✅ Tâche ajoutée: {task.name}", "INFO")
        
        # Refresh UI
        self._refresh_tasks_table()
        self._update_status_display()
    
    def _create_viewer_config_tab(self):
        """Créer le tab de visualisation CSV"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Form layout
        form_group = QGroupBox("Visualisation de données")
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)
        
        # Sélection fichier
        file_layout = QHBoxLayout()
        
        self.viewer_csv_label = QLabel("Aucun fichier sélectionné")
        self.viewer_csv_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
        """)
        self.viewer_csv_label.setWordWrap(True)
        file_layout.addWidget(self.viewer_csv_label, 1)
        
        browse_btn = QPushButton("📁 Parcourir...")
        browse_btn.setMinimumWidth(120)
        browse_btn.setMinimumHeight(35)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        browse_btn.clicked.connect(self._browse_viewer_csv)
        file_layout.addWidget(browse_btn)
        
        form_layout.addLayout(file_layout)
        
        self.viewer_csv_path = None
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Info
        info_label = QLabel(
            "<b>👁️ Visualisation de données</b><br><br>"
            "• Affiche les données du CSV<br>"
            "• Limite à <b>1000 lignes</b><br>"
            "• Toutes les colonnes affichées<br>"
            "• Utile pour <b>vérifier les données</b>"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            QLabel {
                padding: 15px;
                background-color: #F3E5F5;
                border: 2px solid #9C27B0;
                border-radius: 8px;
                font-size: 12px;
                line-height: 1.8;
                color: #4A148C;
            }
        """)
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # Bouton
        add_button = QPushButton("➕ Ajouter à la Queue")
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 12px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #7B1FA2;
            }
        """)
        add_button.clicked.connect(self._add_viewer_task)
        layout.addWidget(add_button)
        
        return tab
    
    def _browse_viewer_csv(self):
        """Parcourir pour visualisation"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier CSV à visualiser",
            "",
            "Fichiers CSV (*.csv);;Tous les fichiers (*.*)"
        )
        
        if file_path:
            self.viewer_csv_path = file_path
            filename = os.path.basename(file_path)
            self.viewer_csv_label.setText(filename)
            self.viewer_csv_label.setToolTip(file_path)
    
    def _add_viewer_task(self):
        """Ajouter une tâche de visualisation"""
        if not self.viewer_csv_path:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un fichier CSV")
            return
        
        if not os.path.exists(self.viewer_csv_path):
            QMessageBox.warning(self, "Erreur", "Fichier CSV introuvable")
            return
        
        from tasks.viewer_task import ViewerTask
        
        task = ViewerTask(csv_file=self.viewer_csv_path, parent_window=self)
        task.set_log_callback(self._on_task_log)
        
        self.pipeline_manager.add_task(task)
        self._add_log(f"✅ Tâche ajoutée: {task.name}", "INFO")
        
        self._refresh_tasks_table()
        self._update_status_display()
    
    def _create_metrics_config_tab(self):
        """Créer le tab de calcul de métriques"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Form layout
        form_group = QGroupBox("Calcul de métriques")
        form_layout = QVBoxLayout()
        form_layout.setSpacing(10)
        
        # Sélection fichier
        file_layout = QHBoxLayout()
        
        self.metrics_csv_label = QLabel("Aucun fichier sélectionné")
        self.metrics_csv_label.setStyleSheet("""
            QLabel {
                padding: 8px;
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
        """)
        self.metrics_csv_label.setWordWrap(True)
        file_layout.addWidget(self.metrics_csv_label, 1)
        
        browse_btn = QPushButton("📁 Parcourir...")
        browse_btn.setMinimumWidth(120)
        browse_btn.setMinimumHeight(35)
        browse_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        browse_btn.clicked.connect(self._browse_metrics_csv)
        file_layout.addWidget(browse_btn)
        
        form_layout.addLayout(file_layout)
        
        self.metrics_csv_path = None
        
        form_group.setLayout(form_layout)
        layout.addWidget(form_group)
        
        # Info
        info_label = QLabel(
            "<b>📈 Métriques calculées</b><br><br>"
            "<b>Statistiques de base:</b><br>"
            "• Total runs, joueurs uniques, plateformes<br>"
            "• Meilleur/moyen/pire temps<br><br>"
            "<b>Métriques avancées:</b><br>"
            "• Top players, distribution plateformes<br>"
            "• Évolution temporelle, records par catégorie"
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("""
            QLabel {
                padding: 15px;
                background-color: #E8F5E9;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                font-size: 12px;
                line-height: 1.8;
                color: #1B5E20;
            }
        """)
        layout.addWidget(info_label)
        
        layout.addStretch()
        
        # Bouton
        add_button = QPushButton("➕ Ajouter à la Queue")
        add_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 12px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        add_button.clicked.connect(self._add_metrics_task)
        layout.addWidget(add_button)
        
        return tab
    
    def _browse_metrics_csv(self):
        """Parcourir pour métriques"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Sélectionner un fichier CSV pour analyse",
            "",
            "Fichiers CSV (*.csv);;Tous les fichiers (*.*)"
        )
        
        if file_path:
            self.metrics_csv_path = file_path
            filename = os.path.basename(file_path)
            self.metrics_csv_label.setText(filename)
            self.metrics_csv_label.setToolTip(file_path)
    
    def _add_metrics_task(self):
        """Ajouter une tâche de calcul de métriques"""
        if not self.metrics_csv_path:
            QMessageBox.warning(self, "Erreur", "Veuillez sélectionner un fichier CSV")
            return
        
        if not os.path.exists(self.metrics_csv_path):
            QMessageBox.warning(self, "Erreur", "Fichier CSV introuvable")
            return
        
        from tasks.metrics_task import MetricsTask
        
        task = MetricsTask(csv_file=self.metrics_csv_path, parent_window=self)
        task.set_log_callback(self._on_task_log)
        
        self.pipeline_manager.add_task(task)
        self._add_log(f"✅ Tâche ajoutée: {task.name}", "INFO")
        
        self._refresh_tasks_table()
        self._update_status_display()
    
    def _create_right_panel(self):
        """Créer le panel de monitoring (droite)"""
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Titre
        title_label = QLabel("📊 Monitoring du Pipeline")
        title_label.setStyleSheet("font-size: 14px; font-weight: bold; padding: 5px;")
        layout.addWidget(title_label)
        
        # Contrôles du pipeline
        controls_widget = self._create_pipeline_controls()
        layout.addWidget(controls_widget)
        
        # Splitter vertical (haut/bas)
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        layout.addWidget(v_splitter)
        
        # Haut - Table des tâches
        tasks_group = QGroupBox("📋 Queue de Tâches")
        tasks_layout = QVBoxLayout()
        
        self.tasks_table = QTableWidget()
        self.tasks_table.setColumnCount(6)
        self.tasks_table.setHorizontalHeaderLabels([
            "Nom", "Status", "Progression", "Priorité", "Durée", "Message"
        ])
        self.tasks_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tasks_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.tasks_table.setAlternatingRowColors(True)
        self.tasks_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        
        tasks_layout.addWidget(self.tasks_table)
        tasks_group.setLayout(tasks_layout)
        v_splitter.addWidget(tasks_group)
        
        # Bas - Logs
        logs_group = QGroupBox("📝 Logs d'Exécution")
        logs_layout = QVBoxLayout()
        
        self.logs_text = QTextEdit()
        self.logs_text.setReadOnly(True)
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: 'Courier New', monospace;
                font-size: 11px;
            }
        """)
        logs_layout.addWidget(self.logs_text)
        logs_group.setLayout(logs_layout)
        v_splitter.addWidget(logs_group)
        
        # Proportions
        v_splitter.setSizes([400, 300])
        
        return panel
    
    def _create_pipeline_controls(self):
        """Créer les contrôles du pipeline"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Bouton Start
        self.start_button = QPushButton("▶️ Démarrer Pipeline")
        self.start_button.setMinimumHeight(40)
        self.start_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.start_button.clicked.connect(self._start_pipeline)
        layout.addWidget(self.start_button)
        
        # Bouton Pause
        self.pause_button = QPushButton("⏸️ Pause")
        self.pause_button.setMinimumHeight(40)
        self.pause_button.setEnabled(False)
        self.pause_button.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.pause_button.clicked.connect(self._toggle_pause)
        layout.addWidget(self.pause_button)
        
        # Bouton Stop
        self.stop_button = QPushButton("⏹️ Arrêter")
        self.stop_button.setMinimumHeight(40)
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.stop_button.clicked.connect(self._stop_pipeline)
        layout.addWidget(self.stop_button)
        
        # Bouton Clear
        clear_button = QPushButton("🗑️ Nettoyer")
        clear_button.setMinimumHeight(40)
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                font-size: 13px;
                font-weight: bold;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        clear_button.clicked.connect(self._clear_completed)
        layout.addWidget(clear_button)
        
        return widget
    
    def _create_status_bar(self, layout):
        """Créer la barre de status"""
        status_widget = QWidget()
        status_layout = QHBoxLayout(status_widget)
        status_layout.setContentsMargins(10, 5, 10, 5)
        
        # Status général
        self.status_label = QLabel("🟢 Prêt")
        self.status_label.setStyleSheet("font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        status_layout.addStretch()
        
        # Statistiques
        self.stats_label = QLabel("Tâches: 0 en attente | 0 complétées | 0 échouées")
        self.stats_label.setStyleSheet("color: gray;")
        status_layout.addWidget(self.stats_label)
        
        # Progress bar
        self.main_progress = QProgressBar()
        self.main_progress.setMaximumWidth(300)
        self.main_progress.setMinimumHeight(20)
        self.main_progress.setValue(0)
        status_layout.addWidget(self.main_progress)
        
        layout.addWidget(status_widget)
    
    def _setup_pipeline_callbacks(self):
        """Configurer les callbacks du pipeline manager"""
        self.pipeline_manager.set_callbacks(
            on_task_started=lambda task: self.task_started_signal.emit(task),
            on_task_completed=lambda task: self.task_completed_signal.emit(task),
            on_task_failed=lambda task: self.task_completed_signal.emit(task),
            on_pipeline_completed=lambda stats: self.pipeline_completed_signal.emit(stats),
            on_pipeline_progress=lambda task, prog, msg: self.task_progress_signal.emit(task, prog, msg)
        )
    
    def _add_scraper_task(self):
        """Ajouter une tâche de scraping"""
        # Récupérer les valeurs
        url = self.url_input.text().strip()
        start_page = self.start_page_input.value()
        end_page = self.end_page_input.value()
        project_name = self.project_name_input.text().strip()
        
        # Validation basique
        if not url:
            QMessageBox.warning(self, "Erreur", "Veuillez entrer une URL speedrun.com")
            return
        
        if not url.startswith('http'):
            QMessageBox.warning(self, "Erreur", "URL invalide")
            return
        
        if end_page < start_page:
            QMessageBox.warning(self, "Erreur", "La page de fin doit être >= page de départ")
            return
        
        if not project_name:
            project_name = "speedrun_data"
        
        # Créer la tâche
        task = ScraperTask(
            speedrun_url=url,
            start_page=start_page,
            end_page=end_page,
            project_name=project_name
        )
        
        # Configurer callback de log
        task.set_log_callback(self._on_task_log)
        
        # Ajouter au pipeline
        self.pipeline_manager.add_task(task)
        
        # Log
        self._add_log(f"✅ Tâche ajoutée: {task.name}", "INFO")
        
        # Refresh UI
        self._refresh_tasks_table()
        self._update_status_display()
    
    def _start_pipeline(self):
        """Démarrer le pipeline"""
        if self.pipeline_manager.task_queue.empty():
            QMessageBox.warning(self, "Erreur", "Aucune tâche dans la queue")
            return
        
        self._add_log("🚀 Démarrage du pipeline...", "INFO")
        self.pipeline_manager.start_pipeline()
        
        # Update UI
        self.start_button.setEnabled(False)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self.status_label.setText("🟡 Pipeline en cours...")
    
    def _toggle_pause(self):
        """Basculer pause/resume"""
        if self.pipeline_manager.is_paused:
            self.pipeline_manager.resume_pipeline()
            self.pause_button.setText("⏸️ Pause")
            self.status_label.setText("🟡 Pipeline en cours...")
            self._add_log("▶️ Pipeline repris", "INFO")
        else:
            self.pipeline_manager.pause_pipeline()
            self.pause_button.setText("▶️ Reprendre")
            self.status_label.setText("🟠 Pipeline en pause")
            self._add_log("⏸️ Pipeline en pause", "INFO")
    
    def _stop_pipeline(self):
        """Arrêter le pipeline"""
        reply = QMessageBox.question(
            self,
            "Confirmation",
            "Voulez-vous vraiment arrêter le pipeline en cours ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self._add_log("🛑 Arrêt du pipeline...", "WARNING")
            self.pipeline_manager.cancel_pipeline()
    
    def _clear_completed(self):
        """Nettoyer les tâches terminées"""
        self.pipeline_manager.clear_completed_tasks()
        self._refresh_tasks_table()
        self._update_status_display()
        self._add_log("🗑️ Tâches terminées nettoyées", "INFO")
    
    def _refresh_ui(self):
        """Refresh périodique de l'UI"""
        self._refresh_tasks_table()
        self._update_status_display()
    
    def _refresh_tasks_table(self):
        """Rafraîchir la table des tâches"""
        self.tasks_table.setRowCount(0)
        
        for task in self.pipeline_manager.tasks:
            row = self.tasks_table.rowCount()
            self.tasks_table.insertRow(row)
            
            # Nom
            self.tasks_table.setItem(row, 0, QTableWidgetItem(task.name))
            
            # Status avec couleur
            status_item = QTableWidgetItem(task.status.value)
            if task.status == TaskStatus.COMPLETED:
                status_item.setBackground(QColor("#4CAF50"))
                status_item.setForeground(QColor("white"))
            elif task.status == TaskStatus.FAILED:
                status_item.setBackground(QColor("#f44336"))
                status_item.setForeground(QColor("white"))
            elif task.status == TaskStatus.RUNNING:
                status_item.setBackground(QColor("#FF9800"))
                status_item.setForeground(QColor("white"))
            self.tasks_table.setItem(row, 1, status_item)
            
            # Progression
            prog_text = f"{task.progress}%"
            self.tasks_table.setItem(row, 2, QTableWidgetItem(prog_text))
            
            # Priorité
            self.tasks_table.setItem(row, 3, QTableWidgetItem(task.priority.name))
            
            # Durée
            duration = task.get_duration()
            duration_text = f"{duration:.1f}s" if duration else "-"
            self.tasks_table.setItem(row, 4, QTableWidgetItem(duration_text))
            
            # Message
            self.tasks_table.setItem(row, 5, QTableWidgetItem(task.progress_message))
    
    def _update_status_display(self):
        """Mettre à jour l'affichage du status"""
        stats = self.pipeline_manager.get_pipeline_stats()
        
        # Stats label
        stats_text = (
            f"Tâches: {stats['pending']} en attente | "
            f"{stats['completed']} complétées | "
            f"{stats['failed']} échouées"
        )
        self.stats_label.setText(stats_text)
        
        # Status label
        if stats['is_running']:
            if stats['is_paused']:
                self.status_label.setText("🟠 Pipeline en pause")
            else:
                current = stats['current_task'] or "..."
                self.status_label.setText(f"🟡 En cours: {current}")
        else:
            if stats['completed'] > 0 or stats['failed'] > 0:
                self.status_label.setText("🟢 Pipeline terminé")
            else:
                self.status_label.setText("🟢 Prêt")
    
    def _on_task_started_ui(self, task):
        """Callback UI quand une tâche démarre"""
        self._add_log(f"▶️ Démarrage: {task.name}", "INFO")
        self._refresh_tasks_table()
    
    def _on_task_completed_ui(self, task):
        """Callback UI quand une tâche se termine"""
        if task.status == TaskStatus.COMPLETED:
            self._add_log(f"✅ Terminé: {task.name}", "SUCCESS")
            if hasattr(task, 'get_summary'):
                self._add_log(task.get_summary(), "INFO")
            
            # Ouvrir les fenêtres spécifiques selon le type de tâche
            if task.name == "Visualisation CSV":
                self._open_viewer_window(task)
            elif task.name == "Calcul de Métriques":
                self._open_metrics_window(task)
        else:
            self._add_log(f"❌ Échec: {task.name} - {task.error_message}", "ERROR")
        
        self._refresh_tasks_table()
    
    def _open_viewer_window(self, task):
        """Ouvrir la fenêtre de visualisation"""
        try:
            from ui.viewer_window import ViewerWindow
            
            csv_file = task.config['csv_file']
            dataframe = task.outputs.get('dataframe')
            
            if dataframe is not None:
                viewer = ViewerWindow(csv_file, dataframe, self)
                viewer.exec()
            else:
                self._add_log("❌ Impossible d'ouvrir le viewer: données non disponibles", "ERROR")
        except Exception as e:
            self._add_log(f"❌ Erreur ouverture viewer: {str(e)}", "ERROR")
            import traceback
            print(traceback.format_exc())
    
    def _open_metrics_window(self, task):
        """Ouvrir la fenêtre de métriques"""
        try:
            from ui.metrics_window import MetricsWindow
            
            csv_file = task.config['csv_file']
            basic_stats = task.basic_stats
            advanced_metrics = task.advanced_metrics
            
            if basic_stats:
                metrics = MetricsWindow(csv_file, basic_stats, advanced_metrics, self)
                metrics.exec()
            else:
                self._add_log("❌ Impossible d'ouvrir les métriques: données non disponibles", "ERROR")
        except Exception as e:
            self._add_log(f"❌ Erreur ouverture métriques: {str(e)}", "ERROR")
            import traceback
            print(traceback.format_exc())
    
    def _on_task_progress_ui(self, task, progress, message):
        """Callback UI pour la progression"""
        self.main_progress.setValue(progress)
        self._refresh_tasks_table()
    
    def _on_pipeline_completed_ui(self, stats):
        """Callback UI quand le pipeline se termine"""
        self._add_log("🎉 Pipeline terminé !", "SUCCESS")
        self._add_log(f"Statistiques: {stats}", "INFO")
        
        # Reset buttons
        self.start_button.setEnabled(True)
        self.pause_button.setEnabled(False)
        self.pause_button.setText("⏸️ Pause")
        self.stop_button.setEnabled(False)
        self.main_progress.setValue(100)
        
        # Message de succès
        QMessageBox.information(
            self,
            "Pipeline Terminé",
            f"Pipeline exécuté avec succès !\n\n"
            f"✅ Complétées: {stats['completed']}\n"
            f"❌ Échouées: {stats['failed']}\n"
            f"⏱️ Durée: {stats['duration']:.1f}s"
        )
    
    def _on_task_log(self, log_entry):
        """Callback pour les logs des tâches"""
        level = log_entry['level']
        message = log_entry['message']
        timestamp = log_entry['timestamp']
        
        self._add_log(message, level, timestamp)
    
    
    def _toggle_theme(self):
        """Basculer entre le thème clair et sombre"""
        if self.current_theme == "light":
            self.current_theme = "dark"
            self.theme_button.setText("☀️ Mode Clair")
            self._apply_dark_theme()
        else:
            self.current_theme = "light"
            self.theme_button.setText("🌙 Mode Sombre")
            self._apply_light_theme()
    
    def _apply_light_theme(self):
        """Appliquer le thème clair"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #F5F5F5;
            }
            QWidget {
                background-color: #FFFFFF;
                color: #212121;
            }
            QGroupBox {
                background-color: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QTableWidget {
                background-color: #FFFFFF;
                alternate-row-color: #F5F5F5;
                gridline-color: #E0E0E0;
                border: 1px solid #E0E0E0;
            }
            QHeaderView::section {
                background-color: #EEEEEE;
                color: #212121;
                padding: 5px;
                border: 1px solid #E0E0E0;
                font-weight: bold;
            }
            QLineEdit, QSpinBox {
                background-color: #FFFFFF;
                border: 2px solid #E0E0E0;
                border-radius: 4px;
                padding: 5px;
                color: #212121;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 2px solid #2196F3;
            }
            QLabel {
                color: #212121;
            }
            QProgressBar {
                border: 2px solid #E0E0E0;
                border-radius: 5px;
                text-align: center;
                background-color: #FFFFFF;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        
        # Mettre à jour l'info box pour le thème clair
        self.info_label.setStyleSheet("""
            QLabel {
                padding: 15px;
                background-color: #E3F2FD;
                border: 2px solid #2196F3;
                border-radius: 8px;
                font-size: 12px;
                line-height: 1.8;
                color: #1565C0;
            }
        """)
        
        # Mettre à jour l'info box de téléchargement si elle existe
        if hasattr(self, 'download_info_label'):
            self.download_info_label.setStyleSheet("""
                QLabel {
                    padding: 15px;
                    background-color: #FFF3E0;
                    border: 2px solid #FF9800;
                    border-radius: 8px;
                    font-size: 12px;
                    line-height: 1.8;
                    color: #E65100;
                }
            """)
        
        # Mettre à jour la console de logs pour le thème clair
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #FAFAFA;
                color: #212121;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
        """)
    
    def _apply_dark_theme(self):
        """Appliquer le thème sombre"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #1E1E1E;
            }
            QWidget {
                background-color: #2D2D30;
                color: #CCCCCC;
            }
            QGroupBox {
                background-color: #252526;
                border: 1px solid #3E3E42;
                border-radius: 5px;
                margin-top: 10px;
                font-weight: bold;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #CCCCCC;
            }
            QTableWidget {
                background-color: #1E1E1E;
                alternate-row-color: #252526;
                gridline-color: #3E3E42;
                border: 1px solid #3E3E42;
                color: #CCCCCC;
            }
            QHeaderView::section {
                background-color: #2D2D30;
                color: #CCCCCC;
                padding: 5px;
                border: 1px solid #3E3E42;
                font-weight: bold;
            }
            QLineEdit, QSpinBox {
                background-color: #1E1E1E;
                border: 2px solid #3E3E42;
                border-radius: 4px;
                padding: 5px;
                color: #CCCCCC;
            }
            QLineEdit:focus, QSpinBox:focus {
                border: 2px solid #007ACC;
            }
            QLabel {
                color: #CCCCCC;
            }
            QProgressBar {
                border: 2px solid #3E3E42;
                border-radius: 5px;
                text-align: center;
                background-color: #1E1E1E;
                color: #CCCCCC;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
            }
        """)
        
        # Mettre à jour l'info box pour le thème sombre
        self.info_label.setStyleSheet("""
            QLabel {
                padding: 15px;
                background-color: #1A237E;
                border: 2px solid #3F51B5;
                border-radius: 8px;
                font-size: 12px;
                line-height: 1.8;
                color: #BBDEFB;
            }
        """)
        
        # Mettre à jour l'info box de téléchargement si elle existe
        if hasattr(self, 'download_info_label'):
            self.download_info_label.setStyleSheet("""
                QLabel {
                    padding: 15px;
                    background-color: #E65100;
                    border: 2px solid #FF9800;
                    border-radius: 8px;
                    font-size: 12px;
                    line-height: 1.8;
                    color: #FFE0B2;
                }
            """)
        
        # Mettre à jour la console de logs pour le thème sombre
        self.logs_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                font-family: 'Courier New', monospace;
                font-size: 11px;
                border: 1px solid #3E3E42;
                border-radius: 4px;
            }
        """)
    
    def _add_log(self, message, level="INFO", timestamp=None):
        """Ajouter un log à la console"""
        if timestamp is None:
            from datetime import datetime
            timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Couleur selon le niveau
        color_map = {
            'INFO': '#d4d4d4',
            'SUCCESS': '#4CAF50',
            'WARNING': '#FF9800',
            'ERROR': '#f44336'
        }
        color = color_map.get(level, '#d4d4d4')
        
        # Format HTML
        log_html = f'<span style="color: gray;">[{timestamp}]</span> <span style="color: {color};">{message}</span>'
        
        # Ajouter au text edit
        self.logs_text.append(log_html)
        
        # Auto-scroll
        scrollbar = self.logs_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())