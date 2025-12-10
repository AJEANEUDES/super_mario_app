#!/usr/bin/env python3
"""
Example - Utilisation programmatique du Pipeline Manager
Démonstration d'utilisation sans interface graphique
"""

import sys
import os

# Ajouter le dossier au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline_manager import PipelineManager
from tasks.scraper_task import ScraperTask

def example_simple():
    """Exemple simple: Extraction d'une catégorie"""
    print("=" * 60)
    print("EXEMPLE 1: Extraction Simple")
    print("=" * 60)
    
    # Créer le pipeline manager
    pipeline = PipelineManager()
    
    # Créer une tâche de scraping
    task = ScraperTask(
        speedrun_url="https://www.speedrun.com/smb1?h=Any-NTSC",
        start_page=1,
        end_page=2,
        project_name="SMB_Any_NTSC"
    )
    
    # Ajouter au pipeline
    pipeline.add_task(task)
    
    # Démarrer l'exécution
    pipeline.start_pipeline()
    
    # Attendre la fin
    while pipeline.is_running:
        import time
        time.sleep(1)
    
    # Afficher les résultats
    stats = pipeline.get_pipeline_stats()
    print("\n📊 Résultats:")
    print(f"   Tâches complétées: {stats['completed']}")
    print(f"   Tâches échouées: {stats['failed']}")
    print(f"   Durée totale: {stats['duration']:.1f}s")

def example_multiple_tasks():
    """Exemple avancé: Plusieurs tâches enchaînées"""
    print("\n" + "=" * 60)
    print("EXEMPLE 2: Extraction Multiple")
    print("=" * 60)
    
    # Créer le pipeline manager
    pipeline = PipelineManager()
    
    # Configurer callbacks pour monitoring
    def on_task_started(task):
        print(f"\n▶️ Démarrage: {task.name}")
    
    def on_task_completed(task):
        print(f"✅ Terminé: {task.name}")
        if hasattr(task, 'result') and task.result:
            print(f"   Runs extraits: {task.result.get('total_runs', 'N/A')}")
    
    def on_progress(task, progress, message):
        print(f"   [{progress}%] {message}")
    
    pipeline.set_callbacks(
        on_task_started=on_task_started,
        on_task_completed=on_task_completed,
        on_pipeline_progress=on_progress
    )
    
    # Créer plusieurs tâches
    tasks = [
        ScraperTask(
            speedrun_url="https://www.speedrun.com/smb1?h=Any-NTSC",
            start_page=1,
            end_page=2,
            project_name="SMB_Any_NTSC"
        ),
        ScraperTask(
            speedrun_url="https://www.speedrun.com/smb1?h=Warpless-PAL",
            start_page=1,
            end_page=2,
            project_name="SMB_Warpless_PAL"
        )
    ]
    
    # Ajouter toutes les tâches
    for task in tasks:
        pipeline.add_task(task)
    
    # Démarrer l'exécution
    pipeline.start_pipeline()
    
    # Attendre la fin
    while pipeline.is_running:
        import time
        time.sleep(1)
    
    # Afficher résumé final
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ FINAL")
    print("=" * 60)
    
    stats = pipeline.get_pipeline_stats()
    print(f"Total de tâches: {stats['total_tasks']}")
    print(f"Complétées: {stats['completed']}")
    print(f"Échouées: {stats['failed']}")
    print(f"Durée totale: {stats['duration']:.1f}s")
    
    # Afficher détails des tâches réussies
    completed_tasks = pipeline.get_completed_tasks()
    if completed_tasks:
        print("\n✅ Tâches réussies:")
        for task in completed_tasks:
            info = task.get_info()
            print(f"   • {info['name']}")
            print(f"     Durée: {info['duration']:.1f}s")
            if hasattr(task, 'result') and task.result:
                print(f"     Résultat: {task.result.get('total_runs', 'N/A')} runs")

def example_with_custom_callbacks():
    """Exemple avec callbacks personnalisés"""
    print("\n" + "=" * 60)
    print("EXEMPLE 3: Callbacks Personnalisés")
    print("=" * 60)
    
    # Créer le pipeline
    pipeline = PipelineManager()
    
    # Statistiques personnalisées
    stats = {
        'tasks_started': 0,
        'tasks_completed': 0,
        'total_runs_extracted': 0
    }
    
    # Callbacks personnalisés
    def custom_on_start(task):
        stats['tasks_started'] += 1
        print(f"🚀 Tâche {stats['tasks_started']} démarrée: {task.name}")
    
    def custom_on_complete(task):
        stats['tasks_completed'] += 1
        if hasattr(task, 'result') and task.result:
            runs = task.result.get('total_runs', 0)
            stats['total_runs_extracted'] += runs
            print(f"✅ Tâche terminée: {runs} runs extraits")
    
    def custom_on_pipeline_complete(pipeline_stats):
        print("\n" + "=" * 60)
        print("🎉 PIPELINE TERMINÉ")
        print("=" * 60)
        print(f"Tâches exécutées: {stats['tasks_started']}")
        print(f"Tâches réussies: {stats['tasks_completed']}")
        print(f"Total runs extraits: {stats['total_runs_extracted']}")
        print(f"Durée: {pipeline_stats['duration']:.1f}s")
    
    pipeline.set_callbacks(
        on_task_started=custom_on_start,
        on_task_completed=custom_on_complete,
        on_pipeline_completed=custom_on_pipeline_complete
    )
    
    # Ajouter une tâche
    task = ScraperTask(
        speedrun_url="https://www.speedrun.com/smb1?h=Any-NTSC",
        start_page=1,
        end_page=1,
        project_name="SMB_Quick_Test"
    )
    
    pipeline.add_task(task)
    
    # Exécuter
    pipeline.start_pipeline()
    
    # Attendre
    while pipeline.is_running:
        import time
        time.sleep(1)

def main():
    """Point d'entrée des exemples"""
    print("\n🎮 SPEEDRUN PIPELINE MANAGER - EXEMPLES D'UTILISATION")
    print("=" * 60)
    print("\nCes exemples montrent comment utiliser le Pipeline Manager")
    print("de manière programmatique (sans interface graphique).")
    print()
    
    # Menu de sélection
    print("Choisissez un exemple:")
    print("1. Extraction simple (1 tâche)")
    print("2. Extraction multiple (2 tâches)")
    print("3. Callbacks personnalisés")
    print("0. Quitter")
    print()
    
    choice = input("Votre choix [1-3]: ").strip()
    
    if choice == '1':
        example_simple()
    elif choice == '2':
        example_multiple_tasks()
    elif choice == '3':
        example_with_custom_callbacks()
    elif choice == '0':
        print("👋 Au revoir!")
        return
    else:
        print("❌ Choix invalide")
        return
    
    print("\n✅ Exemple terminé!")
    print("Consultez le dossier downloads/ pour les fichiers CSV générés.")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Arrêté par l'utilisateur")
    except Exception as e:
        print(f"\n❌ Erreur: {e}")
        import traceback
        traceback.print_exc()