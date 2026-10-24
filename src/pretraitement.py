"""
pretraitement.py
Partie 4 du projet : des CSV bruts (un par site et par jour) aux tables prêtes pour l'analyse et Power BI.

Entrée  : resultats/brut/{site_id}_{AAAA-MM-JJ}.csv   (produits chaque nuit par la collecte)
Sorties : resultats/observations_quotidiennes.csv      1 ligne = 1 véhicule vu sur 1 site, 1 jour
          resultats/vehicules_occasion_consolide.csv   1 ligne = 1 véhicule (NIV), tout son historique résumé
          resultats/concessionnaires.csv               1 ligne = 1 site (table de dimension pour Power BI)
          resultats/rapport_qualite.csv                les contrôles de qualité et leurs résultats

Principes :
  - la source n'est jamais perdue : chaque ligne garde son fichier, son site, sa plateforme, son groupe
    et sa date ; les valeurs d'origine sont gardées dans des colonnes *_brut ;
  - on ne supprime pas une ligne douteuse, on la signale (colonnes km_suspect, niv_invalide, ...) :
    c'est l'analyse qui décide de l'exclure ou non ;
  - toutes les règles (harmonisation, seuils, collectes incomplètes) sont dans config.py ;
  - les cases vides (carburant, catégorie, traction) sont complétées par le décodage officiel du NIV
    (API vPIC de la NHTSA, cache écrit par enrichissement.py), jamais en écrasant une valeur du site ;
    l'origine de chaque valeur est gardée dans <colonne>_source.

Fonctions (dans l'ordre du traitement) :
    charger_collectes()          -> toutes les lignes brutes + colonnes de source
    nettoyer_types(df)           -> NIV propre, nombres, dates, prix 0 -> manquant
    harmoniser(df)               -> une seule écriture par valeur (état, transmission, couleur, ...)
    completer_avec_vpic(df)      -> cases vides complétées par le NIV décodé (appelée par harmoniser)
    ajouter_prix_comparable(df)  -> prix sans les frais Dilawri, pour comparer les sites entre eux
    controler_qualite(df)        -> indicateurs de qualité + rapport
    construire_observations(df)  -> table des observations (1 véhicule, 1 site, 1 jour)
    construire_vehicules(obs)    -> table des véhicules (1 NIV)
    pretraiter()                 -> tout, de bout en bout, et écrit les 4 fichiers
"""

import re
from datetime import datetime

import numpy as np
import pandas as pd

import config

# Colonnes de source ajoutées à chaque ligne
COLONNES_SOURCE = ["fichier_source", "groupe", "jour", "collecte_complete"]

# Colonnes harmonisées : (colonne, règles de config) ; la valeur d'origine est gardée dans <colonne>_brut
HARMONISATIONS = [
    ("transmission", config.REGLES_TRANSMISSION),
    ("traction", config.REGLES_TRACTION),
    ("carburant", config.REGLES_CARBURANT),
    ("categorie", config.REGLES_CATEGORIE),
]


# ---------------------------------------------------------------------------
# 1. Chargement : tous les fichiers bruts, sans perdre la source
# ---------------------------------------------------------------------------

def _est_complete(plateforme, jour):
    """False si la collecte (plateforme, jour) est déclarée incomplète dans config.py."""
    return not any(c["plateforme"] == plateforme and c["jour"] == jour for c in config.COLLECTES_INCOMPLETES)


def charger_collectes(dossier=None):
    """
    Lit tous les CSV de resultats/brut/ et les empile.
    Ajoute à chaque ligne : fichier_source, groupe, jour (AAAA-MM-JJ) et collecte_complete.
    Tout est lu en texte (dtype=str) : les types sont fixés ensuite, volontairement, dans nettoyer_types().
    """
    dossier = dossier or config.DOSSIER_BRUT
    fichiers = sorted(dossier.glob("*.csv"))
    if not fichiers:
        raise FileNotFoundError(f"Aucun CSV dans {dossier} : lancer d'abord la collecte.")

    morceaux = []
    for f in fichiers:
        morceau = pd.read_csv(f, encoding="utf-8-sig", dtype=str)
        if morceau.empty:
            continue
        morceau["fichier_source"] = f.name
        morceaux.append(morceau)
    df = pd.concat(morceaux, ignore_index=True)     # ignore_index : un numéro de ligne unique

    df["groupe"] = df["site_id"].map(config.GROUPES).fillna(config.GROUPE_PAR_DEFAUT)
    df["jour"] = df["date_collecte"].str[:10]        # '2026-10-22T19:53:19' -> '2026-10-22'
    df["collecte_complete"] = [_est_complete(p, j) for p, j in zip(df["plateforme"], df["jour"])]
    print(f"{len(fichiers)} fichiers lus, {len(df)} lignes, "
          f"{df['jour'].nunique()} jours ({df['jour'].min()} à {df['jour'].max()}), "
          f"{df['site_id'].nunique()} sites")
    return df


