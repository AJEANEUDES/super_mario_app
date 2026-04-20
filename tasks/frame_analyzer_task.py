"""
Frame Analyzer Task - Analyse statistique des images dans un dossier
Collecte les informations sur les résolutions, formats, tailles, modes couleur
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Callable
from collections import Counter, defaultdict
from datetime import datetime

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False


@dataclass
class AnalyzerConfig:
    """Configuration de l'analyseur"""
    source_dir: str = ""
    recursive: bool = True
    output_json: str = ""


@dataclass
class ImageInfo:
    """Informations sur une image"""
    filename: str
    filepath: str
    resolution: str
    width: int
    height: int
    channels: int
    format: str
    mode: str
    file_size_bytes: int
    file_size_kb: float
    aspect_ratio: float


@dataclass
class LevelStats:
    """Statistiques par niveau/dossier"""
    name: str
    count: int = 0
    total_size: int = 0
    images: List[ImageInfo] = field(default_factory=list)


@dataclass
class AnalysisResult:
    """Résultat de l'analyse"""
    success: bool = False
    total_images: int = 0
    total_size_bytes: int = 0
    total_size_mb: float = 0.0
    avg_size_kb: float = 0.0
    min_size_kb: float = 0.0
    max_size_kb: float = 0.0
    
    resolutions: Dict[str, int] = field(default_factory=dict)
    formats: Dict[str, int] = field(default_factory=dict)
    color_modes: Dict[str, int] = field(default_factory=dict)
    aspect_ratios: Dict[str, int] = field(default_factory=dict)
    
    by_level: Dict[str, LevelStats] = field(default_factory=dict)
    
    width_range: tuple = (0, 0)
    height_range: tuple = (0, 0)
    
    errors: List[str] = field(default_factory=list)
    output_file: str = ""
    analysis_time: float = 0.0


