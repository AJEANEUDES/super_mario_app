"""
Crop Comparison Task - Analyseur de comparaison entre dossiers original et croppé
Compare les fichiers et identifie ceux qui ont été modifiés
"""

import os
import json
import time
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Dict, List, Tuple, Optional

from .base_task import BaseTask, TaskStatus, TaskPriority


@dataclass
class FileInfo:
    """Informations sur un fichier"""
    filename: str
    size_bytes: int
    size_mb: float
    exists: bool


@dataclass
class ComparisonResult:
    """Résultat de comparaison entre original et croppé"""
    filename: str
    original_size: int
    cropped_size: int
    status: str  # "cropped", "copied", "missing", "error"
    size_reduction_bytes: int
    size_reduction_percent: float


class CropComparisonTask(BaseTask):
    """
    Tâche d'analyse de comparaison entre dossiers original et croppé
    Identifie quels fichiers ont été croppés, copiés ou sont manquants
    """
    
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
    
    def __init__(self, priority: TaskPriority = TaskPriority.NORMAL):
        super().__init__(
            name="Comparaison Crop",
            description="Analyse des différences entre original et croppé",
            priority=priority
        )
        
        self.original_dir = None
        self.cropped_dir = None
        self.cancel_flag = False
        
        # Résultats
        self.comparisons: List[ComparisonResult] = []
        self.stats: Dict = {}
        self.only_in_cropped: List[str] = []
    
    def configure(self,
                  original_dir: str,
                  cropped_dir: str,
                  size_threshold: int = 1024,
                  export_lists: bool = True):
        """
        Configurer la tâche
        
        Args:
            original_dir: Dossier contenant les images originales
            cropped_dir: Dossier contenant les images croppées
            size_threshold: Seuil en bytes pour différencier crop vs copie (défaut: 1KB)
            export_lists: Exporter les listes de fichiers en .txt
        """
        self.config = {
            'original_dir': original_dir,
            'cropped_dir': cropped_dir,
            'size_threshold': size_threshold,
            'export_lists': export_lists
        }
        
        self.original_dir = Path(original_dir)
        self.cropped_dir = Path(cropped_dir)
    
    def validate_config(self) -> Tuple[bool, str]:
        """Valider la configuration"""
        if 'original_dir' not in self.config:
            return False, "Dossier original non spécifié"
        
        if 'cropped_dir' not in self.config:
            return False, "Dossier croppé non spécifié"
        
        if not self.original_dir.exists():
            return False, f"Dossier original non trouvé: {self.original_dir}"
        
        if not self.cropped_dir.exists():
            return False, f"Dossier croppé non trouvé: {self.cropped_dir}"
        
        # Vérifier qu'il y a des images
        original_images = self._count_images(self.original_dir)
        if original_images == 0:
            return False, "Aucune image trouvée dans le dossier original"
        
        return True, "Configuration valide"
    
    def _count_images(self, directory: Path) -> int:
        """Compter le nombre d'images dans un dossier"""
        count = 0
        for f in directory.iterdir():
            if f.is_file() and f.suffix.lower() in self.IMAGE_EXTENSIONS:
                count += 1
        return count
    
    def _scan_directory(self, directory: Path) -> Dict[str, FileInfo]:
        """Scanner un dossier et retourner les infos des fichiers"""
        files_info = {}
        
        if not directory.exists():
            return files_info
        
        for file_path in directory.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.IMAGE_EXTENSIONS:
                size_bytes = file_path.stat().st_size
                files_info[file_path.name] = FileInfo(
                    filename=file_path.name,
                    size_bytes=size_bytes,
                    size_mb=size_bytes / (1024 * 1024),
                    exists=True
                )
        
        return files_info
    
    def execute(self) -> bool:
        """Exécuter l'analyse de comparaison"""
        try:
            self.update_status(TaskStatus.RUNNING, "Démarrage de l'analyse...")
            
            start_time = time.time()
            size_threshold = self.config.get('size_threshold', 1024)
            
            # Scanner le dossier original
            self.log("Scan du dossier original...", "INFO")
            self.update_progress(10, "Scan dossier original...")
            original_files = self._scan_directory(self.original_dir)
            
            if self.cancel_flag:
                self.update_status(TaskStatus.CANCELLED, "Annulé")
                return False
            
            # Scanner le dossier croppé
            self.log("Scan du dossier croppé...", "INFO")
            self.update_progress(30, "Scan dossier croppé...")
            cropped_files = self._scan_directory(self.cropped_dir)
            
            self.log(f"Fichiers - Original: {len(original_files):,}, Croppé: {len(cropped_files):,}", "INFO")
            
            if self.cancel_flag:
                self.update_status(TaskStatus.CANCELLED, "Annulé")
                return False
            
            # Comparer les fichiers
            self.log("Comparaison des fichiers...", "INFO")
            self.update_progress(50, "Comparaison en cours...")
            
            self.comparisons = []
            total_files = len(original_files)
            
            for idx, (filename, original_info) in enumerate(original_files.items()):
                if self.cancel_flag:
                    self.update_status(TaskStatus.CANCELLED, "Annulé")
                    return False
                
                cropped_info = cropped_files.get(filename)
                
                if cropped_info is None:
                    # Fichier manquant
                    comparison = ComparisonResult(
                        filename=filename,
                        original_size=original_info.size_bytes,
                        cropped_size=0,
                        status="missing",
                        size_reduction_bytes=0,
                        size_reduction_percent=0.0
                    )
                else:
                    # Fichier présent dans les deux
                    size_diff = original_info.size_bytes - cropped_info.size_bytes
                    
                    if size_diff > size_threshold:
                        status = "cropped"
                        reduction_percent = (size_diff / original_info.size_bytes) * 100 if original_info.size_bytes > 0 else 0
                    elif abs(size_diff) <= size_threshold:
                        status = "copied"
                        reduction_percent = 0.0
                    else:
                        status = "error"
                        reduction_percent = (size_diff / original_info.size_bytes) * 100 if original_info.size_bytes > 0 else 0
                    
                    comparison = ComparisonResult(
                        filename=filename,
                        original_size=original_info.size_bytes,
                        cropped_size=cropped_info.size_bytes,
                        status=status,
                        size_reduction_bytes=size_diff,
                        size_reduction_percent=reduction_percent
                    )
                
                self.comparisons.append(comparison)
                
                # Progression
                if idx % 100 == 0:
                    progress = 50 + int((idx / total_files) * 40)
                    self.update_progress(progress, f"Comparaison {idx:,}/{total_files:,}")
            
            # Fichiers uniquement dans le dossier croppé
            self.only_in_cropped = [
                filename for filename in cropped_files
                if filename not in original_files
            ]
            
            if self.only_in_cropped:
                self.log(f"Fichiers uniquement dans croppé: {len(self.only_in_cropped)}", "WARNING")
            
            # Calculer les statistiques
            self.update_progress(95, "Calcul des statistiques...")
            self.stats = self._calculate_statistics()
            
            # Sauvegarder le rapport
            self._save_report()
            
            # Exporter les listes si demandé
            if self.config.get('export_lists', True):
                self._export_file_lists()
            
            # Résumé
            elapsed = time.time() - start_time
            self.log(f"Analyse terminée en {elapsed:.1f}s", "INFO")
            self.log(f"Croppés: {self.stats['totals']['files_cropped']:,}", "INFO")
            self.log(f"Copiés: {self.stats['totals']['files_copied']:,}", "INFO")
            self.log(f"Manquants: {self.stats['totals']['files_missing']:,}", "INFO")
            self.log(f"Espace économisé: {self.stats['space']['reduction_mb']:.1f} MB", "INFO")
            
            self.update_progress(100, "✅ Analyse terminée")
            self.update_status(TaskStatus.COMPLETED, "Analyse terminée")
            
            return True
            
        except Exception as e:
            self.error_message = str(e)
            self.update_status(TaskStatus.FAILED, str(e))
            self.log(f"Erreur: {str(e)}", "ERROR")
            import traceback
            self.log(traceback.format_exc(), "ERROR")
            return False
    
    def _calculate_statistics(self) -> Dict:
        """Calculer les statistiques de comparaison"""
        
        status_counts = {"cropped": 0, "copied": 0, "missing": 0, "error": 0}
        total_original_size = 0
        total_cropped_size = 0
        total_reduction = 0
        
        cropped_files = []
        copied_files = []
        missing_files = []
        error_files = []
        
        for comp in self.comparisons:
            status_counts[comp.status] += 1
            total_original_size += comp.original_size
            
            if comp.status == "cropped":
                cropped_files.append(comp.filename)
                total_cropped_size += comp.cropped_size
                total_reduction += comp.size_reduction_bytes
            elif comp.status == "copied":
                copied_files.append(comp.filename)
                total_cropped_size += comp.cropped_size
            elif comp.status == "missing":
                missing_files.append(comp.filename)
            elif comp.status == "error":
                error_files.append(comp.filename)
                total_cropped_size += comp.cropped_size
        
        total_files = len(self.comparisons)
        
        # Pourcentages
        if total_files > 0:
            cropped_pct = (status_counts["cropped"] / total_files) * 100
            copied_pct = (status_counts["copied"] / total_files) * 100
            missing_pct = (status_counts["missing"] / total_files) * 100
            error_pct = (status_counts["error"] / total_files) * 100
        else:
            cropped_pct = copied_pct = missing_pct = error_pct = 0
        
        # Réduction d'espace
        if total_original_size > 0:
            space_reduction_pct = (total_reduction / total_original_size) * 100
        else:
            space_reduction_pct = 0
        
        return {
            "totals": {
                "total_files": total_files,
                "files_cropped": status_counts["cropped"],
                "files_copied": status_counts["copied"],
                "files_missing": status_counts["missing"],
                "files_error": status_counts["error"],
                "files_only_in_cropped": len(self.only_in_cropped)
            },
            "percentages": {
                "cropped": cropped_pct,
                "copied": copied_pct,
                "missing": missing_pct,
                "error": error_pct
            },
            "space": {
                "original_mb": total_original_size / (1024 * 1024),
                "cropped_mb": total_cropped_size / (1024 * 1024),
                "reduction_mb": total_reduction / (1024 * 1024),
                "reduction_pct": space_reduction_pct
            },
            "file_lists": {
                "cropped": cropped_files,
                "copied": copied_files,
                "missing": missing_files,
                "error": error_files,
                "only_in_cropped": self.only_in_cropped
            }
        }
    
    def _save_report(self):
        """Sauvegarder le rapport JSON"""
        report_path = self.cropped_dir / "crop_comparison_report.json"
        
        report = {
            "analysis_info": {
                "original_directory": str(self.original_dir),
                "cropped_directory": str(self.cropped_dir),
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "size_threshold": self.config.get('size_threshold', 1024)
            },
            "statistics": self.stats,
            "comparisons_summary": {
                "total": len(self.comparisons),
                "sample": [asdict(c) for c in self.comparisons[:100]]  # Échantillon
            }
        }
        
        try:
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self.log(f"Rapport sauvé: {report_path}", "INFO")
        except Exception as e:
            self.log(f"Erreur sauvegarde rapport: {e}", "WARNING")
    
    def _export_file_lists(self):
        """Exporter les listes de fichiers en .txt"""
        file_lists = self.stats.get("file_lists", {})
        
        for list_name, file_list in file_lists.items():
            if not file_list:
                continue
            
            output_path = self.cropped_dir / f"{list_name}_files.txt"
            
            try:
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(f"# {list_name.replace('_', ' ').title()} Files\n")
                    f.write(f"# Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Total: {len(file_list):,} files\n\n")
                    
                    for filename in sorted(file_list):
                        f.write(f"{filename}\n")
                
                self.log(f"Liste '{list_name}' exportée: {len(file_list):,} fichiers", "INFO")
            except Exception as e:
                self.log(f"Erreur export liste {list_name}: {e}", "WARNING")
    
    def cancel(self):
        """Annuler la tâche"""
        self.cancel_flag = True
        self.log("Annulation demandée...", "WARNING")
    
    def get_summary(self) -> str:
        """Résumé des résultats"""
        if not self.stats:
            return "Aucune statistique disponible"
        
        s = self.stats
        return f"""📊 Résumé Comparaison:
• Total analysés: {s['totals']['total_files']:,}
• Croppés: {s['totals']['files_cropped']:,} ({s['percentages']['cropped']:.1f}%)
• Copiés: {s['totals']['files_copied']:,} ({s['percentages']['copied']:.1f}%)
• Manquants: {s['totals']['files_missing']:,}
• Espace économisé: {s['space']['reduction_mb']:.1f} MB ({s['space']['reduction_pct']:.1f}%)"""