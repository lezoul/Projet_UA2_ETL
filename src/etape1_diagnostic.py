"""
etape1_diagnostic.py
Projet de groupe Web scraping : concessionnaires de véhicules d'occasion (Ottawa-Gatineau)
Groupe : Yacine Lezoul, Mouncif Bouchachi

Étape 1 : vérifications de la partie 1 + diagnostic de la partie 2 du document
« Projet de groupe Web scraping », pour les 18 sites validés.

Pour chaque URL (liste dédoublonnée), le script :
  1. lance ws.diagnostiquer() : robots.txt, statut HTTP, protection, encodage, JavaScript,
     JSON intégré, tableaux, pagination, blocs répétés -> cas A à I (partie 2) ;
  2. s'arrête si le cas est STOP ou G (règles de conduite : ne jamais contourner) ;
  3. télécharge la page une seule fois avec ws.obtenir() et l'enregistre dans
     pages_brutes/<id>.html (sert à écrire la fonction d'extraction) ;
  4. cherche les signes d'API ou de données structurées (question 1 de la partie 1,
     cas E du cours) : JSON-LD, scripts application/json, adresses d'API dans la page,
     et vérifie dans robots.txt si les chemins /api/ et /json/ sont permis ;
  5. écrit resultats/journal_tests.csv : colonnes de l'annexe C en premier,
     puis les détails du diagnostic. Encodage utf-8-sig, comme scraper.py.

Aucune donnée de véhicule n'est extraite ici (ce sera l'étape 2).
Volume : 2 requêtes par site + robots.txt, délai d'au moins 2 s (5 s pour les sites D2C).

Utilisation (dans le même dossier que projet_scraping.py) :
    python etape1_diagnostic.py                                   # tous les sites
    python etape1_diagnostic.py hyundai_gatineau bank_street_mazda  # seulement certains sites
"""

import csv
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import projet_scraping as ws

# ---------------------------------------------------------------------------
# 0. Configuration (partie 0 du cours)
# ---------------------------------------------------------------------------

# Identifiez-vous honnêtement (critère « Éthique et robustesse »).
COURRIEL_YACINE = "2748526@collegelacite.ca"
COURRIEL_MOUNCIF = "2743259@collegelacite.ca"

USER_AGENT = (
    "CoursCollecteDonnees-LaCite/1.0 (projet etudiant; "
    f"contact: {COURRIEL_YACINE}, {COURRIEL_MOUNCIF})"
)

DELAI_MINIMUM = 2.0     # secondes entre deux requêtes au même site (le cours exige au moins 1 s)

DOSSIER = Path(__file__).resolve().parent
DOSSIER_HTML = DOSSIER / "pages_brutes"
DOSSIER_RESULTATS = DOSSIER / "resultats"
FICHIER_JOURNAL = DOSSIER_RESULTATS / "journal_tests.csv"

# Question 1 de la partie 1 : « Existe-t-il une API officielle ou un jeu de données ouvert ? »
# Vérification manuelle faite le 9 octobre 2026 (à refaire et à dater avant la remise) :
#   - aucun lien « API », « développeurs » ou « données » dans le pied de page des 18 sites ;
#   - aucun jeu de données d'inventaire de concessionnaires sur ouvert.canada.ca ni sur
#     donneesquebec.ca ; Statistique Canada publie seulement des ventes agrégées ;
#   - il existe des fournisseurs commerciaux payants (ex. MarketCheck, VinAudit), qui ne sont
#     ni officiels ni ouverts.
VERIFICATION_API_MANUELLE = (
    "Aucune API officielle ni donnée ouverte trouvée (pied de page du site, ouvert.canada.ca, "
    "donneesquebec.ca ; vérifié le 2026-10-09). Seules des sources commerciales payantes existent."
)

# Chemins d'API à tester dans robots.txt (aucune requête de plus : robots.txt est déjà en cache)
CHEMINS_API = ["/api/", "/json/"]

# ---------------------------------------------------------------------------
# 1. Les 18 sites validés
#    delai_robots : Crawl-delay lu dans robots.txt le 9 octobre 2026 (None = aucun)
#    regles       : restrictions relevées dans robots.txt et les conditions d'utilisation
# ---------------------------------------------------------------------------

