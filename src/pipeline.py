"""
pipeline.py
Lance tout le projet de bout en bout, sans ouvrir le notebook :
    1. diagnostic des 18 sites (parties 1 et 2) ;
    2. collecte des véhicules (partie 3) ;
    3. journal de tests mis à jour (annexe C), fichier de tous les véhicules du jour,
       et une ligne par site ajoutée à l'historique des collectes ;
    4. enrichissement : décodage des nouveaux NIV par l'API officielle vPIC de la NHTSA (cache) ;
    5. prétraitement (partie 4) : tous les fichiers bruts -> observations quotidiennes,
       véhicules consolidés, concessionnaires et rapport de qualité.

Utilisation, depuis la racine du projet (environnement .venv activé) :
    python src/pipeline.py                                    # tout : diagnostic, collecte, enrichissement, prétraitement
    python src/pipeline.py --etapes collecte                  # seulement la collecte
    python src/pipeline.py --etapes pretraitement             # seulement le prétraitement (aucune requête)
    python src/pipeline.py --etapes enrichissement pretraitement   # décoder les NIV puis recalculer les tables
    python src/pipeline.py --sites hull_nissan bank_street_kia   # seulement certains sites
    python src/pipeline.py --etapes collecte enrichissement pretraitement --silencieux --log  # chaque nuit

Collecte quotidienne : scripts/collecte_quotidienne.bat lance la dernière commande ci-dessus,
et scripts/installer_tache.ps1 l'inscrit dans le Planificateur de tâches de Windows.
"""

import argparse
import logging
import sys
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path

# Rend les modules de src/ importables, d'où que le script soit lancé
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

import config
import diagnostic
import enrichissement
import extraction
import pretraitement
import projet_scraping as ws


def choisir_sites(ids):
    """Tous les sites, ou seulement ceux demandés (vérifie que les identifiants existent)."""
    if not ids:
        return config.SITES
    inconnus = set(ids) - {s["id"] for s in config.SITES}
    if inconnus:
        sys.exit(f"Identifiants inconnus : {', '.join(sorted(inconnus))}")
    return [s for s in config.SITES if s["id"] in ids]


def ajouter_historique(rapports, sites):
    """
    Ajoute une ligne par site à resultats/historique_collectes.csv (jamais écrasé).
    Contrairement au journal, qui décrit le dernier état, l'historique garde la trace de
    chaque collecte : c'est la preuve de la régularité et de la politesse de la collecte quotidienne.
    """
    noms = {s["id"]: s["nom"] for s in sites}
    lignes = [{
        "date_collecte": r.get("date_collecte", ""),
        "id": r["id"],
        "nom": noms.get(r["id"], ""),
        "nb_vehicules": r.get("nb_lignes", 0),
        "pages_collectees": r.get("pages_collectees", 0),
        "fichier_csv": r.get("fichier_csv", ""),
        "remarques": " ".join(r.get("remarques", [])),
    } for r in rapports]
    chemin = config.FICHIER_HISTORIQUE
    chemin.parent.mkdir(parents=True, exist_ok=True)
    nouveau = not chemin.exists()
    pd.DataFrame(lignes).to_csv(chemin, mode="a", header=nouveau, index=False, encoding="utf-8-sig")
    return chemin


def executer(args):
    """Le déroulement du pipeline (appelé par main, avec ou sans fichier de log)."""
    debut = datetime.now()
    print(f"{debut:%Y-%m-%d %H:%M:%S} | étapes : {', '.join(args.etapes)}")
    if "diagnostic" in args.etapes or "collecte" in args.etapes:
        executer_collecte(args, debut)

    # --- 4. Enrichissement (API officielle vPIC : seulement les NIV jamais décodés)
    if "enrichissement" in args.etapes:
        print("\n--- Enrichissement (API vPIC de la NHTSA)")
        enrichissement.enrichir(afficher=not args.silencieux)

    # --- 5. Prétraitement (aucune requête : lit seulement resultats/brut/ et le cache des NIV)
    if "pretraitement" in args.etapes:
        print("\n--- Prétraitement")
        pretraitement.pretraiter()
    print(f"Terminé en {(datetime.now() - debut).seconds // 60} min {(datetime.now() - debut).seconds % 60} s")


