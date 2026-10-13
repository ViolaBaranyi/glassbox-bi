"""
Emberi nevek a felülethez: brazil államok, magyar termékkategóriák, a tényezők és a
modellek hétköznapi nyelvű leírása.

Az adat egy brazil online piactérről (Olist) származik: a kétbetűs kódok a brazil
SZÖVETSÉGI ÁLLAMOK hivatalos rövidítései (UF), nem országok. A termékkategóriák az
adathalmaz angol nevei (pl. health_beauty) — itt magyarul jelennek meg.

Csak megjelenítés: a modell és a lekérdezések továbbra is a kódokkal dolgoznak.
"""

from __future__ import annotations

import pandas as pd

# ------------------------------------------------------------- brazil államok
REGIONS = {
    "N": "Észak",
    "NE": "Északkelet",
    "CO": "Közép-Nyugat",
    "SE": "Délkelet",
    "S": "Dél",
}

# kód → (név, régió) — a 26 állam és a szövetségi főváros-kerület
STATES = {
    "AC": ("Acre", "N"),
    "AL": ("Alagoas", "NE"),
    "AP": ("Amapá", "N"),
    "AM": ("Amazonas", "N"),
    "BA": ("Bahia", "NE"),
    "CE": ("Ceará", "NE"),
    "DF": ("Szövetségi Kerület – Brasília", "CO"),
    "ES": ("Espírito Santo", "SE"),
    "GO": ("Goiás", "CO"),
    "MA": ("Maranhão", "NE"),
    "MT": ("Mato Grosso", "CO"),
    "MS": ("Mato Grosso do Sul", "CO"),
    "MG": ("Minas Gerais", "SE"),
    "PA": ("Pará", "N"),
    "PB": ("Paraíba", "NE"),
    "PR": ("Paraná", "S"),
    "PE": ("Pernambuco", "NE"),
    "PI": ("Piauí", "NE"),
    "RJ": ("Rio de Janeiro", "SE"),
    "RN": ("Rio Grande do Norte", "NE"),
    "RS": ("Rio Grande do Sul", "S"),
    "RO": ("Rondônia", "N"),
    "RR": ("Roraima", "N"),
    "SC": ("Santa Catarina", "S"),
    "SP": ("São Paulo", "SE"),
    "SE": ("Sergipe", "NE"),
    "TO": ("Tocantins", "N"),
}


# Egyszerűsített „négyzetrácsos térkép": minden állam egy egyforma négyzet (oszlop, sor),
# a helyük nagyjából a valódi elhelyezkedést követi (észak fent, nyugat balra; a szomszédos
# államok a rácson is szomszédosak, ahol ez megoldható). A kis és a nagy államok így
# egyformán látszanak — ezért nem kell hozzá térképfájl, és a felület internet nélkül is fut.
TILE_GRID = {
    "RR": (1, 0), "AP": (2, 0),
    "AM": (1, 1), "PA": (2, 1), "MA": (3, 1), "CE": (4, 1), "RN": (5, 1),
    "AC": (0, 2), "RO": (1, 2), "TO": (2, 2), "PI": (3, 2), "PE": (4, 2), "PB": (5, 2),
    "MT": (1, 3), "GO": (2, 3), "BA": (3, 3), "AL": (4, 3), "SE": (5, 3),
    "MS": (1, 4), "DF": (2, 4), "MG": (3, 4), "ES": (4, 4),
    "PR": (1, 5), "SP": (2, 5), "RJ": (3, 5),
    "SC": (1, 6),
    "RS": (1, 7),
}


def _missing(v) -> bool:
    try:
        return v is None or bool(pd.isna(v))
    except (TypeError, ValueError):
        return False


def state_name(code) -> str:
    """„Alagoas" — ismeretlen kódnál maga a kód."""
    if _missing(code):
        return "ismeretlen állam"
    code = str(code).strip().upper()
    return STATES[code][0] if code in STATES else code


def state_region(code) -> str:
    if _missing(code):
        return ""
    entry = STATES.get(str(code).strip().upper())
    return REGIONS[entry[1]] if entry else ""


def state_label(code) -> str:
    """„Alagoas (AL)" — a táblázatokban és az ábrákon."""
    if _missing(code):
        return "ismeretlen állam"
    code = str(code).strip().upper()
    return f"{STATES[code][0]} ({code})" if code in STATES else code


