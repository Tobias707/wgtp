#!/usr/bin/env python3
"""
bootstrap_appids.py – Lädt alle Steam AppIDs herunter und speichert sie in all_steam_appids.json

Dies braucht man nur 1x laufen zu lassen. Danach nutzt fetch_games.py die lokale Cache.
"""

import json
import sys
from pathlib import Path

try:
    import requests
except ImportError:
    sys.exit("requests nicht installiert. Bitte: pip install requests")

OUTPUT_FILE = Path(__file__).parent / "all_steam_appids.json"

def bootstrap():
    print("Lade alle Steam AppIDs herunter...")
    print("(Dies kann 30-60 Sekunden dauern)\n")

    # Versuche 1: SteamDB API (zuverlässigste Quelle)
    print("1. Versuche SteamDB API...")
    try:
        resp = requests.get(
            "https://steamdb.info/api/v1/apps/with_release_date",
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()

        if isinstance(data, list):
            appids = sorted(set(
                app.get("appid") for app in data
                if isinstance(app.get("appid"), int)
            ))

            if appids:
                with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                    json.dump(appids, f)
                print(f"✓ Erfolgreich! {len(appids)} AppIDs gespeichert in {OUTPUT_FILE.name}\n")
                return True
    except Exception as e:
        print(f"✗ SteamDB fehlgeschlagen: {e}\n")

    # Versuche 2: Steam API (alter Endpoint)
    print("2. Versuche Steam API...")
    try:
        resp = requests.get(
            "https://api.steampowered.com/ISteamApps/GetAppList/v2/",
            timeout=60
        )
        resp.raise_for_status()
        data = resp.json()
        apps = data.get("applist", {}).get("apps", [])

        if apps:
            appids = sorted([app["appid"] for app in apps if isinstance(app.get("appid"), int)])
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                json.dump(appids, f)
            print(f"✓ Erfolgreich! {len(appids)} AppIDs gespeichert in {OUTPUT_FILE.name}\n")
            return True
    except Exception as e:
        print(f"✗ Steam API fehlgeschlagen: {e}\n")

    # Versuche 3: Manuell herunterladen
    print("3. Manuelle Alternative:")
    print("   a) Gehe zu: https://steamdb.info/api/v1/apps/with_release_date")
    print("   b) Speichere die JSON-Response")
    print("   c) Extrahiere alle 'appid' Werte in ein Array")
    print("   d) Speichere als all_steam_appids.json\n")

    return False

if __name__ == "__main__":
    success = bootstrap()
    if not success:
        print("[FEHLER] Konnte AppID-Liste nicht herunterladen.")
        print(f"Erstelle {OUTPUT_FILE.name} manuell mit einer Liste aller Steam AppIDs.")
        sys.exit(1)
