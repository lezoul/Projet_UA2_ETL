"""
extraction.py
Partie 3 du cours : collecte des véhicules.

Une seule fonction d'entrée, extraire_vehicules(site, session), appelée une fois par URL de la
liste dédoublonnée. Elle choisit le lecteur de page adapté à la plateforme du site, suit la
pagination présente dans le HTML (cas C) et respecte la règle zéro risque du groupe :
  - seulement les pages de liste (jamais les pages détail : interdites chez D2C, inutiles ailleurs) ;
  - seulement le HTML servi par le site et le JSON-LD qu'il contient (cas A et E1a) ;
  - ni API interne, ni navigateur automatisé, ni contournement de blocage ;
  - aucun renseignement personnel : on ne garde que des faits sur les véhicules.

Fonctions principales :
    extraire_vehicules(site, session)          -> (liste de véhicules, rapport du site)
    collecter_tous(sites, session)             -> (DataFrame de tous les véhicules, rapports)
"""

import json
import re
import time
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import pandas as pd

import config
import diagnostic
import projet_scraping as ws

# ---------------------------------------------------------------------------
# 0. Petits outils de nettoyage
# ---------------------------------------------------------------------------

def nombre(texte):
    """'$11,995' -> 11995.0 ; '16 995' -> 16995.0 ; None si aucun nombre (outil du cours, cas H)."""
    return ws.prix_en_nombre(texte) if texte else None


def kilometrage(texte):
    """'122,342 km' ou '141,165 KM' -> 122342 ; None si absent."""
    if not texte:
        return None
    chiffres = re.sub(r"[^\d]", "", texte)
    return int(chiffres) if chiffres else None


def propre(texte):
    """Texte normalisé (espaces insécables, blancs multiples) ; None si vide."""
    t = ws.nettoyer_chaine(texte)
    return t or None


def changer_parametre(url, nom, valeur):
    """Remplace (ou ajoute) un paramètre de l'adresse : ?vip=2, ?pindex=3..."""
    p = urlparse(url)
    params = parse_qs(p.query, keep_blank_values=True)
    params[nom] = [str(valeur)]
    return urlunparse(p._replace(query=urlencode(params, doseq=True)))


def json_ld_vehicules(sp):
    """
    Lit le JSON-LD de la page (cas E1a) et retourne {NIV: {prix, url, annee, marque, modele}}.
    Sert de source complémentaire : on ne fait aucune requête de plus.
    """
    resultat = {}
    for script in sp.select("script[type='application/ld+json']"):
        try:
            donnees = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        elements = donnees if isinstance(donnees, list) else [donnees]
        objets = []
        for e in elements:
            if not isinstance(e, dict):
                continue
            if e.get("@type") == "ItemList":
                objets += [li.get("item", {}) for li in e.get("itemListElement", []) if isinstance(li, dict)]
            else:
                objets.append(e)
        for o in objets:
            niv = o.get("vehicleIdentificationNumber")
            if not niv:
                continue
            offre = o.get("offers") or {}
            marque = o.get("brand")
            resultat[niv] = {
                "prix": offre.get("price"),
                "url": offre.get("url") or o.get("url"),
                "annee": o.get("vehicleModelDate"),
                "marque": marque.get("name") if isinstance(marque, dict) else marque,
                "modele": o.get("model"),
            }
    return resultat


# ---------------------------------------------------------------------------
# 1. Lecteurs de page, un par plateforme
#    Chaque lecteur reçoit la page (BeautifulSoup) et son adresse, et retourne une liste de
#    dictionnaires avec les colonnes de config.COLONNES_VEHICULES (sans les colonnes du site).
# ---------------------------------------------------------------------------

_TRANSMISSION = re.compile(r"auto|cvt|manu|vitesse|boîte|boite|dct|speed", re.I)
_TRACTION = re.compile(r"^(fwd|awd|rwd|4wd|4x4|4×4|2wd|traction|intégrale|propulsion)", re.I)
_CARBURANT = re.compile(r"gasoline|essence|electric|électrique|hybrid|hybride|diesel|plug", re.I)


