"""
YOLO Training Task - Entraînement de modèles YOLO pour Mario
Version améliorée avec arrêt réel, pause/reprise et logs temps réel
"""

import os
import sys
import gc
import json
import signal
import subprocess
import threading
import queue
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List
from pathlib import Path
from datetime import datetime
import torch
import time



try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False


@dataclass
class TrainingConfig:
    """Configuration d'entraînement YOLO"""
    data_path: str = ""
    model_name: str = "yolov8n.pt"
    epochs: int = 100
    batch_size: Optional[int] = None  # Auto si None
    device: Optional[str] = None  # Auto si None
    workers: int = 0
    patience: int = 50
    save_period: int = 10
    
    # Optimisations mémoire
    cache: bool = False
    amp: bool = True  # Mixed Precision
    
    # Augmentations
    mosaic: float = 0.5
    mixup: float = 0.0
    copy_paste: float = 0.0
    
    # Dossier de sortie
    project: str = "runs/train"
    name: str = "mario_yolo"
    
    # Reprise
    resume_from: Optional[str] = None  # Chemin vers last.pt pour reprendre


@dataclass
class TrainingResult:
    """Résultat d'entraînement"""
    success: bool = False
    save_dir: str = ""
    best_model: str = ""
    last_model: str = ""
    epochs_completed: int = 0
    metrics: Dict[str, float] = field(default_factory=dict)
    error_message: str = ""
    was_stopped: bool = False
    was_paused: bool = False


