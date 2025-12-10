"""
Pipeline Manager - Gestion de la queue de tâches
"""

import threading
import queue
from datetime import datetime
from typing import List, Callable, Optional
from tasks.base_task import BaseTask, TaskStatus, TaskPriority

class PipelineManager:
    """
    Gestionnaire de pipeline pour l'exécution séquentielle de tâches
    Gère une queue de tâches avec callbacks de progression
    """
    
    def __init__(self):
        # Queue de tâches
        self.task_queue: queue.PriorityQueue = queue.PriorityQueue()
        self.tasks: List[BaseTask] = []  # Historique de toutes les tâches
        self.current_task: Optional[BaseTask] = None
        
        # État du pipeline
        self.is_running = False
        self.is_paused = False
        self.cancel_requested = False
        
        # Thread d'exécution
        self.execution_thread = None
        
        # Callbacks globaux
        self.on_task_started_callback = None
        self.on_task_completed_callback = None
        self.on_task_failed_callback = None
        self.on_pipeline_completed_callback = None
        self.on_pipeline_progress_callback = None
        
        # Statistiques
        self.total_tasks_completed = 0
        self.total_tasks_failed = 0
        self.pipeline_start_time = None
        self.pipeline_end_time = None
    
    def add_task(self, task: BaseTask):
        """Ajouter une tâche à la queue"""
        # Ajouter à l'historique
        self.tasks.append(task)
        
        # Configurer les callbacks de la tâche
        task.set_progress_callback(self._on_task_progress)
        task.set_status_change_callback(self._on_task_status_change)
        
        # Ajouter à la queue avec priorité
        priority = -task.priority.value  # Négatif pour ordre décroissant
        self.task_queue.put((priority, task))
        
        print(f"✅ Tâche ajoutée: {task.name} (Priorité: {task.priority.name})")
    
    def remove_task(self, task_id: str) -> bool:
        """Retirer une tâche de la queue (seulement si en attente)"""
        task = self.get_task_by_id(task_id)
        
        if not task:
            return False
        
        if task.status != TaskStatus.PENDING:
            return False
        
        # Marquer comme annulée
        task.update_status(TaskStatus.CANCELLED, "Retirée de la queue")
        
        # Note: Difficile de retirer d'une PriorityQueue, 
        # on marque juste comme cancelled et elle sera skip
        return True
    
    def start_pipeline(self):
        """Démarrer l'exécution du pipeline"""
        if self.is_running:
            print("⚠️ Pipeline déjà en cours d'exécution")
            return
        
        if self.task_queue.empty():
            print("⚠️ Aucune tâche dans la queue")
            return
        
        self.is_running = True
        self.is_paused = False
        self.cancel_requested = False
        self.pipeline_start_time = datetime.now()
        
        # Lancer le thread d'exécution
        self.execution_thread = threading.Thread(target=self._execute_pipeline, daemon=True)
        self.execution_thread.start()
        
        print("🚀 Pipeline démarré")
    
    def pause_pipeline(self):
        """Mettre en pause le pipeline"""
        if not self.is_running:
            return
        
        self.is_paused = True
        print("⏸️ Pipeline en pause")
    
    def resume_pipeline(self):
        """Reprendre le pipeline"""
        if not self.is_running or not self.is_paused:
            return
        
        self.is_paused = False
        print("▶️ Pipeline repris")
    
    def cancel_pipeline(self):
        """Annuler l'exécution du pipeline"""
        if not self.is_running:
            return
        
        self.cancel_requested = True
        
        # Annuler la tâche en cours
        if self.current_task:
            self.current_task.cancel()
        
        print("🛑 Annulation du pipeline demandée")
    
    def _execute_pipeline(self):
        """Boucle principale d'exécution du pipeline"""
        try:
            while not self.task_queue.empty() and not self.cancel_requested:
                # Attendre si en pause
                while self.is_paused and not self.cancel_requested:
                    threading.Event().wait(0.1)
                
                if self.cancel_requested:
                    break
                
                # Récupérer la prochaine tâche
                priority, task = self.task_queue.get()
                
                # Skip si déjà annulée
                if task.status == TaskStatus.CANCELLED:
                    continue
                
                self.current_task = task
                
                # Notifier le début de la tâche
                if self.on_task_started_callback:
                    self.on_task_started_callback(task)
                
                print(f"\n{'='*60}")
                print(f"▶️ Exécution: {task.name}")
                print(f"   Description: {task.description}")
                print(f"{'='*60}")
                
                # Exécuter la tâche
                success = task.execute()
                
                # Notifier la fin de la tâche
                if success:
                    self.total_tasks_completed += 1
                    if self.on_task_completed_callback:
                        self.on_task_completed_callback(task)
                    print(f"✅ Tâche terminée: {task.name}")
                else:
                    self.total_tasks_failed += 1
                    if self.on_task_failed_callback:
                        self.on_task_failed_callback(task)
                    print(f"❌ Tâche échouée: {task.name}")
                
                self.current_task = None
                self.task_queue.task_done()
            
            # Pipeline terminé
            self.pipeline_end_time = datetime.now()
            self.is_running = False
            
            # Afficher résumé
            self._print_pipeline_summary()
            
            # Notifier la fin du pipeline
            if self.on_pipeline_completed_callback:
                self.on_pipeline_completed_callback(self.get_pipeline_stats())
            
        except Exception as e:
            print(f"❌ Erreur critique dans le pipeline: {e}")
            self.is_running = False
    
    def _on_task_progress(self, task: BaseTask, progress: int, message: str):
        """Callback pour la progression d'une tâche"""
        if self.on_pipeline_progress_callback:
            self.on_pipeline_progress_callback(task, progress, message)
    
    def _on_task_status_change(self, task: BaseTask, old_status, new_status, message: str):
        """Callback pour les changements de statut d'une tâche"""
        pass  # Géré par les autres callbacks
    
    def _print_pipeline_summary(self):
        """Afficher le résumé du pipeline"""
        duration = (self.pipeline_end_time - self.pipeline_start_time).total_seconds()
        
        print(f"\n{'='*60}")
        print("📊 RÉSUMÉ DU PIPELINE")
        print(f"{'='*60}")
        print(f"   • Durée totale: {duration:.1f}s")
        print(f"   • Tâches réussies: {self.total_tasks_completed}")
        print(f"   • Tâches échouées: {self.total_tasks_failed}")
        print(f"   • Total: {self.total_tasks_completed + self.total_tasks_failed}")
        print(f"{'='*60}\n")
    
    def get_pending_tasks(self) -> List[BaseTask]:
        """Obtenir les tâches en attente"""
        return [t for t in self.tasks if t.status == TaskStatus.PENDING]
    
    def get_completed_tasks(self) -> List[BaseTask]:
        """Obtenir les tâches terminées"""
        return [t for t in self.tasks if t.status == TaskStatus.COMPLETED]
    
    def get_failed_tasks(self) -> List[BaseTask]:
        """Obtenir les tâches échouées"""
        return [t for t in self.tasks if t.status == TaskStatus.FAILED]
    
    def get_task_by_id(self, task_id: str) -> Optional[BaseTask]:
        """Obtenir une tâche par son ID"""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None
    
    def get_pipeline_stats(self):
        """Obtenir les statistiques du pipeline"""
        duration = None
        if self.pipeline_start_time and self.pipeline_end_time:
            duration = (self.pipeline_end_time - self.pipeline_start_time).total_seconds()
        
        return {
            'total_tasks': len(self.tasks),
            'pending': len(self.get_pending_tasks()),
            'completed': self.total_tasks_completed,
            'failed': self.total_tasks_failed,
            'is_running': self.is_running,
            'is_paused': self.is_paused,
            'duration': duration,
            'current_task': self.current_task.name if self.current_task else None
        }
    
    def clear_completed_tasks(self):
        """Nettoyer les tâches terminées de l'historique"""
        self.tasks = [t for t in self.tasks if t.status not in [TaskStatus.COMPLETED, TaskStatus.CANCELLED]]
        self.total_tasks_completed = 0
        self.total_tasks_failed = 0
    
    def set_callbacks(self,
                     on_task_started=None,
                     on_task_completed=None,
                     on_task_failed=None,
                     on_pipeline_completed=None,
                     on_pipeline_progress=None):
        """Configurer tous les callbacks du pipeline"""
        if on_task_started:
            self.on_task_started_callback = on_task_started
        if on_task_completed:
            self.on_task_completed_callback = on_task_completed
        if on_task_failed:
            self.on_task_failed_callback = on_task_failed
        if on_pipeline_completed:
            self.on_pipeline_completed_callback = on_pipeline_completed
        if on_pipeline_progress:
            self.on_pipeline_progress_callback = on_pipeline_progress