"""
Base Task - Classe abstraite pour toutes les tâches du pipeline
"""

from abc import ABC, abstractmethod
from enum import Enum
from datetime import datetime
import uuid

class TaskStatus(Enum):
    """États possibles d'une tâche"""
    PENDING = "En attente"
    RUNNING = "En cours"
    COMPLETED = "Terminée"
    FAILED = "Échouée"
    CANCELLED = "Annulée"

class TaskPriority(Enum):
    """Priorités des tâches"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

class BaseTask(ABC):
    """
    Classe abstraite pour toutes les tâches du pipeline
    Chaque tâche doit implémenter execute() et cancel()
    """
    
    def __init__(self, name: str, description: str = "", priority: TaskPriority = TaskPriority.NORMAL):
        self.task_id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.priority = priority
        self.status = TaskStatus.PENDING
        
        # Timestamps
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        
        # Progression
        self.progress = 0  # 0-100
        self.progress_message = ""
        
        # Résultats et erreurs
        self.result = None
        self.error_message = None
        
        # Callbacks
        self.on_progress_callback = None
        self.on_status_change_callback = None
        self.on_log_callback = None
        
        # Configuration
        self.config = {}
        
        # Dépendances (pour chaînage)
        self.dependencies = []  # Liste de task_ids requis
        self.outputs = {}  # Données de sortie pour les tâches suivantes
        
    def set_progress_callback(self, callback):
        """Définir callback pour les mises à jour de progression"""
        self.on_progress_callback = callback
    
    def set_status_change_callback(self, callback):
        """Définir callback pour les changements de statut"""
        self.on_status_change_callback = callback
        
    def set_log_callback(self, callback):
        """Définir callback pour les logs"""
        self.on_log_callback = callback
    
    def update_progress(self, progress: int, message: str = ""):
        """Mettre à jour la progression (0-100)"""
        self.progress = max(0, min(100, progress))
        self.progress_message = message
        
        if self.on_progress_callback:
            self.on_progress_callback(self, progress, message)
    
    def update_status(self, status: TaskStatus, message: str = ""):
        """Mettre à jour le statut de la tâche"""
        old_status = self.status
        self.status = status
        
        if status == TaskStatus.RUNNING and not self.started_at:
            self.started_at = datetime.now()
        elif status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            self.completed_at = datetime.now()
        
        if self.on_status_change_callback:
            self.on_status_change_callback(self, old_status, status, message)
    
    def log(self, message: str, level: str = "INFO"):
        """Logger un message"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = {
            'timestamp': timestamp,
            'task_id': self.task_id,
            'task_name': self.name,
            'level': level,
            'message': message
        }
        
        if self.on_log_callback:
            self.on_log_callback(log_entry)
    
    def get_duration(self):
        """Obtenir la durée d'exécution"""
        if not self.started_at:
            return None
        
        end_time = self.completed_at if self.completed_at else datetime.now()
        duration = end_time - self.started_at
        return duration.total_seconds()
    
    def get_info(self):
        """Obtenir les informations de la tâche"""
        return {
            'task_id': self.task_id,
            'name': self.name,
            'description': self.description,
            'status': self.status.value,
            'progress': self.progress,
            'progress_message': self.progress_message,
            'priority': self.priority.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration': self.get_duration(),
            'error_message': self.error_message,
            'config': self.config
        }
    
    @abstractmethod
    def execute(self):
        """
        Exécuter la tâche - À implémenter par les sous-classes
        Doit retourner True si succès, False sinon
        """
        pass
    
    @abstractmethod
    def cancel(self):
        """
        Annuler la tâche - À implémenter par les sous-classes
        """
        pass
    
    @abstractmethod
    def validate_config(self):
        """
        Valider la configuration de la tâche
        Doit retourner (bool, str) - (valide, message d'erreur)
        """
        pass
    
    def __str__(self):
        return f"Task[{self.name}] - Status: {self.status.value} - Progress: {self.progress}%"
    
    def __repr__(self):
        return f"<BaseTask id={self.task_id[:8]} name={self.name} status={self.status.value}>"
    
    def __lt__(self, other):
        """
        Comparaison pour PriorityQueue - permet de départager les tâches de même priorité
        Compare par date de création (FIFO: première créée = première exécutée)
        """
        if not isinstance(other, BaseTask):
            return NotImplemented
        return self.created_at < other.created_at
    
    def __eq__(self, other):
        """Égalité basée sur l'ID unique de la tâche"""
        if not isinstance(other, BaseTask):
            return NotImplemented
        return self.task_id == other.task_id