class YOLOTrainingTask:
    """
    Tâche d'entraînement YOLO avec contrôle complet
    - Arrêt réel via subprocess
    - Pause/Reprise via checkpoints
    - Logs temps réel
    """
    
    # Modèles disponibles
    AVAILABLE_MODELS = [
        ("yolov8n.pt", "YOLOv8 Nano (3.2M params) - Rapide"),
        ("yolov8s.pt", "YOLOv8 Small (11.2M params) - Équilibré"),
        ("yolov8m.pt", "YOLOv8 Medium (25.9M params) - Précis"),
        ("yolov8l.pt", "YOLOv8 Large (43.7M params) - Très précis"),
        ("yolov8x.pt", "YOLOv8 XLarge (68.2M params) - Maximum"),
    ]
    
    # Presets d'entraînement
    TRAINING_PRESETS = {
        "quick_test": {
            "name": "Test Rapide",
            "epochs": 5,
            "batch_size": 2,
            "description": "5 epochs pour vérifier la configuration"
        },
        "short": {
            "name": "Court",
            "epochs": 25,
            "batch_size": None,
            "description": "25 epochs pour résultats rapides"
        },
        "standard": {
            "name": "Standard",
            "epochs": 100,
            "batch_size": None,
            "description": "100 epochs pour bons résultats"
        },
        "extended": {
            "name": "Étendu",
            "epochs": 200,
            "batch_size": None,
            "description": "200 epochs pour meilleurs résultats"
        },
        "cpu_safe": {
            "name": "CPU Sécurisé",
            "epochs": 50,
            "batch_size": 4,
            "device": "cpu",
            "description": "Mode CPU si problèmes GPU"
        }
    }
    
    def __init__(self):
        self.config: Optional[TrainingConfig] = None
        self.result: Optional[TrainingResult] = None
        self.process: Optional[subprocess.Popen] = None
        self.is_training = False
        self.is_paused = False
        self.should_stop = False
        self.current_epoch = 0
        self.total_epochs = 0
        
        # Callbacks
        self.log_callback: Optional[Callable[[str], None]] = None
        self.status_callback: Optional[Callable[[str], None]] = None
        self.progress_callback: Optional[Callable[[int, int, dict], None]] = None
        self.finished_callback: Optional[Callable[[TrainingResult], None]] = None
        
        # Queue pour les logs
        self.log_queue = queue.Queue()
        
        # Dernier dossier de résultats
        self.last_save_dir: Optional[str] = None
    
    @staticmethod
    def check_dependencies() -> Dict[str, bool]:
        """Vérifier les dépendances"""
        return {
            "torch": TORCH_AVAILABLE,
            "ultralytics": YOLO_AVAILABLE,
            "cuda": TORCH_AVAILABLE and torch.cuda.is_available()
        }
    
    @staticmethod
    def get_gpu_info() -> Dict[str, Any]:
        """Obtenir les informations GPU"""
        if not TORCH_AVAILABLE:
            return {"available": False, "name": "N/A", "memory_gb": 0}
        
        if torch.cuda.is_available():
            props = torch.cuda.get_device_properties(0)
            return {
                "available": True,
                "name": torch.cuda.get_device_name(0),
                "memory_gb": props.total_memory / 1e9,
                "compute_capability": f"{props.major}.{props.minor}"
            }
        return {"available": False, "name": "CPU uniquement", "memory_gb": 0}
    
    @staticmethod
    def find_existing_results(base_dir: str = "runs/train") -> List[Dict[str, Any]]:
        """Trouver les résultats d'entraînement existants"""
        results = []
        
        if not os.path.exists(base_dir):
            return results
        
        for folder in sorted(os.listdir(base_dir), reverse=True):
            folder_path = os.path.join(base_dir, folder)
            if os.path.isdir(folder_path):
                weights_dir = os.path.join(folder_path, "weights")
                best_pt = os.path.join(weights_dir, "best.pt")
                last_pt = os.path.join(weights_dir, "last.pt")
                
                info = {
                    "name": folder,
                    "path": folder_path,
                    "has_best": os.path.exists(best_pt),
                    "has_last": os.path.exists(last_pt),
                    "best_path": best_pt if os.path.exists(best_pt) else None,
                    "last_path": last_pt if os.path.exists(last_pt) else None,
                    "date": datetime.fromtimestamp(os.path.getmtime(folder_path)).strftime("%Y-%m-%d %H:%M")
                }
                
                # Lire les args si disponibles
                args_file = os.path.join(folder_path, "args.yaml")
                if os.path.exists(args_file):
                    try:
                        import yaml
                        with open(args_file, 'r') as f:
                            args = yaml.safe_load(f)
                            info["epochs"] = args.get("epochs", "?")
                            info["model"] = args.get("model", "?")
                    except:
                        pass
                
                results.append(info)
        
        return results
    
    def _auto_batch_size(self) -> int:
        """Calculer le batch size optimal"""
        if not TORCH_AVAILABLE or not torch.cuda.is_available():
            return 2  # CPU mode
        
        memory_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
        
        if memory_gb < 4:
            return 2
        elif memory_gb < 6:
            return 4
        elif memory_gb < 8:
            return 8
        elif memory_gb < 12:
            return 16
        else:
            return 32
    
    def _log(self, message: str):
        """Logger un message"""
        if self.log_callback:
            self.log_callback(message)
    
    def _update_status(self, status: str):
        """Mettre à jour le statut"""
        if self.status_callback:
            self.status_callback(status)
    
    def _update_progress(self, current: int, total: int, metrics: dict = None):
        """Mettre à jour la progression"""
        self.current_epoch = current
        self.total_epochs = total
        if self.progress_callback:
            self.progress_callback(current, total, metrics or {})
    
    def configure(self, config: TrainingConfig,
                  log_callback: Optional[Callable] = None,
                  status_callback: Optional[Callable] = None,
                  progress_callback: Optional[Callable] = None,
                  finished_callback: Optional[Callable] = None):
        """Configurer la tâche"""
        self.config = config
        self.log_callback = log_callback
        self.status_callback = status_callback
        self.progress_callback = progress_callback
        self.finished_callback = finished_callback
    
    def validate_config(self) -> tuple:
        """Valider la configuration"""
        if not self.config:
            return False, "Configuration manquante"
        
        if not self.config.data_path:
            return False, "Chemin data.yaml non spécifié"
        
        if not os.path.exists(self.config.data_path):
            return False, f"Fichier non trouvé: {self.config.data_path}"
        
        if not YOLO_AVAILABLE:
            return False, "ultralytics non installé. Installez avec: pip install ultralytics"
        
        if not TORCH_AVAILABLE:
            return False, "PyTorch non installé"
        
        return True, "Configuration valide"
    
    def _create_training_script(self) -> str:
        """Créer un script Python temporaire pour l'entraînement"""
        
        batch_val = self.config.batch_size if self.config.batch_size else "None"
        device_val = f'"{self.config.device}"' if self.config.device else '"auto"'
        resume_val = f'r"{self.config.resume_from}"' if self.config.resume_from else 'None'
        
        script_content = f'''# -*- coding: utf-8 -*-
import sys
import os

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

# Configuration environnement
os.environ["CUDA_LAUNCH_BLOCKING"] = "1"
os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "max_split_size_mb:128"

from ultralytics import YOLO
import torch

# Paramètres
data_path = r"{self.config.data_path}"
model_name = "{self.config.model_name}"
epochs = {self.config.epochs}
batch_size = {batch_val}
device = {device_val}
workers = {self.config.workers}
patience = {self.config.patience}
save_period = {self.config.save_period}
cache = {self.config.cache}
amp = {self.config.amp}
mosaic = {self.config.mosaic}
mixup = {self.config.mixup}
copy_paste = {self.config.copy_paste}
project = r"{self.config.project}"
name = "{self.config.name}"
resume_path = {resume_val}

print("=" * 60)
print("YOLO TRAINING - MARIO DATASET")
print("=" * 60)

# Auto batch size
if batch_size is None:
    if torch.cuda.is_available():
        mem = torch.cuda.get_device_properties(0).total_memory / 1e9
        if mem < 4: batch_size = 2
        elif mem < 6: batch_size = 4
        elif mem < 8: batch_size = 8
        else: batch_size = 16
        print(f"[AUTO] Batch size: {{batch_size}} (VRAM: {{mem:.1f}} GB)")
    else:
        batch_size = 2
        print(f"[AUTO] Batch size: {{batch_size}} (CPU mode)")

# Device
if device == "auto":
    device = "cuda" if torch.cuda.is_available() else "cpu"

print(f"[CONFIG] Dataset: {{data_path}}")
print(f"[CONFIG] Model: {{model_name}}")
print(f"[CONFIG] Epochs: {{epochs}}")
print(f"[CONFIG] Batch: {{batch_size}}")
print(f"[CONFIG] Device: {{device}}")
print(f"[CONFIG] Workers: {{workers}}")
print(f"[CONFIG] Patience: {{patience}}")
print(f"[CONFIG] Save Period: {{save_period}}")
print(f"[CONFIG] AMP: {{amp}}")
print(f"[CONFIG] Cache: {{cache}}")
print(f"[CONFIG] Project: {{project}}/{{name}}")

if torch.cuda.is_available():
    print(f"[GPU] {{torch.cuda.get_device_name(0)}}")
    print(f"[GPU] VRAM: {{torch.cuda.get_device_properties(0).total_memory / 1e9:.1f}} GB")

if resume_path:
    print(f"[RESUME] Checkpoint: {{resume_path}}")

print("=" * 60)
print("[START] Loading model...")
sys.stdout.flush()

# Charger le modèle
if resume_path and os.path.exists(resume_path):
    print(f"[RESUME] Loading from checkpoint...")
    model = YOLO(resume_path)
    do_resume = True
else:
    model = YOLO(model_name)
    do_resume = False

print("[START] Training started...")
print("=" * 60)
sys.stdout.flush()

try:
    # Entraînement
    results = model.train(
        data=data_path,
        epochs=epochs,
        batch=batch_size,
        device=device,
        workers=workers,
        cache=cache,
        amp=amp,
        verbose=True,
        patience=patience,
        save=True,
        save_period=save_period,
        mosaic=mosaic,
        mixup=mixup,
        copy_paste=copy_paste,
        project=project,
        name=name,
        exist_ok=do_resume,
        resume=do_resume,
    )

    print("=" * 60)
    print("[SUCCESS] Training completed!")
    print(f"[RESULT] Save dir: {{results.save_dir}}")
    print(f"[RESULT] Best model: {{results.save_dir}}/weights/best.pt")
    print("=" * 60)
    
except KeyboardInterrupt:
    print("\\n[STOPPED] Training interrupted by user")
    sys.exit(1)
except Exception as e:
    print(f"\\n[ERROR] {{e}}")
    sys.exit(2)
'''
        
        # Sauvegarder le script
        script_path = os.path.join(os.path.dirname(__file__), "_yolo_train_script.py")
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(script_content)
        
        return script_path
    
    def _read_output(self, pipe, is_stderr=False):
        """Lire la sortie du processus en temps réel"""
        try:
            for line in iter(pipe.readline, ''):
                if not line:
                    break
                
                line = line.rstrip('\n\r')
                if line:
                    # Parser les informations d'epoch
                    if '/' in line and ('Epoch' in line or any(c.isdigit() for c in line[:10])):
                        self._parse_epoch_info(line)
                    
                    # Appeler le callback si disponible
                    if self.log_callback:
                        self.log_callback(line)
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"[LOG ERROR] {e}")
        finally:
            try:
                pipe.close()
            except:
                pass
    
    def _parse_epoch_info(self, line: str):
        """Parser les informations d'epoch depuis la ligne de log"""
        try:
            # Format typique: "     10/100    0.684G     0.1665"
            parts = line.split()
            for part in parts:
                if '/' in part:
                    try:
                        current, total = part.split('/')
                        current = int(current)
                        total = int(total)
                        if 0 < total <= 1000 and 0 < current <= total:
                            self._update_progress(current, total)
                            break
                    except:
                        continue
        except:
            pass
    
    def execute(self) -> TrainingResult:
        """Exécuter l'entraînement via subprocess"""
        self.result = TrainingResult()
        self.is_training = True
        self.is_paused = False
        self.should_stop = False
        
        try:
            # Validation
            valid, message = self.validate_config()
            if not valid:
                self.result.error_message = message
                self._log(f"❌ {message}")
                return self.result
            
            # Auto-configuration
            if self.config.batch_size is None:
                self.config.batch_size = self._auto_batch_size()
            
            if self.config.device is None:
                self.config.device = "cuda" if (TORCH_AVAILABLE and torch.cuda.is_available()) else "cpu"
            
            # Créer le script d'entraînement
            script_path = self._create_training_script()
            
            self._update_status("Démarrage de l'entraînement...")
            self._log("🚀 Lancement du processus d'entraînement...\n")
            
            # Lancer le subprocess
            startupinfo = None
            creation_flags = 0
            
            if sys.platform == 'win32':
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
            self.process = subprocess.Popen(
                [sys.executable, "-u", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                encoding='utf-8',
                errors='replace',  # Remplacer les caractères non décodables
                creationflags=creation_flags,
                startupinfo=startupinfo
            )
            
            # Thread pour lire la sortie
            output_thread = threading.Thread(
                target=self._read_output,
                args=(self.process.stdout,),
                daemon=True
            )
            output_thread.start()
            
            # Attendre la fin du processus
            return_code = self.process.wait()
            output_thread.join(timeout=5)
            
            # Nettoyer le script
            try:
                os.remove(script_path)
            except:
                pass
            
            # Analyser le résultat
            if self.should_stop:
                self.result.was_stopped = True
                self.result.error_message = "Arrêté par l'utilisateur"
                self._log("\n⏹️ Entraînement arrêté par l'utilisateur")
                self._update_status("Arrêté")
                # Chercher quand même les résultats partiels
                self._find_results()
            elif return_code == 0:
                self.result.success = True
                self._find_results()
                self._log(f"\n🎉 Entraînement terminé avec succès!")
                self._update_status("Terminé avec succès!")
            else:
                self.result.error_message = f"Code de retour: {return_code}"
                self._log(f"\n❌ Erreur lors de l'entraînement (code: {return_code})")
                self._update_status("Erreur!")
                # Chercher quand même les résultats partiels
                self._find_results()
            
        except Exception as e:
            self._log(f"\n❌ Erreur: {e}")
            self.result.error_message = str(e)
            self._update_status("Erreur!")
        
        finally:
            self.is_training = False
            self.process = None
            
            # Callback de fin
            if self.finished_callback:
                self.finished_callback(self.result)
        
        return self.result
    
    def _find_results(self):
        """Trouver les fichiers résultats après l'entraînement"""
        # Chercher le dossier de résultats
        project_dir = self.config.project
        name = self.config.name
        
        # Trouver le dossier le plus récent
        if os.path.exists(project_dir):
            folders = [f for f in os.listdir(project_dir) if f.startswith(name)]
            if folders:
                # Trier par date de modification
                folders.sort(key=lambda x: os.path.getmtime(os.path.join(project_dir, x)), reverse=True)
                latest = folders[0]
                
                save_dir = os.path.join(project_dir, latest)
                self.result.save_dir = save_dir
                self.last_save_dir = save_dir
                
                weights_dir = os.path.join(save_dir, "weights")
                best_pt = os.path.join(weights_dir, "best.pt")
                last_pt = os.path.join(weights_dir, "last.pt")
                
                if os.path.exists(best_pt):
                    self.result.best_model = best_pt
                if os.path.exists(last_pt):
                    self.result.last_model = last_pt
                
                self._log(f"\n📂 Résultats: {save_dir}")
                if self.result.best_model:
                    self._log(f"🏆 Meilleur modèle: {self.result.best_model}")
                if self.result.last_model:
                    self._log(f"💾 Dernier checkpoint: {self.result.last_model}")
    
    def stop(self):
        """Arrêter l'entraînement immédiatement"""
        if not self.process:
            return
        
        self.should_stop = True
        self._log("\n⏹️ Arrêt en cours...")
        self._update_status("Arrêt en cours...")
        
        try:
            if sys.platform == 'win32':
                # Windows: terminer le processus
                self.process.terminate()
                try:
                    self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=2)
            else:
                # Unix: envoyer SIGTERM puis SIGKILL
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
            
            self._log("✅ Processus arrêté")
        except Exception as e:
            self._log(f"⚠️ Erreur lors de l'arrêt: {e}")
            try:
                self.process.kill()
            except:
                pass
    
    def pause(self) -> Optional[str]:
        """
        Mettre en pause l'entraînement
        Retourne le chemin du checkpoint pour reprendre
        """
        if not self.is_training:
            return None
        
        self.is_paused = True
        self._log("\n⏸️ Mise en pause...")
        self._update_status("Mise en pause...")
        
        # Arrêter le processus
        self.stop()
        
        # Trouver le dernier checkpoint
        self._find_results()
        
        if self.result and self.result.last_model and os.path.exists(self.result.last_model):
            self._log(f"💾 Checkpoint sauvegardé: {self.result.last_model}")
            self._log("ℹ️ Utilisez 'Reprendre' pour continuer depuis ce point")
            self.result.was_paused = True
            return self.result.last_model
        
        return None
    
    def get_resumable_checkpoint(self) -> Optional[str]:
        """Obtenir le checkpoint disponible pour reprise"""
        if self.config:
            project_dir = self.config.project
            name = self.config.name
            
            if os.path.exists(project_dir):
                folders = [f for f in os.listdir(project_dir) if f.startswith(name)]
                if folders:
                    folders.sort(key=lambda x: os.path.getmtime(os.path.join(project_dir, x)), reverse=True)
                    latest = folders[0]
                    last_pt = os.path.join(project_dir, latest, "weights", "last.pt")
                    if os.path.exists(last_pt):
                        return last_pt
        return None
    
    def resume(self, checkpoint_path: str) -> TrainingResult:
        """Reprendre l'entraînement depuis un checkpoint"""
        if not os.path.exists(checkpoint_path):
            self.result = TrainingResult()
            self.result.error_message = f"Checkpoint non trouvé: {checkpoint_path}"
            return self.result
        
        self._log(f"\n▶️ Reprise depuis: {checkpoint_path}")
        self.config.resume_from = checkpoint_path
        self.is_paused = False
        
        return self.execute()