def lire_page_magnetis(sp, url_page):
    """Magnetis (Hyundai Gatineau, Gatineau Acura, Gatineau Kia) : div.vehicle-card-wrapper + JSON-LD."""
    complement = json_ld_vehicules(sp)
    vehicules = []
    for carte in sp.select("div.vehicle-card-wrapper"):
        niv = carte.get("data-vehicle-vin")
        lien = carte.select_one("[data-element-type=vehicleInfo] a[href]") or carte.select_one("a[href]")

        # Prix « comptant » : lignes « Price », « Rebate », « Your price »
        prix = {}
        bloc = carte.select_one("[data-price-type=cash]")
        if bloc:
            for rangee in bloc.select("div.d-flex"):
                etiquette = rangee.find("div")
                montant = rangee.select_one(".amount")
                if etiquette and montant:
                    prix[etiquette.get_text(" ", strip=True).lower()] = nombre(montant.get_text())

        # Options affichées : traction, transmission, kilométrage, parfois carburant
        options = {"transmission": None, "traction": None, "carburant": None, "km": None}
        for o in carte.select(".option-value"):
            t = o.get_text(" ", strip=True)
            if "km" in t.lower():
                options["km"] = kilometrage(t)
            elif _TRACTION.search(t):
                options["traction"] = t
            elif _CARBURANT.search(t):
                options["carburant"] = t
            elif _TRANSMISSION.search(t):
                options["transmission"] = t

        prix_final = prix.get("your price") or (complement.get(niv) or {}).get("prix")
        prix_affiche = prix.get("price") or prix_final
        vehicules.append({
            "url_page": url_page,
            "url_fiche": urljoin(url_page, lien["href"]) if lien else (complement.get(niv) or {}).get("url"),
            "id_annonce": carte.get("data-vehicle-id"),
            "no_stock": carte.get("data-vehicle-stock_number"),
            "niv": niv,
            "annee": carte.get("data-vehicle-year"),
            "marque": propre(carte.get("data-vehicle-make")),
            "modele": propre(carte.get("data-vehicle-model")),
            "version": propre(carte.get("data-vehicle-trim")),
            "etat": "Occasion" if carte.get("data-vehicle-status") == "used" else propre(carte.get("data-vehicle-status")),
            "prix_affiche": prix_affiche,
            "rabais": prix.get("rebate"),
            "frais": None,
            "prix_final": prix_final,
            "km": options["km"],
            "transmission": options["transmission"],
            "traction": options["traction"],
            "carburant": options["carburant"],
            "moteur": None, "couleur_ext": None, "categorie": None,
        })
    return vehicules


_ETIQUETTES_D2C = {
    "Moteur:": "moteur", "Transmission:": "transmission", "Motricité:": "traction",
    "Carburant:": "carburant", "Catégorie:": "categorie", "Couleur extérieure:": "couleur_ext",
}


def lire_page_d2c(sp, url_page):
    """D2C Media (Dupont Honda, Hull Hyundai, Hull Nissan, Buckingham GM) : li.carBoxWrapper + JSON-LD."""
    complement = json_ld_vehicules(sp)
    vehicules = []
    for carte in sp.select("li.carBoxWrapper"):
        donnees = carte.select_one("input[data-condition]")
        if donnees is None:          # bandeaux publicitaires insérés dans la liste : pas un véhicule
            continue
        niv = donnees.get("data-vin")

        # Fiche technique : paires « étiquette : valeur »
        fiche = {}
        for valeur in carte.select("span.-ph.--s"):
            etiquette = valeur.find_previous_sibling("span")
            cle = _ETIQUETTES_D2C.get(etiquette.get_text(strip=True) if etiquette else "")
            if cle:
                fiche[cle] = propre(valeur.get_text(" ", strip=True))

        # Prix : prix actuel, et ancien prix barré s'il y a une réduction
        actuel = carte.select_one(".carPrice span.dollarsigned.p-base")
        barre = carte.select_one(".carPrice span.ttStrike")
        prix_final = nombre(actuel.get_text()) if actuel else (complement.get(niv) or {}).get("prix")
        prix_affiche = nombre(barre.get_text()) if barre else prix_final
        rabais = (prix_affiche - prix_final) if (prix_affiche and prix_final and prix_affiche > prix_final) else None

        titre = carte.select_one("a.carTitle[href]")
        version = carte.select_one(".divTrim")
        km = carte.select_one(".s-km")
        est_demo = any(s.strip() == "Démo" for s in carte.find_all(string=True))
        vehicules.append({
            "url_page": url_page,
            "url_fiche": urljoin(url_page, titre["href"]) if titre else (complement.get(niv) or {}).get("url"),
            "id_annonce": donnees.get("data-carid"),
            "no_stock": donnees.get("data-stock-number"),
            "niv": niv,
            "annee": donnees.get("data-year"),
            "marque": propre(donnees.get("data-make")),
            "modele": propre(donnees.get("data-model")),
            "version": propre(version.get_text(" ", strip=True)) if version else None,
            "etat": "Démo" if est_demo else "Occasion",
            "prix_affiche": prix_affiche,
            "rabais": rabais,
            "frais": None,
            "prix_final": prix_final,
            "km": kilometrage(km.get_text()) if km else None,
            "transmission": fiche.get("transmission"),
            "traction": fiche.get("traction"),
            "carburant": fiche.get("carburant"),
            "moteur": fiche.get("moteur"),
            "couleur_ext": fiche.get("couleur_ext"),
            "categorie": fiche.get("categorie"),
        })
    return vehicules


