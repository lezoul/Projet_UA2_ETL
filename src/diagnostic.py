"""
diagnostic.py
Parties 1 et 2 du cours : liste d'URL sans doublons, diagnostic de chaque page (cas A à I),
recherche d'API et de données structurées, journal de tests (annexe C).

Fonctions principales :
    sites_sans_doublons(sites)            -> liste des sites avec URL uniques
    diagnostiquer_site(site, session)     -> une ligne du journal
    diagnostiquer_tous(sites, session)    -> liste de lignes du journal
    construire_journal(lignes)            -> DataFrame avec cas confirmés et techniques
    enregistrer_journal(journal)          -> écrit resultats/journal_tests.csv (utf-8-sig)
"""

import json
import re
import time
from datetime import datetime
from urllib.parse import urlparse

import pandas as pd

import config
import projet_scraping as ws

# ---------------------------------------------------------------------------
# 1. Liste des URL à traiter, sans doublons
# ---------------------------------------------------------------------------

def normaliser_url(url):
    """Clé de comparaison : domaine en minuscules, sans barre oblique finale."""
    p = urlparse(url.strip())
    chemin = p.path.rstrip("/") or "/"
    return f"{p.scheme.lower()}://{p.netloc.lower()}{chemin}" + (f"?{p.query}" if p.query else "")


def sites_sans_doublons(sites):
    """Garde la première occurrence de chaque URL et signale les doublons retirés."""
    vues, uniques = set(), []
    for site in sites:
        cle = normaliser_url(site["url"])
        if cle in vues:
            print(f"Doublon retiré : {site['id']} ({site['url']})")
            continue
        vues.add(cle)
        uniques.append(site)
    return uniques


def delai_du_site(site, crawl_delay=None):
    """Le plus grand des délais : minimum du groupe, Crawl-delay lu, Crawl-delay relevé à la main."""
    return max(config.DELAI_MINIMUM, crawl_delay or 0, site.get("delai_robots") or 0)


# ---------------------------------------------------------------------------
# 2. Recherche d'API et de données structurées (partie 1, question 1 ; cas E)
# ---------------------------------------------------------------------------

CHEMINS_API = ["/api/", "/json/"]
_MOTIF_API = re.compile(r"""["'](/[\w\-/~.]*?(?:api|json|graphql)[\w\-/~.]*)["']""", re.I)
_FICHIERS_STATIQUES = re.compile(r"\.(js|css|png|jpe?g|gif|svg|webp|woff2?)$", re.I)


def chercher_api(html, url, session):
    """
    Observe la page déjà téléchargée (aucune requête de plus) :
      - types JSON-LD et nombre de véhicules décrits (schema.org Vehicle, Car, ItemList) ;
      - scripts <script type="application/json"> ;
      - adresses d'API ou de JSON citées dans le code ;
      - permission robots.txt pour /api/ et /json/ (robots.txt est déjà en cache).
    """
    sp = ws.soupe(html)

    types, nb_vehicules = [], 0
    for script in sp.select("script[type='application/ld+json']"):
        try:
            donnees = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            types.append("JSON-LD illisible")
            continue
        elements = donnees if isinstance(donnees, list) else [donnees]
        # Certains sites regroupent leurs objets dans un « @graph » : on les déplie
        elements = [x for e in elements for x in (e.get("@graph", [e]) if isinstance(e, dict) else [e])]
        for element in elements:
            if not isinstance(element, dict):
                continue
            t = element.get("@type")
            t = "/".join(t) if isinstance(t, list) else str(t)
            if t == "ItemList":
                n = len(element.get("itemListElement", []))
                nb_vehicules += n
                types.append(f"ItemList({n})")
            else:
                if t in ("Vehicle", "Car"):
                    nb_vehicules += 1
                types.append(t)

    resume_types = ", ".join(f"{t} x{types.count(t)}" for t in dict.fromkeys(types))
    adresses = sorted({a for a in _MOTIF_API.findall(html) if not _FICHIERS_STATIQUES.search(a)})

    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    permissions = []
    for chemin in CHEMINS_API:
        ok, _, _ = ws.robots_autorise(base + chemin, session.headers["User-Agent"], session)
        permissions.append(f"{chemin} {'permis' if ok else 'INTERDIT'}")

    return {
        "json_ld_types": resume_types,
        "json_ld_vehicules": nb_vehicules,
        "scripts_application_json": len(sp.select("script[type='application/json']")),
        "adresses_api_dans_page": " | ".join(adresses[:10]),
        "robots_chemins_api": " ; ".join(permissions),
    }


# ---------------------------------------------------------------------------
# 3. Diagnostic d'un site
# ---------------------------------------------------------------------------

