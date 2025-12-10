"""
Viewer Task - Tâche de visualisation de données CSV
"""

import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks.base_task import BaseTask, TaskStatus, TaskPriority

class ViewerTask(BaseTask):
    """
    Tâche de visualisation de données CSV
    Charge un CSV et prépare les données pour affichage
    """
    
    def __init__(self, csv_file: str, max_rows: int = 1000, parent_window=None):
        super().__init__(
            name="Visualisation CSV",
            description=f"Affichage de {os.path.basename(csv_file)}",
            priority=TaskPriority.LOW
        )
        
        # Configuration
        self.config = {
            'csv_file': csv_file,
            'max_rows': max_rows
        }
        
        # Données
        self.df = None
        self.data_dict = None
        self.columns = []
        self.total_rows = 0
        
        # Fenêtre parente pour ouvrir le viewer
        self.parent_window = parent_window
    
    def validate_config(self):
        """Valider la configuration"""
        csv_file = self.config['csv_file']
        
        # Vérifier CSV
        if not os.path.exists(csv_file):
            return False, f"Fichier CSV non trouvé: {csv_file}"
        
        if not csv_file.endswith('.csv'):
            return False, "Le fichier doit être un CSV (.csv)"
        
        # Vérifier lecture
        try:
            df = pd.read_csv(csv_file, nrows=1)
        except Exception as e:
            return False, f"Erreur lecture CSV: {str(e)}"
        
        return True, ""
    
    def execute(self):
        """Exécuter la visualisation"""
        try:
            self.update_status(TaskStatus.RUNNING, "Chargement du CSV...")
            self.log("Démarrage de la visualisation CSV", "INFO")
            
            # Valider
            valid, error_msg = self.validate_config()
            if not valid:
                self.error_message = error_msg
                self.update_status(TaskStatus.FAILED, error_msg)
                self.log(f"Configuration invalide: {error_msg}", "ERROR")
                return False
            
            csv_file = self.config['csv_file']
            max_rows = self.config['max_rows']
            
            self.log(f"Chargement: {csv_file}", "INFO")
            
            # Charger le CSV
            self.update_progress(30, "Lecture du fichier...")
            self.df = pd.read_csv(csv_file)
            
            # Remplacer NaN par chaînes vides
            self.df = self.df.fillna('')
            
            self.total_rows = len(self.df)
            self.columns = list(self.df.columns)
            
            self.log(f"Lignes totales: {self.total_rows}", "INFO")
            self.log(f"Colonnes: {len(self.columns)}", "INFO")
            
            # Limiter affichage
            self.update_progress(60, "Préparation des données...")
            display_df = self.df.head(max_rows)
            self.data_dict = display_df.to_dict('records')
            
            self.log(f"Données préparées: {len(self.data_dict)} lignes", "INFO")
            
            # Résultats
            self.result = {
                'csv_file': csv_file,
                'total_rows': self.total_rows,
                'displayed_rows': len(self.data_dict),
                'columns': self.columns,
                'data': self.data_dict
            }
            
            # Outputs pour chaînage
            self.outputs = {
                'dataframe': self.df,
                'csv_file': csv_file
            }
            
            self.update_progress(100, f"{self.total_rows} lignes chargées")
            self.update_status(TaskStatus.COMPLETED, f"✅ {self.total_rows} lignes visualisées")
            self.log("✅ Visualisation terminée", "SUCCESS")
            
            # Les données sont stockées dans self.outputs et seront accessibles par le parent
            
            return True
            
        except Exception as e:
            self.error_message = str(e)
            self.update_status(TaskStatus.FAILED, f"Erreur: {str(e)}")
            self.log(f"Erreur critique: {str(e)}", "ERROR")
            return False
    
    def cancel(self):
        """Annuler (pas vraiment applicable pour cette tâche)"""
        self.update_status(TaskStatus.CANCELLED, "Annulé")
        self.log("Visualisation annulée", "WARNING")
    
    def get_summary(self):
        """Obtenir un résumé"""
        if not self.result:
            return "Aucun résultat disponible"
        
        summary = f"""
📊 Résumé de la visualisation:
   • Fichier: {os.path.basename(self.result['csv_file'])}
   • Lignes totales: {self.result['total_rows']}
   • Colonnes: {len(self.result['columns'])}
   • Affichées: {self.result['displayed_rows']}
   • Durée: {self.get_duration():.1f}s
        """.strip()
        
        return summary