_ETIQUETTES_DILAWRI = {
    "Engine:": "moteur", "Transmission:": "transmission", "Drivetrain:": "traction", "Exterior:": "couleur_ext",
}


def lire_page_dilawri(sp, url_page):
    """Groupe Dilawri (10 sites d'Ottawa) : div.vsearchresult avec attributs data-chrome-* et liste dt/dd."""
    vehicules = []
    for carte in sp.select("div.vsearchresult"):
        if not carte.get("data-chrome-payment-vid"):   # bandeaux insérés dans la liste : pas un véhicule
            continue
        fiche = {}
        for dt in carte.select("dt"):
            dd = dt.find_next_sibling("dd")
            cle = _ETIQUETTES_DILAWRI.get(dt.get_text(strip=True))
            if cle and dd:
                fiche[cle] = propre(dd.get_text(" ", strip=True))

        # Détail du prix (bouton d'information) : « Price », frais (Admin Fee, OMVIC Fee), réductions
        prix_affiche, rabais, frais = None, None, None
        detail = carte.select_one("button.chrome-payment-price-disclosure[data-content]")
        if detail:
            sous = ws.soupe(detail["data-content"])
            liste_frais, liste_rabais = [], []
            for element in sous.select(".price-breakdown-item"):
                etiquette = element.select_one(".price-breakdown-label")
                montant = nombre(element.select_one(".price-breakdown-amount").get_text()) \
                    if element.select_one(".price-breakdown-amount") else None
                if montant is None:
                    continue
                if "is-deduction" in element.get("class", []):
                    liste_rabais.append(abs(montant))
                elif etiquette and etiquette.get_text(strip=True).lower() == "price":
                    prix_affiche = montant
                else:
                    liste_frais.append(montant)
            rabais = sum(liste_rabais) if liste_rabais else None
            frais = sum(liste_frais) if liste_frais else None
        prix_final = nombre(carte.get("data-chrome-selling-price"))
        if prix_affiche is None:
            prix_affiche = prix_final

        statut = None
        for fort in carte.find_all("strong"):
            if fort.get_text(strip=True) == "Status:":
                suivant = fort.find_next("span")
                statut = propre(suivant.get_text()) if suivant else None
                break

        carfax = carte.select_one("[data-vehicle-script]")
        carrosserie = None
        if carfax:
            m = re.search(r"bodystyle:\s*'([^']*)'", carfax["data-vehicle-script"])
            carrosserie = propre(m.group(1)) if m else None

        km = carte.select_one(".chrome-payment-mileage")
        niv = carte.select_one(".chrome-payment-vin")
        vehicules.append({
            "url_page": url_page,
            "url_fiche": urljoin(url_page, carte.get("data-chrome-payment-url") or ""),
            "id_annonce": carte.get("data-chrome-payment-vid"),
            "no_stock": carte.get("data-chrome-payment-stock"),
            "niv": propre(niv.get_text()) if niv else None,
            "annee": carte.get("data-chrome-payment-year"),
            "marque": propre(carte.get("data-chrome-payment-make")),
            "modele": propre(carte.get("data-chrome-payment-model")),
            "version": propre(carte.get("data-chrome-payment-trim")),
            "etat": statut or "Occasion",
            "prix_affiche": prix_affiche,
            "rabais": rabais,
            "frais": frais,
            "prix_final": prix_final,
            "km": kilometrage(km.get_text()) if km else None,
            "transmission": fiche.get("transmission"),
            "traction": fiche.get("traction"),
            "carburant": None,
            "moteur": fiche.get("moteur"),
            "couleur_ext": fiche.get("couleur_ext"),
            "categorie": carrosserie,
        })
    return vehicules


