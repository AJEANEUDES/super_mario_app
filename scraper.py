import cloudscraper
import json
import csv
import re
import time
import os
import pandas as pd
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

class ImprovedSpeedrunScraper:
    def __init__(self):
        self.scraper = cloudscraper.create_scraper()
        self.all_runs = []
        self.players = {}
        self.platforms = {}
        self.missing_players = set()
        self.missing_platforms = set()
        self.progress_callback = None
        self.debug_mode = True  # Activer debug pour diagnostiquer l'extraction
        
    def set_progress_callback(self, callback):
        """Définir callback pour progression"""
        self.progress_callback = callback
    
    def debug_print(self, message):
        """Print de debug si activé"""
        if self.debug_mode:
            print(f"[DEBUG] {message}")
    
    def scrape_with_progress(self, url, start_page, end_page, progress_callback=None):
        """
        ===== MÉTHODE AJOUTÉE POUR COMPATIBILITÉ HYBRID =====
        Interface attendue par le queue manager hybrid
        """
        # Reset state pour nouveau scraping
        self.all_runs = []
        self.players = {}
        self.platforms = {}
        self.missing_players = set()
        self.missing_platforms = set()
        
        # Set callback
        if progress_callback:
            self.progress_callback = progress_callback
        
        try:
            self.debug_print(f"START SCRAPING: {url} (pages {start_page}-{end_page})")
            
            # Utiliser la méthode existante
            runs = self.scrape_page_range(url, start_page, end_page)
            
            # Debug final
            self.debug_print(f"FINAL: Total runs collectés: {len(runs)}")
            self.debug_print(f"FINAL: {len(self.players)} joueurs mappés, {len(self.platforms)} plateformes mappées")
            if self.players:
                self.debug_print(f"Exemples joueurs: {list(self.players.items())[:3]}")
            if self.platforms:
                self.debug_print(f"Exemples plateformes: {list(self.platforms.items())[:3]}")
            
            # Convertir en DataFrame pour compatibilité
            if runs and len(runs) > 0:
                self.debug_print(f"Converting {len(runs)} runs to DataFrame")
                df = pd.DataFrame(runs)
                self.debug_print(f"DataFrame created: shape={df.shape}")
                return df
            else:
                self.debug_print("WARNING: No runs found, returning empty DataFrame")
                # Retourner DataFrame vide avec colonnes requises
                return pd.DataFrame(columns=['player', 'time', 'video_url', 'rank', 'category', 'platform'])
                
        except Exception as e:
            self.debug_print(f"ERROR in scrape_with_progress: {e}")
            import traceback
            self.debug_print(traceback.format_exc())
            print(f"Erreur scraping: {e}")
            # Retourner DataFrame vide en cas d'erreur
            return pd.DataFrame(columns=['player', 'time', 'video_url', 'rank', 'category', 'platform'])
    
    def extract_url_info(self, url):
        """Extrait infos depuis l'URL"""
        info = {
            'game': '',
            'category': '',
            'version': '',
            'base_url': url.split('?')[0]
        }
        
        # Extraire le jeu
        if '/smb1' in url or '/smb' in url:
            info['game'] = 'Super Mario Bros.'
        elif '/smb2' in url:
            info['game'] = 'Super Mario Bros. 2'
        
        # Extraire catégorie et version depuis paramètres
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        
        if 'h' in params:
            h_value = params['h'][0]
            
            # Parser h= pour catégorie et version
            if 'Any-NTSC' in h_value:
                info['category'] = 'Any%'
                info['version'] = 'NTSC'
            elif 'Any-PAL' in h_value:
                info['category'] = 'Any%'
                info['version'] = 'PAL'
            elif 'Warpless-PAL' in h_value:
                info['category'] = 'Warpless'
                info['version'] = 'PAL'
            elif 'Any_All-Stars' in h_value:
                info['category'] = 'Any% All-Stars'
                info['version'] = ''
            elif 'Warpless_All-Stars' in h_value:
                info['category'] = 'Warpless All-Stars'
                info['version'] = ''
            elif 'Any' in h_value:
                info['category'] = 'Any%'
                info['version'] = ''
            else:
                info['category'] = h_value
                info['version'] = ''
        
        return info
    
    def scrape_page_range(self, base_url, start_page, end_page):
        """Scrape pages spécifiées par l'utilisateur"""
        url_info = self.extract_url_info(base_url)
        total_runs = 0
        
        for page in range(start_page, end_page + 1):
            if self.progress_callback:
                progress = int(((page - start_page) / (end_page - start_page + 1)) * 100)
                self.progress_callback(page, end_page, progress, f"Scraping page {page}/{end_page}...")
            
            # Construire URL avec page
            # IMPORTANT: La page 1 n'a pas besoin du paramètre page=1 sur speedrun.com
            if page == 1:
                page_url = base_url
            else:
                if '?' in base_url:
                    page_url = f"{base_url}&page={page}"
                else:
                    page_url = f"{base_url}?page={page}"
            
            try:
                self.debug_print(f"Scraping: {page_url}")
                response = self.scraper.get(page_url, timeout=30)
                
                if response.status_code != 200:
                    self.debug_print(f"Status {response.status_code} pour page {page}")
                    continue
                
                # Extraire données Next.js
                next_data = self.extract_nextjs_from_html(response.text)
                
                if not next_data:
                    self.debug_print(f"Pas de données Next.js pour page {page}")
                    continue
                
                # Parser la page avec extraction améliorée
                page_runs = self.parse_page_data_enhanced(next_data, page, url_info)
                
                if page_runs:
                    self.all_runs.extend(page_runs)
                    total_runs += len(page_runs)
                    self.debug_print(f"Page {page}: {len(page_runs)} runs extraits")
                
                # Délai entre pages
                if page < end_page:
                    time.sleep(2)
                
            except Exception as e:
                self.debug_print(f"Erreur page {page}: {e}")
                continue
        
        # Résoudre les IDs manquants après toutes les pages
        self.resolve_missing_ids_enhanced()
        
        return self.all_runs
    
    def parse_page_data_enhanced(self, data, page_num, url_info):
        """
        ===== VERSION AMÉLIORÉE EXTRACTION NOMS + PLATEFORMES =====
        Parse avec stratégies multiples pour noms joueurs ET plateformes
        """
        try:
            props = data['props']['pageProps']
            
            # Debug structure
            self.debug_print(f"Props keys: {list(props.keys())}")
            
            # === ÉTAPE 1: MAPPING EXHAUSTIF JOUEURS + PLATEFORMES ===
            self.extract_players_and_platforms_all_methods(data)
            
            # === ÉTAPE 2: PARSER LES RUNS AVEC NOMS ===
            runs = []
            if 'leaderboardData' in props and 'runList' in props['leaderboardData']:
                run_list = props['leaderboardData']['runList']
                self.debug_print(f"RunList: {len(run_list)} runs trouvés")
                
                for i, run in enumerate(run_list):
                    parsed_run = self.parse_single_run_enhanced(run, page_num, url_info, i)
                    if parsed_run:
                        runs.append(parsed_run)
            
            self.debug_print(f"Page {page_num} final: {len(runs)} runs, {len(self.players)} joueurs, {len(self.platforms)} plateformes")
            return runs
            
        except Exception as e:
            self.debug_print(f"Erreur parse_page_data: {e}")
            return []
    
    def extract_players_and_platforms_all_methods(self, data):
        """
        ===== EXTRACTION EXHAUSTIVE JOUEURS + PLATEFORMES =====
        Utilise toutes les méthodes possibles pour extraire les noms
        """
        initial_players = len(self.players)
        initial_platforms = len(self.platforms)
        
        try:
            props = data['props']['pageProps']
            
            # === MÉTHODE 1: gameData direct ===
            if 'gameData' in props:
                game_data = props['gameData']
                
                # Players depuis gameData
                if 'players' in game_data:
                    for player in game_data['players']:
                        if isinstance(player, dict) and 'id' in player and 'name' in player:
                            self.players[player['id']] = player['name']
                            self.debug_print(f"GameData Player: {player['id']} -> {player['name']}")
                
                # Platforms depuis gameData
                if 'platforms' in game_data:
                    for platform in game_data['platforms']:
                        if isinstance(platform, dict) and 'id' in platform and 'name' in platform:
                            self.platforms[platform['id']] = platform['name']
                            self.debug_print(f"GameData Platform: {platform['id']} -> {platform['name']}")
            
            # === MÉTHODE 2: leaderboardData exhaustif ===
            if 'leaderboardData' in props:
                leaderboard = props['leaderboardData']
                
                # Players depuis leaderboardData.players
                if 'players' in leaderboard:
                    players_data = leaderboard['players']
                    if isinstance(players_data, dict):
                        for player_id, player_info in players_data.items():
                            if isinstance(player_info, dict) and 'name' in player_info:
                                self.players[player_id] = player_info['name']
                                self.debug_print(f"Leaderboard Player: {player_id} -> {player_info['name']}")
                
                # Platforms depuis leaderboardData.platforms
                if 'platforms' in leaderboard:
                    platforms_data = leaderboard['platforms']
                    if isinstance(platforms_data, dict):
                        for platform_id, platform_info in platforms_data.items():
                            if isinstance(platform_info, dict) and 'name' in platform_info:
                                self.platforms[platform_id] = platform_info['name']
                                self.debug_print(f"Leaderboard Platform: {platform_id} -> {platform_info['name']}")
                
                # === MÉTHODE 3: Extract depuis runList direct ===
                if 'runList' in leaderboard:
                    for run in leaderboard['runList']:
                        # Extraire players depuis run
                        player_extracted = self.extract_player_from_run(run)
                        if player_extracted:
                            player_id, player_name = player_extracted
                            self.players[player_id] = player_name
                            self.debug_print(f"Run Player: {player_id} -> {player_name}")
                        
                        # Extraire platforms depuis run
                        platform_extracted = self.extract_platform_from_run(run)
                        if platform_extracted:
                            platform_id, platform_name = platform_extracted
                            self.platforms[platform_id] = platform_name
                            self.debug_print(f"Run Platform: {platform_id} -> {platform_name}")
            
            # === MÉTHODE 4: Recherche récursive exhaustive ===
            self.recursive_search_entities_enhanced(data)
            
        except Exception as e:
            self.debug_print(f"Erreur extract_all_methods: {e}")
        
        new_players = len(self.players) - initial_players
        new_platforms = len(self.platforms) - initial_platforms
        self.debug_print(f"Extraits: +{new_players} joueurs, +{new_platforms} plateformes")
    
    def extract_platform_from_run(self, run):
        """
        ===== NOUVELLE MÉTHODE: EXTRACTION PLATEFORMES =====
        Extraire platform info directement depuis un run (comme pour players)
        """
        try:
            # Stratégies multiples pour plateformes
            strategies = [
                # Structure 1: platform direct
                lambda r: self._get_platform_direct(r),
                # Structure 2: platformId + platform mapping
                lambda r: self._get_platform_from_id(r),
                # Structure 3: recherche dans détails run
                lambda r: self._search_platform_in_run_details(r),
            ]
            
            for strategy in strategies:
                try:
                    result = strategy(run)
                    if result and result[0] and result[1]:
                        return result
                except:
                    continue
                    
        except Exception as e:
            self.debug_print(f"Erreur extract_platform_from_run: {e}")
        
        return None
    
    def _get_platform_direct(self, run):
        """Extraire platform depuis structure directe"""
        try:
            if 'platform' in run:
                platform_obj = run['platform']
                if isinstance(platform_obj, dict):
                    platform_id = platform_obj.get('id')
                    platform_name = platform_obj.get('name')
                    if platform_id and platform_name:
                        return platform_id, platform_name
        except Exception as e:
            self.debug_print(f"Erreur _get_platform_direct: {e}")
        return None
    
    def _get_platform_from_id(self, run):
        """Extraire platform depuis platformId"""
        try:
            if 'platformId' in run:
                platform_id = run['platformId']
                
                # Chercher le nom dans les données déjà collectées
                if platform_id in self.platforms:
                    return platform_id, self.platforms[platform_id]
                
                # Chercher dans le run lui-même
                if 'platforms' in run:
                    platforms_in_run = run['platforms']
                    if isinstance(platforms_in_run, dict) and platform_id in platforms_in_run:
                        platform_info = platforms_in_run[platform_id]
                        if isinstance(platform_info, dict) and 'name' in platform_info:
                            return platform_id, platform_info['name']
                        elif isinstance(platform_info, str):
                            return platform_id, platform_info
                
        except Exception as e:
            self.debug_print(f"Erreur _get_platform_from_id: {e}")
        return None
    
    def _search_platform_in_run_details(self, run):
        """Rechercher platform info dans tous les détails du run"""
        try:
            # Recherche récursive dans le run
            def find_platform_name_for_id(obj, target_id):
                if isinstance(obj, dict):
                    # Chercher id + name dans le même objet
                    if obj.get('id') == target_id and 'name' in obj:
                        return obj['name']
                    
                    # Rechercher récursivement
                    for value in obj.values():
                        result = find_platform_name_for_id(value, target_id)
                        if result:
                            return result
                            
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_platform_name_for_id(item, target_id)
                        if result:
                            return result
                return None
            
            if 'platformId' in run:
                platform_id = run['platformId']
                name = find_platform_name_for_id(run, platform_id)
                if name:
                    return platform_id, name
                    
        except Exception as e:
            self.debug_print(f"Erreur _search_platform_in_run_details: {e}")
        
        return None
    
    def extract_player_from_run(self, run):
        """Extraire player info directement depuis un run (méthode existante améliorée)"""
        try:
            # Rechercher dans différentes structures possibles
            strategies = [
                # Structure 1: player direct
                lambda r: (r.get('player', {}).get('id'), r.get('player', {}).get('name')),
                # Structure 2: playerIds + player mapping
                lambda r: self.get_player_from_ids(r),
                # Structure 3: dans les détails du run
                lambda r: self.search_player_in_run_details(r),
            ]
            
            for strategy in strategies:
                try:
                    result = strategy(run)
                    if result and result[0] and result[1]:
                        return result
                except:
                    continue
                    
        except Exception as e:
            self.debug_print(f"Erreur extract_player_from_run: {e}")
        
        return None
    
    def get_player_from_ids(self, run):
        """Extraire player depuis playerIds"""
        try:
            if 'playerIds' in run and run['playerIds']:
                player_id = run['playerIds'][0]
                
                # Chercher le nom dans les données déjà collectées
                if player_id in self.players:
                    return player_id, self.players[player_id]
                
                # Chercher dans le run lui-même
                if 'players' in run:
                    players_in_run = run['players']
                    if isinstance(players_in_run, list) and players_in_run:
                        first_player = players_in_run[0]
                        if isinstance(first_player, dict) and 'name' in first_player:
                            return player_id, first_player['name']
                    elif isinstance(players_in_run, dict) and player_id in players_in_run:
                        player_info = players_in_run[player_id]
                        if isinstance(player_info, dict) and 'name' in player_info:
                            return player_id, player_info['name']
                        elif isinstance(player_info, str):
                            return player_id, player_info
                
        except Exception as e:
            self.debug_print(f"Erreur get_player_from_ids: {e}")
        
        return None
    
    def search_player_in_run_details(self, run):
        """Rechercher player info dans tous les détails du run"""
        try:
            # Recherche récursive dans le run
            def find_name_for_id(obj, target_id):
                if isinstance(obj, dict):
                    # Chercher id + name dans le même objet
                    if obj.get('id') == target_id and 'name' in obj:
                        return obj['name']
                    
                    # Rechercher récursivement
                    for value in obj.values():
                        result = find_name_for_id(value, target_id)
                        if result:
                            return result
                            
                elif isinstance(obj, list):
                    for item in obj:
                        result = find_name_for_id(item, target_id)
                        if result:
                            return result
                return None
            
            if 'playerIds' in run and run['playerIds']:
                player_id = run['playerIds'][0]
                name = find_name_for_id(run, player_id)
                if name:
                    return player_id, name
                    
        except Exception as e:
            self.debug_print(f"Erreur search_player_in_run_details: {e}")
        
        return None
    
    def recursive_search_entities_enhanced(self, obj, path=""):
        """
        ===== RECHERCHE RÉCURSIVE JOUEURS + PLATEFORMES =====
        Recherche récursive améliorée des joueurs ET plateformes
        """
        try:
            if isinstance(obj, dict):
                # Pattern 1: Objet avec id + name
                if 'id' in obj and 'name' in obj:
                    obj_id = obj['id']
                    obj_name = obj['name']
                    
                    # Déterminer si c'est un joueur ou une plateforme
                    context_keys = set(obj.keys())
                    
                    # Détection joueur
                    is_player = any(key in context_keys for key in ['playerIds', 'runs', 'profile', 'username', 'user'])
                    player_path_hints = any(hint in path.lower() for hint in ['player', 'user', 'submitter'])
                    
                    # Détection plateforme
                    is_platform = any(key in context_keys for key in ['platformId', 'console', 'system', 'device'])
                    platform_path_hints = any(hint in path.lower() for hint in ['platform', 'console', 'system'])
                    
                    if is_player or player_path_hints:
                        self.players[obj_id] = obj_name
                        self.debug_print(f"Recursive Player: {obj_id} -> {obj_name} (path: {path})")
                    elif is_platform or platform_path_hints:
                        self.platforms[obj_id] = obj_name
                        self.debug_print(f"Recursive Platform: {obj_id} -> {obj_name} (path: {path})")
                
                # Continuer récursivement
                for key, value in obj.items():
                    new_path = f"{path}.{key}" if path else key
                    self.recursive_search_entities_enhanced(value, new_path)
                    
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    new_path = f"{path}[{i}]" if path else f"[{i}]"
                    self.recursive_search_entities_enhanced(item, new_path)
                    
        except Exception as e:
            self.debug_print(f"Erreur recursive_search: {e}")
    
    def parse_single_run_enhanced(self, run, page_num, url_info, run_index):
        """
        ===== VERSION AMÉLIORÉE PARSE RUN =====
        Parse avec extraction de nom + plateforme améliorée
        """
        try:
            # === EXTRACTION PLAYER AMÉLIORÉE ===
            player_id = None
            player_name = "Unknown Player"
            
            # Stratégie 1: playerIds standard
            if run.get('playerIds'):
                player_id = run['playerIds'][0]
                
            # Stratégie 2: player direct
            elif 'player' in run:
                player_obj = run['player']
                if isinstance(player_obj, dict):
                    player_id = player_obj.get('id')
                    if 'name' in player_obj:
                        player_name = player_obj['name']
                elif isinstance(player_obj, str):
                    player_id = player_obj
            
            # Stratégie 3: chercher dans self.players
            if player_id and player_id in self.players:
                player_name = self.players[player_id]
                self.debug_print(f"Run {run_index}: Player trouvé {player_id} -> {player_name}")
            
            # Stratégie 4: extraction directe depuis le run
            elif player_id:
                direct_name = self.extract_player_from_run(run)
                if direct_name:
                    _, player_name = direct_name
                    self.debug_print(f"Run {run_index}: Player direct {player_id} -> {player_name}")
                else:
                    # Fallback avec ID
                    player_name = f"Player_{player_id}"
                    self.missing_players.add(player_id)
                    self.debug_print(f"Run {run_index}: Player missing {player_id}")
            
            # Stratégie 5: chercher autres champs
            else:
                for key in ['user', 'username', 'playerName', 'submitter']:
                    if key in run and run[key]:
                        if isinstance(run[key], dict) and 'name' in run[key]:
                            player_name = run[key]['name']
                        elif isinstance(run[key], str):
                            player_name = run[key]
                        break
            
            # === EXTRACTION PLATEFORME AMÉLIORÉE ===
            platform_id = None
            platform_name = "Unknown Platform"
            
            # Stratégie 1: platformId standard
            if run.get('platformId'):
                platform_id = run['platformId']
            
            # Stratégie 2: platform direct
            elif 'platform' in run:
                platform_obj = run['platform']
                if isinstance(platform_obj, dict):
                    platform_id = platform_obj.get('id')
                    if 'name' in platform_obj:
                        platform_name = platform_obj['name']
                elif isinstance(platform_obj, str):
                    platform_id = platform_obj
            
            # Stratégie 3: chercher dans self.platforms
            if platform_id and platform_id in self.platforms:
                platform_name = self.platforms[platform_id]
                self.debug_print(f"Run {run_index}: Platform trouvée {platform_id} -> {platform_name}")
            
            # Stratégie 4: extraction directe depuis le run
            elif platform_id:
                direct_platform = self.extract_platform_from_run(run)
                if direct_platform:
                    _, platform_name = direct_platform
                    self.debug_print(f"Run {run_index}: Platform direct {platform_id} -> {platform_name}")
                else:
                    # Fallback avec ID
                    platform_name = f"Platform_{platform_id}"
                    self.missing_platforms.add(platform_id)
                    self.debug_print(f"Run {run_index}: Platform missing {platform_id}")
            
            # Stratégie 5: chercher autres champs plateformes
            else:
                for key in ['console', 'system', 'device', 'platformName']:
                    if key in run and run[key]:
                        if isinstance(run[key], dict) and 'name' in run[key]:
                            platform_name = run[key]['name']
                        elif isinstance(run[key], str):
                            platform_name = run[key]
                        break
            
            platform_raw = self.platforms.get(platform_id, platform_id or 'Unknown')
            
            # === RESTE DU PARSING (identique) ===
            
            # Time
            time_seconds = run.get('time', 0)
            time_formatted = self.format_time(time_seconds)
            
            # Dates
            timestamp = run.get('date', 0)
            date_str = ''
            date_relative = ''
            
            if timestamp:
                run_date = datetime.fromtimestamp(timestamp)
                date_str = run_date.strftime('%Y-%m-%d')
                date_relative = self.calculate_relative_date(run_date)
            
            # Emulator info
            emulator = 'Yes' if run.get('emulator') else 'No'
            
            parsed_run = {
                'rank': run.get('place', run_index + 1),  # Fallback avec index
                'player': player_name,
                'category': url_info['category'],
                'time': time_formatted,
                'time_seconds': time_seconds,
                'platform': platform_name,
                'platform_raw': platform_raw,
                'is_emulator': emulator,
                'version': url_info['version'],
                'date': date_str,
                'date_relative': date_relative,
                'run_url': f"https://www.speedrun.com/run/{run['id']}" if run.get('id') else '',
                'video_url': run.get('video', ''),
                'page_number': page_num
            }
            
            return parsed_run
            
        except Exception as e:
            self.debug_print(f"Erreur parse_single_run: {e}")
            return None
    
    def resolve_missing_ids_enhanced(self):
        """Résoudre les IDs manquants avec stratégies améliorées"""
        if not self.missing_players and not self.missing_platforms:
            return
        
        self.debug_print(f"Résolution: {len(self.missing_players)} joueurs, {len(self.missing_platforms)} plateformes manquants")
        
        # Stratégie: mise à jour depuis les runs déjà parsés
        for run in self.all_runs:
            # Résoudre joueurs manquants
            if run['player'].startswith('Player_'):
                player_id = run['player'].replace('Player_', '')
                
                # Chercher dans d'autres runs du même joueur
                for other_run in self.all_runs:
                    if other_run != run and not other_run['player'].startswith('Player_'):
                        # Si même video_url ou patterns similaires, possiblement même joueur
                        if (run.get('video_url') and run['video_url'] == other_run.get('video_url')) or \
                           (run.get('time_seconds') and abs(run['time_seconds'] - other_run.get('time_seconds', 0)) < 1):
                            run['player'] = other_run['player']
                            self.debug_print(f"Résolu joueur: {player_id} -> {other_run['player']}")
                            break
            
            # Résoudre plateformes manquantes
            if run['platform'].startswith('Platform_'):
                platform_id = run['platform'].replace('Platform_', '')
                
                # Chercher dans d'autres runs de même catégorie/version
                for other_run in self.all_runs:
                    if other_run != run and not other_run['platform'].startswith('Platform_'):
                        # Si même catégorie/version, probablement même plateforme
                        if run.get('category') == other_run.get('category') and \
                           run.get('version') == other_run.get('version'):
                            run['platform'] = other_run['platform']
                            self.debug_print(f"Résolu plateforme: {platform_id} -> {other_run['platform']}")
                            break
    
    def extract_nextjs_from_html(self, html):
        """Extrait données Next.js"""
        patterns = [
            r'window\.__NEXT_DATA__\s*=\s*({.+?});',
            r'<script id="__NEXT_DATA__"[^>]*>([^<]+)</script>'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except:
                    continue
        return None
    
    def format_time(self, seconds):
        """Formate temps en format lisible"""
        if seconds <= 0:
            return "0s"
        
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        
        if minutes > 0:
            return f"{minutes}m {secs}s {ms}ms"
        return f"{secs}s {ms}ms"
    
    def calculate_relative_date(self, run_date):
        """Calcule date relative"""
        now = datetime.now()
        diff = now - run_date
        
        if diff.days == 0:
            return "aujourd'hui"
        elif diff.days == 1:
            return "il y a 1 jour"
        elif diff.days < 7:
            return f"il y a {diff.days} jours"
        elif diff.days < 14:
            return "il y a 1 semaine"
        elif diff.days < 30:
            weeks = diff.days // 7
            return f"il y a {weeks} semaines"
        elif diff.days < 60:
            return "il y a 1 mois"
        elif diff.days < 365:
            months = diff.days // 30
            return f"il y a {months} mois"
        else:
            years = diff.days // 365
            return f"il y a {years} an{'s' if years > 1 else ''}"
    
    def save_csv_desktop(self, filepath):
        """Sauvegarde CSV pour version desktop"""
        if not self.all_runs:
            return False
        
        if not filepath.startswith('downloads/'):
            filename = os.path.basename(filepath)
            filepath = os.path.join('downloads', filename)
        
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        
        # Trier par rang
        self.all_runs.sort(key=lambda x: x['rank'])
        
        fieldnames = [
            'rank', 'player', 'category', 'time', 'time_seconds', 
            'platform', 'platform_raw', 'is_emulator', 'version',
            'date', 'date_relative', 'run_url', 'video_url', 'page_number'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.all_runs)
        
        # Debug final amélioré
        player_stats = {'Found': 0, 'Missing': 0}
        platform_stats = {'Found': 0, 'Missing': 0}
        
        for run in self.all_runs:
            # Stats joueurs
            if run['player'].startswith('Player_'):
                player_stats['Missing'] += 1
            else:
                player_stats['Found'] += 1
            
            # Stats plateformes
            if run['platform'].startswith('Platform_'):
                platform_stats['Missing'] += 1
            else:
                platform_stats['Found'] += 1
        
        print(f"CSV sauvé: {len(self.all_runs)} runs")
        print(f"Joueurs: {player_stats}")
        print(f"Plateformes: {platform_stats}")
        
        return True
    
    def save_csv(self, filename):
        """Sauvegarde CSV version originale"""
        if not self.all_runs:
            print("Aucune donnée")
            return
        
        if not filename.startswith('downloads/'):
            filename = os.path.join('downloads', os.path.basename(filename))
        
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        # Trier par rang
        self.all_runs.sort(key=lambda x: x['rank'])
        
        fieldnames = [
            'rank', 'player', 'category', 'time', 'time_seconds', 
            'platform', 'platform_raw', 'is_emulator', 'version',
            'date', 'date_relative', 'run_url', 'video_url', 'page_number'
        ]
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.all_runs)
        
        # Stats améliorées
        real_players = len([r for r in self.all_runs if not r['player'].startswith('Player_')])
        missing_players = len([r for r in self.all_runs if r['player'].startswith('Player_')])
        real_platforms = len([r for r in self.all_runs if not r['platform'].startswith('Platform_')])
        missing_platforms = len([r for r in self.all_runs if r['platform'].startswith('Platform_')])
        
        print(f"{len(self.all_runs)} runs sauvées dans {filename}")
        print(f"Joueurs: {real_players} trouvés, {missing_players} manquants")
        print(f"Plateformes: {real_platforms} trouvées, {missing_platforms} manquantes")
        
        if real_players == 0 and missing_players > 0:
            print("⚠️ AUCUN nom de joueur extrait")
        elif real_players > 0:
            print(f"✅ {real_players}/{len(self.all_runs)} noms joueurs extraits")
            
        if real_platforms == 0 and missing_platforms > 0:
            print("⚠️ AUCUN nom de plateforme extrait")
        elif real_platforms > 0:
            print(f"✅ {real_platforms}/{len(self.all_runs)} noms plateformes extraits")

# Alias pour compatibilité
SpeedrunScraper = ImprovedSpeedrunScraper