"""
Nyelvi réteg (M4, rendszerterv 14.): két szigorúan határolt nyelvimodell-hívás és a KAPU ②.

  client.py    vékony kliens: helyi Ollama vagy OpenAI-kompatibilis API, JSON-séma, napló
  to_spec.py   ① kérdés → QuerySpec (utána a KAPU ①, semantic/spec.py)
  idoszak.py   időkifejezések és idősor-szándék, determinisztikusan
  szotar.py    köznyelvi kategória-, régió- és mérőszám-szavak (v5)
  to_text.py   ② eredmény → mondat, hely-kitöltéssel
  verifier.py  KAPU ② — a szöveg minden száma visszavezethető-e
  pipeline.py  a kettő egymás után, a determinisztikus réteggel középen

A modell a kérdésen kívül csak a metrikakatalógus kivonatát (①) és a lekérdezés eredményét
(②) látja; adatsort, adatbázist, modellt soha.
"""

# A nyelvi réteg változata (a mérés fejléce rögzíti). v3: a lezárt K1 mérés kódja (okt. 16.,
# ujjlenyomat db97e252…); v4: a v3 mérésén látott hibák javítása (okt. 20.) — új kérdéseken mérve;
# v5: a v2 mérésén látott, modellmérettől független hibák kódbeli javítása (okt. 22.) — idősor-szándék,
# évszakos és összevető időszakok, köznyelvi szótár, két lépés elutasítása, „az 5 legforgalmasabb
# állam …” két lépésben, a 2. kapun a jelzett kerekítés („kb. 59%”); a v3 kérdéssoron mérendő.
VERZIO = "v5"