# Une ligne par plateforme : quel lecteur utiliser, et quel paramètre porte le numéro de page
PLATEFORMES = {
    "Magnetis":  {"lire_page": lire_page_magnetis, "param_page": "vip"},
    "D2C Media": {"lire_page": lire_page_d2c, "param_page": None},       # une seule page : liste seulement
    "Dilawri":   {"lire_page": lire_page_dilawri, "param_page": "pindex"},
}


# ---------------------------------------------------------------------------
# 2. Pagination (cas C)
# ---------------------------------------------------------------------------

def modele_pagination(sp, url_page, param):
    """
    Cherche dans la page un lien qui contient le paramètre de pagination (?vip=, ?pindex=).
    On ne fabrique une adresse de page que si le site en propose lui-même dans son HTML.
    """
    if not param:
        return None
    for a in sp.select(f"a[href*='{param}=']"):
        return urljoin(url_page, a["href"])
    return None


def meme_ordre(url_depart, url_modele, param):
    """
    Vrai si l'adresse de départ et le lien de pagination ont les mêmes paramètres (tri, filtres),
    sans compter le numéro de page. Exemple : Magnetis (?vip=2 seul) -> vrai ;
    Dilawri (?type=U contre ?type=U&sort=tadded_asc&psize=12...) -> faux.
    """
    def parametres(url):
        p = parse_qs(urlparse(url).query, keep_blank_values=True)
        p.pop(param, None)
        return p
    return parametres(url_depart) == parametres(url_modele)


def total_annonce(sp):
    """Nombre de véhicules annoncé par la page (sert de condition d'arrêt), ou None."""
    texte = ws.texte_visible(sp)
    for motif in (r"(\d+)\s+vehicles?\s+(?:found|in inventory)", r"of\s+(\d+)\s+results",
                  r"Used (?:Inventory|Vehicles)\s*\((\d+)\)"):
        m = re.search(motif, texte, re.I)
        if m:
            return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# 3. Fonction unique d'extraction
# ---------------------------------------------------------------------------

def extraire_vehicules(site, session, afficher=True):
    """
    Collecte tous les véhicules d'un site, en respectant ses règles.
    Retourne (vehicules, rapport) ; rapport = dictionnaire pour le journal de tests.
    """
    rapport = {"id": site["id"], "date_collecte": datetime.now().isoformat(timespec="seconds"),
               "pages_collectees": 0, "nb_lignes": 0, "remarques": []}

    if not site.get("collecter", True):
        rapport["remarques"].append("Site non collecté (règle zéro risque : voir le diagnostic).")
        return [], rapport
    plateforme = PLATEFORMES.get(site["plateforme"])
    if plateforme is None:
        rapport["remarques"].append(f"Aucun lecteur pour la plateforme {site['plateforme']}.")
        return [], rapport

    delai = diagnostic.delai_du_site(site)
    vehicules, vus, pages_vues = [], set(), set()
    url, numero, modele, total = site["url"], 1, None, None
    realigne = False     # True une fois la page 1 relue dans l'ordre des liens de pagination

    while url and len(pages_vues) < config.MAX_PAGES_PAR_SITE:
        if url in pages_vues:                       # même logique que parcourir_pages() du cours
            break
        pages_vues.add(url)
        try:
            r = ws.obtenir(session, url, delai=delai)     # robots.txt revérifié, 429/5xx gérés
        except ws.AccesBloque as e:
            rapport["remarques"].append(f"ARRÊT (accès bloqué) : {e}")
            break
        except Exception as e:
            rapport["remarques"].append(f"ÉCHEC page {numero} : {type(e).__name__} : {e}")
            break
        if r is None:
            rapport["remarques"].append(f"Page {numero} introuvable (404) : arrêt.")
            break

        sp = ws.soupe(r)
        rapport["pages_collectees"] += 1
        nouveaux = 0
        for v in plateforme["lire_page"](sp, r.url):
            cle = v.get("niv") or v.get("id_annonce")      # un véhicule n'est gardé qu'une fois
            if cle in vus:
                continue
            vus.add(cle)
            vehicules.append(v)
            nouveaux += 1
        if afficher:
            print(f"  page {numero} : {nouveaux} nouveaux véhicules (total {len(vehicules)})")

        if numero == 1:
            modele = modele_pagination(sp, r.url, plateforme["param_page"])
            total = total_annonce(sp)

            # Même ordre de tri pour toutes les pages. Chez Dilawri, l'adresse de départ utilise le tri
            # par défaut du site, mais les liens de pagination imposent un autre tri (sort=tadded_asc).
            # Lire la page 1 dans un ordre et les pages 2 à N dans un autre ferait manquer une page
            # entière (constaté le 2026-10-22 : 12 véhicules manquants sur chaque site Dilawri).
            # On relit donc une fois la page 1 dans l'ordre des liens (une requête de plus par site).
            if modele and not realigne and not meme_ordre(site["url"], modele, plateforme["param_page"]):
                realigne = True
                url = changer_parametre(modele, plateforme["param_page"], 1)
                if afficher:
                    print("  page 1 relue dans l'ordre de tri des liens de pagination")
                continue

        # Conditions d'arrêt : pas de pagination, page sans nouveauté, total annoncé atteint
        if modele is None or nouveaux == 0 or (total and len(vehicules) >= total):
            break
        numero += 1
        url = changer_parametre(modele, plateforme["param_page"], numero)

    # Colonnes communes à tous les véhicules du site
    for v in vehicules:
        v.update(site_id=site["id"], concessionnaire=site["nom"], ville=site["ville"],
                 province=site["province"], plateforme=site["plateforme"],
                 date_collecte=rapport["date_collecte"])

    rapport["nb_lignes"] = len(vehicules)
    if total and len(vehicules) < total:
        rapport["remarques"].append(f"{len(vehicules)} véhicules collectés sur {total} annoncés.")
    return vehicules, rapport


