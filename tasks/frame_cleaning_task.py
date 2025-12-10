"""
Frame Cleaning Task - Tâche de nettoyage automatique des frames floues/invalides
Intègre le système de détection GPU avec le pipeline
"""

import os
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional

from .base_task import BaseTask, TaskStatus, TaskPriority

# Imports conditionnels pour GPU
try:
    import torch
    import torch.nn.functional as F
    from torchvision import transforms
    from PIL import Image
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    import cv2
    import numpy as np
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


@dataclass
class CleaningConfig:
    """Configuration des seuils de nettoyage"""
    # Seuils de détection (adaptés pour tenseurs normalisés [0,1])
    black_threshold: float = 0.08           # Luminosité moyenne max pour "noir"
    blur_threshold: float = 0.0015          # Variance Laplacian min pour "net"
    uniform_threshold: float = 0.008        # Variance couleur min pour "varié"
    edge_threshold: float = 0.005           # Ratio contours min pour "contenu"
    
    # Seuils de taille/résolution
    min_width: int = 200
    min_height: int = 150
    
    # Options de nettoyage
    remove_black: bool = True
    remove_blurry: bool = True
    remove_uniform: bool = True
    remove_low_content: bool = True
    remove_corrupted: bool = True
    remove_small: bool = True
    
    # Performance
    batch_size: int = 32
    resize_for_analysis: Tuple[int, int] = (224, 224)
    
    # Seuils combinés
    min_issues_to_remove: int = 1


@dataclass
class FrameAnalysis:
    """Résultat d'analyse d'une frame"""
    filename: str
    filepath: str
    is_valid: bool
    issues: List[str]
    metrics: Dict[str, float]
    file_size: int


