"""
Metrics Task - Tâche de calcul de métriques sur données CSV
"""

import os
import sys
import pandas as pd
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks.base_task import BaseTask, TaskStatus, TaskPriority

class MetricsTask(BaseTask):
    """
    Tâche de calcul de métriques sur données CSV
    Calcule statistiques de base et métriques avancées
    """
    
    def __init__(self, csv_file: str, parent_window=None):
        super().__init__(
            name="Calcul de Métriques",
            description=f"Analyse de {os.path.basename(csv_file)}",
            priority=TaskPriority.LOW
        )
        
        # Configuration
        self.config = {
            'csv_file': csv_file
        }
        
        # Données
        self.df = None
        self.basic_stats = {}
        self.advanced_metrics = {}
        
        # Fenêtre parente
        self.parent_window = parent_window
    
    def validate_config(self):
        """Valider la configuration"""
        csv_file = self.config['csv_file']
        
        # Vérifier CSV
        if not os.path.exists(csv_file):
            return False, f"Fichier CSV non trouvé: {csv_file}"
        
        if not csv_file.endswith('.csv'):
            return False, "Le fichier doit être un CSV (.csv)"
        
        return True, ""
    
    def execute(self):
        """Exécuter le calcul de métriques"""
        try:
            self.update_status(TaskStatus.RUNNING, "Chargement des données...")
            self.log("Démarrage du calcul de métriques", "INFO")
            
            # Valider
            valid, error_msg = self.validate_config()
            if not valid:
                self.error_message = error_msg
                self.update_status(TaskStatus.FAILED, error_msg)
                self.log(f"Configuration invalide: {error_msg}", "ERROR")
                return False
            
            csv_file = self.config['csv_file']
            self.log(f"Analyse: {csv_file}", "INFO")
            
            # Charger le CSV
            self.update_progress(20, "Lecture du fichier...")
            self.df = pd.read_csv(csv_file)
            self.df = self.df.fillna('')
            
            self.log(f"Données chargées: {len(self.df)} lignes", "INFO")
            
            # Calculer statistiques de base
            self.update_progress(40, "Calcul statistiques de base...")
            self.basic_stats = self._calculate_basic_stats()
            self.log("Statistiques de base calculées", "INFO")
            
            # Calculer métriques avancées
            self.update_progress(70, "Calcul métriques avancées...")
            self.advanced_metrics = self._calculate_advanced_metrics()
            self.log("Métriques avancées calculées", "INFO")
            
            # Résultats
            self.result = {
                'csv_file': csv_file,
                'basic_stats': self.basic_stats,
                'advanced_metrics': self.advanced_metrics,
                'total_rows': len(self.df)
            }
            
            # Outputs
            self.outputs = {
                'stats': self.basic_stats,
                'metrics': self.advanced_metrics
            }
            
            self.update_progress(100, "Métriques calculées")
            self.update_status(TaskStatus.COMPLETED, "✅ Métriques calculées")
            self.log("✅ Calcul terminé", "SUCCESS")
            
            return True
            
        except Exception as e:
            self.error_message = str(e)
            self.update_status(TaskStatus.FAILED, f"Erreur: {str(e)}")
            self.log(f"Erreur critique: {str(e)}", "ERROR")
            return False
    
    def _calculate_basic_stats(self):
        """Calculer statistiques de base"""
        stats = {
            'total_runs': len(self.df),
            'unique_players': 0,
            'unique_platforms': 0,
            'categories': []
        }
        
        # Joueurs uniques
        if 'player' in self.df.columns:
            stats['unique_players'] = self.df['player'].nunique()
        
        # Plateformes uniques
        if 'platform' in self.df.columns:
            stats['unique_platforms'] = self.df['platform'].nunique()
        
        # Catégories
        if 'category' in self.df.columns:
            stats['categories'] = self.df['category'].unique().tolist()
        
        # Statistiques de temps
        if 'time_seconds' in self.df.columns:
            times = pd.to_numeric(self.df['time_seconds'], errors='coerce')
            times = times[times > 0]
            
            if len(times) > 0:
                stats['best_time'] = self._format_time(times.min())
                stats['average_time'] = self._format_time(times.mean())
                stats['worst_time'] = self._format_time(times.max())
                stats['median_time'] = self._format_time(times.median())
        
        # Statistiques de vidéos
        if 'video_url' in self.df.columns:
            videos_with_url = self.df[self.df['video_url'] != '']
            stats['runs_with_video'] = len(videos_with_url)
            stats['runs_without_video'] = len(self.df) - len(videos_with_url)
            stats['video_coverage'] = (len(videos_with_url) / len(self.df) * 100) if len(self.df) > 0 else 0
        
        return stats
    
    def _calculate_advanced_metrics(self):
        """Calculer métriques avancées"""
        metrics = {}
        
        # Top players par nombre de runs
        if 'player' in self.df.columns:
            top_players = self.df[self.df['player'] != '']['player'].value_counts().head(10).to_dict()
            metrics['top_players'] = top_players
        
        # Distribution par plateforme
        if 'platform' in self.df.columns:
            platform_dist = self.df[self.df['platform'] != '']['platform'].value_counts().to_dict()
            metrics['platform_distribution'] = platform_dist
        
        # Emulator vs Console
        if 'is_emulator' in self.df.columns:
            emulator_count = len(self.df[self.df['is_emulator'] == True])
            console_count = len(self.df[self.df['is_emulator'] == False])
            metrics['emulator_vs_console'] = {
                'emulator': emulator_count,
                'console': console_count
            }
        
        # Distribution par version
        if 'version' in self.df.columns:
            version_dist = self.df[self.df['version'] != '']['version'].value_counts().to_dict()
            metrics['version_distribution'] = version_dist
        
        # Évolution temporelle
        if 'date' in self.df.columns:
            df_dates = self.df[self.df['date'] != ''].copy()
            df_dates['date'] = pd.to_datetime(df_dates['date'], errors='coerce')
            df_dates = df_dates.dropna(subset=['date'])
            
            if len(df_dates) > 0:
                # Runs par mois
                monthly_runs = df_dates.groupby(df_dates['date'].dt.to_period('M')).size().to_dict()
                metrics['monthly_trends'] = {str(k): v for k, v in monthly_runs.items()}
                
                # Runs par année
                yearly_runs = df_dates.groupby(df_dates['date'].dt.year).size().to_dict()
                metrics['yearly_trends'] = yearly_runs
        
        # Records par catégorie
        if 'category' in self.df.columns and 'time_seconds' in self.df.columns:
            df_times = self.df[(self.df['category'] != '') & (self.df['time_seconds'] != '')].copy()
            df_times['time_seconds'] = pd.to_numeric(df_times['time_seconds'], errors='coerce')
            df_times = df_times[(df_times['time_seconds'] > 0) & (df_times['time_seconds'].notna())]
            
            if len(df_times) > 0:
                records = df_times.groupby('category')['time_seconds'].min().to_dict()
                metrics['category_records'] = {k: self._format_time(v) for k, v in records.items()}
                
                # Moyenne par catégorie
                averages = df_times.groupby('category')['time_seconds'].mean().to_dict()
                metrics['category_averages'] = {k: self._format_time(v) for k, v in averages.items()}
        
        # Top 10 temps les plus rapides
        if 'time_seconds' in self.df.columns and 'player' in self.df.columns:
            df_top = self.df[self.df['time_seconds'] != ''].copy()
            df_top['time_seconds'] = pd.to_numeric(df_top['time_seconds'], errors='coerce')
            df_top = df_top.dropna(subset=['time_seconds'])
            
            if len(df_top) > 0:
                top_times = df_top.nsmallest(10, 'time_seconds')[['player', 'time_seconds']].to_dict('records')
                metrics['top_10_times'] = [
                    {'player': row['player'], 'time': self._format_time(row['time_seconds'])}
                    for row in top_times
                ]
        
        return metrics
    
    def _format_time(self, seconds):
        """Formater le temps en format lisible"""
        if pd.isna(seconds) or seconds <= 0:
            return "0s"
        
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        
        if minutes > 0:
            return f"{minutes}m {secs}s {ms}ms"
        return f"{secs}s {ms}ms"
    
    def cancel(self):
        """Annuler (pas vraiment applicable)"""
        self.update_status(TaskStatus.CANCELLED, "Annulé")
        self.log("Calcul de métriques annulé", "WARNING")
    
    def get_summary(self):
        """Obtenir un résumé"""
        if not self.result:
            return "Aucun résultat disponible"
        
        stats = self.result['basic_stats']
        
        summary = f"""
📊 Résumé des métriques:
   • Total runs: {stats.get('total_runs', 0)}
   • Joueurs uniques: {stats.get('unique_players', 0)}
   • Plateformes: {stats.get('unique_platforms', 0)}
   • Meilleur temps: {stats.get('best_time', 'N/A')}
   • Temps moyen: {stats.get('average_time', 'N/A')}
   • Durée: {self.get_duration():.1f}s
        """.strip()
        
        return summary