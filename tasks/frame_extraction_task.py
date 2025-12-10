"""
Frame Extraction Task - Tâche d'extraction de frames depuis des vidéos
Intégrée au pipeline avec support multi-threading et organisation par joueur
"""

import cv2
import os
import sys
import threading
import queue
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tasks.base_task import BaseTask, TaskStatus, TaskPriority


class FrameExtractionTask(BaseTask):
    """
    Tâche d'extraction de frames depuis des vidéos téléchargées
    Supporte l'extraction depuis un dossier contenant des sous-dossiers par joueur
    ou depuis une vidéo unique
    """
    
    def __init__(self,
                 source_path: str,
                 output_base_dir: str = None,
                 every_n_frames: int = 1,
                 num_threads: int = 4,
                 jpeg_quality: int = 85,
                 start_time: float = None,
                 end_time: float = None,
                 max_frames_per_video: int = None):
        """
        Args:
            source_path: Chemin vers une vidéo OU un dossier contenant des sous-dossiers joueurs
            output_base_dir: Dossier de sortie (si None, crée 'frames' à côté des vidéos)
            every_n_frames: Extraire 1 frame sur N (1 = tous les frames)
            num_threads: Nombre de threads pour la sauvegarde
            jpeg_quality: Qualité JPEG (1-100)
            start_time: Temps de début en secondes (optionnel)
            end_time: Temps de fin en secondes (optionnel)
            max_frames_per_video: Limite de frames par vidéo (optionnel)
        """
        
        super().__init__(
            name="Extraction de Frames",
            description=f"Extraction depuis {os.path.basename(source_path)}",
            priority=TaskPriority.NORMAL
        )
        
        self.config = {
            'source_path': source_path,
            'output_base_dir': output_base_dir,
            'every_n_frames': every_n_frames,
            'num_threads': num_threads,
            'jpeg_quality': jpeg_quality,
            'start_time': start_time,
            'end_time': end_time,
            'max_frames_per_video': max_frames_per_video
        }
        
        # État
        self.cancel_flag = False
        self.pause_flag = False
        
        # Statistiques
        self.total_frames_extracted = 0
        self.total_videos_processed = 0
        self.failed_videos = []
        self.processing_stats = []
        
        # Queue pour sauvegarde multi-thread
        self.save_queue = None
        self.save_threads = []
        
        # Extensions vidéo supportées
        self.video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv', '.wmv'}
    
    def validate_config(self):
        """Valider la configuration"""
        source_path = self.config['source_path']
        
        if not os.path.exists(source_path):
            return False, f"Chemin non trouvé: {source_path}"
        
        # Vérifier si c'est un fichier vidéo ou un dossier
        if os.path.isfile(source_path):
            ext = os.path.splitext(source_path)[1].lower()
            if ext not in self.video_extensions:
                return False, f"Format non supporté: {ext}"
        
        # Vérifier every_n_frames
        if self.config['every_n_frames'] < 1:
            return False, "every_n_frames doit être >= 1"
        
        # Vérifier qualité JPEG
        quality = self.config['jpeg_quality']
        if quality < 1 or quality > 100:
            return False, "jpeg_quality doit être entre 1 et 100"
        
        return True, ""
    
    def execute(self):
        """Exécuter l'extraction de frames"""
        try:
            self.update_status(TaskStatus.RUNNING, "Initialisation...")
            self.log("Démarrage de l'extraction de frames", "INFO")
            
            # Valider config
            valid, error_msg = self.validate_config()
            if not valid:
                self.error_message = error_msg
                self.update_status(TaskStatus.FAILED, error_msg)
                self.log(f"Configuration invalide: {error_msg}", "ERROR")
                return False
            
            source_path = self.config['source_path']
            
            # Déterminer le mode (fichier unique ou dossier)
            if os.path.isfile(source_path):
                # Mode fichier unique
                self.log(f"Mode: Vidéo unique", "INFO")
                success = self._process_single_video(source_path)
            else:
                # Mode dossier (structure par joueur)
                self.log(f"Mode: Dossier avec sous-dossiers joueurs", "INFO")
                success = self._process_player_folders(source_path)
            
            if self.cancel_flag:
                self.update_status(TaskStatus.CANCELLED, "Extraction annulée")
                self.log("Extraction annulée par l'utilisateur", "WARNING")
                return False
            
            # Résultats
            self.result = {
                'total_frames': self.total_frames_extracted,
                'videos_processed': self.total_videos_processed,
                'failed_videos': self.failed_videos,
                'stats': self.processing_stats
            }
            
            self.outputs = {
                'total_frames': self.total_frames_extracted,
                'videos_processed': self.total_videos_processed
            }
            
            # Status final
            if self.total_frames_extracted > 0:
                status_msg = f"✅ {self.total_frames_extracted:,} frames extraits de {self.total_videos_processed} vidéo(s)"
                self.update_status(TaskStatus.COMPLETED, status_msg)
                self.log(status_msg, "SUCCESS")
                return True
            else:
                status_msg = "❌ Aucun frame extrait"
                self.update_status(TaskStatus.FAILED, status_msg)
                self.log(status_msg, "ERROR")
                return False
                
        except Exception as e:
            self.error_message = str(e)
            self.update_status(TaskStatus.FAILED, f"Erreur: {str(e)}")
            self.log(f"Erreur critique: {str(e)}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False
    
    def _process_player_folders(self, base_path: str) -> bool:
        """
        Traiter un dossier contenant des sous-dossiers par joueur
        Structure attendue:
            base_path/
                player1/
                    video.mp4
                player2/
                    video.mkv
        """
        base_path = Path(base_path)
        
        # Lister les sous-dossiers (joueurs)
        player_folders = [f for f in base_path.iterdir() if f.is_dir()]
        
        if not player_folders:
            self.log("Aucun sous-dossier joueur trouvé", "WARNING")
            # Peut-être que les vidéos sont directement dans le dossier
            return self._process_videos_in_folder(base_path)
        
        self.log(f"Trouvé {len(player_folders)} dossiers joueurs", "INFO")
        
        total_players = len(player_folders)
        
        for idx, player_folder in enumerate(player_folders):
            if self.cancel_flag:
                break
            
            # Gérer la pause
            while self.pause_flag and not self.cancel_flag:
                time.sleep(0.5)
            
            player_name = player_folder.name
            progress = int((idx / total_players) * 100)
            self.update_progress(progress, f"Joueur: {player_name} ({idx+1}/{total_players})")
            
            self.log(f"Traitement joueur: {player_name}", "INFO")
            
            # Chercher les vidéos dans le dossier du joueur
            videos = self._find_videos_in_folder(player_folder)
            
            if not videos:
                self.log(f"  Aucune vidéo trouvée pour {player_name}", "WARNING")
                continue
            
            # Créer le dossier frames pour ce joueur
            frames_dir = player_folder / "frames"
            frames_dir.mkdir(exist_ok=True)
            
            # Traiter chaque vidéo du joueur
            for video_path in videos:
                if self.cancel_flag:
                    break
                
                self.log(f"  Extraction: {video_path.name}", "INFO")
                
                try:
                    stats = self._extract_frames_from_video(
                        video_path=str(video_path),
                        output_dir=str(frames_dir),
                        prefix=f"{player_name}_"
                    )
                    
                    if stats:
                        self.total_frames_extracted += stats['frames_extracted']
                        self.total_videos_processed += 1
                        self.processing_stats.append(stats)
                        self.log(f"  ✅ {stats['frames_extracted']:,} frames extraits", "SUCCESS")
                    
                except Exception as e:
                    self.log(f"  ❌ Erreur: {str(e)}", "ERROR")
                    self.failed_videos.append(str(video_path))
        
        return self.total_videos_processed > 0
    
    def _process_videos_in_folder(self, folder_path: Path) -> bool:
        """Traiter les vidéos directement dans un dossier (sans structure joueur)"""
        videos = self._find_videos_in_folder(folder_path)
        
        if not videos:
            self.log("Aucune vidéo trouvée dans le dossier", "WARNING")
            return False
        
        self.log(f"Trouvé {len(videos)} vidéo(s) à traiter", "INFO")
        
        for idx, video_path in enumerate(videos):
            if self.cancel_flag:
                break
            
            progress = int((idx / len(videos)) * 100)
            self.update_progress(progress, f"Vidéo {idx+1}/{len(videos)}: {video_path.name}")
            
            # Créer dossier frames à côté de la vidéo
            video_name = video_path.stem
            frames_dir = video_path.parent / f"{video_name}_frames"
            frames_dir.mkdir(exist_ok=True)
            
            try:
                stats = self._extract_frames_from_video(
                    video_path=str(video_path),
                    output_dir=str(frames_dir)
                )
                
                if stats:
                    self.total_frames_extracted += stats['frames_extracted']
                    self.total_videos_processed += 1
                    self.processing_stats.append(stats)
                    
            except Exception as e:
                self.log(f"Erreur {video_path.name}: {str(e)}", "ERROR")
                self.failed_videos.append(str(video_path))
        
        return self.total_videos_processed > 0
    
    def _process_single_video(self, video_path: str) -> bool:
        """Traiter une seule vidéo"""
        video_path = Path(video_path)
        
        # Déterminer le dossier de sortie
        if self.config['output_base_dir']:
            frames_dir = Path(self.config['output_base_dir'])
        else:
            # Créer dossier 'frames' à côté de la vidéo
            frames_dir = video_path.parent / f"{video_path.stem}_frames"
        
        frames_dir.mkdir(parents=True, exist_ok=True)
        
        self.log(f"Extraction vers: {frames_dir}", "INFO")
        
        try:
            stats = self._extract_frames_from_video(
                video_path=str(video_path),
                output_dir=str(frames_dir)
            )
            
            if stats:
                self.total_frames_extracted = stats['frames_extracted']
                self.total_videos_processed = 1
                self.processing_stats.append(stats)
                return True
            
        except Exception as e:
            self.log(f"Erreur: {str(e)}", "ERROR")
            self.failed_videos.append(str(video_path))
        
        return False
    
    def _find_videos_in_folder(self, folder_path: Path) -> list:
        """Trouver toutes les vidéos dans un dossier"""
        videos = []
        for ext in self.video_extensions:
            videos.extend(folder_path.glob(f"*{ext}"))
            videos.extend(folder_path.glob(f"*{ext.upper()}"))
        return videos
    
    def _extract_frames_from_video(self, video_path: str, output_dir: str, prefix: str = "") -> dict:
        """
        Extraire les frames d'une vidéo avec multi-threading
        
        Returns:
            dict avec statistiques d'extraction
        """
        # Ouvrir la vidéo
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise ValueError(f"Impossible d'ouvrir: {video_path}")
        
        # Infos vidéo
        fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / fps if fps > 0 else 0
        
        self.log(f"    Vidéo: {fps:.1f} FPS, {total_frames:,} frames, {duration/60:.1f} min", "INFO")
        
        # Calcul des bornes
        start_time_config = self.config['start_time']
        end_time_config = self.config['end_time']
        
        start_frame = int(start_time_config * fps) if start_time_config else 0
        end_frame = int(end_time_config * fps) if end_time_config else total_frames
        
        # Limiter si max_frames défini
        max_frames = self.config['max_frames_per_video']
        every_n = self.config['every_n_frames']
        
        # Calculer le nombre total de frames à extraire (pour la progression)
        frames_to_process = end_frame - start_frame
        expected_extractions = frames_to_process // every_n
        if max_frames and max_frames < expected_extractions:
            expected_extractions = max_frames
        
        self.log(f"    Frames à extraire: ~{expected_extractions:,}", "INFO")
        
        # Positionnement
        if start_frame > 0:
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
        
        # Initialiser queue et threads de sauvegarde
        self.save_queue = queue.Queue(maxsize=100)
        self.save_threads = []
        
        for _ in range(self.config['num_threads']):
            t = threading.Thread(target=self._save_frame_worker)
            t.daemon = True
            t.start()
            self.save_threads.append(t)
        
        # Variables de suivi
        extracted_count = 0
        current_frame = start_frame
        start_extraction_time = time.time()
        last_progress_update = start_extraction_time
        
        # Activer optimisations OpenCV
        cv2.setUseOptimized(True)
        
        output_path = Path(output_dir)
        
        try:
            while current_frame < end_frame:
                if self.cancel_flag:
                    break
                
                ret, frame = cap.read()
                if not ret:
                    break
                
                # Extraire seulement 1 frame sur N
                if (current_frame - start_frame) % every_n == 0:
                    # Vérifier limite
                    if max_frames and extracted_count >= max_frames:
                        break
                    
                    # Nom du fichier
                    frame_filename = f"{prefix}frame_{extracted_count:06d}.jpg"
                    frame_path = output_path / frame_filename
                    
                    # Ajouter à la queue
                    self.save_queue.put((frame.copy(), str(frame_path), self.config['jpeg_quality']))
                    extracted_count += 1
                    
                    # Mise à jour de la progression toutes les 0.5 secondes
                    current_time = time.time()
                    if current_time - last_progress_update >= 0.5:
                        if expected_extractions > 0:
                            progress = int((extracted_count / expected_extractions) * 100)
                            progress = min(progress, 99)  # Garder 100% pour la fin
                        else:
                            progress = 0
                        
                        elapsed = current_time - start_extraction_time
                        fps_speed = extracted_count / elapsed if elapsed > 0 else 0
                        
                        # Estimation du temps restant
                        remaining = expected_extractions - extracted_count
                        eta = remaining / fps_speed if fps_speed > 0 else 0
                        
                        progress_msg = f"{extracted_count:,}/{expected_extractions:,} frames ({fps_speed:.0f} f/s, ETA: {eta/60:.1f}min)"
                        self.update_progress(progress, progress_msg)
                        
                        last_progress_update = current_time
                
                current_frame += 1
                
        finally:
            cap.release()
            
            # Attendre la fin des sauvegardes
            self.log(f"    Finalisation des sauvegardes...", "INFO")
            self.save_queue.join()
            
            # Arrêter les threads
            for _ in self.save_threads:
                self.save_queue.put(None)
            
            for t in self.save_threads:
                t.join(timeout=5)
            
            self.save_threads = []
        
        # Statistiques
        total_time = time.time() - start_extraction_time
        avg_fps = extracted_count / total_time if total_time > 0 else 0
        
        # Mise à jour finale de la progression
        self.update_progress(100, f"✅ {extracted_count:,} frames extraits")
        
        return {
            'video_path': video_path,
            'output_dir': output_dir,
            'frames_extracted': extracted_count,
            'processing_time': total_time,
            'average_fps': avg_fps,
            'video_fps': fps,
            'video_duration_min': duration / 60
        }
    
    def _save_frame_worker(self):
        """Worker thread pour sauvegarder les frames"""
        while True:
            item = self.save_queue.get()
            if item is None:
                self.save_queue.task_done()
                break
            
            frame, frame_path, quality = item
            try:
                # Paramètres de compression JPEG
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
                cv2.imwrite(frame_path, frame, encode_params)
            except Exception as e:
                self.log(f"Erreur sauvegarde: {e}", "ERROR")
            finally:
                self.save_queue.task_done()
    
    def cancel(self):
        """Annuler l'extraction"""
        self.cancel_flag = True
        self.update_status(TaskStatus.CANCELLED, "Annulation en cours...")
        self.log("Demande d'annulation reçue", "WARNING")
    
    def pause(self):
        """Mettre en pause"""
        self.pause_flag = True
        self.log("Extraction en pause", "WARNING")
    
    def resume(self):
        """Reprendre"""
        self.pause_flag = False
        self.log("Extraction reprise", "INFO")
    
    def get_summary(self):
        """Obtenir un résumé de l'extraction"""
        if not self.result:
            return "Aucun résultat disponible"
        
        summary = f"""
📷 Résumé de l'extraction:
   • Frames extraits: {self.result['total_frames']:,}
   • Vidéos traitées: {self.result['videos_processed']}
   • Vidéos échouées: {len(self.result['failed_videos'])}
   • Durée: {self.get_duration():.1f}s
        """.strip()
        
        return summary


# Fonction utilitaire pour extraction rapide hors pipeline
def extract_frames_quick(video_path: str, output_dir: str = None, every_n: int = 1) -> dict:
    """
    Fonction rapide pour extraire des frames sans passer par le pipeline
    
    Args:
        video_path: Chemin vers la vidéo
        output_dir: Dossier de sortie (optionnel)
        every_n: Extraire 1 frame sur N
    
    Returns:
        dict avec statistiques
    """
    task = FrameExtractionTask(
        source_path=video_path,
        output_base_dir=output_dir,
        every_n_frames=every_n
    )
    
    success = task.execute()
    return task.result if success else None