"""
config.py
Projet de groupe Web scraping : concessionnaires de véhicules d'occasion (Ottawa-Gatineau)
Groupe : Yacine Lezoul (2748526) et Mouncif Bouchachi (2743259)

Tous les réglages du projet au même endroit : chemins, User-Agent, délais, liste des sites,
sites exclus, vérifications éthiques et cas confirmés. Le notebook et pipeline.py lisent ce fichier.
"""

from pathlib import Path

# ---------------------------------------------------------------------------
# Chemins (la racine du projet est le dossier parent de src/)
# ---------------------------------------------------------------------------

RACINE = Path(__file__).resolve().parent.parent
DOSSIER_HTML = RACINE / "pages_brutes"           # HTML téléchargé au diagnostic (non publié)
DOSSIER_RESULTATS = RACINE / "resultats"
DOSSIER_BRUT = DOSSIER_RESULTATS / "brut"        # un CSV par site et par date de collecte
FICHIER_JOURNAL = DOSSIER_RESULTATS / "journal_tests.csv"

# ---------------------------------------------------------------------------
# Partie 0 du cours : identification et politesse
# ---------------------------------------------------------------------------

COURRIEL_YACINE = "2748526@collegelacite.ca"
COURRIEL_MOUNCIF = "2743259@collegelacite.ca"

USER_AGENT = (
    "CoursCollecteDonnees-LaCite/1.0 (projet etudiant; "
    f"contact: {COURRIEL_YACINE}, {COURRIEL_MOUNCIF})"
)
DELAI_MINIMUM = 2.0          # secondes entre deux requêtes au même site (le cours exige au moins 1 s)
MAX_PAGES_PAR_SITE = 20      # garde-fou : jamais plus de 20 pages de liste par site

# ---------------------------------------------------------------------------
# Partie 1 du cours : question 1 (API officielle ou données ouvertes)
# À revérifier et à redater avant la remise.
# ---------------------------------------------------------------------------

VERIFICATION_API_MANUELLE = (
    "Aucune API officielle ni donnée ouverte trouvée (pied de page du site, ouvert.canada.ca, "
    "donneesquebec.ca ; vérifié le 2026-10-09). Seules des sources commerciales payantes existent."
)

# ---------------------------------------------------------------------------
# Les 18 sites validés
#   delai_robots : Crawl-delay relevé dans robots.txt le 2026-10-09 (None = aucun)
#   regles       : restrictions relevées dans robots.txt et les conditions d'utilisation
#   collecter    : False = site noté dans le journal mais jamais collecté (règle zéro risque)
# ---------------------------------------------------------------------------

_REGLES_MAGNETIS = "robots.txt : rien n'est bloqué. Conditions : usage personnel et non commercial."
_REGLES_D2C = ("robots.txt : Crawl-delay 5 s ; /used/detail.html et /json/ interdits (liste seulement). "
               "Conditions : usage personnel et non commercial.")
_REGLES_DILAWRI = "robots.txt : seuls /oops et /signalr/ bloqués. Aucune condition d'utilisation trouvée."
_REGLES_DILAWRI_BLOGUE = "robots.txt : /oops, /signalr/ et le blogue bloqués. Aucune condition d'utilisation trouvée."

