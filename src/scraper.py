"""
scraper.py — Pipeline unifié : diagnostic -> choix du cas -> extraction -> CSV + journal

Usage :
    python scraper.py URL [URL ...] [--sortie resultats] [--pages 3] [--navigateur]

Pour chaque URL :
  1. diagnostiquer(url)                      (rapport affiché)
  2. extraction automatique selon le cas détecté :
       STOP / G   -> rien n'est collecté
       E          -> JSON intégré, sinon rendu Playwright si --navigateur
       B          -> chaque tableau dans un CSV
       C / A / D  -> blocs répétés, en suivant la pagination (max --pages)
  3. une ligne ajoutée à resultats/journal_tests.csv
"""

import argparse
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import projet_scraping as ws


def nom_fichier(url):
    p = urlparse(url)
    brut = (p.netloc + p.path).strip("/") or "page"
    return re.sub(r"[^\w.-]+", "_", brut)[:80]


def traiter(url, session, dossier, max_pages=3, navigateur=False):
    d = ws.diagnostiquer(url, session)
    ligne = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "url": url,
        "statut": d.get("statut"),
        "robots": d.get("robots_raison"),
        "cas": " | ".join(d.get("cas", [])),
        "recommandation": d.get("recommandation"),
        "nb_lignes": 0,
        "fichiers": "",
        "remarques": "",
    }
    principal = (d.get("cas") or ["?"])[0]
    base = dossier / nom_fichier(url)
    fichiers = []

    try:
        if principal.startswith(("STOP", "G")) or d.get("statut") != 200:
            ligne["remarques"] = "aucune collecte (arrêt volontaire)"

        elif principal.startswith("E"):
            r = session.get(url, timeout=ws.TIMEOUT)
            donnees = ws.extraire_json_integre(r.text)
            if donnees:
                chemin = Path(f"{base}.json")
                chemin.write_text(json.dumps(donnees, ensure_ascii=False, indent=2), encoding="utf-8")
                fichiers.append(chemin)
                ligne["nb_lignes"] = sum(len(x) if isinstance(x, list) else 1 for x in donnees)
                ligne["remarques"] = f"{len(donnees)} bloc(s) JSON intégrés trouvés"
            elif navigateur:
                html = ws.rendre_page(url)
                sp = ws.soupe(html)
                blocs = ws.detecter_blocs_repetes(sp)
                if blocs:
                    lignes = ws.extraire_blocs_generiques(sp, url, blocs["selecteur"])
                    fichiers.append(ws.sauvegarder_csv(lignes, f"{base}.csv"))
                    ligne["nb_lignes"] = len(lignes)
                ligne["remarques"] = "rendu avec Playwright"
            else:
                ligne["remarques"] = "pas de JSON intégré : inspecter l'onglet Réseau ou relancer avec --navigateur"

        elif principal.startswith("B"):
            tableaux = ws.extraire_tableaux(session, url)
            for i, df in enumerate(tableaux, 1):
                if len(df) >= 2:
                    fichiers.append(ws.sauvegarder_csv(ws.nettoyer_tableau(df), f"{base}_tableau{i}.csv"))
                    ligne["nb_lignes"] += len(df)
            ligne["remarques"] = f"{len(tableaux)} tableau(x) lus"

        elif principal.startswith("F"):
            ligne["remarques"] = "page de connexion : utiliser se_connecter() avec votre propre compte, puis collecter"

        else:  # A, C, D, H : on cherche les blocs répétés et on suit la pagination
            r = ws.obtenir(session, url)
            blocs = ws.detecter_blocs_repetes(ws.soupe(r)) if r is not None else None
            if not blocs:
                ligne["remarques"] = "aucun bloc répété : écrire un extracteur sur mesure (cas A)"
            else:
                sel = blocs["selecteur"]
                extraire = lambda sp, u: ws.extraire_blocs_generiques(sp, u, sel)
                lignes = ws.parcourir_pages(session, url, extraire, max_pages=max_pages)
                fichiers.append(ws.sauvegarder_csv(lignes, f"{base}.csv"))
                ligne["nb_lignes"] = len(lignes)
                ligne["remarques"] = f"blocs « {sel} »"
    except ws.AccesBloque as e:
        ligne["remarques"] = f"accès bloqué pendant la collecte : {e}"
    except Exception as e:  # on note l'erreur et on passe au site suivant
        ligne["remarques"] = f"ERREUR {type(e).__name__} : {e}"

    ligne["fichiers"] = ";".join(str(f) for f in fichiers)
    return ligne


def ajouter_au_journal(ligne, dossier):
    journal = dossier / "journal_tests.csv"
    nouveau = not journal.exists()
    with journal.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(ligne))
        if nouveau:
            w.writeheader()
        w.writerow(ligne)
    return journal


def main():
    ap = argparse.ArgumentParser(description="Diagnostic et collecte automatique")
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--sortie", default="resultats")
    ap.add_argument("--pages", type=int, default=3, help="pages maximum à suivre (défaut : 3)")
    ap.add_argument("--navigateur", action="store_true", help="autoriser Playwright pour le cas E")
    args = ap.parse_args()

    dossier = Path(args.sortie)
    dossier.mkdir(parents=True, exist_ok=True)
    session = ws.creer_session()
    for url in args.urls:
        ligne = traiter(url, session, dossier, args.pages, args.navigateur)
        journal = ajouter_au_journal(ligne, dossier)
        print(f"  → {ligne['nb_lignes']} lignes | {ligne['remarques']}\n")
    print(f"Journal : {journal}")


if __name__ == "__main__":
    main()
