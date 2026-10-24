"""
enrichissement.py
Décodage des NIV par l'API officielle vPIC de la NHTSA (département des Transports des États-Unis).

Pourquoi : le carburant n'est publié que pour 16 % des véhicules et la catégorie manque chez Magnetis.
Le NIV (17 caractères, norme ISO 3779) code le constructeur, le modèle, la carrosserie et le moteur ;
vPIC traduit ces codes à partir des déclarations des constructeurs. C'est une API publique, gratuite,
sans inscription, faite pour cet usage : la voie « API officielle » de la partie 1 du cours.
Le NIV ne code pas la couleur : elle ne peut pas être complétée ainsi.

Fonctionnement :
  - on relit les NIV de tous les fichiers bruts (resultats/brut/) ;
  - on ne décode que les NIV valides absents du cache resultats/niv_decodes_vpic.csv :
    chaque NIV n'est envoyé qu'une seule fois (la première fois environ 950 NIV, soit 19 lots ;
    ensuite seulement les nouveaux véhicules de la nuit, en général un lot) ;
  - lots de 50 NIV (maximum de la méthode), 2 s entre deux lots, robots.txt vérifié, User-Agent du projet ;
  - le cache est enregistré après chaque lot : une interruption ne fait rien perdre.
Le prétraitement lit ensuite ce cache pour compléter les cases vides, sans jamais écraser une valeur
publiée par le concessionnaire.

Fonctions :
    niv_a_decoder()            -> NIV valides des fichiers bruts, absents du cache
    decoder_lot(nivs, session) -> une requête vPIC pour au plus 50 NIV
    enrichir(session)          -> tout : lots successifs, cache mis à jour
"""

import time
from datetime import datetime

import numpy as np
import pandas as pd

import config
import pretraitement
import projet_scraping as ws

COLONNES_CACHE = ["niv", *config.CHAMPS_VPIC.values(), "date_decodage"]


def lire_cache():
    """Le cache des NIV déjà décodés (vide s'il n'existe pas encore)."""
    if config.FICHIER_NIV_DECODES.exists():
        return pd.read_csv(config.FICHIER_NIV_DECODES, encoding="utf-8-sig", dtype=str)
    return pd.DataFrame(columns=COLONNES_CACHE)


def niv_a_decoder():
    """NIV valides (17 caractères, sans I, O ni Q) présents dans les fichiers bruts et pas encore décodés."""
    brut = pretraitement.charger_collectes()
    nivs = brut["niv"].map(pretraitement.nettoyer_niv).dropna()
    nivs = set(nivs[nivs.str.fullmatch(config.MOTIF_NIV)])
    deja = set(lire_cache()["niv"].dropna())
    return sorted(nivs - deja)


def decoder_lot(nivs, session):
    """
    Une requête POST à DecodeVINValuesBatch pour au plus 50 NIV (« NIV1;NIV2;... »).
    Retourne une liste de dictionnaires au format du cache.
    """
    reponse = session.post(config.URL_VPIC, data={"format": "json", "data": ";".join(nivs)},
                           timeout=ws.TIMEOUT)
    if reponse.status_code in (403, 429):
        raise ws.AccesBloque(f"vPIC a répondu {reponse.status_code} : arrêt, nouvel essai la nuit suivante")
    reponse.raise_for_status()
    maintenant = datetime.now().isoformat(timespec="seconds")
    lignes = []
    for resultat in reponse.json().get("Results", []):
        ligne = {"niv": (resultat.get("VIN") or "").strip().upper(), "date_decodage": maintenant}
        for champ, colonne in config.CHAMPS_VPIC.items():
            valeur = (resultat.get(champ) or "").strip()
            ligne[colonne] = valeur or np.nan
        lignes.append(ligne)
    return lignes


def enrichir(session=None, afficher=True):
    """
    Décode les nouveaux NIV par lots et met à jour le cache. Retourne un petit rapport.
    S'arrête sans erreur si robots.txt interdit l'API ou si vPIC refuse : le prétraitement
    fonctionne alors avec le cache existant.
    """
    session = session or ws.creer_session(config.USER_AGENT)
    rapport = {"niv_a_decoder": 0, "niv_decodes": 0, "lots": 0, "remarques": []}

    autorise, raison, _ = ws.robots_autorise(config.URL_VPIC, session.headers["User-Agent"], session)
    if not autorise:
        rapport["remarques"].append(f"robots.txt interdit l'API vPIC ({raison}) : aucun décodage.")
        print(rapport["remarques"][-1])
        return rapport

    a_decoder = niv_a_decoder()
    rapport["niv_a_decoder"] = len(a_decoder)
    lots = [a_decoder[i:i + config.TAILLE_LOT_VPIC] for i in range(0, len(a_decoder), config.TAILLE_LOT_VPIC)]
    if len(lots) > config.MAX_LOTS_VPIC:
        rapport["remarques"].append(f"{len(lots)} lots nécessaires : limité à {config.MAX_LOTS_VPIC} "
                                    "cette fois, la suite la nuit suivante.")
        lots = lots[:config.MAX_LOTS_VPIC]
    if afficher:
        print(f"{len(a_decoder)} NIV à décoder en {len(lots)} lot(s) de {config.TAILLE_LOT_VPIC} au plus")

    cache = lire_cache()
    for numero, lot in enumerate(lots, start=1):
        if numero > 1:
            time.sleep(config.DELAI_VPIC)
        try:
            lignes = decoder_lot(lot, session)
        except ws.AccesBloque as e:
            rapport["remarques"].append(str(e))
            break
        except Exception as e:      # réseau, réponse illisible : on garde ce qui est déjà décodé
            rapport["remarques"].append(f"Échec du lot {numero} : {type(e).__name__} : {e}")
            break
        cache = pd.concat([cache, pd.DataFrame(lignes)], ignore_index=True)
        cache = cache.drop_duplicates(subset="niv", keep="last")
        config.FICHIER_NIV_DECODES.parent.mkdir(parents=True, exist_ok=True)
        cache.reindex(columns=COLONNES_CACHE).to_csv(config.FICHIER_NIV_DECODES, index=False, encoding="utf-8-sig")
        rapport["lots"] += 1
        rapport["niv_decodes"] += len(lignes)
        if afficher:
            print(f"  lot {numero}/{len(lots)} : {len(lignes)} NIV décodés")

    print(f"Enrichissement : {rapport['niv_decodes']} NIV décodés en {rapport['lots']} requête(s) ; "
          f"cache : {len(cache)} NIV -> {config.FICHIER_NIV_DECODES.relative_to(config.RACINE)}"
          + (f" ; {' '.join(rapport['remarques'])}" if rapport["remarques"] else ""))
    return rapport


if __name__ == "__main__":
    enrichir()