SITES = [
    # --- Gatineau : plateforme Magnetis
    {"id": "hyundai_gatineau", "nom": "Hyundai Gatineau", "ville": "Gatineau", "province": "QC",
     "plateforme": "Magnetis", "delai_robots": None, "collecter": True,
     "url": "https://hyundaigatineau.ca/en/pre-owned", "regles": _REGLES_MAGNETIS},
    {"id": "gatineau_acura", "nom": "Gatineau Acura", "ville": "Gatineau", "province": "QC",
     "plateforme": "Magnetis", "delai_robots": None, "collecter": True,
     "url": "https://gatineauacura.com/en/pre-owned", "regles": _REGLES_MAGNETIS},
    {"id": "gatineau_kia", "nom": "Gatineau Kia", "ville": "Gatineau", "province": "QC",
     "plateforme": "Magnetis", "delai_robots": None, "collecter": True,
     "url": "https://www.gatineaukia.ca/en/pre-owned", "regles": _REGLES_MAGNETIS},
    # --- Gatineau : plateforme D2C Media
    {"id": "dupont_honda", "nom": "Dupont & Dupont Honda", "ville": "Gatineau", "province": "QC",
     "plateforme": "D2C Media", "delai_robots": 5, "collecter": True,
     "url": "https://www.dupontduponthonda.com/occasion/recherche.html", "regles": _REGLES_D2C},
    {"id": "hull_hyundai", "nom": "Hull Hyundai", "ville": "Gatineau (Hull)", "province": "QC",
     "plateforme": "D2C Media", "delai_robots": 5, "collecter": True,
     "url": "https://www.hullhyundai.com/occasion/recherche.html", "regles": _REGLES_D2C},
    {"id": "hull_nissan", "nom": "Hull Nissan", "ville": "Gatineau (Hull)", "province": "QC",
     "plateforme": "D2C Media", "delai_robots": 5, "collecter": True,
     "url": "https://www.hullnissangatineau.ca/occasion/recherche.html", "regles": _REGLES_D2C},
    {"id": "buckingham_gm", "nom": "Buckingham Chevrolet Buick GMC", "ville": "Gatineau (Buckingham)",
     "province": "QC", "plateforme": "D2C Media", "delai_robots": 5, "collecter": True,
     "url": "https://www.buckinghamgm.com/occasion/recherche.html", "regles": _REGLES_D2C},
    # --- Ottawa : plateforme EDealer (bloqué par Cloudflare : jamais collecté)
    {"id": "ottawa_honda", "nom": "Ottawa Honda", "ville": "Ottawa", "province": "ON",
     "plateforme": "EDealer", "delai_robots": None, "collecter": False,
     "url": "https://www.ottawahonda.com/inventory/used/",
     "regles": "robots.txt : /inventory/ permis ; URL avec filtres interdites sauf ?condition=USED. "
               "Aucune condition d'utilisation trouvée. Protégé par Cloudflare (403)."},
    # --- Ottawa : groupe Dilawri
    {"id": "bank_street_mazda", "nom": "Bank Street Mazda", "ville": "Ottawa", "province": "ON",
     "plateforme": "Dilawri", "delai_robots": None, "collecter": True,
     "url": "https://www.bankstreetmazda.com/ottawa-Mazda-dealer/used-cars/used-vehicle-inventory?type=U",
     "regles": _REGLES_DILAWRI},
    {"id": "bank_street_hyundai", "nom": "Bank Street Hyundai", "ville": "Ottawa", "province": "ON",
     "plateforme": "Dilawri", "delai_robots": None, "collecter": True,
     "url": "https://www.bankstreethyundai.com/ottawa-gloucester-hyundai-dealer/used-cars/used-vehicle-inventory?type=U",
     "regles": _REGLES_DILAWRI},
    {"id": "bank_street_kia", "nom": "Bank Street Kia", "ville": "Ottawa", "province": "ON",
     "plateforme": "Dilawri", "delai_robots": None, "collecter": True,
     "url": "https://www.bankstreetkia.com/ottawa-Kia-dealer/used-cars/used-vehicle-inventory?type=U",
     "regles": _REGLES_DILAWRI},
    {"id": "bank_street_mitsubishi", "nom": "Bank Street Mitsubishi", "ville": "Ottawa", "province": "ON",
     "plateforme": "Dilawri", "delai_robots": None, "collecter": True,
     "url": "https://www.bankstreetmitsubishi.com/ottawa-Mitsubishi-dealer/used-cars/used-vehicle-inventory?type=U",
     "regles": _REGLES_DILAWRI},
    {"id": "barrhaven_mazda", "nom": "Barrhaven Mazda", "ville": "Ottawa (Barrhaven)", "province": "ON",
     "plateforme": "Dilawri", "delai_robots": None, "collecter": True,
     "url": "https://www.barrhavenmazda.com/ottawa/used/inventory?type=U", "regles": _REGLES_DILAWRI},
    {"id": "barrhaven_cjdr", "nom": "Barrhaven Chrysler Jeep Dodge Ram", "ville": "Ottawa (Barrhaven)",
     "province": "ON", "plateforme": "Dilawri", "delai_robots": None, "collecter": True,
     "url": "https://www.barrhavenjeepdodgeram.com/used-vehicles/used-vehicle-inventory?type=U",
     "regles": _REGLES_DILAWRI},
    {"id": "dilawri_cjdr", "nom": "Dilawri Chrysler Jeep Dodge Ram", "ville": "Ottawa", "province": "ON",
     "plateforme": "Dilawri", "delai_robots": None, "collecter": True,
     "url": "https://www.dilawrichrysler.com/chrysler-jeep-dodge-ram-dealer-ottawa/used-cars/used-vehicle-inventory?type=U",
     "regles": _REGLES_DILAWRI},
    {"id": "orleans_mitsubishi", "nom": "Orleans Mitsubishi", "ville": "Ottawa (Orléans)", "province": "ON",
     "plateforme": "Dilawri", "delai_robots": None, "collecter": True,
     "url": "https://www.orleansmitsubishi.com/mitsubishi/used-inventory.html?type=U",
     "regles": _REGLES_DILAWRI_BLOGUE},
    {"id": "hyundai_hunt_club", "nom": "Hyundai On Hunt Club", "ville": "Ottawa (Nepean)", "province": "ON",
     "plateforme": "Dilawri", "delai_robots": None, "collecter": True,
     "url": "https://www.hyundaionhuntclub.com/hyundai/used~vehicles/inventory.html?type=U",
     "regles": _REGLES_DILAWRI},
    {"id": "kia_hunt_club", "nom": "Kia On Hunt Club", "ville": "Ottawa (Nepean)", "province": "ON",
     "plateforme": "Dilawri", "delai_robots": None, "collecter": True,
     "url": "https://www.kiaonhuntclub.com/kia/used-inventory.html?type=U", "regles": _REGLES_DILAWRI_BLOGUE},
]

