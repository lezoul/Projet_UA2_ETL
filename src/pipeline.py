"""
pipeline.py
Lance tout le projet de bout en bout, sans ouvrir le notebook :
    1. diagnostic des 18 sites (parties 1 et 2) ;
    2. collecte des véhicules (partie 3) ;
    3. journal de tests mis à jour (annexe C) et fichier de tous les véhicules.

Utilisation, depuis la racine du projet (environnement .venv activé) :
    python src/pipeline.py                         # tout : diagnostic + collecte
    python src/pipeline.py --etapes collecte       # seulement la collecte
    python src/pipeline.py --sites hull_nissan bank_street_kia   # seulement certains sites
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

# Rend les modules de src/ importables, d'où que le script soit lancé
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd

import config
import diagnostic
import extraction
import projet_scraping as ws


def choisir_sites(ids):
    """Tous les sites, ou seulement ceux demandés (vérifie que les identifiants existent)."""
    if not ids:
        return config.SITES
    inconnus = set(ids) - {s["id"] for s in config.SITES}
    if inconnus:
        sys.exit(f"Identifiants inconnus : {', '.join(sorted(inconnus))}")
    return [s for s in config.SITES if s["id"] in ids]


def main(argv=None):
    ap = argparse.ArgumentParser(description="Diagnostic et collecte des inventaires de véhicules d'occasion")
    ap.add_argument("--etapes", nargs="+", choices=["diagnostic", "collecte"], default=["diagnostic", "collecte"])
    ap.add_argument("--sites", nargs="*", default=[], help="identifiants des sites (par défaut : tous)")
    ap.add_argument("--silencieux", action="store_true", help="n'affiche que le résumé")
    args = ap.parse_args(argv)

    sites = choisir_sites(args.sites)
    afficher = not args.silencieux
    session = ws.creer_session(config.USER_AGENT)
    print(f"{len(diagnostic.sites_sans_doublons(sites))} URL uniques ; étapes : {', '.join(args.etapes)}")

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
        if len(vehicules):
            jour = datetime.now().strftime("%Y-%m-%d")
            chemin = config.DOSSIER_RESULTATS / f"vehicules_brut_{jour}.csv"
            vehicules.to_csv(chemin, index=False, encoding="utf-8-sig")
            print(f"\n{len(vehicules)} véhicules au total → {chemin.relative_to(config.RACINE)}")

    # --- 3. Journal
    chemin_journal = diagnostic.enregistrer_journal(journal)
    print(f"Journal de tests → {chemin_journal.relative_to(config.RACINE)}")
    resume = journal.reindex(columns=["nom", "statut", "cas_confirme", "nb_lignes"]).copy()
    resume["cas_confirme"] = resume["cas_confirme"].astype(str).str.split(" (", regex=False).str[0]
    print(resume.to_string(index=False))


if __name__ == "__main__":
    main()
