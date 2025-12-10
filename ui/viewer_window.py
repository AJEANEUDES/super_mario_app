"""
Viewer Window - Fenêtre de visualisation de données CSV
Version corrigée avec bugs fixés
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QHeaderView, QLineEdit, QComboBox, QMessageBox,
    QFileDialog
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
import pandas as pd
import os


class ViewerWindow(QDialog):
    """
    Fenêtre de visualisation de données CSV
    Affiche les données dans une table interactive avec filtres et recherche
    """
    
    def __init__(self, csv_file, dataframe=None, parent=None):
        super().__init__(parent)
        
        self.csv_file = csv_file
        self.df = dataframe
        self.filtered_df = None
        
        # Configuration fenêtre
        self.setWindowTitle(f"📊 Visualisation - {os.path.basename(csv_file)}")
        self.setGeometry(100, 100, 1200, 700)
        self.setMinimumSize(800, 500)
        
        # Charger les données si pas fournies
        if self.df is None:
            if not self._load_csv():
                return
        else:
            # S'assurer que le DataFrame est propre
            self.df = self.df.copy()
            self.df = self.df.fillna('')
        
        # Réinitialiser l'index pour avoir des indices séquentiels
        self.df = self.df.reset_index(drop=True)
        self.filtered_df = self.df.copy()
        
        # Créer l'interface
        self._create_ui()
        
        # Charger les données dans la table
        self._load_data()
    
    def _load_csv(self):
        """Charger le fichier CSV"""
        try:
            self.df = pd.read_csv(self.csv_file)
            self.df = self.df.fillna('')
            return True
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Erreur", 
                f"Impossible de charger le CSV:\n{str(e)}"
            )
            self.close()
            return False
    
    def _create_ui(self):
        """Créer l'interface utilisateur"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Header avec infos fichier
        header = self._create_header()
        layout.addWidget(header)
        
        # Barre de recherche et filtres
        filter_bar = self._create_filter_bar()
        layout.addLayout(filter_bar)
        
        # Table principale
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                alternate-background-color: #F5F5F5;
                gridline-color: #E0E0E0;
                selection-background-color: #2196F3;
                selection-color: white;
            }
            QHeaderView::section {
                background-color: #2196F3;
                color: white;
                padding: 8px;
                font-weight: bold;
                border: 1px solid #1976D2;
            }
            QTableWidget::item {
                padding: 5px;
            }
        """)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table)
        
        # Footer avec statistiques
        footer = self._create_footer()
        layout.addWidget(footer)
        
        # Boutons d'action
        buttons_layout = QHBoxLayout()
        buttons_layout.addStretch()
        
        # Bouton Exporter
        export_btn = QPushButton("💾 Exporter les données filtrées")
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        export_btn.clicked.connect(self._export_data)
        buttons_layout.addWidget(export_btn)
        
        # Bouton Fermer
        close_btn = QPushButton("❌ Fermer")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #757575;
                color: white;
                font-weight: bold;
                padding: 10px 20px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #616161;
            }
        """)
        close_btn.clicked.connect(self.close)
        buttons_layout.addWidget(close_btn)
        
        layout.addLayout(buttons_layout)
    
    def _create_header(self):
        """Créer le header avec informations sur le fichier"""
        header_widget = QLabel()
        
        total_rows = len(self.df)
        total_cols = len(self.df.columns)
        file_name = os.path.basename(self.csv_file)
        
        header_text = f"""
        <h2>📊 Visualisation de Données</h2>
        <p><b>Fichier:</b> {file_name}</p>
        <p><b>Lignes:</b> {total_rows} | <b>Colonnes:</b> {total_cols}</p>
        """
        
        header_widget.setText(header_text)
        header_widget.setStyleSheet("""
            QLabel {
                padding: 15px;
                background-color: #E3F2FD;
                border: 2px solid #2196F3;
                border-radius: 8px;
            }
        """)
        
        return header_widget
    
    def _create_filter_bar(self):
        """Créer la barre de recherche et filtres"""
        layout = QHBoxLayout()
        
        # Label recherche
        search_label = QLabel("🔍 Rechercher:")
        layout.addWidget(search_label)
        
        # Champ de recherche
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Tapez pour rechercher...")
        self.search_input.setMinimumWidth(200)
        self.search_input.setStyleSheet("""
            QLineEdit {
                padding: 8px;
                border: 2px solid #E0E0E0;
                border-radius: 4px;
            }
            QLineEdit:focus {
                border: 2px solid #2196F3;
            }
        """)
        self.search_input.textChanged.connect(self._apply_filters)
        layout.addWidget(self.search_input)
        
        # Label colonne
        column_label = QLabel("Dans:")
        layout.addWidget(column_label)
        
        # Sélection de colonne pour le filtre
        self.column_combo = QComboBox()
        self.column_combo.addItem("Toutes les colonnes")
        self.column_combo.addItems(self.df.columns.tolist())
        self.column_combo.setMinimumWidth(150)
        self.column_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 2px solid #E0E0E0;
                border-radius: 4px;
            }
        """)
        self.column_combo.currentIndexChanged.connect(self._apply_filters)
        layout.addWidget(self.column_combo)
        
        # Bouton réinitialiser
        reset_btn = QPushButton("🔄 Réinitialiser")
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                font-weight: bold;
                padding: 8px 15px;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        reset_btn.clicked.connect(self._reset_filters)
        layout.addWidget(reset_btn)
        
        layout.addStretch()
        
        return layout
    
    def _create_footer(self):
        """Créer le footer avec statistiques"""
        self.footer_label = QLabel()
        self.footer_label.setStyleSheet("""
            QLabel {
                padding: 10px;
                background-color: #F5F5F5;
                border: 1px solid #E0E0E0;
                border-radius: 4px;
            }
        """)
        self._update_footer()
        return self.footer_label
    
    def _update_footer(self):
        """Mettre à jour les statistiques du footer"""
        displayed = len(self.filtered_df)
        total = len(self.df)
        
        text = f"📊 Affichage: {displayed} / {total} lignes"
        
        if displayed < total:
            text += " (filtré)"
        
        self.footer_label.setText(text)
    
    def _load_data(self):
        """Charger les données dans la table"""
        df_to_display = self.filtered_df
        
        # Limiter à 1000 lignes pour performance
        max_rows = 1000
        truncated = False
        
        if len(df_to_display) > max_rows:
            df_to_display = df_to_display.head(max_rows)
            truncated = True
        
        # Configuration de la table
        self.table.setRowCount(len(df_to_display))
        self.table.setColumnCount(len(df_to_display.columns))
        self.table.setHorizontalHeaderLabels(df_to_display.columns.tolist())
        
        # Remplir les données - CORRECTION: utiliser enumerate pour l'index de ligne
        for row_idx, (_, row) in enumerate(df_to_display.iterrows()):
            for col_idx, col in enumerate(df_to_display.columns):
                value = str(row[col]) if row[col] != '' else ''
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Read-only
                
                # CORRECTION: Passer row_idx et col_idx correctement
                self.table.setItem(row_idx, col_idx, item)
        
        # Ajuster les colonnes
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.resizeColumnsToContents()
        
        # Limiter la largeur max des colonnes
        for col in range(self.table.columnCount()):
            if self.table.columnWidth(col) > 300:
                self.table.setColumnWidth(col, 300)
        
        # Afficher avertissement si tronqué
        if truncated:
            QMessageBox.information(
                self,
                "Information",
                f"Affichage limité à {max_rows} lignes pour des raisons de performance.\n"
                f"Total: {len(self.filtered_df)} lignes.\n\n"
                f"Utilisez les filtres pour affiner votre recherche ou exportez les données."
            )
    
    def _apply_filters(self):
        """Appliquer les filtres de recherche"""
        search_text = self.search_input.text().lower().strip()
        selected_column = self.column_combo.currentText()
        
        if not search_text:
            # Pas de filtre, afficher tout
            self.filtered_df = self.df.copy()
        else:
            if selected_column == "Toutes les colonnes":
                # Rechercher dans toutes les colonnes
                mask = self.df.astype(str).apply(
                    lambda row: row.str.lower().str.contains(search_text, na=False).any(),
                    axis=1
                )
            else:
                # Rechercher dans une colonne spécifique
                mask = self.df[selected_column].astype(str).str.lower().str.contains(
                    search_text, na=False
                )
            
            self.filtered_df = self.df[mask].copy()
        
        # Réinitialiser l'index pour la nouvelle vue
        self.filtered_df = self.filtered_df.reset_index(drop=True)
        
        # Recharger la table
        self._load_data()
        self._update_footer()
    
    def _reset_filters(self):
        """Réinitialiser les filtres"""
        self.search_input.clear()
        self.column_combo.setCurrentIndex(0)
        self.filtered_df = self.df.copy()
        self._load_data()
        self._update_footer()
    
    def _export_data(self):
        """Exporter les données filtrées vers un nouveau CSV"""
        # Générer un nom de fichier par défaut
        base_name = os.path.splitext(os.path.basename(self.csv_file))[0]
        default_name = f"{base_name}_filtered.csv"
        
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exporter les données",
            default_name,
            "Fichiers CSV (*.csv);;Tous les fichiers (*.*)"
        )
        
        if file_path:
            try:
                self.filtered_df.to_csv(file_path, index=False, encoding='utf-8')
                QMessageBox.information(
                    self,
                    "Succès",
                    f"Données exportées avec succès !\n\n"
                    f"📁 Fichier: {os.path.basename(file_path)}\n"
                    f"📊 Lignes: {len(self.filtered_df)}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Erreur",
                    f"Erreur lors de l'export:\n{str(e)}"
                )