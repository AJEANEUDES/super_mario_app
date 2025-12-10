"""
Advanced Blur Detection Task - Détection avancée de frames floues
Analyse multi-critères avec support GPU pour une détection précise
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
class AdvancedBlurConfig:
    """Configuration avancée pour détection de flou"""
    
    # Zone de gameplay (coordonnées relatives: x, y, width, height)
    gameplay_region: Tuple[float, float, float, float] = (0.0, 0.0, 1.0, 1.0)
    
    # Seuils de détection
    laplacian_threshold: float = 0.002
    sobel_threshold: float = 0.05
    fft_threshold: float = 0.12
    texture_threshold: float = 20.0
    pixelation_threshold: float = 0.25
    
    # Seuils de transition/loading
    uniformity_threshold: float = 0.02
    black_ratio_threshold: float = 0.4
    
    # Performance
    batch_size: int = 32
    num_issues_threshold: int = 2
    resize_for_analysis: Tuple[int, int] = (224, 224)


class AdvancedBlurTask(BaseTask):
    """
    Tâche de détection avancée de frames floues
    Utilise plusieurs méthodes d'analyse pour une détection précise
    """
    
    def __init__(self, priority: TaskPriority = TaskPriority.NORMAL):
        super().__init__(
            name="Détection Avancée de Flou",
            description="Analyse multi-critères des frames floues",
            priority=priority
        )
        
        # Configuration
        self.blur_config = AdvancedBlurConfig()
        
        # Résultats
        self.analysis_results: List[Dict] = []
        self.stats: Dict = {}
        
        # Contrôle
        self.cancel_flag = False
        self.dry_run = True
        
        # GPU
        self.device = None
        self.laplacian_kernel = None
        self.sobel_x = None
        self.sobel_y = None
        self.transform = None
    
    def configure(self,
                  frames_dir: str,
                  dry_run: bool = True,
                  # Région de gameplay
                  region_x: float = 0.0,
                  region_y: float = 0.0,
                  region_w: float = 1.0,
                  region_h: float = 1.0,
                  # Seuils
                  laplacian_threshold: float = 0.002,
                  sobel_threshold: float = 0.05,
                  fft_threshold: float = 0.12,
                  texture_threshold: float = 20.0,
                  pixelation_threshold: float = 0.25,
                  uniformity_threshold: float = 0.02,
                  black_ratio_threshold: float = 0.4,
                  # Décision
                  num_issues_threshold: int = 2,
                  # Performance
                  batch_size: int = 32,
                  use_gpu: bool = True):
        """Configurer la tâche"""
        
        self.config = {
            'frames_dir': frames_dir,
            'dry_run': dry_run,
            'use_gpu': use_gpu
        }
        
        self.dry_run = dry_run
        self.use_gpu = use_gpu and TORCH_AVAILABLE
        
        self.blur_config = AdvancedBlurConfig(
            gameplay_region=(region_x, region_y, region_w, region_h),
            laplacian_threshold=laplacian_threshold,
            sobel_threshold=sobel_threshold,
            fft_threshold=fft_threshold,
            texture_threshold=texture_threshold,
            pixelation_threshold=pixelation_threshold,
            uniformity_threshold=uniformity_threshold,
            black_ratio_threshold=black_ratio_threshold,
            num_issues_threshold=num_issues_threshold,
            batch_size=batch_size
        )
    
    def validate_config(self) -> Tuple[bool, str]:
        """Valider la configuration"""
        if 'frames_dir' not in self.config:
            return False, "Dossier de frames non spécifié"
        
        frames_dir = self.config['frames_dir']
        if not os.path.exists(frames_dir):
            return False, f"Dossier non trouvé: {frames_dir}"
        
        # Vérifier les images
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        has_images = any(
            f.lower().endswith(tuple(image_extensions))
            for f in os.listdir(frames_dir)
            if os.path.isfile(os.path.join(frames_dir, f))
        )
        
        if not has_images:
            return False, "Aucune image trouvée dans le dossier"
        
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
        
        # Transform
        self.transform = transforms.Compose([
            transforms.Resize(self.blur_config.resize_for_analysis),
            transforms.ToTensor()
        ])
    
    def execute(self) -> bool:
        """Exécuter l'analyse"""
        try:
            self.update_status(TaskStatus.RUNNING, "Démarrage de l'analyse avancée...")
            
            frames_dir = self.config['frames_dir']
            
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
        
        self.log(f"Mode GPU sur {self.device}", "INFO")
        
        # Lister les images
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        all_files = sorted([
            f for f in os.listdir(frames_dir)
            if f.lower().endswith(tuple(image_extensions))
        ])
        
        total_files = len(all_files)
        self.log(f"Frames à analyser: {total_files:,}", "INFO")
        
        if total_files == 0:
            self.update_status(TaskStatus.COMPLETED, "Aucune frame à analyser")
            return True
        
        batch_size = self.blur_config.batch_size
        all_results = []
        processed = 0
        start_time = time.time()
        last_update = start_time
        
        for batch_start in range(0, total_files, batch_size):
            if self.cancel_flag:
                self.update_status(TaskStatus.CANCELLED, "Annulé")
                return False
            
            batch_end = min(batch_start + batch_size, total_files)
            batch_files = all_files[batch_start:batch_end]
            
            # Charger le batch
            images = []
            paths = []
            
            for filename in batch_files:
                filepath = os.path.join(frames_dir, filename)
                try:
                    img = Image.open(filepath).convert("RGB")
                    img_tensor = self.transform(img)
                    images.append(img_tensor)
                    paths.append(filepath)
                except Exception as e:
                    all_results.append({
                        "filename": filename,
                        "filepath": filepath,
                        "is_blurry": True,
                        "reason": "corrupted_file",
                        "all_issues": ["corrupted_file"],
                        "confidence": 1.0,
                        "metrics": {}
                    })
            
            if images:
                batch_tensor = torch.stack(images).to(self.device)
                batch_results = self._analyze_batch_gpu(batch_tensor, paths)
                all_results.extend(batch_results)
            
            processed = batch_end
            
            # Progression
            current_time = time.time()
            if current_time - last_update >= 0.5:
                progress = int((processed / total_files) * 100)
                elapsed = current_time - start_time
                fps = processed / elapsed if elapsed > 0 else 0
                blurry = sum(1 for r in all_results if r["is_blurry"])
                
                msg = f"{processed:,}/{total_files:,} ({fps:.0f} f/s) - {blurry:,} floues"
                self.update_progress(min(progress, 99), msg)
                last_update = current_time
        
        # Résultats
        self.analysis_results = all_results
        self.stats = self._calculate_stats(all_results)
        
        # Suppression
        if not self.dry_run:
            self.log("Phase de suppression...", "INFO")
            removed = self._remove_blurry_frames(all_results, frames_dir)
            self.stats["removed_files"] = removed
            self.stats["removed_count"] = len(removed)
        else:
            self.stats["removed_files"] = []
            self.stats["removed_count"] = 0
        
        # Rapport
        self._save_report(frames_dir)
        
        mode_str = "Analyse" if self.dry_run else "Nettoyage"
        self.update_progress(100, f"✅ {mode_str} terminé")
        self.update_status(TaskStatus.COMPLETED, f"{mode_str} terminé")
        
        return True
    
    def _extract_gameplay_region(self, batch: torch.Tensor) -> torch.Tensor:
        """Extraire la région de gameplay"""
        B, C, H, W = batch.shape
        
        x_rel, y_rel, w_rel, h_rel = self.blur_config.gameplay_region
        
        x = int(x_rel * W)
        y = int(y_rel * H)
        width = int(w_rel * W)
        height = int(h_rel * H)
        
        # S'assurer que la région est valide
        width = max(1, min(width, W - x))
        height = max(1, min(height, H - y))
        
        return batch[:, :, y:y+height, x:x+width]
    
    def _analyze_batch_gpu(self, batch: torch.Tensor, paths: List[str]) -> List[Dict]:
        """Analyse avancée GPU d'un batch"""
        
        # Extraire la région de gameplay
        gameplay = self._extract_gameplay_region(batch)
        
        if gameplay.numel() == 0:
            return [{
                "filename": Path(p).name,
                "filepath": p,
                "is_blurry": True,
                "reason": "no_gameplay_region",
                "all_issues": ["no_gameplay_region"],
                "confidence": 1.0,
                "metrics": {}
            } for p in paths]
        
        batch_size = batch.shape[0]
        cfg = self.blur_config
        
        # 1. Laplacian
        gray = gameplay.mean(dim=1, keepdim=True)
        gray_smooth = F.avg_pool2d(gray, kernel_size=3, stride=1, padding=1)
        laplace = F.conv2d(gray_smooth, self.laplacian_kernel, padding=1)
        laplacian_scores = laplace.var(dim=[1, 2, 3])
        
        # 2. Sobel
        grad_x = F.conv2d(gray, self.sobel_x, padding=1)
        grad_y = F.conv2d(gray, self.sobel_y, padding=1)
        magnitude = torch.sqrt(grad_x**2 + grad_y**2)
        sobel_scores = magnitude.mean(dim=[1, 2, 3])
        
        # 3. FFT
        fft_scores = self._analyze_fft_batch(gray)
        
        # 4. Pixelisation
        pixelation_scores = self._analyze_pixelation_batch(gray)
        
        # 5. Texture
        texture_scores = self._analyze_texture_batch(gray)
        
        # 6. Transitions
        color_variance = gameplay.var(dim=[1, 2, 3])
        grad_variance = magnitude.var(dim=[1, 2, 3])
        transition_flags = (color_variance < cfg.uniformity_threshold) | (grad_variance < 0.001)
        
        # 7. Zones noires
        black_mask = gray.squeeze(1) < 0.12
        black_ratios = black_mask.float().mean(dim=[1, 2])
        
        # Construire les résultats
        results = []
        
        for i in range(batch_size):
            issues = []
            
            if laplacian_scores[i] < cfg.laplacian_threshold:
                issues.append("low_laplacian")
            
            if sobel_scores[i] < cfg.sobel_threshold:
                issues.append("low_gradients")
            
            if fft_scores[i] < cfg.fft_threshold:
                issues.append("low_frequency_content")
            
            if pixelation_scores[i] > cfg.pixelation_threshold:
                issues.append("high_pixelation")
            
            if texture_scores[i] < cfg.texture_threshold:
                issues.append("poor_texture")
            
            if transition_flags[i]:
                issues.append("transition_screen")
            
            if black_ratios[i] > cfg.black_ratio_threshold:
                issues.append("too_much_black")
            
            confidence = len(issues) / 7.0
            is_blurry = len(issues) >= cfg.num_issues_threshold
            
            results.append({
                "filename": Path(paths[i]).name,
                "filepath": paths[i],
                "is_blurry": is_blurry,
                "reason": issues[0] if issues else "good_quality",
                "all_issues": issues,
                "confidence": confidence,
                "metrics": {
                    "laplacian_variance": float(laplacian_scores[i]),
                    "sobel_gradient": float(sobel_scores[i]),
                    "fft_ratio": float(fft_scores[i]),
                    "pixelation": float(pixelation_scores[i]),
                    "texture": float(texture_scores[i]),
                    "is_transition": bool(transition_flags[i]),
                    "black_ratio": float(black_ratios[i])
                }
            })
        
        return results
    
    def _analyze_fft_batch(self, gray_batch: torch.Tensor) -> torch.Tensor:
        """Analyse FFT pour détecter le contenu haute fréquence"""
        B, C, H, W = gray_batch.shape
        
        # FFT 2D
        fft = torch.fft.fft2(gray_batch.squeeze(1))
        fft_shift = torch.fft.fftshift(fft)
        magnitude = torch.abs(fft_shift)
        
        # Masque pour hautes fréquences
        center_h, center_w = H // 2, W // 2
        y, x = torch.meshgrid(torch.arange(H), torch.arange(W), indexing='ij')
        y, x = y.to(self.device), x.to(self.device)
        
        dist = torch.sqrt((y - center_h).float()**2 + (x - center_w).float()**2)
        
        inner_radius = min(H, W) // 6
        outer_radius = min(H, W) // 3
        mask = (dist > inner_radius) & (dist < outer_radius)
        
        ratios = []
        for i in range(B):
            mag = magnitude[i]
            high_freq = mag[mask].mean() if mask.any() else torch.tensor(0.0).to(self.device)
            total = mag.mean()
            ratio = high_freq / (total + 1e-8)
            ratios.append(ratio)
        
        return torch.stack(ratios)
    
    def _analyze_pixelation_batch(self, gray_batch: torch.Tensor) -> torch.Tensor:
        """Détecter la pixelisation"""
        B, C, H, W = gray_batch.shape
        block_size = 8
        
        scores = []
        for i in range(B):
            img = gray_batch[i, 0]
            
            try:
                blocks = F.unfold(
                    img.unsqueeze(0).unsqueeze(0),
                    kernel_size=block_size,
                    stride=block_size // 2
                )
                
                if blocks.shape[-1] == 0:
                    scores.append(torch.tensor(0.0).to(self.device))
                    continue
                
                blocks = blocks.squeeze(0).transpose(0, 1)
                block_stds = blocks.std(dim=1)
                uniform_ratio = (block_stds < 0.02).float().mean()
                scores.append(uniform_ratio)
            except:
                scores.append(torch.tensor(0.0).to(self.device))
        
        return torch.stack(scores)
    
    def _analyze_texture_batch(self, gray_batch: torch.Tensor) -> torch.Tensor:
        """Analyse de texture via LBP simplifié"""
        B, C, H, W = gray_batch.shape
        
        # Kernels LBP
        offsets = [(-1,-1), (-1,0), (-1,1), (0,1), (1,1), (1,0), (1,-1), (0,-1)]
        kernels = []
        
        for dy, dx in offsets:
            kernel = torch.zeros(3, 3, device=self.device)
            kernel[1, 1] = -1
            kernel[1+dy, 1+dx] = 1
            kernels.append(kernel.unsqueeze(0).unsqueeze(0))
        
        kernels = torch.cat(kernels, dim=0)
        
        # Réponses
        responses = F.conv2d(gray_batch, kernels, padding=1)
        binary = (responses > 0).float()
        
        # Pattern LBP
        powers = torch.pow(2, torch.arange(8, device=self.device).float()).view(1, 8, 1, 1)
        lbp = (binary * powers).sum(dim=1)
        
        # Variance
        texture_var = lbp.var(dim=[1, 2])
        
        return texture_var
    
    def _execute_cpu(self, frames_dir: str) -> bool:
        """Exécution CPU avec OpenCV"""
        self.log("Mode CPU (OpenCV)", "INFO")
        
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp'}
        all_files = sorted([
            f for f in os.listdir(frames_dir)
            if f.lower().endswith(tuple(image_extensions))
        ])
        
        total_files = len(all_files)
        self.log(f"Frames à analyser: {total_files:,}", "INFO")
        
        if total_files == 0:
            self.update_status(TaskStatus.COMPLETED, "Aucune frame")
            return True
        
        all_results = []
        start_time = time.time()
        last_update = start_time
        cfg = self.blur_config
        
        for idx, filename in enumerate(all_files):
            if self.cancel_flag:
                self.update_status(TaskStatus.CANCELLED, "Annulé")
                return False
            
            filepath = os.path.join(frames_dir, filename)
            
            try:
                img = cv2.imread(filepath)
                if img is None:
                    all_results.append({
                        "filename": filename,
                        "filepath": filepath,
                        "is_blurry": True,
                        "reason": "corrupted_file",
                        "all_issues": ["corrupted_file"],
                        "confidence": 1.0,
                        "metrics": {}
                    })
                    continue
                
                # Extraire région
                h, w = img.shape[:2]
                x_rel, y_rel, w_rel, h_rel = cfg.gameplay_region
                x = int(x_rel * w)
                y = int(y_rel * h)
                rw = int(w_rel * w)
                rh = int(h_rel * h)
                
                region = img[y:y+rh, x:x+rw]
                if region.size == 0:
                    region = img
                
                gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
                gray_float = gray.astype(np.float32) / 255.0
                
                issues = []
                
                # 1. Laplacian
                laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                lap_var = laplacian.var() / 10000.0
                if lap_var < cfg.laplacian_threshold:
                    issues.append("low_laplacian")
                
                # 2. Sobel
                sobel_x = cv2.Sobel(gray_float, cv2.CV_64F, 1, 0, ksize=3)
                sobel_y = cv2.Sobel(gray_float, cv2.CV_64F, 0, 1, ksize=3)
                sobel_mag = np.sqrt(sobel_x**2 + sobel_y**2)
                sobel_mean = sobel_mag.mean()
                if sobel_mean < cfg.sobel_threshold:
                    issues.append("low_gradients")
                
                # 3. FFT
                f = np.fft.fft2(gray_float)
                fshift = np.fft.fftshift(f)
                magnitude = np.abs(fshift)
                ch, cw = gray.shape[0]//2, gray.shape[1]//2
                inner_r = min(gray.shape) // 6
                outer_r = min(gray.shape) // 3
                y_idx, x_idx = np.ogrid[:gray.shape[0], :gray.shape[1]]
                dist = np.sqrt((y_idx - ch)**2 + (x_idx - cw)**2)
                mask = (dist > inner_r) & (dist < outer_r)
                fft_ratio = magnitude[mask].mean() / (magnitude.mean() + 1e-8)
                if fft_ratio < cfg.fft_threshold:
                    issues.append("low_frequency_content")
                
                # 4. Pixelisation (simplifié)
                block_size = 8
                h_blocks = gray.shape[0] // block_size
                w_blocks = gray.shape[1] // block_size
                if h_blocks > 0 and w_blocks > 0:
                    uniform_count = 0
                    total_blocks = 0
                    for by in range(h_blocks):
                        for bx in range(w_blocks):
                            block = gray_float[by*block_size:(by+1)*block_size,
                                              bx*block_size:(bx+1)*block_size]
                            if block.std() < 0.02:
                                uniform_count += 1
                            total_blocks += 1
                    pix_score = uniform_count / total_blocks if total_blocks > 0 else 0
                    if pix_score > cfg.pixelation_threshold:
                        issues.append("high_pixelation")
                else:
                    pix_score = 0
                
                # 5. Texture
                texture_var = gray_float.var() * 1000
                if texture_var < cfg.texture_threshold:
                    issues.append("poor_texture")
                
                # 6. Transition
                color_var = region.astype(np.float32).var() / (255**2)
                if color_var < cfg.uniformity_threshold:
                    issues.append("transition_screen")
                
                # 7. Zones noires
                black_ratio = (gray_float < 0.12).mean()
                if black_ratio > cfg.black_ratio_threshold:
                    issues.append("too_much_black")
                
                confidence = len(issues) / 7.0
                is_blurry = len(issues) >= cfg.num_issues_threshold
                
                all_results.append({
                    "filename": filename,
                    "filepath": filepath,
                    "is_blurry": is_blurry,
                    "reason": issues[0] if issues else "good_quality",
                    "all_issues": issues,
                    "confidence": confidence,
                    "metrics": {
                        "laplacian_variance": lap_var,
                        "sobel_gradient": sobel_mean,
                        "fft_ratio": fft_ratio,
                        "pixelation": pix_score,
                        "texture": texture_var,
                        "is_transition": "transition_screen" in issues,
                        "black_ratio": black_ratio
                    }
                })
                
            except Exception as e:
                all_results.append({
                    "filename": filename,
                    "filepath": filepath,
                    "is_blurry": True,
                    "reason": "error",
                    "all_issues": ["processing_error"],
                    "confidence": 1.0,
                    "metrics": {}
                })
            
            # Progression
            current_time = time.time()
            if current_time - last_update >= 0.5:
                progress = int(((idx + 1) / total_files) * 100)
                elapsed = current_time - start_time
                fps = (idx + 1) / elapsed if elapsed > 0 else 0
                blurry = sum(1 for r in all_results if r["is_blurry"])
                
                msg = f"{idx + 1:,}/{total_files:,} ({fps:.0f} f/s) - {blurry:,} floues"
                self.update_progress(min(progress, 99), msg)
                last_update = current_time
        
        # Résultats
        self.analysis_results = all_results
        self.stats = self._calculate_stats(all_results)
        
        if not self.dry_run:
            removed = self._remove_blurry_frames(all_results, frames_dir)
            self.stats["removed_files"] = removed
            self.stats["removed_count"] = len(removed)
        else:
            self.stats["removed_files"] = []
            self.stats["removed_count"] = 0
        
        self._save_report(frames_dir)
        
        mode_str = "Analyse" if self.dry_run else "Nettoyage"
        self.update_progress(100, f"✅ {mode_str} terminé")
        self.update_status(TaskStatus.COMPLETED, f"{mode_str} terminé")
        
        return True
    
    def _calculate_stats(self, results: List[Dict]) -> Dict:
        """Calculer les statistiques"""
        total = len(results)
        blurry = sum(1 for r in results if r["is_blurry"])
        sharp = total - blurry
        
        # Répartition des problèmes
        issues_breakdown = {}
        for r in results:
            for issue in r.get("all_issues", []):
                issues_breakdown[issue] = issues_breakdown.get(issue, 0) + 1
        
        # Métriques moyennes (frames nettes)
        quality_metrics = {}
        if sharp > 0:
            metric_sums = {}
            for r in results:
                if not r["is_blurry"]:
                    for metric, value in r.get("metrics", {}).items():
                        if isinstance(value, (int, float)):
                            if metric not in metric_sums:
                                metric_sums[metric] = 0
                            metric_sums[metric] += value
            
            for metric, total_val in metric_sums.items():
                quality_metrics[f"avg_{metric}"] = total_val / sharp
        
        return {
            "total_frames": total,
            "sharp_frames": sharp,
            "blurry_frames": blurry,
            "sharp_percentage": (sharp / total * 100) if total > 0 else 0,
            "issues_breakdown": issues_breakdown,
            "quality_metrics": quality_metrics
        }
    
    def _remove_blurry_frames(self, results: List[Dict], frames_dir: str) -> List[str]:
        """Supprimer les frames floues"""
        removed = []
        
        for r in results:
            if r["is_blurry"]:
                filepath = r.get("filepath", os.path.join(frames_dir, r["filename"]))
                try:
                    if os.path.exists(filepath):
                        os.remove(filepath)
                        removed.append(r["filename"])
                except Exception as e:
                    self.log(f"Erreur suppression {r['filename']}: {e}", "ERROR")
        
        self.log(f"Supprimé: {len(removed):,} frames", "INFO")
        return removed
    
    def _save_report(self, frames_dir: str):
        """Sauvegarder le rapport"""
        report_path = os.path.join(frames_dir, "advanced_blur_report.json")
        
        report = {
            **self.stats,
            "config": asdict(self.blur_config),
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
        """Résumé des résultats"""
        if not self.stats:
            return "Aucune statistique disponible"
        
        s = self.stats
        mode = "Analyse" if self.dry_run else "Nettoyage"
        
        summary = f"""📊 Résumé {mode} Avancé:
• Frames analysées: {s['total_frames']:,}
• Frames nettes: {s['sharp_frames']:,} ({s['sharp_percentage']:.1f}%)
• Frames floues: {s['blurry_frames']:,}"""
        
        if not self.dry_run and 'removed_count' in s:
            summary += f"\n• Frames supprimées: {s['removed_count']:,}"
        
        return summary