# --------------------------------------------------------- termékkategóriák
# Az Olist angol kategórianevei → magyarul (a „costruction" és „fashio" elírás az
# eredeti adatban van, a kulcs ezért így szerepel).
CATEGORIES = {
    "agro_industry_and_commerce": "mezőgazdaság, ipar és kereskedelem",
    "air_conditioning": "légkondicionálók",
    "art": "műalkotások",
    "arts_and_craftmanship": "kézművesség és hobbi",
    "audio": "hangtechnika",
    "auto": "autós termékek",
    "baby": "babatermékek",
    "bed_bath_table": "lakástextil (ágy, fürdő, asztal)",
    "books_general_interest": "könyvek (általános)",
    "books_imported": "import könyvek",
    "books_technical": "szakkönyvek",
    "cds_dvds_musicals": "CD-k, DVD-k, musicalek",
    "christmas_supplies": "karácsonyi kellékek",
    "cine_photo": "film- és fotótechnika",
    "computers": "számítógépek",
    "computers_accessories": "számítógép-tartozékok",
    "consoles_games": "játékkonzolok és videojátékok",
    "construction_tools_construction": "építőipari szerszámok",
    "construction_tools_lights": "világítás (építkezéshez)",
    "construction_tools_safety": "munkavédelmi eszközök",
    "cool_stuff": "trendi ajándéktárgyak",
    "costruction_tools_garden": "kerti szerszámok",
    "costruction_tools_tools": "kéziszerszámok",
    "dvds_blu_ray": "DVD- és Blu-ray-lemezek",
    "diapers_and_hygiene": "pelenkák és higiéniai termékek",
    "drinks": "italok",
    "electronics": "elektronika",
    "fashio_female_clothing": "női ruházat",
    "fashion_bags_accessories": "táskák és divatkiegészítők",
    "fashion_childrens_clothes": "gyerekruházat",
    "fashion_male_clothing": "férfiruházat",
    "fashion_shoes": "cipők",
    "fashion_sport": "sportruházat",
    "fashion_underwear_beach": "fehérnemű és strandruházat",
    "fixed_telephony": "vezetékes telefonok",
    "flowers": "virágok",
    "food": "élelmiszer",
    "food_drink": "étel és ital",
    "furniture_bedroom": "hálószobabútorok",
    "furniture_decor": "bútorok és lakásdekoráció",
    "furniture_living_room": "nappalibútorok",
    "furniture_mattress_and_upholstery": "matracok és kárpitos bútorok",
    "garden_tools": "kerti eszközök",
    "health_beauty": "egészség és szépségápolás",
    "home_appliances": "háztartási gépek",
    "home_appliances_2": "háztartási gépek (2. csoport)",
    "home_comfort_2": "lakáskomfort (2. csoport)",
    "home_confort": "lakáskomfort (párnák, takarók)",
    "home_construction": "lakásfelújítás",
    "housewares": "háztartási cikkek",
    "industry_commerce_and_business": "ipar, kereskedelem, üzlet",
    "kitchen_dining_laundry_garden_furniture": "konyhai, étkezőhöz, mosókonyhába és kertbe való bútorok",
    "la_cuisine": "konyhai eszközök (La Cuisine)",
    "luggage_accessories": "bőröndök és utazási kiegészítők",
    "market_place": "vegyes piactéri termékek",
    "music": "zene",
    "musical_instruments": "hangszerek",
    "office_furniture": "irodabútorok",
    "party_supplies": "partikellékek",
    "pc_gamer": "gamer számítógépek",
    "perfumery": "parfümök",
    "pet_shop": "kisállat-felszerelés",
    "portateis_cozinha_e_preparadores_de_alimentos": "hordozható konyhai kisgépek",
    "security_and_services": "biztonság és szolgáltatások",
    "signaling_and_security": "jelzőberendezések és biztonságtechnika",
    "small_appliances": "háztartási kisgépek",
    "small_appliances_home_oven_and_coffee": "kisgépek: sütők és kávéfőzők",
    "sports_leisure": "sport és szabadidő",
    "stationery": "írószerek és papíráru",
    "tablets_printing_image": "tabletek, nyomtatás, képalkotás",
    "telephony": "telefonok és tartozékok",
    "toys": "játékok",
    "watches_gifts": "órák és ajándékok",
    "ismeretlen": "ismeretlen kategória",
}


