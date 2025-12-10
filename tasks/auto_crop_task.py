"""
Auto Crop Task - Système de crop automatique/manuel des frames
Supporte le crop des 4 bords avec prévisualisation
"""

import os
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional

from .base_task import BaseTask, TaskStatus, TaskPriority

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


@dataclass
class CropConfig:
    """Configuration pour le crop automatique"""
    
    # Pixels à enlever de chaque côté
    crop_left: int = 0
    crop_right: int = 0
    crop_top: int = 0
    crop_bottom: int = 0
    
    # Sécurité
    min_remaining_width: int = 100
    min_remaining_height: int = 100
    
    # Performance
    batch_size: int = 64
    jpeg_quality: int = 95
    
    # Sortie
    output_suffix: str = "_cropped"
    overwrite_originals: bool = False


class AutoCropTask(BaseTask):
    """
    Tâche de crop automatique des frames
    Permet de supprimer des bordures de toutes les images d'un dossier
    """
    
    def __init__(self, priority: TaskPriority = TaskPriority.NORMAL):
        super().__init__(
            name="Crop Automatique",
            description="Suppression des bordures des frames",
            priority=priority
        )
        
        self.crop_config = CropConfig()
        self.cancel_flag = False
        self.stats = {}
    
    def configure(self,
                  frames_dir: str,
                  crop_left: int = 0,
                  crop_right: int = 0,
                  crop_top: int = 0,
                  crop_bottom: int = 0,
                  min_remaining_width: int = 100,
                  min_remaining_height: int = 100,
                  batch_size: int = 64,
                  jpeg_quality: int = 95,
                  output_suffix: str = "_cropped",
                  overwrite_originals: bool = False):
        """Configurer la tâche de crop"""
        
        self.config = {
            'frames_dir': frames_dir,
            'output_suffix': output_suffix,
            'overwrite_originals': overwrite_originals
        }
        
        self.crop_config = CropConfig(
            crop_left=crop_left,
            crop_right=crop_right,
            crop_top=crop_top,
            crop_bottom=crop_bottom,
            min_remaining_width=min_remaining_width,
            min_remaining_height=min_remaining_height,
            batch_size=batch_size,
            jpeg_quality=jpeg_quality,
            output_suffix=output_suffix,
            overwrite_originals=overwrite_originals
        )
    
    def validate_config(self) -> Tuple[bool, str]:
        """Valider la configuration"""
        if not PIL_AVAILABLE:
            return False, "Pillow non disponible. Installez: pip install Pillow"
        
        if 'frames_dir' not in self.config:
            return False, "Dossier de frames non spécifié"
        
        frames_dir = self.config['frames_dir']
        if not os.path.exists(frames_dir):
            return False, f"Dossier non trouvé: {frames_dir}"
        
        # Vérifier qu'il y a des images
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        has_images = any(
            f.lower().endswith(tuple(image_extensions))
            for f in os.listdir(frames_dir)
            if os.path.isfile(os.path.join(frames_dir, f))
        )
        
        if not has_images:
            return False, "Aucune image trouvée dans le dossier"
        
        # Vérifier qu'au moins un crop est défini
        cfg = self.crop_config
        if cfg.crop_left == 0 and cfg.crop_right == 0 and cfg.crop_top == 0 and cfg.crop_bottom == 0:
            return False, "Aucun crop défini (tous les bords à 0)"
        
        return True, "Configuration valide"
    
    def execute(self) -> bool:
        """Exécuter le crop"""
        try:
            self.update_status(TaskStatus.RUNNING, "Démarrage du crop...")
            
            frames_dir = self.config['frames_dir']
            cfg = self.crop_config
            
            # Lister les images
            image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
            all_files = sorted([
                f for f in os.listdir(frames_dir)
                if f.lower().endswith(tuple(image_extensions))
            ])
            
            total_files = len(all_files)
            self.log(f"Images à traiter: {total_files:,}", "INFO")
            
            if total_files == 0:
                self.update_status(TaskStatus.COMPLETED, "Aucune image à traiter")
                return True
            
            # Vérifier les dimensions sur la première image
            first_image_path = os.path.join(frames_dir, all_files[0])
            with Image.open(first_image_path) as img:
                orig_w, orig_h = img.size
            
            # Calculer les dimensions finales
            final_w = orig_w - cfg.crop_left - cfg.crop_right
            final_h = orig_h - cfg.crop_top - cfg.crop_bottom
            
            self.log(f"Image originale: {orig_w}x{orig_h}px", "INFO")
            self.log(f"Crop: gauche={cfg.crop_left}, droite={cfg.crop_right}, haut={cfg.crop_top}, bas={cfg.crop_bottom}", "INFO")
            self.log(f"Image finale: {final_w}x{final_h}px", "INFO")
            
            # Validation des dimensions
            if final_w < cfg.min_remaining_width or final_h < cfg.min_remaining_height:
                error_msg = (f"Dimensions finales trop petites: {final_w}x{final_h}px. "
                           f"Minimum: {cfg.min_remaining_width}x{cfg.min_remaining_height}px")
                self.log(error_msg, "ERROR")
                self.update_status(TaskStatus.FAILED, error_msg)
                return False
            
            # Créer le dossier de sortie
            if cfg.overwrite_originals:
                output_dir = frames_dir
                self.log("Mode: Écrasement des originaux", "WARNING")
            else:
                output_dir = frames_dir.rstrip('/\\') + cfg.output_suffix
                os.makedirs(output_dir, exist_ok=True)
                self.log(f"Sortie: {output_dir}", "INFO")
            
            # Traitement
            processed = 0
            cropped = 0
            errors = 0
            start_time = time.time()
            last_update = start_time
            
            for idx, filename in enumerate(all_files):
                if self.cancel_flag:
                    self.update_status(TaskStatus.CANCELLED, "Annulé")
                    return False
                
                filepath = os.path.join(frames_dir, filename)
                output_path = os.path.join(output_dir, filename)
                
                try:
                    with Image.open(filepath) as img:
                        img_w, img_h = img.size
                        
                        # Calculer la boîte de crop
                        left = cfg.crop_left
                        top = cfg.crop_top
                        right = img_w - cfg.crop_right
                        bottom = img_h - cfg.crop_bottom
                        
                        # Vérifier que le crop est valide pour cette image
                        if right <= left or bottom <= top:
                            self.log(f"Skip {filename}: dimensions invalides après crop", "WARNING")
                            errors += 1
                            continue
                        
                        # Appliquer le crop
                        cropped_img = img.crop((left, top, right, bottom))
                        
                        # Sauvegarder
                        if filename.lower().endswith(('.jpg', '.jpeg')):
                            cropped_img.save(output_path, quality=cfg.jpeg_quality, optimize=True)
                        else:
                            cropped_img.save(output_path, optimize=True)
                        
                        cropped += 1
                
                except Exception as e:
                    self.log(f"Erreur {filename}: {str(e)}", "ERROR")
                    errors += 1
                
                processed += 1
                
                # Mise à jour progression
                current_time = time.time()
                if current_time - last_update >= 0.5:
                    progress = int((processed / total_files) * 100)
                    elapsed = current_time - start_time
                    fps = processed / elapsed if elapsed > 0 else 0
                    
                    msg = f"{processed:,}/{total_files:,} ({fps:.0f} img/s)"
                    self.update_progress(min(progress, 99), msg)
                    last_update = current_time
            
            # Statistiques finales
            total_time = time.time() - start_time
            final_fps = processed / total_time if total_time > 0 else 0
            
            self.stats = {
                "total_processed": processed,
                "total_cropped": cropped,
                "total_errors": errors,
                "processing_time": total_time,
                "fps": final_fps,
                "success_rate": (cropped / processed * 100) if processed > 0 else 0,
                "original_size": (orig_w, orig_h),
                "final_size": (final_w, final_h),
                "crop_config": asdict(cfg),
                "output_directory": output_dir
            }
            
            # Sauvegarder le rapport
            self._save_report(output_dir)
            
            self.update_progress(100, f"✅ {cropped:,} images croppées")
            self.update_status(TaskStatus.COMPLETED, f"Terminé: {cropped:,} images")
            
            return True
            
        except Exception as e:
            self.error_message = str(e)
            self.update_status(TaskStatus.FAILED, str(e))
            self.log(f"Erreur: {str(e)}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False
    
    def _save_report(self, output_dir: str):
        """Sauvegarder le rapport de crop"""
        report_path = os.path.join(output_dir, "crop_report.json")
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
            self.log(f"Rapport sauvé: {report_path}", "INFO")
        except Exception as e:
            self.log(f"Erreur sauvegarde rapport: {e}", "WARNING")
    
    def cancel(self):
        """Annuler la tâche"""
        self.cancel_flag = True
        self.log("Annulation demandée...", "WARNING")
    
    def get_summary(self) -> str:
        """Résumé des résultats"""
        if not self.stats:
            return "Aucune statistique disponible"
        
        s = self.stats
        return f"""📊 Résumé Crop:
• Images traitées: {s['total_cropped']:,}/{s['total_processed']:,}
• Taux de réussite: {s['success_rate']:.1f}%
• Taille originale: {s['original_size'][0]}x{s['original_size'][1]}px
• Taille finale: {s['final_size'][0]}x{s['final_size'][1]}px
• Vitesse: {s['fps']:.1f} img/s"""


class ImageAnalyzer:
    """Analyseur des dimensions d'images dans un dossier"""
    
    SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    
    @staticmethod
    def analyze_folder(folder_path: str, sample_size: int = 50) -> Dict:
        """Analyser les dimensions des images d'un dossier"""
        
        if not os.path.exists(folder_path):
            raise ValueError(f"Dossier non trouvé: {folder_path}")
        
        # Lister les fichiers image
        image_files = [
            os.path.join(folder_path, f)
            for f in os.listdir(folder_path)
            if f.lower().endswith(tuple(ImageAnalyzer.SUPPORTED_FORMATS))
        ]
        
        if not image_files:
            raise ValueError("Aucune image trouvée dans le dossier")
        
        # Échantillonner
        import random
        sample = random.sample(image_files, min(sample_size, len(image_files)))
        
        dimensions = []
        valid_files = []
        
        for img_path in sample:
            try:
                with Image.open(img_path) as img:
                    dimensions.append(img.size)
                    valid_files.append(img_path)
            except:
                pass
        
        if not dimensions:
            raise ValueError("Aucune image valide trouvée")
        
        widths = [d[0] for d in dimensions]
        heights = [d[1] for d in dimensions]
        
        return {
            "total_files": len(image_files),
            "analyzed_files": len(valid_files),
            "width": {
                "min": min(widths),
                "max": max(widths),
                "avg": sum(widths) / len(widths),
                "common": max(set(widths), key=widths.count)
            },
            "height": {
                "min": min(heights),
                "max": max(heights),
                "avg": sum(heights) / len(heights),
                "common": max(set(heights), key=heights.count)
            },
            "uniform_size": len(set(dimensions)) == 1,
            "most_common_size": max(set(dimensions), key=dimensions.count),
            "sample_files": valid_files[:5],
            "all_files": image_files
        }
    
    @staticmethod
    def get_image_dimensions(image_path: str) -> Tuple[int, int]:
        """Obtenir les dimensions d'une image"""
        with Image.open(image_path) as img:
            return img.size
    
    @staticmethod
    def create_preview(image_path: str, crop_left: int = 0, crop_right: int = 0,
                       crop_top: int = 0, crop_bottom: int = 0,
                       max_size: Tuple[int, int] = (800, 600)) -> Tuple[Image.Image, Image.Image]:
        """
        Créer une prévisualisation avant/après du crop
        
        Returns:
            Tuple (image_originale_redimensionnée, image_croppée_redimensionnée)
        """
        with Image.open(image_path) as img:
            orig_w, orig_h = img.size
            
            # Image originale redimensionnée
            original = img.copy()
            original.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            # Appliquer le crop
            left = crop_left
            top = crop_top
            right = orig_w - crop_right
            bottom = orig_h - crop_bottom
            
            if right > left and bottom > top:
                cropped = img.crop((left, top, right, bottom))
                cropped.thumbnail(max_size, Image.Resampling.LANCZOS)
            else:
                cropped = original.copy()
            
            return original, cropped