# ---------------------------------------------------------------------------
# Sites écartés avant toute collecte (conditions d'utilisation)
# ---------------------------------------------------------------------------

SITES_EXCLUS = [
    {"site": "Toyota Gatineau", "url": "https://www.toyotagatineau.ca/fr/conditions-utilisation",
     "motif": "Conditions (plateforme SM360) : interdit « d'utiliser un robot, ou tout autre appareil, "
              "processus ou moyen automatique pour accéder au site Web »."},
    {"site": "Villa Toyota", "url": "https://www.villatoyota.com/fr/conditions-utilisation",
     "motif": "Mêmes conditions SM360 : robots interdits."},
    {"site": "Bel-Air Toyota", "url": "https://www.belairtoyota.ca/terms-conditions",
     "motif": "Conditions, section 12 : interdit de « spider, crawl, or scrape »."},
    {"site": "Car Canada", "url": "https://www.carcanada.com/terms-conditions",
     "motif": "Conditions, section 12 : interdit de « spider, crawl, or scrape »."},
    {"site": "Groupe Myers (16 concessionnaires)", "url": "https://www.myers.ca/terms-conditions",
     "motif": "Conditions, section 12 : interdit de « spider, crawl, or scrape »."},
]

# ---------------------------------------------------------------------------
# Partie 2 du cours : cas confirmés dans le navigateur (Microsoft Edge, F12), le 2026-10-09
# Règle du groupe : en cas de doute sur la légalité ou l'éthique, on ne collecte pas.
# Cas I (Scrapy) non retenu partout : volume faible (environ 60 pages), une boucle requests suffit.
# ---------------------------------------------------------------------------