def executer_collecte(args, debut):
    """Étapes 1 à 3 : diagnostic et/ou collecte, puis journal de tests."""
    sites = choisir_sites(args.sites)
    afficher = not args.silencieux
    session = ws.creer_session(config.USER_AGENT)
    print(f"{len(diagnostic.sites_sans_doublons(sites))} URL uniques")

    # --- 1. Diagnostic
    if "diagnostic" in args.etapes:
        lignes = diagnostic.diagnostiquer_tous(sites, session, afficher=afficher)
        journal = diagnostic.construire_journal(lignes)
    elif config.FICHIER_JOURNAL.exists():
        journal = pd.read_csv(config.FICHIER_JOURNAL, encoding="utf-8-sig", dtype=str)
    else:
        sys.exit("Aucun journal existant : lancer d'abord l'étape diagnostic.")

    # --- 2. Collecte
    if "collecte" in args.etapes:
        vehicules, rapports = extraction.collecter_tous(sites, session, afficher=afficher)
        journal = extraction.ajouter_collecte_au_journal(journal, rapports)
        chemin_historique = ajouter_historique(rapports, sites)
        print(f"Historique → {chemin_historique.relative_to(config.RACINE)}")
        if len(vehicules):
            jour = debut.strftime("%Y-%m-%d")
            chemin = config.DOSSIER_RESULTATS / f"vehicules_brut_{jour}.csv"
            vehicules.to_csv(chemin, index=False, encoding="utf-8-sig")
            print(f"{len(vehicules)} véhicules au total → {chemin.relative_to(config.RACINE)}")

    # --- 3. Journal
    chemin_journal = diagnostic.enregistrer_journal(journal)
    print(f"Journal de tests → {chemin_journal.relative_to(config.RACINE)}")
    resume = journal.reindex(columns=["nom", "statut", "cas_confirme", "nb_lignes"]).copy()
    resume["cas_confirme"] = resume["cas_confirme"].astype(str).str.split(" (", regex=False).str[0]
    print(resume.to_string(index=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description="Diagnostic et collecte des inventaires de véhicules d'occasion")
    ap.add_argument("--etapes", nargs="+", choices=["diagnostic", "collecte", "enrichissement", "pretraitement"],
                    default=["diagnostic", "collecte", "enrichissement", "pretraitement"])
    ap.add_argument("--sites", nargs="*", default=[], help="identifiants des sites (par défaut : tous)")
    ap.add_argument("--silencieux", action="store_true", help="n'affiche que le résumé")
    ap.add_argument("--log", action="store_true",
                    help="écrit tout l'affichage dans logs/pipeline_AAAA-MM-JJ_HHhMMmSS.log (mode automatique)")
    args = ap.parse_args(argv)

    if not args.log:
        executer(args)
        return

    # Mode automatique : personne ne regarde l'écran, donc tout va dans un fichier de log daté,
    # y compris les messages de projet_scraping (module logging) et les erreurs éventuelles.
    config.DOSSIER_LOGS.mkdir(parents=True, exist_ok=True)
    chemin_log = config.DOSSIER_LOGS / f"pipeline_{datetime.now():%Y-%m-%d_%Hh%Mm%S}.log"
    with open(chemin_log, "w", encoding="utf-8") as f, redirect_stdout(f), redirect_stderr(f):
        gestionnaire = logging.StreamHandler(f)
        gestionnaire.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s", "%H:%M:%S"))
        racine_log = logging.getLogger()
        anciens = racine_log.handlers[:]
        racine_log.handlers = [gestionnaire]
        try:
            executer(args)
        except SystemExit:
            raise
        except Exception:
            logging.exception("ERREUR pendant le pipeline")
            raise
        finally:
            racine_log.handlers = anciens


if __name__ == "__main__":
    main()