def category_name(code) -> str:
    """Magyar kategórianév; ismeretlen kódnál a kód olvashatóbb alakja."""
    if _missing(code) or str(code) in ("ismeretlen", "(ismeretlen)"):
        return CATEGORIES["ismeretlen"]
    code = str(code)
    return CATEGORIES.get(code, code.replace("_", " "))


# ------------------------------------------------- a tényezők hétköznapi nyelven
# A 21 megjelenítési tényező (a hónap két kódoló oszlopa egy tényező): mit jelent,
# és miért számíthat. Mindegyik a rendelés LEADÁSAKOR ismert adat.
PLAIN_INFO = {
    "tetel_szam": "Hány darab termék van a rendelésben.",
    "elado_szam": "Hány különböző eladótól (boltból) jön a rendelés. Több eladó több külön "
                  "csomagot jelent.",
    "kategoria_szam": "Hányféle termékkategória van a rendelésben.",
    "kosar_ertek": "A termékek ára összesen, brazil reálban (BRL).",
    "szallitasi_dij": "A szállításért fizetett díj összesen, brazil reálban (BRL).",
    "dij_arany": "A szállítási díj a termékek árához képest. Ha magas, a szállítás drága a "
                 "termékhez képest — például mert nehéz vagy messzire megy.",
    "tavolsag_km": "Az eladó és a vevő távolsága légvonalban. Közelítő érték: az irányítószám-"
                   "körzetek középpontja alapján számoljuk.",
    "suly_g": "A rendelésben lévő termékek összsúlya grammban.",
    "terfogat_cm3": "A rendelésben lévő termékek összes térfogata (cm³) — a csomag mérete.",
    "vallalt_ido_nap": "Hány napot ígért a webáruház a kézbesítésre a rendeléskor. Ehhez mérjük a "
                       "késést: ha a csomag az ígért nap után érkezik, a rendelés késett.",
    "honap": "Melyik hónapban adták le a rendelést. Csak két évnyi adatunk van, ezért ez inkább "
             "azt mutatja, mi történt abban a konkrét időszakban — nem biztos, hogy minden évben "
             "így lesz.",
    "het_napja": "A hét melyik napján adták le a rendelést.",
    "elado_korabbi_keses_arany": "Az eladó korábbi, már kézbesített rendeléseinek hány százaléka "
                                 "késett — csak azokból, amelyek a rendelés pillanatáig már "
                                 "megérkeztek.",
    "elado_korabbi_rendelesek": "Hány rendelést kapott már korábban az eladó — mennyire "
                                "tapasztalt.",
    "elado_atlagos_feladas_nap": "Az eladónak korábban átlagosan hány nap kellett ahhoz, hogy a "
                                 "csomagot átadja a futárnak.",
    "vevo_korabbi_rendelesek": "Hányszor rendelt már korábban ez a vevő.",
    "azonos_allam": "Ugyanabban a brazil államban van-e az eladó és a vevő.",
    "unnep_kozeli": "November 20. és december 31. között adták-e le a rendelést (Black Friday és "
                    "a karácsonyi csúcsidőszak).",
    "kategoria": "A rendelés legdrágább termékének kategóriája.",
    "elado_allam": "Melyik brazil államban van az eladó (a rendelés legdrágább termékéé).",
    "vevo_allam": "Melyik brazil államba megy a csomag.",
}

# ----------------------------------------------------- a modellek egy mondatban
MODEL_PLAIN = {
    "lightgbm": "sok kis „ha–akkor” döntési fa, amelyek egymás hibáit javítják — ez a felület "
                "fő modellje",
    "logreg": "egyszerű pontozás: minden tényező hozzáad vagy levon a kockázatból, mindig "
              "ugyanannyit",
    "dontesi_fa": "egyetlen „ha–akkor” kérdéssor (pl. ha a vállalt idő rövid és a vevő messze "
                  "van, akkor…)",
    "random_forest": "sok független döntési fa, amelyek „megszavazzák” a kockázatot",
}

# ------------------------------------------------------------ az időszakok
# A belső nevek (tanító / validációs / teszt) maradnak; a felület ezeket mutatja.
WINDOW_LABELS = {
    "tanító": "tanulási időszak",
    "validációs": "ellenőrző időszak",
    "teszt": "teszt-időszak",
}

WINDOW_PLAIN = {
    "tanító": "Ebből az időszakból tanult a modell.",
    "validációs": "A modell ebből nem tanult; a teszt előtti ellenőrzésre szolgált.",
    "teszt": "A modell ezt sosem látta tanulás közben: ezen mértük le, mennyire jó.",
}