SITES = [
    # --- Gatineau : plateforme Magnetis -----------------------------------------------
    {
        "id": "hyundai_gatineau", "nom": "Hyundai Gatineau", "ville": "Gatineau", "province": "QC",
        "plateforme": "Magnetis", "delai_robots": None,
        "url": "https://hyundaigatineau.ca/en/pre-owned",
        "regles": "robots.txt : rien n'est bloqué. Conditions : usage personnel et non commercial.",
    },
    {
        "id": "gatineau_acura", "nom": "Gatineau Acura", "ville": "Gatineau", "province": "QC",
        "plateforme": "Magnetis", "delai_robots": None,
        "url": "https://gatineauacura.com/en/pre-owned",
        "regles": "robots.txt : rien n'est bloqué. Conditions : usage personnel et non commercial.",
    },
    {
        "id": "gatineau_kia", "nom": "Gatineau Kia", "ville": "Gatineau", "province": "QC",
        "plateforme": "Magnetis", "delai_robots": None,
        "url": "https://www.gatineaukia.ca/en/pre-owned",
        "regles": "robots.txt : rien n'est bloqué. Conditions : usage personnel et non commercial.",
    },
    # --- Gatineau : plateforme D2C Media ----------------------------------------------
    {
        "id": "dupont_honda", "nom": "Dupont & Dupont Honda", "ville": "Gatineau", "province": "QC",
        "plateforme": "D2C Media", "delai_robots": 5,
        "url": "https://www.dupontduponthonda.com/occasion/recherche.html",
        "regles": "robots.txt : Crawl-delay 5 s ; /used/detail.html et /json/ interdits (liste seulement). "
                  "Conditions : usage personnel et non commercial.",
    },
    {
        "id": "hull_hyundai", "nom": "Hull Hyundai", "ville": "Gatineau (Hull)", "province": "QC",
        "plateforme": "D2C Media", "delai_robots": 5,
        "url": "https://www.hullhyundai.com/occasion/recherche.html",
        "regles": "robots.txt : Crawl-delay 5 s ; /used/detail.html et /json/ interdits (liste seulement). "
                  "Conditions : usage personnel et non commercial.",
    },
    {
        "id": "hull_nissan", "nom": "Hull Nissan", "ville": "Gatineau (Hull)", "province": "QC",
        "plateforme": "D2C Media", "delai_robots": 5,
        "url": "https://www.hullnissangatineau.ca/occasion/recherche.html",
        "regles": "robots.txt : Crawl-delay 5 s ; /used/detail.html et /json/ interdits (liste seulement). "
                  "Conditions : usage personnel et non commercial.",
    },
    {
        "id": "buckingham_gm", "nom": "Buckingham Chevrolet Buick GMC", "ville": "Gatineau (Buckingham)",
        "province": "QC", "plateforme": "D2C Media", "delai_robots": 5,
        "url": "https://www.buckinghamgm.com/occasion/recherche.html",
        "regles": "robots.txt : Crawl-delay 5 s ; /used/detail.html et /json/* interdits (liste seulement). "
                  "Conditions : usage personnel et non commercial.",
    },
    # --- Ottawa : plateforme EDealer -------------------------------------------------
    {
        "id": "ottawa_honda", "nom": "Ottawa Honda", "ville": "Ottawa", "province": "ON",
        "plateforme": "EDealer", "delai_robots": None,
        "url": "https://www.ottawahonda.com/inventory/used/",
        "regles": "robots.txt : /inventory/ permis ; URL avec filtres interdites sauf ?condition=USED. "
                  "Aucune condition d'utilisation trouvée.",
    },
    # --- Ottawa : groupe Dilawri ------------------------------------------------------
    {
        "id": "bank_street_mazda", "nom": "Bank Street Mazda", "ville": "Ottawa", "province": "ON",
        "plateforme": "Dilawri", "delai_robots": None,
        "url": "https://www.bankstreetmazda.com/ottawa-Mazda-dealer/used-cars/used-vehicle-inventory?type=U",
        "regles": "robots.txt : seuls /oops et /signalr/ bloqués. Aucune condition d'utilisation trouvée.",
    },
    {
        "id": "bank_street_hyundai", "nom": "Bank Street Hyundai", "ville": "Ottawa", "province": "ON",
        "plateforme": "Dilawri", "delai_robots": None,
        "url": "https://www.bankstreethyundai.com/ottawa-gloucester-hyundai-dealer/used-cars/used-vehicle-inventory?type=U",
        "regles": "robots.txt : seuls /oops et /signalr/ bloqués. Aucune condition d'utilisation trouvée.",
    },
    {
        "id": "bank_street_kia", "nom": "Bank Street Kia", "ville": "Ottawa", "province": "ON",
        "plateforme": "Dilawri", "delai_robots": None,
        "url": "https://www.bankstreetkia.com/ottawa-Kia-dealer/used-cars/used-vehicle-inventory?type=U",
        "regles": "robots.txt : seuls /oops et /signalr/ bloqués. Aucune condition d'utilisation trouvée.",
    },
    {
        "id": "bank_street_mitsubishi", "nom": "Bank Street Mitsubishi", "ville": "Ottawa", "province": "ON",
        "plateforme": "Dilawri", "delai_robots": None,
        "url": "https://www.bankstreetmitsubishi.com/ottawa-Mitsubishi-dealer/used-cars/used-vehicle-inventory?type=U",
        "regles": "robots.txt : seuls /oops et /signalr/ bloqués. Aucune condition d'utilisation trouvée.",
    },
    {
        "id": "barrhaven_mazda", "nom": "Barrhaven Mazda", "ville": "Ottawa (Barrhaven)", "province": "ON",
        "plateforme": "Dilawri", "delai_robots": None,
        "url": "https://www.barrhavenmazda.com/ottawa/used/inventory?type=U",
        "regles": "robots.txt : seuls /oops et /signalr/ bloqués. Aucune condition d'utilisation trouvée.",
    },
    {
        "id": "barrhaven_cjdr", "nom": "Barrhaven Chrysler Jeep Dodge Ram", "ville": "Ottawa (Barrhaven)",
        "province": "ON", "plateforme": "Dilawri", "delai_robots": None,
        "url": "https://www.barrhavenjeepdodgeram.com/used-vehicles/used-vehicle-inventory?type=U",
        "regles": "robots.txt : seuls /oops et /signalr/ bloqués. Aucune condition d'utilisation trouvée.",
    },
    {
        "id": "dilawri_cjdr", "nom": "Dilawri Chrysler Jeep Dodge Ram", "ville": "Ottawa", "province": "ON",
        "plateforme": "Dilawri", "delai_robots": None,
        "url": "https://www.dilawrichrysler.com/chrysler-jeep-dodge-ram-dealer-ottawa/used-cars/used-vehicle-inventory?type=U",
        "regles": "robots.txt : seuls /oops et /signalr/ bloqués. Aucune condition d'utilisation trouvée.",
    },
    {
        "id": "orleans_mitsubishi", "nom": "Orleans Mitsubishi", "ville": "Ottawa (Orléans)", "province": "ON",
        "plateforme": "Dilawri", "delai_robots": None,
        "url": "https://www.orleansmitsubishi.com/mitsubishi/used-inventory.html?type=U",
        "regles": "robots.txt : /oops, /signalr/ et le blogue bloqués. Aucune condition d'utilisation trouvée.",
    },
    {
        "id": "hyundai_hunt_club", "nom": "Hyundai On Hunt Club", "ville": "Ottawa (Nepean)", "province": "ON",
        "plateforme": "Dilawri", "delai_robots": None,
        "url": "https://www.hyundaionhuntclub.com/hyundai/used~vehicles/inventory.html?type=U",
        "regles": "robots.txt : seuls /oops et /signalr/ bloqués. Aucune condition d'utilisation trouvée.",
    },
    {
        "id": "kia_hunt_club", "nom": "Kia On Hunt Club", "ville": "Ottawa (Nepean)", "province": "ON",
        "plateforme": "Dilawri", "delai_robots": None,
        "url": "https://www.kiaonhuntclub.com/kia/used-inventory.html?type=U",
        "regles": "robots.txt : /oops, /signalr/ et le blogue bloqués. Aucune condition d'utilisation trouvée.",
    },
]