CAS_CONFIRMES = {
    # --- Magnetis
    "hyundai_gatineau": "A + C + E1a (vérifié : 2 pages, lien ?vip=2 ; Ctrl+U : JSON-LD ItemList de "
                        "20 véhicules par page ; pages détail non utilisées, la liste suffit)",
    "gatineau_acura":   "A + E1a (même plateforme que Hyundai Gatineau ; une seule page, 29 fiches et "
                        "ItemList de 29 véhicules dans le HTML)",
    "gatineau_kia":     "A + C + E1a (même plateforme que Hyundai Gatineau ; lien ?vip=2, ItemList de "
                        "20 véhicules par page)",
    # --- D2C Media : seulement les fiches présentes dans le HTML
    "dupont_honda":     "A + H (36 fiches dans le HTML sur 38 annoncées ; les 2 autres ne sont accessibles "
                        "que par JavaScript ou par des chemins interdits : non collectées ; encodage iso-8859-1)",
    "hull_hyundai":     "A + H (HAR : aucune requête au défilement ; 39 fiches dans le HTML, seules collectées ; "
                        "pages détail et /json/ interdits par robots.txt ; encodage iso-8859-1)",
    "hull_nissan":      "A + H (12 fiches dans le HTML sur 12 annoncées : inventaire complet ; encodage iso-8859-1)",
    "buckingham_gm":    "A + H (HAR : 36 fiches dans le HTML, aucune requête au défilement ; la page charge "
                        "/js/json/chatboost/inventory/inventory-index.json (61 occasions et démos) : fichier "
                        "interne du chatbot, NON UTILISÉ PAR PRUDENCE car son usage par un robot n'est pas "
                        "clairement autorisé ; seules les 36 fiches du HTML sont collectées)",
    # --- EDealer
    "ottawa_honda":     "G (403 + défi Cloudflare « Just a moment » ; dans le navigateur, chargement lent = "
                        "vérification silencieuse ; ARRÊT, aucune tentative de contournement, site non collecté)",
    # --- Dilawri : pagination par les liens du HTML, sans JavaScript
    "bank_street_mazda":      "A + C (vérifié : défilement continu dans le navigateur, mais liens ?pindex= "
                              "présents dans le HTML ; on suit ces liens ; pages détail non utilisées)",
    "bank_street_hyundai":    "A + C (même plateforme que Bank Street Mazda ; liens ?pindex= dans le HTML)",
    "bank_street_kia":        "A + C (même plateforme ; liens ?pindex= ; tableaux détectés = calcul de "
                              "paiement : cas B écarté)",
    "bank_street_mitsubishi": "A + C (même plateforme ; liens ?pindex= ; cas B écarté, même raison)",
    "barrhaven_mazda":        "A + C (même plateforme ; liens ?pindex= dans le HTML)",
    "barrhaven_cjdr":         "A + C (même plateforme ; liens ?pindex= dans le HTML)",
    "dilawri_cjdr":           "A + C (même plateforme ; liens ?pindex= dans le HTML)",
    "orleans_mitsubishi":     "A + C (même plateforme ; liens ?pindex= ; cas B écarté, même raison)",
    "hyundai_hunt_club":      "A + C (même plateforme ; liens ?pindex= dans le HTML)",
    "kia_hunt_club":          "A + C (même plateforme ; liens ?pindex= ; cas B écarté ; JSON-LD illisible, "
                              "sans véhicules)",
}

# Technique retenue pour la collecte (colonne « technique » de l'annexe C)
TECHNIQUES = {
    "Magnetis":  "requests + BeautifulSoup + JSON-LD intégré ; pages ?vip= avec délai",
    "D2C Media": "requests + BeautifulSoup + JSON-LD intégré ; correction de l'encodage ; liste seulement",
    "Dilawri":   "requests + BeautifulSoup ; pages ?pindex= avec délai",
    "EDealer":   "Aucune (arrêt volontaire)",
}

# ---------------------------------------------------------------------------
# Colonnes des fichiers produits
# ---------------------------------------------------------------------------

COLONNES_JOURNAL = [
    # Annexe C
    "url", "cas_diagnostic", "cas_confirme", "technique", "nb_lignes", "problemes_remarques",
    # Identification
    "date", "id", "nom", "ville", "province", "plateforme",
    # Partie 1 : cadre légal et éthique
    "robots", "crawl_delay", "delai_utilise_s", "regles_site",
    "api_officielle_ou_donnees_ouvertes", "robots_chemins_api",
    # Partie 2 : diagnostic
    "statut", "recommandation", "protection", "signes_js", "json_integre", "json_ld_types",
    "json_ld_vehicules", "scripts_application_json", "adresses_api_dans_page", "blocs_repetes",
    "pagination", "page_suivante", "nb_tableaux", "taille_ko", "encodage", "alertes", "fichier_html",
    # Partie 3 : collecte
    "date_collecte", "pages_collectees", "fichier_csv",
]

COLONNES_VEHICULES = [
    "site_id", "concessionnaire", "ville", "province", "plateforme", "date_collecte",
    "url_page", "url_fiche", "id_annonce", "no_stock", "niv",
    "annee", "marque", "modele", "version", "etat",
    "prix_affiche", "rabais", "frais", "prix_final", "km",
    "transmission", "traction", "carburant", "moteur", "couleur_ext", "categorie",
]
