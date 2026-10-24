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
FICHIER_HISTORIQUE = DOSSIER_RESULTATS / "historique_collectes.csv"   # une ligne par site et par collecte
DOSSIER_LOGS = RACINE / "logs"                   # un fichier de log par exécution automatique

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
# Pied de page de chaque site vérifié le 2026-10-09 ; portails de données ouvertes revérifiés le 2026-10-22.
# À redater si on revérifie avant la remise.
# ---------------------------------------------------------------------------

VERIFICATION_API_MANUELLE = (
    "Aucune API officielle ni donnée ouverte trouvée (pied de page du site vérifié le 2026-10-09 ; "
    "ouvert.canada.ca et donneesquebec.ca revérifiés le 2026-10-22). Seules des sources commerciales "
    "payantes existent (services de collecte revendus, places de marché). Pour le décodage du NIV, "
    "l'API officielle vPIC de la NHTSA existe et est utilisée (voir la section Enrichissement plus bas)."
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

# ---------------------------------------------------------------------------
# Prétraitement (notebook 02_pretraitement.ipynb et src/pretraitement.py)
# Toutes les règles de nettoyage sont ici, visibles et modifiables sans toucher au code.
# ---------------------------------------------------------------------------

# Fichiers produits par le prétraitement (dans resultats/)
FICHIER_OBSERVATIONS = DOSSIER_RESULTATS / "observations_quotidiennes.csv"      # 1 ligne = 1 véhicule, 1 site, 1 jour
FICHIER_VEHICULES = DOSSIER_RESULTATS / "vehicules_occasion_consolide.csv"      # 1 ligne = 1 véhicule (NIV)
FICHIER_CONCESSIONNAIRES = DOSSIER_RESULTATS / "concessionnaires.csv"           # 1 ligne = 1 site (table de dimension)
FICHIER_QUALITE = DOSSIER_RESULTATS / "rapport_qualite.csv"                     # contrôles de qualité

# Groupe propriétaire de chaque site. Les 10 sites d'Ottawa appartiennent au Groupe Dilawri
# (même plateforme, mentions « Dilawri » sur les sites). Pour Gatineau, aucune information
# vérifiée : on écrit « Non déterminé » plutôt que de deviner (règle zéro risque, aussi pour les données).
GROUPE_PAR_DEFAUT = "Non déterminé"
GROUPES = {s["id"]: "Groupe Dilawri" for s in SITES if s["plateforme"] == "Dilawri"}

# Collectes connues comme incomplètes : gardées dans les observations (avec collecte_complete = False),
# mais exclues du calcul des statuts « nouveau » et « retiré » (sinon : faux nouveaux et faux retraits).
COLLECTES_INCOMPLETES = [
    {"plateforme": "Dilawri", "jour": "2026-10-09",
     "raison": "Tri par défaut différent de la pagination : environ 12 véhicules manqués par site "
               "(corrigé le 2026-10-22, fonction meme_ordre)."},
]

# Format d'un NIV valide : 17 caractères, sans I, O ni Q (norme ISO 3779)
MOTIF_NIV = r"[A-HJ-NPR-Z0-9]{17}"

# Seuils des contrôles de qualité
KM_MINIMUM_PLAUSIBLE = 100     # moins de 100 km sur un véhicule de plus de 2 ans : suspect
AGE_MINIMUM_KM_SUSPECT = 2     # (une démo récente avec 10 km est normale)

# Harmonisation des valeurs : (motif, valeur harmonisée). Le motif est une expression régulière
# cherchée dans le texte en minuscules ; la PREMIÈRE règle qui correspond gagne (l'ordre compte).
# Une valeur qu'aucune règle ne reconnaît devient « Non reconnu » et apparaît dans rapport_qualite.csv.

# « etat » mélange deux informations selon la plateforme : l'état (occasion ou démo) chez Magnetis
# et D2C, la disponibilité (en stock ou en arrivage) chez Dilawri. On les sépare en deux colonnes.
REGLES_ETAT = [
    (r"d[ée]mo", "Démo"),
    (r"occasion|used|pre-?owned|in.?stock|incoming", "Occasion"),   # pages « occasion » seulement
]
REGLES_DISPONIBILITE = [
    (r"incoming|arrivage|transit", "En arrivage"),
    (r"in.?stock|en stock", "En stock"),
]

REGLES_TRANSMISSION = [
    (r"manu|^man\b|^man\.", "Manuelle"),
    (r"auto|cvt|variation continue", "Automatique"),   # une CVT est une boîte automatique
]

REGLES_TRACTION = [
    (r"awd|int[ée]grale|all.?wheel", "Intégrale (AWD)"),
    (r"4\s*[x×]\s*4|4wd|4 roues motrices", "4x4"),
    (r"fwd|traction avant|front", "Avant (FWD)"),
    (r"rwd|propulsion|4\s*[x×]\s*2|rear", "Arrière (RWD)"),
]

REGLES_CARBURANT = [
    (r"hybrid", "Hybride"),
    (r"[ée]lectri|electric|\bev\b", "Électrique"),
    (r"diesel", "Diesel"),
    (r"essence|gas", "Essence"),
]

REGLES_CATEGORIE = [
    (r"suv|vus|utilitaire sport|crossover", "VUS"),
    (r"cargo|commercia", "Fourgon utilitaire"),
    (r"passenger van|minivan|fourgonnette", "Fourgonnette"),
    (r"regular side|pickup|pick-up|camion|truck|\bcab\b", "Camionnette"),
    (r"sedan|berline|hatchback|coupe|coupé|convertible|cabriolet|wagon|familiale|autos?$", "Automobile"),
]

REGLES_COULEUR = [            # famille de couleur, à partir du nom commercial (souvent tronqué)
    (r"noir|black|ebony|onyx|midnight", "Noir"),
    (r"blanc|white|snow|wind chill|alpine|blizzard|powder", "Blanc"),
    (r"rouge|red\b|maroon|crimson|bordeaux|chili|lava", "Rouge"),
    (r"bleu|blue|navy|denim|\bbl$", "Bleu"),          # « bl » : nom tronqué par le site
    (r"vert|green", "Vert"),
    (r"brun|brown|bronze|copper|cuivre", "Brun"),
    (r"orange", "Orange"),
    (r"jaune|yellow", "Jaune"),
    (r"beige|sable|sand", "Beige"),
    (r"argent|silver|lunaire", "Argent"),
    (r"gris|grey|gray|graphite|steel|granite|anvil|titan|cement|magnetic|gravity|carbon|acier", "Gris"),
]

# Marques : une seule écriture par marque (ACURA, Acura -> Acura). Clé en majuscules.
MARQUES = {
    "ACURA": "Acura", "HYUNDAI": "Hyundai", "INFINITI": "Infiniti", "FIAT": "Fiat",
    "RAM": "RAM", "GMC": "GMC", "BMW": "BMW", "MERCEDES-BENZ": "Mercedes-Benz",
    "ALFA ROMEO": "Alfa Romeo", "MINI": "MINI",
}

# ---------------------------------------------------------------------------
# Enrichissement par le NIV : API officielle vPIC de la NHTSA (src/enrichissement.py)
# Vérifié le 2026-10-23 sur https://vpic.nhtsa.dot.gov/About et la FAQ de l'API :
#   - service public du département des Transports des États-Unis, données déclarées par les
#     constructeurs (49 CFR Part 565), « freely used by the public », gratuit, sans inscription ;
#   - contrôle automatique du trafic ; les gros traitements par lots sont demandés la nuit (heure de l'Est) :
#     notre collecte de 3 h respecte cette demande ;
#   - couvre les véhicules homologués pour la vente aux États-Unis (modèle 1981 et plus récents).
# Le NIV ne contient pas la couleur : elle ne peut pas être complétée par cette source.
# ---------------------------------------------------------------------------

URL_VPIC = "https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/"
FICHIER_NIV_DECODES = DOSSIER_RESULTATS / "niv_decodes_vpic.csv"   # cache : chaque NIV n'est décodé qu'une fois
TAILLE_LOT_VPIC = 50          # maximum de la méthode DecodeVINValuesBatch
DELAI_VPIC = 2.0              # secondes entre deux lots, comme pour les sites
MAX_LOTS_VPIC = 40            # garde-fou : au plus 2 000 NIV par exécution

# Champs de vPIC conservés -> nom de colonne dans le cache
CHAMPS_VPIC = {
    "FuelTypePrimary": "vpic_carburant",
    "FuelTypeSecondary": "vpic_carburant_secondaire",
    "ElectrificationLevel": "vpic_electrification",
    "BodyClass": "vpic_carrosserie",
    "DriveType": "vpic_traction",
    "ErrorCode": "vpic_code_erreur",
}

# Carburant à partir de vPIC : on lit « électrification | carburant principal », électrification d'abord,
# car un hybride a « Gasoline » comme carburant principal et « Strong HEV » comme électrification.
REGLES_CARBURANT_VPIC = [
    (r"hybrid|\bhev\b|phev", "Hybride"),
    (r"\bbev\b|battery electric|^\s*\|\s*electric", "Électrique"),
    (r"diesel", "Diesel"),
    (r"gasoline|ethanol|flex", "Essence"),
]
# Carrosserie et traction de vPIC : mêmes règles que pour les sites (REGLES_CATEGORIE, REGLES_TRACTION).