# Colonnes du journal : d'abord celles de l'annexe C, puis les détails du diagnostic
COLONNES = [
    # --- Annexe C (gabarit du journal de tests)
    "url", "cas_diagnostic", "cas_confirme", "technique", "nb_lignes", "problemes_remarques",
    # --- Identification
    "date", "id", "nom", "ville", "province", "plateforme",
    # --- Partie 1 : cadre légal et éthique
    "robots", "crawl_delay", "delai_utilise_s", "regles_site",
    "api_officielle_ou_donnees_ouvertes", "robots_chemins_api",
    # --- Partie 2 : diagnostic
    "statut", "recommandation", "protection", "signes_js", "json_integre",
    "json_ld_types", "json_ld_vehicules", "scripts_application_json", "adresses_api_dans_page",
    "blocs_repetes", "pagination", "page_suivante", "nb_tableaux", "taille_ko", "encodage",
    "alertes", "fichier_html",
]


# ---------------------------------------------------------------------------
# 2. Liste des URL à traiter, sans doublons
# ---------------------------------------------------------------------------

def normaliser_url(url):
    """Clé de comparaison : minuscules pour le domaine, sans barre oblique finale."""
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


# ---------------------------------------------------------------------------
# 3. Recherche d'API et de données structurées (partie 1, question 1 ; cas E)
# ---------------------------------------------------------------------------

