"""
spider_livres.py — Cas I : le même travail que le cas C, avec Scrapy.

Lancer :  scrapy runspider spider_livres.py -o livres_scrapy.csv
Autre point de départ : scrapy runspider spider_livres.py -a depart=https://... -o sortie.csv
Scrapy gère lui-même : robots.txt, délais, requêtes en parallèle, reprises, export.
"""

import scrapy

NOTES = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


class LivresSpider(scrapy.Spider):
    name = "livres"
    start_urls = ["https://books.toscrape.com/"]

    custom_settings = {
        "USER_AGENT": "CoursCollecteDonnees/1.0 (projet etudiant; contact: prenom.nom@exemple.ca)",
        "ROBOTSTXT_OBEY": True,          # respecte robots.txt
        "DOWNLOAD_DELAY": 1.0,           # 1 s entre deux requêtes au même site
        "AUTOTHROTTLE_ENABLED": True,    # ralentit si le serveur répond lentement
        "CONCURRENT_REQUESTS_PER_DOMAIN": 2,
        "CLOSESPIDER_PAGECOUNT": 60,     # garde-fou pour le projet
        "FEED_EXPORT_ENCODING": "utf-8-sig",
    }

    def __init__(self, depart=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if depart:
            self.start_urls = [depart]

    def parse(self, response):
        # Niveau 1 : la page de liste
        for livre in response.css("article.product_pod"):
            classes = livre.css("p.star-rating::attr(class)").get(default="").split()
            yield response.follow(
                livre.css("h3 a::attr(href)").get(),
                callback=self.parse_detail,
                cb_kwargs={
                    "titre": livre.css("h3 a::attr(title)").get(),
                    "note": next((NOTES[c] for c in classes if c in NOTES), None),
                },
            )
        # Pagination : response.follow gère les URL relatives
        suivante = response.css("li.next a::attr(href)").get()
        if suivante:
            yield response.follow(suivante, callback=self.parse)

    def parse_detail(self, response, titre, note):
        # Niveau 2 : la fiche détail
        infos = {
            ligne.css("th::text").get(): ligne.css("td::text").get()
            for ligne in response.css("table.table-striped tr")
        }
        yield {
            "titre": titre,
            "note": note,
            "prix": response.css("p.price_color::text").get(),
            "upc": infos.get("UPC"),
            "disponibilite": infos.get("Availability"),
            "categorie": response.css("ul.breadcrumb li:nth-child(3) a::text").get(),
            "url": response.url,
        }
