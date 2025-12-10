"""
Scraper Task - Tâche d'extraction de données depuis speedrun.com
"""

import os
import sys
import threading
from datetime import datetime

# Ajouter le répertoire parent pour importer le scraper
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks.base_task import BaseTask, TaskStatus, TaskPriority

# Import du scraper (avec gestion d'erreur)
try:
    from scraper import ImprovedSpeedrunScraper
    SCRAPER_AVAILABLE = True
except ImportError:
    SCRAPER_AVAILABLE = False
    print("⚠️ Module scraper.py non disponible")

class ScraperTask(BaseTask):
    """
    Tâche d'extraction de données speedrun.com
    Utilise ImprovedSpeedrunScraper pour récupérer les données
    """
    
    def __init__(self, 
                 speedrun_url: str,
                 start_page: int = 1,
                 end_page: int = 3,
                 output_filename: str = None,
                 project_name: str = "speedrun_data"):
        
        super().__init__(
            name="Extraction Speedrun",
            description=f"Scraping {speedrun_url} (pages {start_page}-{end_page})",
            priority=TaskPriority.NORMAL
        )
        
        # Configuration
        self.config = {
            'speedrun_url': speedrun_url,
            'start_page': start_page,
            'end_page': end_page,
            'project_name': project_name,
            'output_filename': output_filename or f"{project_name}_data.csv"
        }
        
        # Données
        self.scraper = None
        self.cancel_flag = False
        self.scraped_data = None
        
    def validate_config(self):
        """Valider la configuration"""
        url = self.config['speedrun_url']
        start = self.config['start_page']
        end = self.config['end_page']
        
        # Vérifier que le scraper est disponible
        if not SCRAPER_AVAILABLE:
            return False, "Module scraper.py non disponible"
        
        # Vérifier URL
        if not url or not url.startswith('http'):
            return False, "URL invalide"
        
        # Vérifier pages
        if start < 1:
            return False, "Page de départ doit être >= 1"
        
        if end < start:
            return False, "Page de fin doit être >= page de départ"
        
        if end - start > 50:
            return False, "Maximum 50 pages par extraction"
        
        return True, ""
    
    def execute(self):
        """Exécuter le scraping"""
        try:
            self.update_status(TaskStatus.RUNNING, "Initialisation du scraper...")
            self.log("Démarrage de l'extraction Speedrun", "INFO")
            
            # Valider config
            valid, error_msg = self.validate_config()
            if not valid:
                self.error_message = error_msg
                self.update_status(TaskStatus.FAILED, error_msg)
                self.log(f"Configuration invalide: {error_msg}", "ERROR")
                return False
            
            # Initialiser le scraper
            self.scraper = ImprovedSpeedrunScraper()
            
            # Configurer le callback de progression
            def progress_callback(current_page, total_pages, progress, message):
                if self.cancel_flag:
                    return
                self.update_progress(progress, message)
                self.log(f"Page {current_page}/{total_pages}: {message}", "INFO")
            
            self.scraper.set_progress_callback(progress_callback)
            
            # Lancer le scraping
            url = self.config['speedrun_url']
            start_page = self.config['start_page']
            end_page = self.config['end_page']
            
            self.log(f"Scraping: {url}", "INFO")
            self.log(f"Pages: {start_page} à {end_page}", "INFO")
            
            # Appeler la méthode de scraping
            self.scraped_data = self.scraper.scrape_with_progress(
                url=url,
                start_page=start_page,
                end_page=end_page,
                progress_callback=progress_callback
            )
            
            # Vérifier annulation
            if self.cancel_flag:
                self.update_status(TaskStatus.CANCELLED, "Scraping annulé par l'utilisateur")
                self.log("Scraping annulé", "WARNING")
                return False
            
            # Vérifier résultat
            if self.scraped_data is None or len(self.scraped_data) == 0:
                self.error_message = "Aucune donnée extraite"
                self.update_status(TaskStatus.FAILED, "Aucune donnée extraite")
                self.log("Aucune donnée récupérée", "ERROR")
                return False
            
            # Sauvegarder en CSV
            output_path = self._save_to_csv()
            
            if not output_path:
                self.error_message = "Erreur lors de la sauvegarde CSV"
                self.update_status(TaskStatus.FAILED, "Erreur sauvegarde CSV")
                self.log("Échec de la sauvegarde CSV", "ERROR")
                return False
            
            # Succès !
            total_runs = len(self.scraped_data)
            self.result = {
                'total_runs': total_runs,
                'output_file': output_path,
                'data': self.scraped_data
            }
            
            # Stocker outputs pour les tâches suivantes
            self.outputs = {
                'csv_file': output_path,
                'data': self.scraped_data,
                'total_runs': total_runs
            }
            
            self.update_progress(100, f"{total_runs} runs extraits")
            self.update_status(TaskStatus.COMPLETED, f"Extraction terminée: {total_runs} runs")
            self.log(f"✅ Extraction réussie: {total_runs} runs → {output_path}", "SUCCESS")
            
            return True
            
        except Exception as e:
            self.error_message = str(e)
            self.update_status(TaskStatus.FAILED, f"Erreur: {str(e)}")
            self.log(f"Erreur critique: {str(e)}", "ERROR")
            return False
    
    def _save_to_csv(self):
        """Sauvegarder les données en CSV"""
        try:
            # Créer le dossier downloads s'il n'existe pas
            downloads_dir = os.path.join(os.getcwd(), 'downloads')
            os.makedirs(downloads_dir, exist_ok=True)
            
            # Générer nom de fichier avec timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = self.config['output_filename']
            
            # Ajouter timestamp si le fichier existe déjà
            base_name = filename.replace('.csv', '')
            output_file = f"{base_name}_{timestamp}.csv"
            output_path = os.path.join(downloads_dir, output_file)
            
            # Sauvegarder avec le scraper
            self.scraper.all_runs = self.scraped_data.to_dict('records') if hasattr(self.scraped_data, 'to_dict') else self.scraped_data
            success = self.scraper.save_csv_desktop(output_path)
            
            if success:
                self.log(f"CSV sauvegardé: {output_path}", "INFO")
                return output_path
            else:
                return None
                
        except Exception as e:
            self.log(f"Erreur sauvegarde CSV: {str(e)}", "ERROR")
            return None
    
    def cancel(self):
        """Annuler le scraping"""
        self.cancel_flag = True
        self.update_status(TaskStatus.CANCELLED, "Annulation en cours...")
        self.log("Demande d'annulation reçue", "WARNING")
    
    def get_summary(self):
        """Obtenir un résumé de l'extraction"""
        if not self.result:
            return "Aucun résultat disponible"
        
        return f"""
📊 Résumé de l'extraction:
   • Runs extraits: {self.result['total_runs']}
   • Fichier: {self.result['output_file']}
   • URL: {self.config['speedrun_url']}
   • Pages: {self.config['start_page']}-{self.config['end_page']}
   • Durée: {self.get_duration():.1f}s
        """.strip()