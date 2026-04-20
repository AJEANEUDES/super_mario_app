"""
Batch Predict Task - Logique métier pour la prédiction YOLO par lot

Exécute yolo predict sur un dossier source (un niveau augmenté ou brut),
en temps réel avec callback de progression et de log.

Version 1.0.0
Fichier: tasks/batch_predict_task.py
"""

import os
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from tasks.base_task import BaseTask, TaskStatus


# ──────────────────────────────────────────────────────────────────────────────
#  Structures de données
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PredictConfig:
    """Paramètres de la prédiction YOLO."""
    model_path: str          # Chemin vers best.pt
    source_dir: str          # Dossier source (images à prédire)
    output_dir: str          # Dossier racine des résultats (project)
    run_name: str            # Nom du sous-dossier (name)
    confidence: float = 0.25
    iou: float = 0.45
    save_txt: bool = True    # Sauvegarder les labels .txt
    save_conf: bool = True   # Inclure la confidence dans les .txt
    save_crop: bool = False  # Sauvegarder les crops des détections
    device: str = ""         # "" = auto (CPU ou GPU), "cpu", "0", etc.
    image_size: int = 640


@dataclass
class PredictResult:
    """Résultat de la prédiction."""
    success: bool
    message: str
    images_processed: int = 0
    detections_found: int = 0
    output_path: str = ""
    errors: List[str] = field(default_factory=list)


# ──────────────────────────────────────────────────────────────────────────────
#  Tâche
# ──────────────────────────────────────────────────────────────────────────────

