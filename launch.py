#!/usr/bin/env python3
"""
Launcher - Script de lancement rapide pour Speedrun Pipeline Manager
Vérifie et installe automatiquement les dépendances si nécessaire
"""

import subprocess
import sys
import os

def check_and_install_dependencies():
    """Vérifier et installer les dépendances manquantes"""
    print("🔍 Vérification des dépendances...")
    
    dependencies = {
        'PyQt6': 'PyQt6',
        'pandas': 'pandas',
        'cloudscraper': 'cloudscraper'
    }
    
    missing = []
    
    for module, package in dependencies.items():
        try:
            __import__(module)
            print(f"   ✅ {package}")
        except ImportError:
            print(f"   ❌ {package} - manquant")
            missing.append(package)
    
    if missing:
        print(f"\n📦 Installation de {len(missing)} dépendance(s) manquante(s)...")
        
        for package in missing:
            print(f"\n   Installation de {package}...")
            try:
                subprocess.check_call([
                    sys.executable, "-m", "pip", "install", 
                    package, "--break-system-packages"
                ])
                print(f"   ✅ {package} installé avec succès")
            except subprocess.CalledProcessError:
                print(f"   ❌ Échec de l'installation de {package}")
                print("\n⚠️  Installation manuelle requise:")
                print(f"   pip install {package} --break-system-packages")
                return False
    
    return True

def main():
    """Point d'entrée du launcher"""
    print("=" * 60)
    print("🎮 SPEEDRUN PIPELINE MANAGER - LAUNCHER")
    print("=" * 60)
    print()
    
    # Vérifier version Python
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ requis")
        print(f"   Version actuelle: {sys.version}")
        input("\nAppuyez sur Entrée pour fermer...")
        return 1
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print()
    
    # Vérifier et installer dépendances
    if not check_and_install_dependencies():
        input("\nAppuyez sur Entrée pour fermer...")
        return 1
    
    print("\n✅ Toutes les dépendances sont installées")
    print()
    
    # Lancer l'application
    print("🚀 Lancement de l'application...")
    print("=" * 60)
    print()
    
    try:
        # Importer et lancer main.py
        import main
        return main.main()
    
    except KeyboardInterrupt:
        print("\n\n👋 Application fermée par l'utilisateur")
        return 0
    
    except Exception as e:
        print(f"\n❌ Erreur lors du lancement: {e}")
        import traceback
        traceback.print_exc()
        input("\nAppuyez sur Entrée pour fermer...")
        return 1

if __name__ == '__main__':
    sys.exit(main())