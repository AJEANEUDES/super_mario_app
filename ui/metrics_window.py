"""
Metrics Window - Fenêtre d'affichage des métriques calculées
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import json

class MetricsWindow(QDialog):
    """
    Fenêtre d'affichage des métriques calculées
    Affiche les statistiques de base et métriques avancées
    """
    
    def __init__(self, csv_file, basic_stats, advanced_metrics, parent=None):
        super().__init__(parent)
        
        self.csv_file = csv_file
        self.basic_stats = basic_stats
        self.advanced_metrics = advanced_metrics
        
        # Configuration fenêtre
        self.setWindowTitle(f"📈 Métriques - {csv_file}")
        self.setGeometry(100, 100, 1000, 700)
        self.setMinimumSize(800, 600)
        
        # Créer l'interface
        self._create_ui()
    
    def _create_ui(self):
        """Créer l'interface utilisateur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header
        header = self._create_header()
        layout.addWidget(header)
        
        # Scroll area pour le contenu
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")
        
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        
        # Statistiques de base
        basic_group = self._create_basic_stats_group()
        content_layout.addWidget(basic_group)
        
        # Métriques avancées
        if self.advanced_metrics:
            advanced_group = self._create_advanced_metrics_group()
            content_layout.addWidget(advanced_group)
        
        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)
        
        # Boutons
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        export_btn = QPushButton("💾 Exporter JSON")
        export_btn.clicked.connect(self._export_json)
        buttons_layout.addWidget(export_btn)
        
        close_btn = QPushButton("❌ Fermer")
        close_btn.clicked.connect(self.close)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
    
    def _create_header(self):
        """Créer le header"""
        header_widget = QLabel()
        
        header_text = f"""
        <h2>📈 Analyse de Métriques</h2>
        <p><b>Fichier:</b> {self.csv_file}</p>
        <p><b>Total runs:</b> {self.basic_stats.get('total_runs', 0)}</p>
        """
        
        header_widget.setText(header_text)
        header_widget.setStyleSheet("""
            QLabel {
                padding: 15px;
                background-color: #E8F5E9;
                border: 2px solid #4CAF50;
                border-radius: 8px;
            }
        """)
        
        return header_widget
    
    def _create_basic_stats_group(self):
        """Créer le groupe de statistiques de base"""
        group = QGroupBox("📊 Statistiques de Base")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #4CAF50;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Grid de stats
        stats_html = "<table width='100%' style='border-collapse: collapse;'>"
        
        # Comptages
        stats_html += self._create_stat_row("📊 Total runs", self.basic_stats.get('total_runs', 0))
        stats_html += self._create_stat_row("👤 Joueurs uniques", self.basic_stats.get('unique_players', 0))
        stats_html += self._create_stat_row("🎮 Plateformes uniques", self.basic_stats.get('unique_platforms', 0))
        
        # Catégories
        categories = self.basic_stats.get('categories', [])
        if categories:
            cats_str = ", ".join([str(c) for c in categories if c])
            stats_html += self._create_stat_row("📁 Catégories", cats_str)
        
        # Temps
        if 'best_time' in self.basic_stats:
            stats_html += "<tr><td colspan='2'><hr style='border: 1px solid #E0E0E0; margin: 10px 0;'></td></tr>"
            stats_html += self._create_stat_row("⏱️ Meilleur temps", self.basic_stats.get('best_time', 'N/A'), color='#4CAF50')
            stats_html += self._create_stat_row("📊 Temps moyen", self.basic_stats.get('average_time', 'N/A'))
            stats_html += self._create_stat_row("📈 Temps médian", self.basic_stats.get('median_time', 'N/A'))
            stats_html += self._create_stat_row("⏱️ Pire temps", self.basic_stats.get('worst_time', 'N/A'), color='#F44336')
        
        # Vidéos
        if 'runs_with_video' in self.basic_stats:
            stats_html += "<tr><td colspan='2'><hr style='border: 1px solid #E0E0E0; margin: 10px 0;'></td></tr>"
            stats_html += self._create_stat_row("🎬 Runs avec vidéo", self.basic_stats.get('runs_with_video', 0))
            stats_html += self._create_stat_row("❌ Runs sans vidéo", self.basic_stats.get('runs_without_video', 0))
            coverage = self.basic_stats.get('video_coverage', 0)
            stats_html += self._create_stat_row("📊 Couverture vidéo", f"{coverage:.1f}%")
        
        stats_html += "</table>"
        
        label = QLabel(stats_html)
        label.setTextFormat(Qt.TextFormat.RichText)
        label.setWordWrap(True)
        layout.addWidget(label)
        
        group.setLayout(layout)
        return group
    
    def _create_advanced_metrics_group(self):
        """Créer le groupe de métriques avancées"""
        group = QGroupBox("🎯 Métriques Avancées")
        group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                font-size: 14px;
                border: 2px solid #2196F3;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        
        layout = QVBoxLayout()
        
        # Top Players
        if 'top_players' in self.advanced_metrics:
            top_players_label = QLabel("<b>👑 Top 10 Joueurs (par nombre de runs)</b>")
            layout.addWidget(top_players_label)
            
            top_players_table = self._create_top_players_table()
            layout.addWidget(top_players_table)
        
        # Distribution Plateformes
        if 'platform_distribution' in self.advanced_metrics:
            platform_label = QLabel("<b>🎮 Distribution par Plateforme</b>")
            layout.addWidget(platform_label)
            
            platform_table = self._create_platform_table()
            layout.addWidget(platform_table)
        
        # Emulator vs Console
        if 'emulator_vs_console' in self.advanced_metrics:
            emu_label = QLabel("<b>💻 Emulator vs Console</b>")
            layout.addWidget(emu_label)
            
            emu_data = self.advanced_metrics['emulator_vs_console']
            emu_html = f"""
            <table width='100%' style='border-collapse: collapse;'>
                {self._create_stat_row("💻 Emulator", emu_data.get('emulator', 0))}
                {self._create_stat_row("🎮 Console", emu_data.get('console', 0))}
            </table>
            """
            emu_widget = QLabel(emu_html)
            emu_widget.setTextFormat(Qt.TextFormat.RichText)
            layout.addWidget(emu_widget)
        
        # Records par catégorie
        if 'category_records' in self.advanced_metrics:
            records_label = QLabel("<b>🏆 Records par Catégorie</b>")
            layout.addWidget(records_label)
            
            records_table = self._create_records_table()
            layout.addWidget(records_table)
        
        # Top 10 Temps
        if 'top_10_times' in self.advanced_metrics:
            top_times_label = QLabel("<b>⚡ Top 10 Temps les Plus Rapides</b>")
            layout.addWidget(top_times_label)
            
            top_times_table = self._create_top_times_table()
            layout.addWidget(top_times_table)
        
        # Évolution temporelle
        if 'monthly_trends' in self.advanced_metrics or 'yearly_trends' in self.advanced_metrics:
            trends_label = QLabel("<b>📅 Évolution Temporelle</b>")
            layout.addWidget(trends_label)
            
            if 'yearly_trends' in self.advanced_metrics:
                yearly_data = self.advanced_metrics['yearly_trends']
                yearly_html = "<p><b>Par année:</b><br>"
                for year, count in sorted(yearly_data.items()):
                    yearly_html += f"{year}: {count} runs<br>"
                yearly_html += "</p>"
                yearly_widget = QLabel(yearly_html)
                layout.addWidget(yearly_widget)
        
        group.setLayout(layout)
        return group
    
    def _create_stat_row(self, label, value, color=None):
        """Créer une ligne de statistique HTML"""
        value_style = f"color: {color};" if color else ""
        return f"""
        <tr style='border-bottom: 1px solid #E0E0E0;'>
            <td style='padding: 8px; font-weight: bold;'>{label}</td>
            <td style='padding: 8px; text-align: right; {value_style}'>{value}</td>
        </tr>
        """
    
    def _create_top_players_table(self):
        """Créer la table des top players"""
        top_players = self.advanced_metrics['top_players']
        
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["#", "Joueur", "Runs"])
        table.setRowCount(len(top_players))
        
        for i, (player, count) in enumerate(top_players.items()):
            # Rang
            rank_item = QTableWidgetItem(str(i + 1))
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 0, rank_item)
            
            # Joueur
            player_item = QTableWidgetItem(str(player))
            table.setItem(i, 1, player_item)
            
            # Nombre de runs
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 2, count_item)
        
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setMaximumHeight(300)
        
        return table
    
    def _create_platform_table(self):
        """Créer la table de distribution des plateformes"""
        platforms = self.advanced_metrics['platform_distribution']
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Plateforme", "Runs"])
        table.setRowCount(len(platforms))
        
        for i, (platform, count) in enumerate(platforms.items()):
            # Plateforme
            platform_item = QTableWidgetItem(str(platform))
            table.setItem(i, 0, platform_item)
            
            # Nombre de runs
            count_item = QTableWidgetItem(str(count))
            count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 1, count_item)
        
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setMaximumHeight(250)
        
        return table
    
    def _create_records_table(self):
        """Créer la table des records par catégorie"""
        records = self.advanced_metrics['category_records']
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Catégorie", "Record"])
        table.setRowCount(len(records))
        
        for i, (category, time) in enumerate(records.items()):
            # Catégorie
            cat_item = QTableWidgetItem(str(category))
            table.setItem(i, 0, cat_item)
            
            # Temps
            time_item = QTableWidgetItem(str(time))
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 1, time_item)
        
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        table.setMaximumHeight(250)
        
        return table
    
    def _create_top_times_table(self):
        """Créer la table des top 10 temps"""
        top_times = self.advanced_metrics['top_10_times']
        
        table = QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["#", "Joueur", "Temps"])
        table.setRowCount(len(top_times))
        
        for i, entry in enumerate(top_times):
            # Rang
            rank_item = QTableWidgetItem(str(i + 1))
            rank_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 0, rank_item)
            
            # Joueur
            player_item = QTableWidgetItem(str(entry['player']))
            table.setItem(i, 1, player_item)
            
            # Temps
            time_item = QTableWidgetItem(str(entry['time']))
            time_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            table.setItem(i, 2, time_item)
        
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        table.setMaximumHeight(350)
        
        return table
    
    def _export_json(self):
        """Exporter les métriques en JSON"""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter les métriques",
            f"{self.csv_file.replace('.csv', '_metrics.json')}",
            "Fichiers JSON (*.json)"
        )
        
        if file_path:
            try:
                data = {
                    'csv_file': self.csv_file,
                    'basic_stats': self.basic_stats,
                    'advanced_metrics': self.advanced_metrics
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(
                    self,
                    "Succès",
                    f"Métriques exportées avec succès!\n{file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de l'export:\n{str(e)}"
                )