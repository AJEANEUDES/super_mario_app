"""
Frame Analyzer Widget - Interface pour l'analyse statistique des frames
"""

import os
import json
from pathlib import Path
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QFrame, QScrollArea,
    QGridLayout, QProgressBar, QLineEdit, QCheckBox,
    QTextEdit, QSizePolicy, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget, QSplitter
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QFont, QTextCursor, QColor


class AnalysisThread(QThread):
    """Thread pour l'analyse en arrière-plan"""
    
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int, str)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(object)
    
    def __init__(self, task, parent=None):
        super().__init__(parent)
        self.task = task
    
    def run(self):
        """Exécuter l'analyse"""
        self.task.log_callback = self._log
        self.task.progress_callback = self._progress
        self.task.status_callback = self._status
        
        result = self.task.execute()
        self.finished_signal.emit(result)
    
    def _log(self, message: str):
        self.log_signal.emit(message)
    
    def _progress(self, current: int, total: int, filename: str):
        self.progress_signal.emit(current, total, filename)
    
    def _status(self, status: str):
        self.status_signal.emit(status)


class FrameAnalyzerWidget(QWidget):
    """
    Widget pour l'analyse statistique des frames/images
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.current_task = None
        self.analysis_thread = None
        self.last_result = None
        self.is_running = False
        
        self._create_ui()
    
    def _create_ui(self):
        """Créer l'interface"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Splitter principal
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # Partie haute
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)
        
        top_layout.addWidget(self._create_banner())
        top_layout.addWidget(self._create_config_group())
        top_layout.addWidget(self._create_progress_group())
        
        splitter.addWidget(top_widget)
        
        # Partie basse - Résultats
        bottom_widget = QWidget()
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        bottom_layout.addWidget(self._create_results_tabs())
        
        splitter.addWidget(bottom_widget)
        
        splitter.setSizes([250, 450])
        
        layout.addWidget(splitter)
        
        # Boutons d'action
        layout.addLayout(self._create_action_buttons())
    
    def _create_banner(self):
        """Créer la bannière"""
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1565C0, stop:1 #1976D2);
                border-radius: 8px;
                padding: 10px;
            }
            QLabel { color: white; }
        """)
        
        layout = QVBoxLayout(banner)
        
        title = QLabel("📊 Analyse des Frames")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title.setStyleSheet("color: white;")
        layout.addWidget(title)
        
        desc = QLabel(
            "Analysez les statistiques de vos images: résolutions, formats,\n"
            "tailles, modes couleur, et répartition par dossier."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #BBDEFB; font-size: 10px;")
        layout.addWidget(desc)
        
        return banner
    
    def _create_config_group(self):
        """Créer le groupe configuration"""
        group = QGroupBox("📁 Configuration")
        group.setStyleSheet(self._get_group_style("#2196F3"))
        
        layout = QGridLayout()
        
        # Dossier source
        layout.addWidget(QLabel("Dossier à analyser:"), 0, 0)
        
        self.edit_source = QLineEdit()
        self.edit_source.setPlaceholderText("Sélectionner un dossier contenant des images...")
        self.edit_source.textChanged.connect(self._on_source_changed)
        layout.addWidget(self.edit_source, 0, 1)
        
        btn_browse = QPushButton("📂 Parcourir")
        btn_browse.clicked.connect(self._browse_source)
        layout.addWidget(btn_browse, 0, 2)
        
        # Options
        options_layout = QHBoxLayout()
        
        self.check_recursive = QCheckBox("Analyse récursive (sous-dossiers)")
        self.check_recursive.setChecked(True)
        options_layout.addWidget(self.check_recursive)
        
        self.check_save_json = QCheckBox("Sauvegarder rapport JSON")
        self.check_save_json.setChecked(True)
        options_layout.addWidget(self.check_save_json)
        
        options_layout.addStretch()
        
        layout.addLayout(options_layout, 1, 0, 1, 3)
        
        # Info rapide
        self.label_quick_info = QLabel("")
        self.label_quick_info.setStyleSheet("color: #666; font-size: 10px;")
        layout.addWidget(self.label_quick_info, 2, 0, 1, 3)
        
        group.setLayout(layout)
        return group
    
    def _create_progress_group(self):
        """Créer le groupe progression"""
        group = QGroupBox("📈 Progression")
        group.setStyleSheet(self._get_group_style("#4CAF50"))
        
        layout = QVBoxLayout()
        
        # Barre de progression
        progress_layout = QHBoxLayout()
        
        self.label_progress = QLabel("En attente...")
        self.label_progress.setStyleSheet("font-weight: bold;")
        progress_layout.addWidget(self.label_progress)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        progress_layout.addWidget(self.progress_bar)
        
        layout.addLayout(progress_layout)
        
        # Statut
        self.status_label = QLabel("Configurez le dossier source pour commencer")
        self.status_label.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(self.status_label)
        
        group.setLayout(layout)
        return group
    
    def _create_results_tabs(self):
        """Créer les onglets de résultats"""
        self.tabs = QTabWidget()
        
        # Onglet Résumé
        self.tab_summary = QWidget()
        summary_layout = QVBoxLayout(self.tab_summary)
        
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setFont(QFont("Consolas", 10))
        self.summary_text.setStyleSheet("""
            QTextEdit {
                background-color: #1E1E1E;
                color: #D4D4D4;
                border: 1px solid #333;
            }
        """)
        summary_layout.addWidget(self.summary_text)
        
        self.tabs.addTab(self.tab_summary, "📋 Résumé")
        
        # Onglet Résolutions
        self.tab_resolutions = QWidget()
        res_layout = QVBoxLayout(self.tab_resolutions)
        
        self.table_resolutions = QTableWidget()
        self.table_resolutions.setColumnCount(3)
        self.table_resolutions.setHorizontalHeaderLabels(["Résolution", "Nombre", "%"])
        self.table_resolutions.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        res_layout.addWidget(self.table_resolutions)
        
        self.tabs.addTab(self.tab_resolutions, "📐 Résolutions")
        
        # Onglet Formats
        self.tab_formats = QWidget()
        fmt_layout = QVBoxLayout(self.tab_formats)
        
        self.table_formats = QTableWidget()
        self.table_formats.setColumnCount(3)
        self.table_formats.setHorizontalHeaderLabels(["Format", "Nombre", "%"])
        self.table_formats.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        fmt_layout.addWidget(self.table_formats)
        
        self.tabs.addTab(self.tab_formats, "🖼️ Formats")
        
        # Onglet Par Dossier
        self.tab_levels = QWidget()
        levels_layout = QVBoxLayout(self.tab_levels)
        
        self.table_levels = QTableWidget()
        self.table_levels.setColumnCount(3)
        self.table_levels.setHorizontalHeaderLabels(["Dossier", "Images", "Taille (KB)"])
        self.table_levels.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        levels_layout.addWidget(self.table_levels)
        
        self.tabs.addTab(self.tab_levels, "📂 Par Dossier")
        
        # Onglet Logs
        self.tab_logs = QWidget()
        logs_layout = QVBoxLayout(self.tab_logs)
        
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
        logs_layout.addWidget(self.log_text)
        
        # Boutons logs
        log_btn_layout = QHBoxLayout()
        
        btn_clear = QPushButton("🗑️ Effacer")
        btn_clear.clicked.connect(self.log_text.clear)
        log_btn_layout.addWidget(btn_clear)
        
        btn_copy = QPushButton("📋 Copier")
        btn_copy.clicked.connect(self._copy_logs)
        log_btn_layout.addWidget(btn_copy)
        
        log_btn_layout.addStretch()
        
        logs_layout.addLayout(log_btn_layout)
        
        self.tabs.addTab(self.tab_logs, "📋 Logs")
        
        return self.tabs
    
    def _create_action_buttons(self):
        """Créer les boutons d'action"""
        layout = QHBoxLayout()
        
        self.btn_analyze = QPushButton("🔍 Lancer l'Analyse")
        self.btn_analyze.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 12px 30px;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { background-color: #9E9E9E; }
        """)
        self.btn_analyze.clicked.connect(self._start_analysis)
        self.btn_analyze.setEnabled(False)
        layout.addWidget(self.btn_analyze)
        
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
        self.btn_stop.clicked.connect(self._stop_analysis)
        self.btn_stop.setEnabled(False)
        layout.addWidget(self.btn_stop)
        
        layout.addStretch()
        
        self.btn_export = QPushButton("💾 Exporter JSON")
        self.btn_export.clicked.connect(self._export_json)
        self.btn_export.setEnabled(False)
        layout.addWidget(self.btn_export)
        
        self.btn_open_folder = QPushButton("📂 Ouvrir Dossier")
        self.btn_open_folder.clicked.connect(self._open_source_folder)
        self.btn_open_folder.setEnabled(False)
        layout.addWidget(self.btn_open_folder)
        
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
    
    def _browse_source(self):
        """Parcourir pour sélectionner le dossier source"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "Sélectionner le dossier à analyser"
        )
        if folder:
            self.edit_source.setText(folder)
    
    def _on_source_changed(self, path: str):
        """Quand le dossier source change"""
        if os.path.exists(path) and os.path.isdir(path):
            self.btn_analyze.setEnabled(True)
            self.btn_open_folder.setEnabled(True)
            
            # Stats rapides
            from tasks.frame_analyzer_task import FrameAnalyzerTask
            task = FrameAnalyzerTask()
            stats = task.get_quick_stats(path)
            
            info = f"📊 {stats['total_files']:,} images | {stats['total_size_mb']:.1f} MB"
            if stats['subdirs'] > 0:
                info += f" | {stats['subdirs']} sous-dossiers"
            
            self.label_quick_info.setText(info)
            self.label_quick_info.setStyleSheet("color: #4CAF50; font-size: 10px;")
        else:
            self.btn_analyze.setEnabled(False)
            self.btn_open_folder.setEnabled(False)
            self.label_quick_info.setText("⚠️ Dossier invalide")
            self.label_quick_info.setStyleSheet("color: #f44336; font-size: 10px;")
    
    def _start_analysis(self):
        """Démarrer l'analyse"""
        source_dir = self.edit_source.text().strip()
        
        if not source_dir or not os.path.exists(source_dir):
            QMessageBox.warning(self, "Erreur", "Dossier source invalide")
            return
        
        # Configurer la tâche
        from tasks.frame_analyzer_task import FrameAnalyzerTask, AnalyzerConfig
        
        output_json = ""
        if self.check_save_json.isChecked():
            output_json = os.path.join(source_dir, "frame_analysis.json")
        
        config = AnalyzerConfig(
            source_dir=source_dir,
            recursive=self.check_recursive.isChecked(),
            output_json=output_json
        )
        
        self.current_task = FrameAnalyzerTask()
        self.current_task.configure(config)
        
        # Thread
        self.analysis_thread = AnalysisThread(self.current_task, self)
        self.analysis_thread.log_signal.connect(self._on_log)
        self.analysis_thread.progress_signal.connect(self._on_progress)
        self.analysis_thread.status_signal.connect(self._on_status)
        self.analysis_thread.finished_signal.connect(self._on_finished)
        
        # UI
        self.is_running = True
        self.btn_analyze.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.btn_export.setEnabled(False)
        self.log_text.clear()
        self.progress_bar.setValue(0)
        
        self.status_label.setText("🔍 Analyse en cours...")
        self.tabs.setCurrentIndex(4)  # Onglet Logs
        
        self.analysis_thread.start()
    
    def _stop_analysis(self):
        """Arrêter l'analyse"""
        if self.current_task:
            reply = QMessageBox.question(
                self,
                "Confirmer l'arrêt",
                "Voulez-vous vraiment arrêter l'analyse?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            
            if reply == QMessageBox.StandardButton.Yes:
                self.current_task.stop()
                self.btn_stop.setEnabled(False)
    
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
        """Quand l'analyse est terminée"""
        self.is_running = False
        self.last_result = result
        
        self.btn_analyze.setEnabled(True)
        self.btn_stop.setEnabled(False)
        
        if result.success:
            self.status_label.setText("✅ Analyse terminée!")
            self.status_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
            self.btn_export.setEnabled(True)
            
            # Remplir les résultats
            self._populate_results(result)
            
            # Afficher l'onglet résumé
            self.tabs.setCurrentIndex(0)
            
            QMessageBox.information(
                self,
                "Analyse terminée",
                f"✅ Analyse réussie!\n\n"
                f"📊 Images analysées: {result.total_images:,}\n"
                f"📐 Résolutions uniques: {len(result.resolutions)}\n"
                f"📁 Dossiers: {len(result.by_level)}\n"
                f"⏱️ Temps: {result.analysis_time:.1f}s"
            )
        else:
            self.status_label.setText("❌ Erreur")
            self.status_label.setStyleSheet("color: #f44336; font-weight: bold;")
            
            if result.errors:
                QMessageBox.warning(self, "Erreurs", "\n".join(result.errors[:5]))
    
    def _populate_results(self, result):
        """Remplir les tableaux de résultats"""
        # Résumé
        summary_lines = [
            "=" * 50,
            "📊 RAPPORT D'ANALYSE DES FRAMES",
            "=" * 50,
            "",
            f"📈 STATISTIQUES GLOBALES:",
            f"   Total d'images: {result.total_images:,}",
            f"   Taille totale: {result.total_size_mb:.1f} MB",
            f"   Taille moyenne: {result.avg_size_kb:.1f} KB",
            f"   Min/Max: {result.min_size_kb:.1f} - {result.max_size_kb:.1f} KB",
            "",
            f"📐 DIMENSIONS:",
            f"   Largeurs: {result.width_range[0]} - {result.width_range[1]} px",
            f"   Hauteurs: {result.height_range[0]} - {result.height_range[1]} px",
            "",
            f"🖼️ FORMATS: {len(result.formats)} types",
            f"🎨 MODES COULEUR: {len(result.color_modes)} types",
            f"📂 DOSSIERS: {len(result.by_level)}",
            "",
            f"⏱️ Temps d'analyse: {result.analysis_time:.1f}s"
        ]
        
        if result.output_file:
            summary_lines.append(f"💾 Rapport JSON: {result.output_file}")
        
        self.summary_text.setText("\n".join(summary_lines))
        
        # Tableau Résolutions
        self._fill_table(
            self.table_resolutions,
            result.resolutions,
            result.total_images
        )
        
        # Tableau Formats
        self._fill_table(
            self.table_formats,
            result.formats,
            result.total_images
        )
        
        # Tableau Par Dossier
        self.table_levels.setRowCount(len(result.by_level))
        sorted_levels = sorted(result.by_level.items(), key=lambda x: x[1].count, reverse=True)
        
        for i, (name, stats) in enumerate(sorted_levels):
            self.table_levels.setItem(i, 0, QTableWidgetItem(name))
            self.table_levels.setItem(i, 1, QTableWidgetItem(f"{stats.count:,}"))
            self.table_levels.setItem(i, 2, QTableWidgetItem(f"{stats.total_size / 1024:.1f}"))
    
    def _fill_table(self, table: QTableWidget, data: dict, total: int):
        """Remplir un tableau avec les données"""
        sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)
        table.setRowCount(len(sorted_data))
        
        for i, (key, count) in enumerate(sorted_data):
            pct = (count / total) * 100 if total > 0 else 0
            
            table.setItem(i, 0, QTableWidgetItem(str(key)))
            table.setItem(i, 1, QTableWidgetItem(f"{count:,}"))
            table.setItem(i, 2, QTableWidgetItem(f"{pct:.1f}%"))
    
    def _copy_logs(self):
        """Copier les logs"""
        from PyQt6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        clipboard.setText(self.log_text.toPlainText())
        self.status_label.setText("📋 Logs copiés!")
    
    def _export_json(self):
        """Exporter les résultats en JSON"""
        if not self.last_result:
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Sauvegarder le rapport",
            "frame_analysis.json",
            "JSON (*.json)"
        )
        
        if file_path:
            try:
                json_data = {
                    "summary": {
                        "total_images": self.last_result.total_images,
                        "total_size_mb": self.last_result.total_size_mb,
                        "avg_size_kb": self.last_result.avg_size_kb,
                        "width_range": self.last_result.width_range,
                        "height_range": self.last_result.height_range
                    },
                    "resolutions": self.last_result.resolutions,
                    "formats": self.last_result.formats,
                    "color_modes": self.last_result.color_modes,
                    "aspect_ratios": self.last_result.aspect_ratios,
                    "by_level": {
                        name: {"count": stats.count, "size_kb": round(stats.total_size / 1024, 2)}
                        for name, stats in self.last_result.by_level.items()
                    }
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(json_data, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(self, "Exporté", f"Rapport sauvegardé: {file_path}")
                
            except Exception as e:
                QMessageBox.warning(self, "Erreur", f"Erreur d'export: {e}")
    
    def _open_source_folder(self):
        """Ouvrir le dossier source"""
        source_dir = self.edit_source.text().strip()
        if source_dir and os.path.exists(source_dir):
            import subprocess
            import sys
            if sys.platform == 'win32':
                subprocess.run(['explorer', source_dir])
            elif sys.platform == 'darwin':
                subprocess.run(['open', source_dir])
            else:
                subprocess.run(['xdg-open', source_dir])