def diagnostiquer_site(site, session, afficher=True):
    """
    Arbre de décision du cours :
      1. ws.diagnostiquer() : robots.txt + une requête -> cas A à I ;
      2. arrêt si STOP (robots.txt) ou G (blocage) : on ne contourne jamais ;
      3. sinon, téléchargement unique avec ws.obtenir() et sauvegarde dans pages_brutes/ ;
      4. recherche d'API et de données structurées dans la page téléchargée.
    Retourne une ligne du journal (dictionnaire).
    """
    if afficher:
        print(f"\n{'=' * 70}\n{site['nom']} ({site['ville']}, {site['plateforme']})\n{'=' * 70}")

    ligne = {
        "url": site["url"], "cas_confirme": "", "nb_lignes": "",
        "date": datetime.now().isoformat(timespec="seconds"),
        "id": site["id"], "nom": site["nom"], "ville": site["ville"],
        "province": site["province"], "plateforme": site["plateforme"],
        "regles_site": site["regles"],
        "api_officielle_ou_donnees_ouvertes": config.VERIFICATION_API_MANUELLE,
        "fichier_html": "", "problemes_remarques": "",
    }

    # --- 3.1 Diagnostic (robots.txt + 1 requête)
    d = ws.diagnostiquer(site["url"], session=session, afficher=afficher)
    crawl_delay = d.get("crawl_delay")
    delai = delai_du_site(site, crawl_delay)
    ligne.update(
        statut=d.get("statut"), robots=d.get("robots_raison"), crawl_delay=crawl_delay,
        delai_utilise_s=delai, cas_diagnostic=" | ".join(d.get("cas", [])),
        recommandation=d.get("recommandation", ""), technique=d.get("recommandation", ""),
        protection=" | ".join(d.get("protection", [])), signes_js=" | ".join(d.get("signes_js", [])),
        json_integre=" | ".join(d.get("json_integre", [])), blocs_repetes=d.get("blocs_repetes", ""),
        pagination=d.get("pagination", ""), page_suivante=d.get("page_suivante") or "",
        nb_tableaux=d.get("nb_tableaux", ""), taille_ko=d.get("taille_ko", ""),
        encodage=f"déclaré={d.get('charset_declare')} ; détecté={d.get('encodage_detecte')}",
        alertes=" | ".join(d.get("alertes", [])),
    )
    time.sleep(delai)    # diagnostiquer() n'attend pas après sa requête : on respecte le délai ici

    # --- 3.2 Arrêts (arbre de décision)
    if d.get("statut") is None:
        ligne.update(technique="Aucune (site injoignable)",
                     problemes_remarques=f"Site injoignable ({ligne['recommandation']}). Relancer plus tard.")
        return ligne
    cas = ligne["cas_diagnostic"]
    if cas.startswith("STOP") or cas.startswith("G"):
        if afficher:
            print(f"→ Arrêt pour {site['nom']} : {cas}")
        ligne.update(technique="Aucune (arrêt volontaire)",
                     problemes_remarques=f"ARRÊT : {cas} (statut {d.get('statut')}). "
                                         "Aucune tentative de contournement.")
        return ligne

    # --- 3.3 Sauvegarde du HTML
    try:
        r = ws.obtenir(session, site["url"], delai=delai)
    except ws.AccesBloque as e:
        ligne["problemes_remarques"] = f"ARRÊT (accès bloqué) : {e}"
        return ligne
    except Exception as e:
        ligne["problemes_remarques"] = f"ÉCHEC : {type(e).__name__} : {e}"
        return ligne
    if r is None:
        ligne["problemes_remarques"] = "Page introuvable (404)."
        return ligne

    config.DOSSIER_HTML.mkdir(parents=True, exist_ok=True)
    chemin = config.DOSSIER_HTML / f"{site['id']}.html"
    chemin.write_text(r.text, encoding="utf-8")
    ligne["fichier_html"] = str(chemin.relative_to(config.RACINE))
    if afficher:
        print(f"→ HTML enregistré : {ligne['fichier_html']} ({len(r.content) / 1024:.0f} Ko)")

    # --- 3.4 API et données structurées
    api = chercher_api(r.text, site["url"], session)
    ligne.update(api)
    if afficher:
        print(f"→ JSON-LD : {api['json_ld_types'] or 'aucun'} ; véhicules décrits : {api['json_ld_vehicules']}")
        print(f"→ robots.txt pour les API : {api['robots_chemins_api']}")
    if "INTERDIT" in api["robots_chemins_api"]:
        ligne["problemes_remarques"] = ("Une API interne existe peut-être, mais robots.txt interdit son "
                                        "chemin : ne pas l'utiliser.")
    return ligne


def diagnostiquer_tous(sites, session, afficher=True):
    """Diagnostic de chaque URL unique. Un site en erreur n'arrête pas les autres."""
    lignes = []
    for site in sites_sans_doublons(sites):
        try:
            lignes.append(diagnostiquer_site(site, session, afficher=afficher))
        except Exception as e:
            lignes.append({
                "url": site["url"], "date": datetime.now().isoformat(timespec="seconds"),
                "id": site["id"], "nom": site["nom"], "plateforme": site["plateforme"],
                "problemes_remarques": f"ERREUR INATTENDUE : {type(e).__name__} : {e}",
            })
    return lignes


# ---------------------------------------------------------------------------
# 4. Journal de tests (annexe C)
# ---------------------------------------------------------------------------

def construire_journal(lignes):
    """DataFrame du journal, avec les cas confirmés (F12) et la technique retenue par plateforme."""
    journal = pd.DataFrame(lignes)
    journal["cas_confirme"] = journal["id"].map(config.CAS_CONFIRMES).fillna("")
    if "technique" not in journal:
        journal["technique"] = ""
    journal["technique"] = journal["plateforme"].map(config.TECHNIQUES).fillna(journal["technique"])
    return journal


def enregistrer_journal(journal, chemin=None):
    """Écrit le journal : colonnes de l'annexe C d'abord, encodage utf-8-sig (comme scraper.py)."""
    chemin = chemin or config.FICHIER_JOURNAL
    chemin.parent.mkdir(parents=True, exist_ok=True)
    journal.reindex(columns=config.COLONNES_JOURNAL).to_csv(chemin, index=False, encoding="utf-8-sig")
    return chemin
