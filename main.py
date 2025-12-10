#!/usr/bin/env python3
"""
Speedrun Pipeline Manager - Main Entry Point
Application desktop pour gérer le pipeline d'extraction et d'analyse de données speedrun
"""

import sys
import os
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow
# Ajouter le dossier courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def check_dependencies():
    """Vérifier que toutes les dépendances sont installées"""
    missing = []
    
    # PyQt6
    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        missing.append("PyQt6")
    
    # pandas
    try:
        import pandas
    except ImportError:
        missing.append("pandas")
    
    # cloudscraper
    try:
        import cloudscraper
    except ImportError:
        missing.append("cloudscraper")
    
    return missing

def check_scraper_module():
    """Vérifier que le module scraper.py est disponible"""
    if not os.path.exists('scraper.py'):
        return False, "Fichier scraper.py non trouvé dans le dossier de l'application"
    
    try:
        from scraper import ImprovedSpeedrunScraper
        return True, "Module scraper disponible"
    except ImportError as e:
        return False, f"Erreur lors de l'import du scraper: {str(e)}"

def create_directories():
    """Créer les dossiers nécessaires"""
    directories = [
        'downloads',  # Pour les CSV extraits
        'logs',       # Pour les logs
        'data',       # Pour les données
        'config'      # Pour les configurations sauvegardées
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"✅ Dossier créé: {directory}/")

def print_banner():
    """Afficher la bannière de l'application"""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║       🎮 SPEEDRUN PIPELINE MANAGER 🎮                     ║
║                                                           ║
║       Extraction & Analyse de Données Speedrun           ║
║       Version 1.0.0 - Phase 1: Extraction                ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)

def main():
    """Point d'entrée principal de l'application"""
    print_banner()
    
    print("\n Vérifications préliminaires...")
    print("=" * 60)
    
    # 1. Vérifier les dépendances
    print("\n1️⃣ Vérification des dépendances Python...")
    missing_deps = check_dependencies()
    
    if missing_deps:
        print(" Dépendances manquantes:")
        for dep in missing_deps:
            print(f"   • {dep}")
        print("\n Installation requise:")
        print("pip install PyQt6 pandas cloudscraper --break-system-packages")
        input("\nAppuyez sur Entrée pour fermer...")
        return 1
    else:
        print(" Toutes les dépendances Python sont installées")
    
    # 2. Vérifier le module scraper
    print("\n2️⃣ Vérification du module scraper...")
    scraper_ok, scraper_msg = check_scraper_module()
    
    if not scraper_ok:
        print(f" {scraper_msg}")
        print("\n Solution:")
        print("   1. Placez le fichier scraper.py dans le dossier de l'application")
        print("   2. Assurez-vous qu'il contient la classe ImprovedSpeedrunScraper")
        
        # Demander si on continue quand même
        response = input("\nContinuer quand même (certaines fonctionnalités seront désactivées)? [o/N]: ")
        if response.lower() != 'o':
            return 1
    else:
        print(f"✅ {scraper_msg}")
    
    # 3. Créer les dossiers nécessaires
    print("\n3️⃣ Création des dossiers...")
    create_directories()
    
    # 4. Lancer l'application PyQt6
    print("\n4️⃣ Lancement de l'interface graphique...")
    print("=" * 60)
    print("\nDémarrage de l'application...\n")
    
    try:
        # Configuration de l'application Qt
        app = QApplication(sys.argv)
        app.setApplicationName("Speedrun Pipeline Manager")
        app.setOrganizationName("LADDER Research Project")
        
        # Importer et créer la fenêtre principale
        from ui.main_window import MainWindow
        
        # Créer et afficher la fenêtre
        window = MainWindow()
        window.show()
        
        print("Interface lancée avec succès")
        print("L'application est maintenant prête à l'emploi\n")
        
        # Lancer la boucle d'événements
        sys.exit(app.exec())
        
    except Exception as e:
        print(f"\n Erreur lors du lancement de l'application:")
        print(f"   {str(e)}")
        print("\n Stack trace complète:")
        import traceback
        traceback.print_exc()
        input("\nAppuyez sur Entrée pour fermer...")
        return 1

if __name__ == '__main__':
    sys.exit(main())