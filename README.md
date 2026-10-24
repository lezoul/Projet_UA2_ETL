# Projet UA2 : web scraping des véhicules d'occasion (Ottawa-Gatineau)

**Cours :** Collecte et nettoyage des données (projet UA2), Collège La Cité
**Groupe :** Yacine Lezoul (2748526) et Mouncif Bouchachi (2743259)
**Remise :** lundi 2 novembre 2026, 22 h

Collecte quotidienne de l'inventaire de véhicules d'occasion de 17 concessionnaires d'Ottawa-Gatineau,
dans le respect de robots.txt, des conditions d'utilisation et d'une règle « zéro risque » : ce qui est
interdit, ou dont on ne peut pas être sûrs que c'est permis, n'est pas fait. Les données collectées sont
nettoyées, complétées par le décodage officiel du NIV (API vPIC de la NHTSA) et fusionnées en tables
prêtes pour l'analyse et Power BI.

**Usage strictement pédagogique.** Ce dépôt est privé ; les données ne sont ni publiées ni exploitées
en dehors de ce travail.

## Résultats

| Élément | Valeur |
|---|---|
| Sites retenus | 18 validés : 17 collectés, 1 arrêté au diagnostic (protection Cloudflare, aucun contournement) |
| Sites écartés | 5 sites ou groupes, avant toute collecte (conditions d'utilisation interdisant les robots) |
| Collecte du 2026-10-22 | 801 véhicules (230 à Gatineau, 571 à Ottawa) |
| Source officielle complémentaire | API vPIC de la NHTSA : décodage du NIV (carburant, catégorie, traction) |
| Fréquence | une fois par jour, à 3 h (Planificateur de tâches de Windows) |

## Organisation

```
Projet_UA2_ETL/
├── notebook/
│   ├── 01_collecte.ipynb          # parties 0 à 3 : préparation, éthique, diagnostic, collecte ; paragraphe par URL
│   └── 02_pretraitement.ipynb     # nettoyage, complément par le NIV, fusion, tables pour Power BI
├── src/
│   ├── config.py                  # tous les réglages : chemins, User-Agent, délais, sites, règles de nettoyage
│   ├── diagnostic.py              # parties 1 et 2 : URL sans doublons, cas A à I, API, journal de tests
│   ├── extraction.py              # partie 3 : 3 lecteurs de page, une fonction d'extraction pour tous les sites
│   ├── enrichissement.py          # décodage des nouveaux NIV par l'API officielle vPIC (cache)
│   ├── pretraitement.py           # fichiers bruts -> observations quotidiennes + véhicules consolidés
│   ├── pipeline.py                # tout le projet en une commande (mode automatique avec log)
│   ├── projet_scraping.py         # boîte à outils fournie par le cours
│   ├── scraper.py                 # exemple fourni par le cours (référence)
│   └── spider_livres.py           # exemple Scrapy fourni par le cours (référence)
├── scripts/
│   ├── collecte_quotidienne.bat   # lanceur appelé chaque nuit par le Planificateur de tâches
│   └── installer_tache.ps1        # inscrit le lanceur dans le Planificateur (3 h par défaut)
├── resultats/
│   ├── brut/                      # {site}_{AAAA-MM-JJ}.csv : un fichier par site et par jour
│   ├── vehicules_brut_AAAA-MM-JJ.csv   # tous les véhicules d'une collecte
│   ├── historique_collectes.csv        # une ligne par site et par collecte (jamais écrasé)
│   ├── journal_tests.csv               # journal de tests (annexe C)
│   ├── niv_decodes_vpic.csv            # cache des NIV décodés (chaque NIV une seule fois)
│   ├── observations_quotidiennes.csv   # 1 ligne = 1 véhicule, 1 site, 1 jour
│   ├── vehicules_occasion_consolide.csv # 1 ligne = 1 véhicule (NIV)
│   ├── concessionnaires.csv            # 1 ligne = 1 site (dimension Power BI)
│   └── rapport_qualite.csv             # contrôles de qualité
├── pages_brutes/                  # HTML du diagnostic (non publié)
├── logs/                          # un log par exécution automatique (non publié)
├── README.md
├── requirements.txt
└── .gitignore
```

## Installation (Windows, PowerShell)

Python 3.13.14 ou plus récent est nécessaire : avant cette version, `urllib.robotparser` peut déclarer
permise une page interdite par robots.txt.

```
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m ipykernel install --user --name projet-scraping --display-name "Python (projet-scraping)"
```

## Utilisation

**Avec les notebooks** : ouvrir `notebook/01_collecte.ipynb` puis `notebook/02_pretraitement.ipynb` dans VS Code,
choisir le noyau « Python (projet-scraping) », puis **Run All**.

**En ligne de commande**, depuis la racine du projet :

```
.venv\Scripts\python.exe src\pipeline.py                                     # diagnostic, collecte, enrichissement, prétraitement
.venv\Scripts\python.exe src\pipeline.py --etapes collecte                   # collecte seulement
.venv\Scripts\python.exe src\pipeline.py --etapes pretraitement              # prétraitement seulement, aucune requête
.venv\Scripts\python.exe src\pipeline.py --etapes enrichissement pretraitement # décoder les NIV puis recalculer
.venv\Scripts\python.exe src\pipeline.py --sites hull_nissan bank_street_kia # certains sites seulement
```

**Collecte quotidienne** (une seule fois, dans un PowerShell ouvert à la racine du projet) :

```
Unblock-File .\scripts\installer_tache.ps1
.\scripts\installer_tache.ps1
```

La tâche lance chaque jour à 3 h `scripts\collecte_quotidienne.bat`, qui exécute la collecte, le décodage
des nouveaux NIV puis le prétraitement et écrit un log daté dans `logs\`. Si l'ordinateur est éteint à 3 h, la tâche s'exécute à la
prochaine ouverture de session. Pour la retirer : `.\scripts\installer_tache.ps1 -Desinstaller`.

## Règles éthiques appliquées

- User-Agent identifiable avec nos deux courriels ; au moins 2 s entre deux requêtes au même site, 5 s chez
  D2C Media (Crawl-delay) ; 20 pages au plus par site.
- robots.txt revérifié avant chaque page ; pages de liste seulement, jamais de page détail ni d'API interne.
- Arrêt immédiat devant un blocage (403, Cloudflare, CAPTCHA), sans aucune tentative de contournement.
- Aucun renseignement personnel : seulement des faits sur les véhicules (année, modèle, prix, kilométrage, NIV).
- Sites écartés et motifs : `config.SITES_EXCLUS` ; cas confirmés site par site : `config.CAS_CONFIRMES`.
- Décodage du NIV par l'API officielle vPIC de la NHTSA (gratuite, données ouvertes au public) : lots de 50 NIV,
  2 s entre deux lots, la nuit comme le demande la NHTSA, chaque NIV envoyé une seule fois (cache). Seules les
  cases vides sont complétées, avec leur origine notée ; la couleur n'est pas codée dans le NIV.