class FrameCleaningTask(BaseTask):
    """
    Tâche de nettoyage automatique des frames
    Détecte et supprime les frames de mauvaise qualité
    """
    
    def __init__(self, priority: TaskPriority = TaskPriority.NORMAL):
        super().__init__(
            name="Nettoyage de Frames",
            description="Analyse et suppression des frames floues/invalides",
            priority=priority
        )
        
        # Configuration par défaut
        self.cleaning_config = CleaningConfig()
        
        # Résultats
        self.analysis_results: List[FrameAnalysis] = []
        self.cleaning_stats: Dict = {}
        
        # Contrôle
        self.cancel_flag = False
        self.dry_run = True  # Par défaut, analyse seulement
        
        # Device GPU/CPU
        self.device = None
        self.use_gpu = False
        
        # Kernels pour analyse
        self.laplacian_kernel = None
        self.sobel_x = None
        self.sobel_y = None
        self.gaussian_kernel = None
        self.transform = None
    
    def configure(self, 
                  frames_dir: str,
                  dry_run: bool = True,
                  # Seuils
                  black_threshold: float = 0.08,
                  blur_threshold: float = 0.0015,
                  uniform_threshold: float = 0.008,
                  edge_threshold: float = 0.005,
                  min_width: int = 200,
                  min_height: int = 150,
                  # Options
                  remove_black: bool = True,
                  remove_blurry: bool = True,
                  remove_uniform: bool = True,
                  remove_low_content: bool = True,
                  remove_small: bool = True,
                  # Performance
                  batch_size: int = 32,
                  use_gpu: bool = True):
        """Configurer la tâche de nettoyage"""
        
        self.config = {
            'frames_dir': frames_dir,
            'dry_run': dry_run,
            'use_gpu': use_gpu
        }
        
        self.dry_run = dry_run
        self.use_gpu = use_gpu and TORCH_AVAILABLE
        
        # Mettre à jour la configuration
        self.cleaning_config = CleaningConfig(
            black_threshold=black_threshold,
            blur_threshold=blur_threshold,
            uniform_threshold=uniform_threshold,
            edge_threshold=edge_threshold,
            min_width=min_width,
            min_height=min_height,
            remove_black=remove_black,
            remove_blurry=remove_blurry,
            remove_uniform=remove_uniform,
            remove_low_content=remove_low_content,
            remove_small=remove_small,
            batch_size=batch_size
        )
    
    def validate_config(self) -> Tuple[bool, str]:
        """Valider la configuration"""
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
        
        # Vérifier les dépendances
        if self.use_gpu and not TORCH_AVAILABLE:
            return False, "PyTorch non disponible. Installez: pip install torch torchvision"
        
        if not self.use_gpu and not CV2_AVAILABLE:
            return False, "OpenCV non disponible. Installez: pip install opencv-python"
        
        return True, "Configuration valide"
    
    def _setup_gpu(self):
        """Initialiser les ressources GPU"""
        if not TORCH_AVAILABLE:
            return
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.log(f"Device: {self.device}", "INFO")
        
        # Kernel Laplacian
        self.laplacian_kernel = torch.tensor([
            [0, 1, 0],
            [1, -4, 1],
            [0, 1, 0]
        ], dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(self.device)
        
        # Kernels Sobel
        self.sobel_x = torch.tensor([
            [-1, 0, 1],
            [-2, 0, 2],
            [-1, 0, 1]
        ], dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(self.device)
        
        self.sobel_y = torch.tensor([
            [-1, -2, -1],
            [0, 0, 0],
            [1, 2, 1]
        ], dtype=torch.float32).unsqueeze(0).unsqueeze(0).to(self.device)
        
        # Kernel Gaussian
        gaussian = torch.tensor([
            [1, 2, 1],
            [2, 4, 2],
            [1, 2, 1]
        ], dtype=torch.float32) / 16.0
        self.gaussian_kernel = gaussian.unsqueeze(0).unsqueeze(0).to(self.device)
        
        # Transform
        self.transform = transforms.Compose([
            transforms.Resize(self.cleaning_config.resize_for_analysis),
            transforms.ToTensor()
        ])
    
    def execute(self) -> bool:
        """Exécuter le nettoyage"""
        try:
            self.update_status(TaskStatus.RUNNING, "Démarrage du nettoyage...")
            
            frames_dir = self.config['frames_dir']
            
            # Initialiser GPU si disponible
            if self.use_gpu:
                self._setup_gpu()
                return self._execute_gpu(frames_dir)
            else:
                return self._execute_cpu(frames_dir)
            
        except Exception as e:
            self.error_message = str(e)
            self.update_status(TaskStatus.FAILED, str(e))
            self.log(f"Erreur: {str(e)}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False
    
    def _execute_gpu(self, frames_dir: str) -> bool:
        """Exécution avec PyTorch GPU"""
        from PIL import Image
        
        self.log(f"Mode GPU activé sur {self.device}", "INFO")
        
        # Lister les images
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        all_files = sorted([
            f for f in os.listdir(frames_dir)
            if f.lower().endswith(tuple(image_extensions))
        ])
        
        total_files = len(all_files)
        self.log(f"Frames à analyser: {total_files:,}", "INFO")
        
        if total_files == 0:
            self.update_status(TaskStatus.COMPLETED, "Aucune frame à analyser")
            return True
        
        # Analyse par batches
        batch_size = self.cleaning_config.batch_size
        all_results = []
        processed = 0
        start_time = time.time()
        last_update = start_time
        
        for batch_start in range(0, total_files, batch_size):
            if self.cancel_flag:
                self.update_status(TaskStatus.CANCELLED, "Annulé par l'utilisateur")
                return False
            
            batch_end = min(batch_start + batch_size, total_files)
            batch_files = all_files[batch_start:batch_end]
            
            # Charger le batch
            images = []
            paths = []
            file_sizes = []
            original_sizes = []
            corrupted = []
            
            for filename in batch_files:
                filepath = os.path.join(frames_dir, filename)
                try:
                    file_size = os.path.getsize(filepath)
                    img = Image.open(filepath).convert("RGB")
                    original_size = img.size
                    img_tensor = self.transform(img)
                    
                    images.append(img_tensor)
                    paths.append(filepath)
                    file_sizes.append(file_size)
                    original_sizes.append(original_size)
                except Exception as e:
                    # Fichier corrompu
                    corrupted.append(FrameAnalysis(
                        filename=filename,
                        filepath=filepath,
                        is_valid=False,
                        issues=["corrupted_file"],
                        metrics={},
                        file_size=os.path.getsize(filepath) if os.path.exists(filepath) else 0
                    ))
            
            # Ajouter les fichiers corrompus
            all_results.extend(corrupted)
            
            if images:
                # Analyser le batch
                batch_tensor = torch.stack(images).to(self.device)
                batch_results = self._analyze_batch_gpu(batch_tensor, paths, file_sizes, original_sizes)
                all_results.extend(batch_results)
            
            processed = batch_end
            
            # Mise à jour progression
            current_time = time.time()
            if current_time - last_update >= 0.5:
                progress = int((processed / total_files) * 100)
                elapsed = current_time - start_time
                fps = processed / elapsed if elapsed > 0 else 0
                invalid_count = sum(1 for r in all_results if not r.is_valid)
                
                msg = f"{processed:,}/{total_files:,} frames ({fps:.0f} f/s) - {invalid_count:,} invalides"
                self.update_progress(min(progress, 99), msg)
                last_update = current_time
        
        # Stocker les résultats
        self.analysis_results = all_results
        self.cleaning_stats = self._calculate_statistics(all_results)
        
        # Phase de suppression si pas dry_run
        if not self.dry_run:
            self.log("Phase de suppression...", "INFO")
            removed = self._remove_invalid_frames(all_results, frames_dir)
            self.cleaning_stats["removed_files"] = removed
            self.cleaning_stats["removed_count"] = len(removed)
        else:
            self.cleaning_stats["removed_files"] = []
            self.cleaning_stats["removed_count"] = 0
        
        # Sauvegarder le rapport
        self._save_report(frames_dir)
        
        # Finaliser
        mode_str = "Analyse" if self.dry_run else "Nettoyage"
        self.update_progress(100, f"✅ {mode_str} terminé")
        self.update_status(TaskStatus.COMPLETED, f"{mode_str} terminé avec succès")
        
        return True
    
    def _analyze_batch_gpu(self, batch: torch.Tensor, paths: List[str],
                           file_sizes: List[int], original_sizes: List[Tuple]) -> List[FrameAnalysis]:
        """Analyser un batch avec GPU"""
        batch_size = batch.shape[0]
        results = []
        
        # Analyses par type
        cfg = self.cleaning_config
        
        # Frames noires
        if cfg.remove_black:
            brightness = batch.mean(dim=[1, 2, 3])
            black_mask = brightness < cfg.black_threshold
        else:
            black_mask = torch.zeros(batch_size, dtype=torch.bool, device=self.device)
        
        # Frames floues
        if cfg.remove_blurry:
            gray = batch.mean(dim=1, keepdim=True)
            laplace = F.conv2d(gray, self.laplacian_kernel, padding=1)
            blur_var = laplace.var(dim=[1, 2, 3])
            blur_mask = blur_var < cfg.blur_threshold
        else:
            blur_mask = torch.zeros(batch_size, dtype=torch.bool, device=self.device)
        
        # Frames uniformes
        if cfg.remove_uniform:
            color_var = batch.var(dim=[1, 2, 3])
            uniform_mask = color_var < cfg.uniform_threshold
        else:
            uniform_mask = torch.zeros(batch_size, dtype=torch.bool, device=self.device)
        
        # Faible contenu
        if cfg.remove_low_content:
            gray = batch.mean(dim=1, keepdim=True)
            denoised = F.conv2d(gray, self.gaussian_kernel, padding=1)
            grad_x = F.conv2d(denoised, self.sobel_x, padding=1)
            grad_y = F.conv2d(denoised, self.sobel_y, padding=1)
            magnitude = torch.sqrt(grad_x**2 + grad_y**2)
            
            low_content_mask = []
            for i in range(batch_size):
                mag = magnitude[i, 0]
                threshold = torch.quantile(mag.flatten(), 0.85)
                edges = (mag > threshold).float()
                edge_ratio = edges.mean()
                low_content_mask.append(edge_ratio < cfg.edge_threshold)
            low_content_mask = torch.stack(low_content_mask)
        else:
            low_content_mask = torch.zeros(batch_size, dtype=torch.bool, device=self.device)
        
        # Calculer métriques
        brightness_vals = batch.mean(dim=[1, 2, 3])
        color_vars = batch.var(dim=[1, 2, 3])
        
        gray = batch.mean(dim=1, keepdim=True)
        laplace = F.conv2d(gray, self.laplacian_kernel, padding=1)
        blur_scores = laplace.var(dim=[1, 2, 3])
        
        # Construire résultats
        for i in range(batch_size):
            issues = []
            
            # Vérifier taille
            width, height = original_sizes[i]
            if cfg.remove_small and (width < cfg.min_width or height < cfg.min_height):
                issues.append("resolution_too_small")
            
            if black_mask[i]:
                issues.append("too_dark")
            if blur_mask[i]:
                issues.append("too_blurry")
            if uniform_mask[i]:
                issues.append("too_uniform")
            if low_content_mask[i]:
                issues.append("low_content")
            
            is_valid = len(issues) < cfg.min_issues_to_remove
            
            metrics = {
                "brightness": float(brightness_vals[i]),
                "color_variance": float(color_vars[i]),
                "blur_score": float(blur_scores[i]),
                "width": width,
                "height": height
            }
            
            results.append(FrameAnalysis(
                filename=Path(paths[i]).name,
                filepath=paths[i],
                is_valid=is_valid,
                issues=issues,
                metrics=metrics,
                file_size=file_sizes[i]
            ))
        
        return results
    
    def _execute_cpu(self, frames_dir: str) -> bool:
        """Exécution avec OpenCV CPU (fallback)"""
        self.log("Mode CPU (OpenCV)", "INFO")
        
        # Lister les images
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        all_files = sorted([
            f for f in os.listdir(frames_dir)
            if f.lower().endswith(tuple(image_extensions))
        ])
        
        total_files = len(all_files)
        self.log(f"Frames à analyser: {total_files:,}", "INFO")
        
        if total_files == 0:
            self.update_status(TaskStatus.COMPLETED, "Aucune frame à analyser")
            return True
        
        all_results = []
        start_time = time.time()
        last_update = start_time
        
        cfg = self.cleaning_config
        
        for idx, filename in enumerate(all_files):
            if self.cancel_flag:
                self.update_status(TaskStatus.CANCELLED, "Annulé")
                return False
            
            filepath = os.path.join(frames_dir, filename)
            
            try:
                file_size = os.path.getsize(filepath)
                img = cv2.imread(filepath)
                
                if img is None:
                    all_results.append(FrameAnalysis(
                        filename=filename,
                        filepath=filepath,
                        is_valid=False,
                        issues=["corrupted_file"],
                        metrics={},
                        file_size=file_size
                    ))
                    continue
                
                height, width = img.shape[:2]
                issues = []
                
                # Conversion grayscale
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                
                # Brightness
                brightness = np.mean(img) / 255.0
                if cfg.remove_black and brightness < cfg.black_threshold:
                    issues.append("too_dark")
                
                # Blur (Laplacian variance)
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                blur_score = laplacian.var() / 10000.0  # Normaliser
                if cfg.remove_blurry and blur_score < cfg.blur_threshold:
                    issues.append("too_blurry")
                
                # Uniformité
                color_var = np.var(img / 255.0)
                if cfg.remove_uniform and color_var < cfg.uniform_threshold:
                    issues.append("too_uniform")
                
                # Contenu (edges)
                edges = cv2.Canny(gray, 50, 150)
                edge_ratio = np.sum(edges > 0) / edges.size
                if cfg.remove_low_content and edge_ratio < cfg.edge_threshold:
                    issues.append("low_content")
                
                # Taille
                if cfg.remove_small and (width < cfg.min_width or height < cfg.min_height):
                    issues.append("resolution_too_small")
                
                is_valid = len(issues) < cfg.min_issues_to_remove
                
                all_results.append(FrameAnalysis(
                    filename=filename,
                    filepath=filepath,
                    is_valid=is_valid,
                    issues=issues,
                    metrics={
                        "brightness": brightness,
                        "blur_score": blur_score,
                        "color_variance": color_var,
                        "edge_ratio": edge_ratio,
                        "width": width,
                        "height": height
                    },
                    file_size=file_size
                ))
                
            except Exception as e:
                all_results.append(FrameAnalysis(
                    filename=filename,
                    filepath=filepath,
                    is_valid=False,
                    issues=["corrupted_file"],
                    metrics={},
                    file_size=0
                ))
            
            # Progression
            current_time = time.time()
            if current_time - last_update >= 0.5:
                progress = int(((idx + 1) / total_files) * 100)
                elapsed = current_time - start_time
                fps = (idx + 1) / elapsed if elapsed > 0 else 0
                invalid = sum(1 for r in all_results if not r.is_valid)
                
                msg = f"{idx + 1:,}/{total_files:,} ({fps:.0f} f/s) - {invalid:,} invalides"
                self.update_progress(min(progress, 99), msg)
                last_update = current_time
        
        # Résultats
        self.analysis_results = all_results
        self.cleaning_stats = self._calculate_statistics(all_results)
        
        if not self.dry_run:
            removed = self._remove_invalid_frames(all_results, frames_dir)
            self.cleaning_stats["removed_files"] = removed
            self.cleaning_stats["removed_count"] = len(removed)
        else:
            self.cleaning_stats["removed_files"] = []
            self.cleaning_stats["removed_count"] = 0
        
        self._save_report(frames_dir)
        
        mode_str = "Analyse" if self.dry_run else "Nettoyage"
        self.update_progress(100, f"✅ {mode_str} terminé")
        self.update_status(TaskStatus.COMPLETED, f"{mode_str} terminé")
        
        return True
    
    def _calculate_statistics(self, results: List[FrameAnalysis]) -> Dict:
        """Calculer les statistiques"""
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid
        
        # Répartition des problèmes
        issues_breakdown = {}
        for r in results:
            for issue in r.issues:
                issues_breakdown[issue] = issues_breakdown.get(issue, 0) + 1
        
        # Tailles
        total_size = sum(r.file_size for r in results) / (1024 * 1024)
        invalid_size = sum(r.file_size for r in results if not r.is_valid) / (1024 * 1024)
        
        return {
            "total_frames": total,
            "valid_frames": valid,
            "invalid_frames": invalid,
            "valid_percentage": (valid / total * 100) if total > 0 else 0,
            "issues_breakdown": issues_breakdown,
            "total_size_mb": total_size,
            "invalid_size_mb": invalid_size,
            "savings_mb": invalid_size
        }
    
    def _remove_invalid_frames(self, results: List[FrameAnalysis], frames_dir: str) -> List[str]:
        """Supprimer les frames invalides"""
        removed = []
        
        for r in results:
            if not r.is_valid:
                try:
                    if os.path.exists(r.filepath):
                        os.remove(r.filepath)
                        removed.append(r.filename)
                except Exception as e:
                    self.log(f"Erreur suppression {r.filename}: {e}", "ERROR")
        
        self.log(f"Supprimé: {len(removed):,} frames", "INFO")
        return removed
    
    def _save_report(self, frames_dir: str):
        """Sauvegarder le rapport JSON"""
        report_path = os.path.join(frames_dir, "cleaning_report.json")
        
        report = {
            **self.cleaning_stats,
            "config": asdict(self.cleaning_config),
            "dry_run": self.dry_run,
            "device": str(self.device) if self.device else "cpu"
        }
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.log(f"Rapport sauvé: {report_path}", "INFO")
        except Exception as e:
            self.log(f"Erreur sauvegarde rapport: {e}", "WARNING")
    
    def cancel(self):
        """Annuler la tâche"""
        self.cancel_flag = True
        self.log("Annulation demandée...", "WARNING")
    
    def get_summary(self) -> str:
        """Obtenir un résumé des résultats"""
        if not self.cleaning_stats:
            return "Aucune statistique disponible"
        
        stats = self.cleaning_stats
        mode = "Analyse" if self.dry_run else "Nettoyage"
        
        summary = f"""📊 Résumé du {mode}:
• Frames analysées: {stats['total_frames']:,}
• Frames valides: {stats['valid_frames']:,} ({stats['valid_percentage']:.1f}%)
• Frames invalides: {stats['invalid_frames']:,}
• Espace économisable: {stats['savings_mb']:.1f} MB"""
        
        if not self.dry_run and 'removed_count' in stats:
            summary += f"\n• Frames supprimées: {stats['removed_count']:,}"
        
        return summary