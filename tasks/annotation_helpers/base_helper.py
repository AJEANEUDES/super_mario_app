"""
Base Helper - Classe de base abstraite pour les helpers d'annotation

Tous les helpers doivent hériter de cette classe et implémenter
les méthodes abstraites.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum


class HelperStatus(Enum):
    """Statut d'exécution d'un helper"""
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass
class HelperResult:
    """Résultat d'exécution d'un helper"""
    success: bool = False
    message: str = ""
    processed: int = 0
    skipped: int = 0
    errors: int = 0
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            
            'message': self.message,
            'processed': self.processed,
            'skipped': self.skipped,
            'errors': self.errors,
            'details': self.details
        }


@dataclass
class HelperInfo:
    """Informations sur un helper"""
    id: str
    name: str
    icon: str
    short_description: str
    long_description: str
    requirements: List[str] = field(default_factory=list)
    estimated_speedup: str = ""
    best_for: List[str] = field(default_factory=list)
    limitations: List[str] = field(default_factory=list)


class BaseAnnotationHelper(ABC):
    """
    Classe de base abstraite pour les helpers d'annotation.
    
    Chaque helper doit implémenter:
    - get_info(): Retourne les informations sur le helper
    - configure(): Configure le helper avec les paramètres utilisateur
    - execute(): Exécute le helper
    - get_config_widget(): Retourne un widget de configuration (optionnel)
    """
    
    def __init__(self):
        self.status = HelperStatus.IDLE
        self.progress = 0.0
        self.cancel_requested = False
        
        # Callbacks
        self.progress_callback: Optional[Callable[[float, str], None]] = None
        self.log_callback: Optional[Callable[[str], None]] = None
    
    @staticmethod
    @abstractmethod
    def get_info() -> HelperInfo:
        """Retourne les informations sur ce helper"""
        pass
    
    @abstractmethod
    def configure(self, task, **kwargs) -> bool:
        """
        Configure le helper avec les paramètres
        
        Args:
            task: Instance de DatasetAnnotatorTask
            **kwargs: Paramètres spécifiques au helper
            
        Returns:
            True si configuration réussie
        """
        pass
    
    @abstractmethod
    def execute(self) -> HelperResult:
        """
        Exécute le helper
        
        Returns:
            HelperResult avec les résultats
        """
        pass
    
    def get_config_widget(self):
        """
        Retourne un widget PyQt pour configurer le helper
        
        Returns:
            QWidget ou None si pas de configuration nécessaire
        """
        return None
    
    def cancel(self):
        """Annuler l'exécution en cours"""
        self.cancel_requested = True
    
    def reset(self):
        """Réinitialiser le helper"""
        self.status = HelperStatus.IDLE
        self.progress = 0.0
        self.cancel_requested = False
    
    def _log(self, message: str):
        """Logger un message"""
        if self.log_callback:
            self.log_callback(message)
    
    def _update_progress(self, progress: float, message: str = ""):
        """Mettre à jour la progression"""
        self.progress = progress
        if self.progress_callback:
            self.progress_callback(progress, message)
    
    def _check_cancelled(self) -> bool:
        """Vérifier si l'annulation a été demandée"""
        return self.cancel_requested