class FrameAnalyzerTask:
    """
    Tâche d'analyse statistique des frames/images
    """
    
    IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.tif', '.webp'}
    
    def __init__(self):
        self.config: Optional[AnalyzerConfig] = None
        
        # État
        self.is_running = False
        self.should_stop = False
        self.current_progress = 0
        self.total_files = 0
        
        # Données collectées
        self.file_sizes: List[int] = []
        self.widths: List[int] = []
        self.heights: List[int] = []
        
        # Callbacks
        self.log_callback: Optional[Callable[[str], None]] = None
        self.progress_callback: Optional[Callable[[int, int, str], None]] = None
        self.status_callback: Optional[Callable[[str], None]] = None
    
    @staticmethod
    def check_dependencies() -> Dict[str, bool]:
        """Vérifier les dépendances"""
        return {
            "cv2": CV2_AVAILABLE,
            "PIL": PIL_AVAILABLE,
            "numpy": NUMPY_AVAILABLE
        }
    
    def _log(self, message: str):
        """Logger un message"""
        if self.log_callback:
            self.log_callback(message)
    
    def _update_progress(self, current: int, total: int, filename: str = ""):
        """Mettre à jour la progression"""
        self.current_progress = current
        self.total_files = total
        if self.progress_callback:
            self.progress_callback(current, total, filename)
    
    def _update_status(self, status: str):
        """Mettre à jour le statut"""
        if self.status_callback:
            self.status_callback(status)
    
    def configure(self, config: AnalyzerConfig,
                  log_callback: Optional[Callable] = None,
                  progress_callback: Optional[Callable] = None,
                  status_callback: Optional[Callable] = None):
        """Configurer la tâche"""
        self.config = config
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.status_callback = status_callback
    
    def validate_config(self) -> tuple:
        """Valider la configuration"""
        if not self.config:
            return False, "Configuration manquante"
        
        if not self.config.source_dir:
            return False, "Dossier source non spécifié"
        
        if not os.path.exists(self.config.source_dir):
            return False, f"Dossier non trouvé: {self.config.source_dir}"
        
        if not CV2_AVAILABLE:
            return False, "OpenCV (cv2) non installé"
        
        return True, "Configuration valide"
    
    def _scan_files(self) -> List[str]:
        """Scanner les fichiers images"""
        image_files = []
        
        if self.config.recursive:
            for root, dirs, files in os.walk(self.config.source_dir):
                for filename in files:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in self.IMAGE_EXTENSIONS:
                        image_files.append(os.path.join(root, filename))
        else:
            for filename in os.listdir(self.config.source_dir):
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.IMAGE_EXTENSIONS:
                    filepath = os.path.join(self.config.source_dir, filename)
                    if os.path.isfile(filepath):
                        image_files.append(filepath)
        
        return sorted(image_files)
    
    def _analyze_image(self, filepath: str) -> Optional[ImageInfo]:
        """Analyser une image"""
        filename = Path(filepath).name
        
        try:
            # Lecture avec OpenCV
            img = cv2.imread(filepath)
            if img is None:
                return None
            
            height, width = img.shape[:2]
            channels = img.shape[2] if len(img.shape) > 2 else 1
            
            # Infos supplémentaires avec PIL
            format_name = "UNKNOWN"
            mode = "RGB"
            
            if PIL_AVAILABLE:
                try:
                    with Image.open(filepath) as pil_img:
                        format_name = pil_img.format or "UNKNOWN"
                        mode = pil_img.mode
                except:
                    pass
            
            file_size = os.path.getsize(filepath)
            aspect_ratio = round(width / height, 2) if height > 0 else 0
            
            return ImageInfo(
                filename=filename,
                filepath=filepath,
                resolution=f"{width}x{height}",
                width=width,
                height=height,
                channels=channels,
                format=format_name,
                mode=mode,
                file_size_bytes=file_size,
                file_size_kb=round(file_size / 1024, 2),
                aspect_ratio=aspect_ratio
            )
            
        except Exception as e:
            self._log(f"⚠️ Erreur avec {filename}: {e}")
            return None
    
    def execute(self) -> AnalysisResult:
        """Exécuter l'analyse"""
        result = AnalysisResult()
        self.is_running = True
        self.should_stop = False
        start_time = datetime.now()
        
        # Réinitialiser les données
        self.file_sizes = []
        self.widths = []
        self.heights = []
        
        # Compteurs
        resolutions = Counter()
        formats = Counter()
        color_modes = Counter()
        aspect_ratios = Counter()
        by_level = defaultdict(lambda: LevelStats(name=""))
        
        try:
            # Validation
            valid, message = self.validate_config()
            if not valid:
                result.errors.append(message)
                self._log(f"❌ {message}")
                return result
            
            # Scanner les fichiers
            self._log(f"🔍 Scan du dossier: {self.config.source_dir}")
            self._update_status("Scan des fichiers...")
            
            image_files = self._scan_files()
            total_files = len(image_files)
            
            if total_files == 0:
                result.errors.append("Aucune image trouvée")
                self._log("❌ Aucune image trouvée dans le dossier")
                return result
            
            self._log(f"📊 {total_files:,} images à analyser")
            self._log("=" * 50)
            
            self._update_status("Analyse en cours...")
            
            # Analyser chaque image
            for i, filepath in enumerate(image_files):
                if self.should_stop:
                    self._log("\n⏹️ Analyse arrêtée par l'utilisateur")
                    break
                
                info = self._analyze_image(filepath)
                
                if info:
                    result.total_images += 1
                    
                    # Statistiques globales
                    resolutions[info.resolution] += 1
                    formats[info.format] += 1
                    color_modes[info.mode] += 1
                    
                    # Ratio d'aspect catégorisé
                    ratio_cat = self._categorize_ratio(info.aspect_ratio)
                    aspect_ratios[ratio_cat] += 1
                    
                    self.file_sizes.append(info.file_size_bytes)
                    self.widths.append(info.width)
                    self.heights.append(info.height)
                    
                    # Par niveau/dossier
                    rel_path = os.path.relpath(os.path.dirname(filepath), self.config.source_dir)
                    level_name = rel_path if rel_path != "." else "root"
                    
                    if level_name not in by_level:
                        by_level[level_name] = LevelStats(name=level_name)
                    
                    by_level[level_name].count += 1
                    by_level[level_name].total_size += info.file_size_bytes
                    by_level[level_name].images.append(info)
                else:
                    result.errors.append(f"Échec lecture: {filepath}")
                
                # Progression
                self._update_progress(i + 1, total_files, Path(filepath).name)
                
                # Log périodique
                if (i + 1) % 500 == 0:
                    self._log(f"📈 Progression: {i + 1:,}/{total_files:,}")
            
            # Calculer les statistiques finales
            if self.file_sizes:
                result.total_size_bytes = sum(self.file_sizes)
                result.total_size_mb = round(result.total_size_bytes / 1024 / 1024, 2)
                result.avg_size_kb = round(sum(self.file_sizes) / len(self.file_sizes) / 1024, 2)
                result.min_size_kb = round(min(self.file_sizes) / 1024, 2)
                result.max_size_kb = round(max(self.file_sizes) / 1024, 2)
            
            if self.widths:
                result.width_range = (min(self.widths), max(self.widths))
            
            if self.heights:
                result.height_range = (min(self.heights), max(self.heights))
            
            result.resolutions = dict(resolutions)
            result.formats = dict(formats)
            result.color_modes = dict(color_modes)
            result.aspect_ratios = dict(aspect_ratios)
            result.by_level = {k: v for k, v in by_level.items()}
            
            # Temps d'analyse
            end_time = datetime.now()
            result.analysis_time = (end_time - start_time).total_seconds()
            
            # Sauvegarder le rapport JSON
            if self.config.output_json:
                self._save_json_report(result)
                result.output_file = self.config.output_json
            
            result.success = True
            
            # Afficher le résumé
            self._print_summary(result)
            
            self._log(f"\n🎉 Analyse terminée en {result.analysis_time:.1f}s!")
            self._update_status("Terminé!")
            
        except Exception as e:
            result.errors.append(str(e))
            self._log(f"\n❌ Erreur: {e}")
            self._update_status("Erreur!")
        
        finally:
            self.is_running = False
        
        return result
    
    def _categorize_ratio(self, ratio: float) -> str:
        """Catégoriser le ratio d'aspect"""
        if ratio < 1.0:
            return "Portrait"
        elif ratio == 1.0:
            return "Carré (1:1)"
        elif 1.3 <= ratio <= 1.4:
            return "4:3"
        elif 1.5 <= ratio <= 1.6:
            return "3:2"
        elif 1.7 <= ratio <= 1.8:
            return "16:9"
        elif ratio > 2.0:
            return "Ultra-wide"
        else:
            return f"Autre ({ratio})"
    
    def _print_summary(self, result: AnalysisResult):
        """Afficher le résumé"""
        self._log("\n" + "=" * 50)
        self._log("📊 RAPPORT D'ANALYSE DES FRAMES")
        self._log("=" * 50)
        
        self._log(f"\n📈 STATISTIQUES GLOBALES:")
        self._log(f"   Total d'images: {result.total_images:,}")
        self._log(f"   Taille totale: {result.total_size_mb:.1f} MB")
        self._log(f"   Taille moyenne: {result.avg_size_kb:.1f} KB")
        self._log(f"   Taille min/max: {result.min_size_kb:.1f} - {result.max_size_kb:.1f} KB")
        
        self._log(f"\n📐 DIMENSIONS:")
        self._log(f"   Largeurs: {result.width_range[0]} - {result.width_range[1]} px")
        self._log(f"   Hauteurs: {result.height_range[0]} - {result.height_range[1]} px")
        
        self._log(f"\n🖼️ RÉSOLUTIONS (top 5):")
        sorted_res = sorted(result.resolutions.items(), key=lambda x: x[1], reverse=True)[:5]
        for res, count in sorted_res:
            pct = (count / result.total_images) * 100
            self._log(f"   {res}: {count:,} ({pct:.1f}%)")
        
        self._log(f"\n📁 FORMATS:")
        for fmt, count in sorted(result.formats.items(), key=lambda x: x[1], reverse=True):
            pct = (count / result.total_images) * 100
            self._log(f"   {fmt}: {count:,} ({pct:.1f}%)")
        
        self._log(f"\n🎨 MODES COULEUR:")
        for mode, count in sorted(result.color_modes.items(), key=lambda x: x[1], reverse=True):
            pct = (count / result.total_images) * 100
            self._log(f"   {mode}: {count:,} ({pct:.1f}%)")
        
        self._log(f"\n📏 RATIOS D'ASPECT:")
        for ratio, count in sorted(result.aspect_ratios.items(), key=lambda x: x[1], reverse=True):
            pct = (count / result.total_images) * 100
            self._log(f"   {ratio}: {count:,} ({pct:.1f}%)")
        
        self._log(f"\n📂 PAR DOSSIER/NIVEAU (top 10):")
        sorted_levels = sorted(result.by_level.items(), key=lambda x: x[1].count, reverse=True)[:10]
        for level_name, stats in sorted_levels:
            size_kb = stats.total_size / 1024
            self._log(f"   {level_name}: {stats.count:,} images ({size_kb:.1f} KB)")
        
        if len(result.by_level) > 10:
            self._log(f"   ... et {len(result.by_level) - 10} autres dossiers")
        
        if result.errors:
            self._log(f"\n⚠️ ERREURS ({len(result.errors)}):")
            for error in result.errors[:5]:
                self._log(f"   {error}")
            if len(result.errors) > 5:
                self._log(f"   ... et {len(result.errors) - 5} autres erreurs")
    
    def _save_json_report(self, result: AnalysisResult):
        """Sauvegarder le rapport en JSON"""
        json_data = {
            "analysis_info": {
                "source_dir": self.config.source_dir,
                "timestamp": datetime.now().isoformat(),
                "analysis_time_seconds": result.analysis_time
            },
            "summary": {
                "total_images": result.total_images,
                "total_size_mb": result.total_size_mb,
                "avg_size_kb": result.avg_size_kb,
                "min_size_kb": result.min_size_kb,
                "max_size_kb": result.max_size_kb,
                "width_range": result.width_range,
                "height_range": result.height_range
            },
            "resolutions": result.resolutions,
            "formats": result.formats,
            "color_modes": result.color_modes,
            "aspect_ratios": result.aspect_ratios,
            "by_level": {
                name: {
                    "count": stats.count,
                    "total_size_kb": round(stats.total_size / 1024, 2)
                }
                for name, stats in result.by_level.items()
            },
            "errors": result.errors[:100]  # Limiter les erreurs
        }
        
        try:
            with open(self.config.output_json, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, indent=2, ensure_ascii=False)
            
            self._log(f"\n💾 Rapport JSON sauvegardé: {self.config.output_json}")
        except Exception as e:
            self._log(f"⚠️ Erreur sauvegarde JSON: {e}")
    
    def stop(self):
        """Arrêter l'analyse"""
        self.should_stop = True
        self._log("⏹️ Arrêt demandé...")
    
    def get_quick_stats(self, source_dir: str) -> Dict[str, Any]:
        """Obtenir des statistiques rapides sans analyse complète"""
        stats = {
            "total_files": 0,
            "total_size_mb": 0,
            "subdirs": 0
        }
        
        if not os.path.exists(source_dir):
            return stats
        
        total_size = 0
        subdirs = set()
        
        for root, dirs, files in os.walk(source_dir):
            subdirs.add(root)
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()
                if ext in self.IMAGE_EXTENSIONS:
                    stats["total_files"] += 1
                    filepath = os.path.join(root, filename)
                    try:
                        total_size += os.path.getsize(filepath)
                    except:
                        pass
        
        stats["total_size_mb"] = round(total_size / 1024 / 1024, 2)
        stats["subdirs"] = len(subdirs) - 1  # Exclure le dossier racine
        
        return stats