_MOTIF_API = re.compile(r"""["'](/[\w\-/~.]*?(?:api|json|graphql)[\w\-/~.]*)["']""", re.I)
_FICHIERS_STATIQUES = re.compile(r"\.(js|css|png|jpe?g|gif|svg|webp|woff2?)$", re.I)


def chercher_api(html, url, session):
    """
    Observe la page téléchargée (aucune requête de plus) et retourne un dictionnaire :
      - types JSON-LD et nombre de véhicules décrits (schema.org Vehicle, Car, ItemList) ;
      - scripts <script type="application/json"> ;
      - adresses d'API ou de JSON citées dans le code de la page ;
      - permission robots.txt pour /api/ et /json/ (une API cachée interdite ne doit pas servir).
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
    scripts_json = sp.select("script[type='application/json']")
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
        "scripts_application_json": len(scripts_json),
        "adresses_api_dans_page": " | ".join(adresses[:10]),
        "robots_chemins_api": " ; ".join(permissions),
    }


# ---------------------------------------------------------------------------
# 4. Traitement d'un site
# ---------------------------------------------------------------------------

def traiter_site(site, session):
    """Diagnostic + recherche d'API + sauvegarde du HTML d'un site. Retourne une ligne du journal."""
    print(f"\n{'=' * 70}\n{site['nom']} ({site['ville']}, {site['plateforme']})\n{'=' * 70}")

    ligne = {
        "url": site["url"], "cas_confirme": "",   # cas_confirme : à remplir après vérification F12
        "nb_lignes": "",                           # rempli à l'étape 2 (collecte)
        "date": datetime.now().isoformat(timespec="seconds"),
        "id": site["id"], "nom": site["nom"], "ville": site["ville"],
        "province": site["province"], "plateforme": site["plateforme"],
        "regles_site": site["regles"],
        "api_officielle_ou_donnees_ouvertes": VERIFICATION_API_MANUELLE,
        "fichier_html": "", "problemes_remarques": "",
    }
    remarques = []

    # --- 4.1 Diagnostic (robots.txt + 1 requête)
    d = ws.diagnostiquer(site["url"], session=session, afficher=True)
    crawl_delay = d.get("crawl_delay")
    delai = max(DELAI_MINIMUM, crawl_delay or 0, site["delai_robots"] or 0)

    ligne.update(
        statut=d.get("statut"),
        robots=d.get("robots_raison"),
        crawl_delay=crawl_delay,
        delai_utilise_s=delai,
        cas_diagnostic=" | ".join(d.get("cas", [])),
        recommandation=d.get("recommandation", ""),
        technique=d.get("recommandation", ""),    # technique prévue ; à corriger après F12
        protection=" | ".join(d.get("protection", [])),
        signes_js=" | ".join(d.get("signes_js", [])),
        json_integre=" | ".join(d.get("json_integre", [])),
        blocs_repetes=d.get("blocs_repetes", ""),
        pagination=d.get("pagination", ""),
        page_suivante=d.get("page_suivante") or "",
        nb_tableaux=d.get("nb_tableaux", ""),
        taille_ko=d.get("taille_ko", ""),
        encodage=f"déclaré={d.get('charset_declare')} ; détecté={d.get('encodage_detecte')}",
        alertes=" | ".join(d.get("alertes", [])),
    )
    time.sleep(delai)    # diagnostiquer() n'attend pas après sa requête : on respecte le délai ici

    # --- 4.2 Arrêts (arbre de décision de la partie 2)
    if d.get("statut") is None:
        remarques.append(f"Site injoignable ({ligne['recommandation']}). Relancer plus tard.")
        ligne["technique"] = "Aucune (site injoignable)"
        ligne["problemes_remarques"] = " ".join(remarques)
        return ligne

    cas = ligne["cas_diagnostic"]
    if cas.startswith("STOP") or cas.startswith("G"):
        remarques.append(f"ARRÊT : {cas} (statut {d.get('statut')}). Aucune tentative de contournement.")
        ligne["technique"] = "Aucune (arrêt volontaire)"
        ligne["problemes_remarques"] = " ".join(remarques)
        print(f"→ Arrêt pour {site['nom']} : {cas}")
        return ligne

    # --- 4.3 Sauvegarde du HTML (obtenir() vérifie robots.txt, gère 429/5xx et s'arrête sur 403)
    try:
        r = ws.obtenir(session, site["url"], delai=delai)
    except ws.AccesBloque as e:
        remarques.append(f"ARRÊT (accès bloqué) : {e}")
        ligne["problemes_remarques"] = " ".join(remarques)
        return ligne
    except Exception as e:     # erreur réseau répétée, etc. : on note et on passe au site suivant
        remarques.append(f"ÉCHEC : {type(e).__name__} : {e}")
        ligne["problemes_remarques"] = " ".join(remarques)
        return ligne

    if r is None:
        remarques.append("Page introuvable (404).")
        ligne["problemes_remarques"] = " ".join(remarques)
        return ligne

    chemin = DOSSIER_HTML / f"{site['id']}.html"
    chemin.write_text(r.text, encoding="utf-8")
    ligne["fichier_html"] = str(chemin.relative_to(DOSSIER))
    print(f"→ HTML enregistré : {ligne['fichier_html']} ({len(r.content) / 1024:.0f} Ko)")

    # --- 4.4 API et données structurées
    api = chercher_api(r.text, site["url"], session)
    ligne.update(api)
    print(f"→ JSON-LD : {api['json_ld_types'] or 'aucun'} ; véhicules décrits : {api['json_ld_vehicules']}")
    print(f"→ robots.txt pour les API : {api['robots_chemins_api']}")
    if "INTERDIT" in api["robots_chemins_api"]:
        remarques.append("Une API interne existe peut-être, mais robots.txt interdit son chemin : ne pas l'utiliser.")

    ligne["problemes_remarques"] = " ".join(remarques)
    return ligne


# ---------------------------------------------------------------------------
# 5. Programme principal
# ---------------------------------------------------------------------------

def main(ids_demandes):
    DOSSIER_HTML.mkdir(exist_ok=True)
    DOSSIER_RESULTATS.mkdir(exist_ok=True)

    inconnus = set(ids_demandes) - {s["id"] for s in SITES}
    if inconnus:
        sys.exit(f"Identifiants inconnus : {', '.join(sorted(inconnus))}")

    sites = sites_sans_doublons(SITES)
    if ids_demandes:
        sites = [s for s in sites if s["id"] in ids_demandes]
    print(f"{len(sites)} URL uniques à traiter.")

    session = ws.creer_session(USER_AGENT)
    lignes = []
    for site in sites:
        try:
            lignes.append(traiter_site(site, session))
        except Exception as e:     # un site en erreur ne doit pas arrêter les autres
            lignes.append({
                "url": site["url"], "date": datetime.now().isoformat(timespec="seconds"),
                "id": site["id"], "nom": site["nom"],
                "problemes_remarques": f"ERREUR INATTENDUE : {type(e).__name__} : {e}",
            })

    with open(FICHIER_JOURNAL, "w", newline="", encoding="utf-8-sig") as f:
        ecrivain = csv.DictWriter(f, fieldnames=COLONNES, extrasaction="ignore")
        ecrivain.writeheader()
        ecrivain.writerows(lignes)

    print(f"\n{'=' * 70}\nRésumé\n{'=' * 70}")
    for l in lignes:
        etat = "HTML OK" if l.get("fichier_html") else "pas de HTML"
        print(f"{l['nom']:<36} {str(l.get('statut', '')):<5} {etat:<12} {l.get('cas_diagnostic', '')}")
    print(f"\nJournal de tests : {FICHIER_JOURNAL.relative_to(DOSSIER)}")
    print(f"Pages HTML       : {DOSSIER_HTML.relative_to(DOSSIER)}/")


if __name__ == "__main__":
    main(sys.argv[1:])