# ---------------------------------------------------------------------------
# 2. Types : texte, nombres, dates
# ---------------------------------------------------------------------------

def nettoyer_niv(valeur):
    """'VIN: 3kpf24ad5me 123456' -> '3KPF24AD5ME123456' (même règle que l'extracteur, pour les anciens fichiers)."""
    if pd.isna(valeur):
        return np.nan
    t = re.sub(r"^\s*(VIN|NIV)\s*[:#]?\s*", "", str(valeur), flags=re.I)
    t = re.sub(r"\s+", "", t).upper()
    return t or np.nan


def nettoyer_types(df):
    """
    - NIV : retire le préfixe « VIN: » (fichiers Dilawri d'avant le 2026-10-23) et met en majuscules ;
    - nombres : année et km en entiers, montants en décimaux ;
    - prix à 0 : ce n'est pas un vrai prix (« appelez-nous ») -> manquant, avec prix_non_affiche = True ;
    - date_collecte en date et heure.
    """
    df = df.copy()
    df["niv_brut"] = df["niv"]
    df["niv"] = df["niv"].map(nettoyer_niv)

    df["annee"] = pd.to_numeric(df["annee"], errors="coerce").astype("Int64")
    df["km"] = pd.to_numeric(df["km"], errors="coerce").astype("Int64")
    for c in ["prix_affiche", "rabais", "frais", "prix_final"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["prix_non_affiche"] = df["prix_final"].isna() | (df["prix_final"] <= 0)
    for c in ["prix_affiche", "prix_final"]:
        df.loc[df[c] <= 0, c] = np.nan

    df["date_collecte"] = pd.to_datetime(df["date_collecte"], errors="coerce")

    # Texte : espaces superflus retirés, chaînes vides -> manquant
    for c in ["concessionnaire", "marque", "modele", "version", "etat", "transmission", "traction",
              "carburant", "moteur", "couleur_ext", "categorie", "no_stock", "id_annonce"]:
        df[c] = df[c].astype(object).where(df[c].notna(), np.nan)
        df[c] = df[c].map(lambda x: re.sub(r"\s+", " ", str(x)).strip() or np.nan if pd.notna(x) else np.nan)
    return df


# ---------------------------------------------------------------------------
# 3. Harmonisation : une seule écriture par valeur
# ---------------------------------------------------------------------------

def appliquer_regles(valeur, regles, si_vide=np.nan):
    """Première règle (motif, résultat) qui correspond au texte en minuscules ; « Non reconnu » sinon."""
    if pd.isna(valeur):
        return si_vide
    texte = str(valeur).lower()
    for motif, resultat in regles:
        if re.search(motif, texte):
            return resultat
    return "Non reconnu"


def harmoniser_marque(valeur):
    """'ACURA' -> 'Acura' ; marques connues d'après config.MARQUES, sinon première lettre en majuscule."""
    if pd.isna(valeur):
        return np.nan
    v = str(valeur).strip()
    return config.MARQUES.get(v.upper(), v if not v.isupper() else v.title())


def deduire_categorie(df):
    """
    Magnetis ne donne pas la catégorie. Si le même modèle (marque + modèle) a une catégorie
    sur d'autres sites, on reprend la plus fréquente, et on le signale (categorie_deduite = True).
    """
    connues = df.dropna(subset=["categorie"])
    connues = connues[connues["categorie"] != "Non reconnu"]
    la_plus_frequente = connues.groupby(["marque", "modele"])["categorie"].agg(lambda s: s.mode().iloc[0])
    manquante = df["categorie"].isna()
    cles = list(zip(df.loc[manquante, "marque"], df.loc[manquante, "modele"]))
    deduites = pd.Series([la_plus_frequente.get(k, np.nan) for k in cles], index=df.index[manquante], dtype=object)
    df["categorie_deduite"] = False
    df.loc[deduites.dropna().index, "categorie_deduite"] = True
    df.loc[manquante, "categorie"] = deduites
    return df


def completer_avec_vpic(df):
    """
    Complète carburant, catégorie et traction quand le site ne les publie pas, à partir du cache
    resultats/niv_decodes_vpic.csv (API officielle vPIC, voir enrichissement.py).
    Priorité : valeur du site > valeur vPIC > (pour la catégorie) déduction par le modèle.
    Colonnes <colonne>_source : « site », « vPIC (NHTSA) », « déduite du modèle » ou vide.
    Sans cache (enrichissement jamais lancé), les colonnes source valent « site » ou vide, rien d'autre ne change.
    """
    for colonne in ["carburant", "categorie", "traction"]:
        df[f"{colonne}_source"] = np.where(df[colonne].notna() & (df[colonne] != "Non reconnu"), "site", None)

    if not config.FICHIER_NIV_DECODES.exists():
        print("Aucun NIV décodé (lancer l'étape enrichissement) : carburant, catégorie et traction "
              "restent tels que publiés par les sites.")
        return df

    vpic = pd.read_csv(config.FICHIER_NIV_DECODES, encoding="utf-8-sig", dtype=str).set_index("niv")
    vpic = vpic[~vpic.index.duplicated(keep="last")]
    texte_carburant = (vpic["vpic_electrification"].fillna("") + " | " + vpic["vpic_carburant"].fillna(""))
    valeurs = pd.DataFrame({
        "carburant": texte_carburant.map(lambda t: appliquer_regles(t, config.REGLES_CARBURANT_VPIC)
                                         if t.strip(" |") else np.nan),
        "categorie": vpic["vpic_carrosserie"].map(lambda v: appliquer_regles(v, config.REGLES_CATEGORIE)),
        "traction": vpic["vpic_traction"].map(lambda v: appliquer_regles(v, config.REGLES_TRACTION)),
    }).replace("Non reconnu", np.nan)

    for colonne in ["carburant", "categorie", "traction"]:
        vide = df[colonne].isna() | (df[colonne] == "Non reconnu")
        complement = df.loc[vide, "niv"].map(valeurs[colonne])
        trouve = complement.dropna().index
        df.loc[trouve, colonne] = complement.loc[trouve]
        df.loc[trouve, f"{colonne}_source"] = "vPIC (NHTSA)"
    return df


def harmoniser(df):
    """
    Remplace chaque variante par une valeur unique (règles dans config.py) et garde l'original dans <col>_brut.
    Exemples : 'Auto.', 'Automatic', 'CVT', 'Boîte automatique' -> 'Automatique' ;
               'SUV', 'VUS' -> 'VUS' ; 'IN-STOCK' -> état 'Occasion' + disponibilité 'En stock'.
    """
    df = df.copy()
    df["etat_brut"] = df["etat"]
    df["disponibilite"] = df["etat"].map(lambda v: appliquer_regles(v, config.REGLES_DISPONIBILITE,
                                                                   si_vide="Non précisé"))
    df.loc[df["disponibilite"] == "Non reconnu", "disponibilite"] = "Non précisé"   # Magnetis, D2C : non publié
    df["etat"] = df["etat"].map(lambda v: appliquer_regles(v, config.REGLES_ETAT, si_vide="Occasion"))

    for colonne, regles in HARMONISATIONS:
        df[f"{colonne}_brut"] = df[colonne]
        df[colonne] = df[colonne].map(lambda v, r=regles: appliquer_regles(v, r))

    df["marque_brut"] = df["marque"]
    df["marque"] = df["marque"].map(harmoniser_marque)
    df["famille_couleur"] = df["couleur_ext"].map(lambda v: appliquer_regles(v, config.REGLES_COULEUR))
    df.loc[df["famille_couleur"] == "Non reconnu", "famille_couleur"] = "Autre"
    df["famille_couleur"] = df["famille_couleur"].fillna("Non précisé")      # couleur non publiée par le site

    df = completer_avec_vpic(df)        # d'abord la source officielle
    df = deduire_categorie(df)          # puis, pour ce qui reste vide, le même modèle sur un autre site
    df.loc[df["categorie_deduite"], "categorie_source"] = "déduite du modèle"
    return df


# ---------------------------------------------------------------------------
# 4. Prix comparable entre sites
# ---------------------------------------------------------------------------

def ajouter_prix_comparable(df):
    """
    Certains sites Dilawri incluent des frais dans leur prix final (prix + frais - rabais = prix final ;
    au 2026-10-22 : 821 $ chez Bank Street Hyundai, 22 $ chez Barrhaven CJDR), les sites Magnetis et D2C
    affichent un prix sans ces frais. Pour comparer, prix_comparable = prix final moins les frais
    (quand il y en a). Le prix final affiché reste disponible tel quel.
    """
    df = df.copy()
    df["prix_comparable"] = df["prix_final"] - df["frais"].fillna(0)
    return df


# ---------------------------------------------------------------------------
# 5. Contrôles de qualité
# ---------------------------------------------------------------------------

def controler_qualite(df):
    """
    Ajoute des colonnes-indicateurs (on signale, on ne supprime pas) et retourne (df, rapport) :
      niv_invalide  : NIV absent ou hors norme (17 caractères, sans I, O ni Q) ;
      km_suspect    : moins de 100 km sur un véhicule de plus de 2 ans ;
      prix_non_affiche (déjà calculé) ; valeurs « Non reconnu » après harmonisation.
    """
    df = df.copy()
    df["niv_invalide"] = ~df["niv"].fillna("").str.fullmatch(config.MOTIF_NIV)
    age = df["date_collecte"].dt.year - df["annee"]
    df["km_suspect"] = ((df["km"] < config.KM_MINIMUM_PLAUSIBLE) &
                        (age > config.AGE_MINIMUM_KM_SUSPECT)).fillna(False).astype(bool)

    n = len(df)
    lignes = []

    def ajouter(controle, masque, detail=""):
        k = int(masque.sum())
        lignes.append({"controle": controle, "nb_lignes": k, "pourcentage": round(100 * k / n, 1) if n else 0,
                       "detail": detail})

    ajouter("Lignes au total", pd.Series(True, index=df.index), f"{df['fichier_source'].nunique()} fichiers")
    ajouter("NIV avec préfixe « VIN: » corrigé", df["niv_brut"].fillna("").str.contains(r"^\s*VIN", case=False))
    ajouter("NIV invalide (gardé, signalé)", df["niv_invalide"],
            " | ".join(sorted(df.loc[df["niv_invalide"], "niv"].dropna().unique())[:10]))
    ajouter("Prix non affiché (0 ou vide)", df["prix_non_affiche"],
            ", ".join(f"{k}: {v}" for k, v in df.loc[df["prix_non_affiche"], "plateforme"].value_counts().items()))
    ajouter("Kilométrage suspect (< 100 km, plus de 2 ans)", df["km_suspect"],
            " | ".join(f"{r.annee} {r.marque} {r.modele} ({r.km} km)" for r in df[df["km_suspect"]].head(10).itertuples()))
    ajouter("Kilométrage manquant", df["km"].isna())
    ajouter("Ligne d'une collecte incomplète (gardée, exclue des statuts)", ~df["collecte_complete"],
            " ; ".join(f"{c['plateforme']} {c['jour']}" for c in config.COLLECTES_INCOMPLETES))
    ajouter("Catégorie déduite du même modèle sur un autre site", df["categorie_deduite"])
    for colonne in ["carburant", "categorie", "traction"]:
        ajouter(f"{colonne} complété par le NIV (API vPIC)", df[f"{colonne}_source"] == "vPIC (NHTSA)")
    for colonne in ["transmission", "traction", "carburant", "categorie"]:
        ajouter(f"{colonne} manquant", df[colonne].isna())
        non_reconnu = df[colonne] == "Non reconnu"
        ajouter(f"{colonne} non reconnu (règle à ajouter dans config.py)", non_reconnu,
                " | ".join(sorted(df.loc[non_reconnu, f"{colonne}_brut"].astype(str).unique())[:10]))
    ajouter("Couleur classée « Autre »", df["famille_couleur"] == "Autre",
            " | ".join(sorted(df.loc[df["famille_couleur"] == "Autre", "couleur_ext"].dropna().unique())[:10]))
    return df, pd.DataFrame(lignes)


# ---------------------------------------------------------------------------
# 6. Table des observations : 1 véhicule, 1 site, 1 jour
# ---------------------------------------------------------------------------

COLONNES_OBSERVATIONS = [
    # Clés et source
    "cle_vehicule", "niv", "site_id", "jour", "date_collecte", "fichier_source", "collecte_complete",
    "concessionnaire", "groupe", "ville", "province", "plateforme",
    # Annonce
    "url_fiche", "id_annonce", "no_stock", "etat", "disponibilite",
    # Véhicule
    "annee", "marque", "modele", "version", "categorie", "categorie_source", "categorie_deduite",
    "transmission", "traction", "traction_source", "carburant", "carburant_source",
    "moteur", "couleur_ext", "famille_couleur", "km",
    # Prix
    "prix_affiche", "rabais", "frais", "prix_final", "prix_comparable", "prix_non_affiche",
    # Qualité
    "niv_invalide", "km_suspect",
    # Valeurs d'origine
    "niv_brut", "marque_brut", "etat_brut", "transmission_brut", "traction_brut", "carburant_brut", "categorie_brut",
]


def construire_observations(df):
    """
    Une ligne par (véhicule, site, jour). Si un site a été collecté deux fois le même jour
    (lancement manuel + tâche de nuit), on garde la collecte la plus récente.
    cle_vehicule = NIV ; à défaut (NIV absent), site + numéro d'annonce, pour ne rien perdre.
    """
    df = df.copy()
    sans_niv = df["niv"].isna()
    df["cle_vehicule"] = df["niv"].astype(object)
    df.loc[sans_niv, "cle_vehicule"] = "SANS-NIV-" + df.loc[sans_niv, "site_id"] + "-" + \
        df.loc[sans_niv, "id_annonce"].fillna("inconnu")

    avant = len(df)
    df = (df.sort_values("date_collecte")
            .drop_duplicates(subset=["cle_vehicule", "site_id", "jour"], keep="last")
            .sort_values(["jour", "site_id", "cle_vehicule"])
            .reset_index(drop=True))
    if avant != len(df):
        print(f"{avant - len(df)} doublons retirés (même véhicule, même site, même jour)")
    return df.reindex(columns=COLONNES_OBSERVATIONS)


# ---------------------------------------------------------------------------
# 7. Table des véhicules : 1 NIV, tout son historique résumé
# ---------------------------------------------------------------------------

def _joindre(valeurs):
    return " | ".join(sorted(set(valeurs.dropna().astype(str))))


def construire_vehicules(obs):
    """
    Résume chaque véhicule (cle_vehicule) :
      - description : valeurs de la dernière observation (la plus à jour) ;
      - présence : sites_vus, nb_sites, groupes, première et dernière date vue, nb de jours observés ;
      - prix : prix_initial, prix_actuel, variation_prix, nb_changements_prix (sur prix_comparable,
        le plus bas des sites le même jour, si le véhicule est sur plusieurs sites) ;
      - statut : « En ligne » s'il était présent à la dernière collecte COMPLÈTE d'au moins un de ses sites,
        sinon « Retiré » (vendu ou retiré de l'annonce : on ne peut pas savoir lequel) ;
      - nouveau : apparu après la première collecte complète de son site (sinon il était déjà là au départ).
    """
    # Repères par site, calculés seulement sur les collectes complètes
    completes = obs[obs["collecte_complete"]]
    derniere_collecte = completes.groupby("site_id")["jour"].max()
    premiere_collecte = completes.groupby("site_id")["jour"].min()

    par_site = obs.groupby(["cle_vehicule", "site_id"])["jour"].agg(premiere_vue_site="min", derniere_vue_site="max")
    par_site = par_site.reset_index()
    par_site["en_ligne_site"] = par_site["derniere_vue_site"] >= par_site["site_id"].map(derniere_collecte).fillna("9999")
    par_site["nouveau_site"] = par_site["premiere_vue_site"] > par_site["site_id"].map(premiere_collecte).fillna("9999")
    statut = par_site.groupby("cle_vehicule").agg(en_ligne=("en_ligne_site", "any"), nouveau=("nouveau_site", "all"))

    # Prix par jour : le plus bas des sites ce jour-là
    prix_jour = (obs.dropna(subset=["prix_comparable"])
                    .groupby(["cle_vehicule", "jour"])["prix_comparable"].min()
                    .reset_index().sort_values(["cle_vehicule", "jour"]))
    prix_jour["change"] = prix_jour.groupby("cle_vehicule")["prix_comparable"].diff().fillna(0).ne(0)
    prix = prix_jour.groupby("cle_vehicule").agg(
        prix_initial=("prix_comparable", "first"),
        prix_actuel=("prix_comparable", "last"),
        nb_changements_prix=("change", "sum"),
    )
    prix["variation_prix"] = prix["prix_actuel"] - prix["prix_initial"]

    # Description : dernière observation
    derniere = obs.sort_values(["jour", "date_collecte"]).groupby("cle_vehicule").tail(1).set_index("cle_vehicule")
    description = derniere[["niv", "annee", "marque", "modele", "version", "categorie", "transmission",
                            "traction", "carburant", "famille_couleur", "km", "etat", "niv_invalide",
                            "site_id", "concessionnaire", "ville", "province", "groupe", "url_fiche"]]
    description = description.rename(columns={"km": "km_actuel", "site_id": "site_actuel",
                                              "concessionnaire": "concessionnaire_actuel"})

    presence = obs.groupby("cle_vehicule").agg(
        sites_vus=("site_id", _joindre),
        nb_sites=("site_id", "nunique"),
        groupes=("groupe", _joindre),
        date_premiere_vue=("jour", "min"),
        date_derniere_vue=("jour", "max"),
        nb_jours_observes=("jour", "nunique"),
        km_suspect=("km_suspect", "any"),
    )
    duree = pd.to_datetime(presence["date_derniere_vue"]) - pd.to_datetime(presence["date_premiere_vue"])
    presence["jours_en_ligne_min"] = duree.dt.days + 1     # au moins : il était peut-être en ligne avant

    vehicules = description.join(presence).join(prix).join(statut)
    vehicules["statut"] = np.where(vehicules["en_ligne"], "En ligne", "Retiré")
    vehicules = vehicules.drop(columns="en_ligne").reset_index()
    vehicules["nb_changements_prix"] = vehicules["nb_changements_prix"].fillna(0).astype(int)
    return vehicules


def construire_concessionnaires():
    """Table de dimension des sites (Power BI : relation sur site_id)."""
    lignes = [{"site_id": s["id"], "concessionnaire": s["nom"], "ville": s["ville"], "province": s["province"],
               "plateforme": s["plateforme"], "groupe": config.GROUPES.get(s["id"], config.GROUPE_PAR_DEFAUT),
               "collecte": "Oui" if s["collecter"] else "Non (site bloqué)", "url": s["url"]}
              for s in config.SITES]
    return pd.DataFrame(lignes)


# ---------------------------------------------------------------------------
# 8. Tout, de bout en bout
# ---------------------------------------------------------------------------

def enregistrer(df, chemin):
    chemin.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(chemin, index=False, encoding="utf-8-sig")
    print(f"  {len(df):>6} lignes -> {chemin.relative_to(config.RACINE)}")
    return chemin


def pretraiter(dossier=None, enregistrer_fichiers=True):
    """Chargement -> types -> harmonisation -> prix comparable -> qualité -> 2 tables + dimension + rapport."""
    debut = datetime.now()
    brut = charger_collectes(dossier)
    df = nettoyer_types(brut)
    df = harmoniser(df)
    df = ajouter_prix_comparable(df)
    df, rapport = controler_qualite(df)
    observations = construire_observations(df)
    vehicules = construire_vehicules(observations)
    concessionnaires = construire_concessionnaires()

    if enregistrer_fichiers:
        print("Fichiers écrits :")
        enregistrer(observations, config.FICHIER_OBSERVATIONS)
        enregistrer(vehicules, config.FICHIER_VEHICULES)
        enregistrer(concessionnaires, config.FICHIER_CONCESSIONNAIRES)
        enregistrer(rapport, config.FICHIER_QUALITE)
    print(f"Prétraitement terminé en {(datetime.now() - debut).total_seconds():.1f} s : "
          f"{len(observations)} observations, {len(vehicules)} véhicules "
          f"({(vehicules['statut'] == 'En ligne').sum()} en ligne, {(vehicules['statut'] == 'Retiré').sum()} retirés)")
    return {"observations": observations, "vehicules": vehicules,
            "concessionnaires": concessionnaires, "rapport": rapport}


if __name__ == "__main__":
    pretraiter()
