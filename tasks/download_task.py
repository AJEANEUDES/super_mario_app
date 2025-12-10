"""
Download Task - Tâche de téléchargement de vidéos depuis un fichier CSV
"""

import os
import sys
import threading
import time
import pandas as pd
from datetime import datetime

# Ajouter le répertoire parent pour importer le scraper
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks.base_task import BaseTask, TaskStatus, TaskPriority

# Import yt-dlp (avec gestion d'erreur)
try:
    import yt_dlp
    from yt_dlp import YoutubeDL
    YT_DLP_AVAILABLE = True
except ImportError:
    YT_DLP_AVAILABLE = False
    print("⚠️ Module yt-dlp non disponible")

class DownloadTask(BaseTask):
    """
    Tâche de téléchargement de vidéos depuis un fichier CSV
    Utilise yt-dlp pour télécharger les vidéos listées dans la colonne video_url
    """
    
    def __init__(self,
                 csv_file: str,
                 output_dir: str = None,
                 game_name: str = "game",
                 max_concurrent: int = 1,
                 video_format: str = "best"):
        
        super().__init__(
            name="Téléchargement Vidéos",
            description=f"Téléchargement depuis {os.path.basename(csv_file)}",
            priority=TaskPriority.NORMAL
        )
        
        # Configuration
        self.config = {
            'csv_file': csv_file,
            'output_dir': output_dir,
            'game_name': game_name,
            'max_concurrent': max_concurrent,
            'video_format': video_format
        }
        
        # État
        self.cancel_flag = False
        self.pause_flag = False
        self.total_videos = 0
        self.completed_videos = 0
        self.failed_videos = 0
        self.errors = []
        
        # Données
        self.video_data = None
        self.current_download = None
    
    def validate_config(self):
        """Valider la configuration"""
        csv_file = self.config['csv_file']
        
        # Vérifier yt-dlp
        if not YT_DLP_AVAILABLE:
            return False, "Module yt-dlp non disponible. Installez-le avec: pip install yt-dlp"
        
        # Vérifier CSV
        if not os.path.exists(csv_file):
            return False, f"Fichier CSV non trouvé: {csv_file}"
        
        # Vérifier que c'est un CSV
        if not csv_file.endswith('.csv'):
            return False, "Le fichier doit être un CSV (.csv)"
        
        # Vérifier le contenu du CSV
        try:
            df = pd.read_csv(csv_file)
            
            if 'video_url' not in df.columns:
                return False, "Le CSV doit contenir une colonne 'video_url'"
            
            if 'player' not in df.columns:
                return False, "Le CSV doit contenir une colonne 'player'"
            
            # Compter vidéos valides
            valid_videos = df[(df['video_url'].notna()) & (df['video_url'] != '')]
            
            if len(valid_videos) == 0:
                return False, "Aucune URL de vidéo valide trouvée dans le CSV"
            
            self.total_videos = len(valid_videos)
            
        except Exception as e:
            return False, f"Erreur lecture CSV: {str(e)}"
        
        return True, ""
    
    def execute(self):
        """Exécuter le téléchargement"""
        try:
            self.update_status(TaskStatus.RUNNING, "Initialisation...")
            self.log("Démarrage du téléchargement de vidéos", "INFO")
            
            # Valider config
            valid, error_msg = self.validate_config()
            if not valid:
                self.error_message = error_msg
                self.update_status(TaskStatus.FAILED, error_msg)
                self.log(f"Configuration invalide: {error_msg}", "ERROR")
                return False
            
            # Charger les données
            csv_file = self.config['csv_file']
            self.log(f"Chargement du CSV: {csv_file}", "INFO")
            
            df = pd.read_csv(csv_file)
            df = df.fillna('')
            
            # Filtrer vidéos valides
            valid_videos = df[(df['video_url'] != '') & (df['player'] != '')]
            self.video_data = valid_videos
            self.total_videos = len(valid_videos)
            
            self.log(f"Vidéos à télécharger: {self.total_videos}", "INFO")
            
            # Créer dossier de sortie
            output_dir = self._create_output_directory(df)
            self.log(f"Dossier de sortie: {output_dir}", "INFO")
            
            # Télécharger les vidéos
            self._download_all_videos(valid_videos, output_dir)
            
            # Vérifier annulation
            if self.cancel_flag:
                self.update_status(TaskStatus.CANCELLED, "Téléchargement annulé")
                self.log("Téléchargement annulé par l'utilisateur", "WARNING")
                return False
            
            # Résultats
            success_rate = (self.completed_videos / self.total_videos * 100) if self.total_videos > 0 else 0
            
            self.result = {
                'total_videos': self.total_videos,
                'completed': self.completed_videos,
                'failed': self.failed_videos,
                'success_rate': success_rate,
                'output_dir': output_dir,
                'errors': self.errors
            }
            
            # Stocker outputs pour chaînage
            self.outputs = {
                'output_dir': output_dir,
                'total_downloaded': self.completed_videos,
                'failed_count': self.failed_videos
            }
            
            # Status final
            if self.failed_videos == 0:
                status_msg = f"✅ {self.completed_videos}/{self.total_videos} vidéos téléchargées"
                self.update_status(TaskStatus.COMPLETED, status_msg)
                self.log(status_msg, "SUCCESS")
            elif self.completed_videos > 0:
                status_msg = f"⚠️ {self.completed_videos}/{self.total_videos} vidéos téléchargées ({self.failed_videos} échecs)"
                self.update_status(TaskStatus.COMPLETED, status_msg)
                self.log(status_msg, "WARNING")
            else:
                status_msg = "❌ Aucune vidéo téléchargée"
                self.update_status(TaskStatus.FAILED, status_msg)
                self.log(status_msg, "ERROR")
                return False
            
            self.update_progress(100, f"{self.completed_videos} vidéos téléchargées")
            
            return True
            
        except Exception as e:
            self.error_message = str(e)
            self.update_status(TaskStatus.FAILED, f"Erreur: {str(e)}")
            self.log(f"Erreur critique: {str(e)}", "ERROR")
            return False
    
    def _create_output_directory(self, df):
        """Créer le dossier de sortie basé sur les métadonnées du CSV"""
        game_name = self.config['game_name']
        
        # Essayer d'extraire catégorie et version du CSV
        category = ""
        version = ""
        
        if 'category' in df.columns:
            categories = df['category'].unique()
            if len(categories) > 0 and categories[0]:
                category = str(categories[0])
        
        if 'version' in df.columns:
            versions = df['version'].unique()
            if len(versions) > 0 and versions[0]:
                version = str(versions[0])
        
        # Nettoyer les noms
        safe_game = "".join(c for c in game_name if c.isalnum() or c in ('-', '_'))
        safe_category = "".join(c for c in category if c.isalnum() or c in ('-', '_'))
        safe_version = "".join(c for c in version if c.isalnum() or c in ('-', '_'))
        
        # Construire nom du dossier
        folder_parts = [safe_game]
        if safe_category:
            folder_parts.append(safe_category)
        if safe_version:
            folder_parts.append(safe_version)
        folder_parts.append('videos')
        
        folder_name = '_'.join(folder_parts)
        
        # Créer chemin complet
        if self.config['output_dir']:
            output_dir = os.path.join(self.config['output_dir'], folder_name)
        else:
            output_dir = os.path.join('downloads', folder_name)
        
        os.makedirs(output_dir, exist_ok=True)
        
        return output_dir
    
    def _download_all_videos(self, videos_df, output_dir):
        """Télécharger toutes les vidéos"""
        for index, row in videos_df.iterrows():
            # Vérifier annulation
            if self.cancel_flag:
                self.log("Arrêt demandé", "WARNING")
                break
            
            # Gérer la pause
            while self.pause_flag and not self.cancel_flag:
                self.update_status(TaskStatus.RUNNING, "En pause...")
                time.sleep(0.5)
            
            if self.cancel_flag:
                break
            
            # Extraire info
            player = row['player']
            video_url = row['video_url']
            
            # Nettoyer nom joueur
            safe_player = self._sanitize_filename(player)
            if not safe_player:
                safe_player = f"player_{index}"
            
            # Créer dossier joueur
            player_dir = os.path.join(output_dir, safe_player)
            os.makedirs(player_dir, exist_ok=True)
            
            # Mettre à jour progression
            progress = int((index / self.total_videos) * 100)
            self.update_progress(progress, f"Téléchargement {player}... ({index + 1}/{self.total_videos})")
            self.current_download = player
            
            self.log(f"Téléchargement vidéo {index + 1}/{self.total_videos}: {player}", "INFO")
            
            # Télécharger
            try:
                self._download_single_video(video_url, player_dir, safe_player)
                self.completed_videos += 1
                self.log(f"✅ Téléchargé: {player}", "SUCCESS")
                
                # Délai anti-rate-limit
                time.sleep(2)
                
            except Exception as e:
                self.failed_videos += 1
                error_msg = f"{player}: {str(e)[:100]}"
                self.errors.append(error_msg)
                self.log(f"❌ Échec {player}: {str(e)[:50]}", "ERROR")
    
    def _download_single_video(self, url, output_dir, filename_prefix):
        """Télécharger une seule vidéo avec yt-dlp"""
        try:
            # Options yt-dlp
            ydl_opts = {
                'outtmpl': os.path.join(output_dir, f'{filename_prefix}.%(ext)s'),
                'format': self.config['video_format'],
                'noplaylist': False,
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False
            }
            
            # Télécharger avec yt-dlp
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
        except Exception as e:
            raise Exception(f"Erreur téléchargement: {str(e)}")
    
    def _sanitize_filename(self, filename):
        """Nettoyer un nom de fichier"""
        # Garder seulement alphanumérique, -, _
        safe = "".join(c for c in filename if c.isalnum() or c in ('_', '-'))
        # Limiter longueur
        return safe[:50]
    
    def cancel(self):
        """Annuler le téléchargement"""
        self.cancel_flag = True
        self.update_status(TaskStatus.CANCELLED, "Annulation en cours...")
        self.log("Demande d'annulation reçue", "WARNING")
    
    def pause(self):
        """Mettre en pause"""
        self.pause_flag = True
        self.log("Téléchargement en pause", "WARNING")
    
    def resume(self):
        """Reprendre"""
        self.pause_flag = False
        self.log("Téléchargement repris", "INFO")
    
    def get_summary(self):
        """Obtenir un résumé du téléchargement"""
        if not self.result:
            return "Aucun résultat disponible"
        
        success_rate = self.result['success_rate']
        
        summary = f"""
Résumé du téléchargement:
   • Vidéos téléchargées: {self.result['completed']}/{self.result['total_videos']}
   • Échecs: {self.result['failed']}
   • Taux de réussite: {success_rate:.1f}%
   • Dossier: {self.result['output_dir']}
   • Durée: {self.get_duration():.1f}s
        """.strip()
        
        return summary