class BatchPredictTask(BaseTask):
    """Tâche de prédiction YOLO par lot sur un dossier de niveaux."""

    def __init__(self):
        super().__init__(name="BatchPredictTask", priority=None)
        self.config: Optional[PredictConfig] = None
        self._cancelled = False
        self._process: Optional[subprocess.Popen] = None

        # Callbacks
        self.log_callback:      Optional[Callable[[str], None]] = None
        self.progress_callback: Optional[Callable[[int, int], None]] = None

    # ── Configuration ──────────────────────────────────────────────────────

    def configure(self, config: PredictConfig) -> None:
        self.config = config

    # ── Cycle de vie ───────────────────────────────────────────────────────

    def cancel(self) -> None:
        self._cancelled = True
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
            except Exception:
                pass

    def run(self) -> PredictResult:
        """Exécute la prédiction et retourne un PredictResult."""
        if not self.config:
            return PredictResult(success=False, message="Configuration manquante.")

        self.status = TaskStatus.RUNNING
        self._cancelled = False

        try:
            result = self._run_prediction()
            self.status = TaskStatus.COMPLETED if result.success else TaskStatus.FAILED
            return result
        except Exception as exc:
            self.status = TaskStatus.FAILED
            return PredictResult(success=False, message=f"Exception: {exc}")

    # ── Logique interne ────────────────────────────────────────────────────

    def _log(self, message: str) -> None:
        if self.log_callback:
            self.log_callback(message)
        print(message)

    def _update_progress(self, current: int, total: int) -> None:
        if self.progress_callback:
            self.progress_callback(current, total)

    def _count_images(self, folder: str) -> int:
        """Compte les images dans un dossier (récursif)."""
        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
        count = 0
        for root, _, files in os.walk(folder):
            count += sum(1 for f in files if Path(f).suffix.lower() in exts)
        return count

    def _parse_yolo_output(self, line: str) -> Optional[int]:
        """Tente d'extraire le numéro d'image courant depuis la sortie YOLO."""
        # Exemple: "image 3/100 path/to/img.jpg: 640x640 ..."
        import re
        m = re.search(r'image\s+(\d+)/(\d+)', line)
        if m:
            return int(m.group(1)), int(m.group(2))
        return None

    def _build_command(self) -> List[str]:
        cfg = self.config
        cmd = [
            "yolo", "predict",
            f"model={cfg.model_path}",
            f"source={cfg.source_dir}",
            f"conf={cfg.confidence}",
            f"iou={cfg.iou}",
            f"imgsz={cfg.image_size}",
            f"project={cfg.output_dir}",
            f"name={cfg.run_name}",
            f"save_txt={str(cfg.save_txt).lower()}",
            f"save_conf={str(cfg.save_conf).lower()}",
            f"save_crop={str(cfg.save_crop).lower()}",
            "exist_ok=True",
        ]
        if cfg.device:
            cmd.append(f"device={cfg.device}")
        return cmd

    def _run_prediction(self) -> PredictResult:
        cfg = self.config

        # ── Validation ──────────────────────────────────────────────────
        if not os.path.isfile(cfg.model_path):
            return PredictResult(False, f"Modèle introuvable: {cfg.model_path}")
        if not os.path.isdir(cfg.source_dir):
            return PredictResult(False, f"Dossier source introuvable: {cfg.source_dir}")

        # ── Compter les images source ────────────────────────────────────
        total_images = self._count_images(cfg.source_dir)
        if total_images == 0:
            return PredictResult(False, "Aucune image trouvée dans le dossier source.")

        self._log(f"🖼️  Images à traiter : {total_images}")
        self._log(f"🤖 Modèle           : {cfg.model_path}")
        self._log(f"📁 Source           : {cfg.source_dir}")
        self._log(f"📤 Sortie           : {cfg.output_dir}/{cfg.run_name}")
        self._log(f"🎯 Confidence       : {cfg.confidence}")
        self._log("")

        cmd = self._build_command()
        self._log(f"▶️  Commande : {' '.join(cmd)}")
        self._log("")

        # ── Lancer le processus ──────────────────────────────────────────
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except FileNotFoundError:
            return PredictResult(
                False,
                "Commande 'yolo' introuvable.\n"
                "Vérifiez que ultralytics est installé: pip install ultralytics"
            )

        current = 0
        detections = 0
        errors: List[str] = []

        # ── Lire la sortie en temps réel ─────────────────────────────────
        for line in self._process.stdout:
            if self._cancelled:
                break
            line = line.rstrip()
            if not line:
                continue

            self._log(line)

            # Progression
            parsed = self._parse_yolo_output(line)
            if parsed:
                current, total_images = parsed
                self._update_progress(current, total_images)

            # Compter les détections (lignes contenant des classes)
            if any(kw in line.lower() for kw in ['Speed:', 'Results saved']):
                pass
            if 'no detections' not in line.lower() and (
                any(c.isdigit() for c in line) and 'image' in line.lower()
            ):
                pass

        self._process.wait()
        returncode = self._process.returncode

        if self._cancelled:
            return PredictResult(False, "Prédiction annulée.", current, detections)

        # ── Chemin de sortie final ───────────────────────────────────────
        output_path = os.path.join(cfg.output_dir, cfg.run_name)
        if not os.path.isdir(output_path):
            # YOLO peut créer un suffixe numérique (ex: run_name2)
            parent = Path(cfg.output_dir)
            candidates = sorted(parent.glob(f"{cfg.run_name}*"), reverse=True)
            if candidates:
                output_path = str(candidates[0])

        # ── Compter les résultats ────────────────────────────────────────
        labels_dir = os.path.join(output_path, "labels")
        if os.path.isdir(labels_dir):
            txt_files = list(Path(labels_dir).glob("*.txt"))
            detections = sum(
                1 for f in txt_files if f.stat().st_size > 0
            )

        if returncode == 0:
            self._log("")
            self._log(f"✅ Prédiction terminée avec succès!")
            self._log(f"📊 Images avec détections : {detections} / {total_images}")
            self._log(f"📂 Résultats dans : {output_path}")
            return PredictResult(
                success=True,
                message="Prédiction terminée avec succès!",
                images_processed=total_images,
                detections_found=detections,
                output_path=output_path,
                errors=errors,
            )
        else:
            self._log(f"❌ Erreur YOLO (code {returncode})")
            return PredictResult(
                False,
                f"YOLO a retourné le code d'erreur {returncode}.",
                current,
                detections,
                errors=errors,
            )

    # ── Méthodes statiques utilitaires ────────────────────────────────────

    @staticmethod
    def find_model_candidates(search_roots: List[str]) -> List[str]:
        """Cherche des fichiers best.pt dans les dossiers donnés."""
        candidates = []
        for root in search_roots:
            if not os.path.isdir(root):
                continue
            for path in Path(root).rglob("best.pt"):
                candidates.append(str(path))
        return candidates

    @staticmethod
    def count_images_in_dir(folder: str) -> int:
        exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tif', '.tiff'}
        return sum(
            1 for root, _, files in os.walk(folder)
            for f in files if Path(f).suffix.lower() in exts
        )