def collecter_tous(sites, session, afficher=True, enregistrer=True):
    """
    Appelle extraire_vehicules() une fois par URL de la liste dédoublonnée.
    Enregistre un CSV par site dans resultats/brut/ et retourne (DataFrame, rapports).
    """
    tous, rapports = [], []
    jour = datetime.now().strftime("%Y-%m-%d")
    for site in diagnostic.sites_sans_doublons(sites):
        if afficher:
            print(f"\n{site['nom']} ({site['plateforme']})")
        try:
            vehicules, rapport = extraire_vehicules(site, session, afficher=afficher)
        except Exception as e:      # un site en erreur n'arrête pas les autres
            vehicules, rapport = [], {"id": site["id"], "nb_lignes": 0, "pages_collectees": 0,
                                      "date_collecte": datetime.now().isoformat(timespec="seconds"),
                                      "remarques": [f"ERREUR INATTENDUE : {type(e).__name__} : {e}"]}
        if enregistrer and vehicules:
            config.DOSSIER_BRUT.mkdir(parents=True, exist_ok=True)
            chemin = config.DOSSIER_BRUT / f"{site['id']}_{jour}.csv"
            pd.DataFrame(vehicules).reindex(columns=config.COLONNES_VEHICULES).to_csv(
                chemin, index=False, encoding="utf-8-sig")
            rapport["fichier_csv"] = str(chemin.relative_to(config.RACINE))
        if afficher:
            print(f"  → {rapport['nb_lignes']} véhicules ; {' '.join(rapport['remarques']) or 'aucune remarque'}")
        tous += vehicules
        rapports.append(rapport)
    return pd.DataFrame(tous).reindex(columns=config.COLONNES_VEHICULES), rapports


def ajouter_collecte_au_journal(journal, rapports):
    """Reporte dans le journal le nombre de lignes, les pages, le fichier et les remarques de la collecte."""
    par_id = {r["id"]: r for r in rapports}
    # pandas 3 : colonnes de type « object » pour pouvoir y écrire des nombres comme du texte
    for colonne in ["nb_lignes", "date_collecte", "pages_collectees", "fichier_csv", "problemes_remarques"]:
        journal[colonne] = journal[colonne].astype(object) if colonne in journal else None
    for i, ligne in journal.iterrows():
        r = par_id.get(ligne["id"])
        if not r:
            continue
        journal.at[i, "nb_lignes"] = r["nb_lignes"]
        journal.at[i, "date_collecte"] = r.get("date_collecte", "")
        journal.at[i, "pages_collectees"] = r.get("pages_collectees", 0)
        journal.at[i, "fichier_csv"] = r.get("fichier_csv", "")
        remarques = " ".join(r["remarques"])
        if remarques:
            avant = ligne.get("problemes_remarques")
            avant = "" if pd.isna(avant) else str(avant)
            journal.at[i, "problemes_remarques"] = (avant + " || Collecte : " + remarques).strip(" |")
    return journal
