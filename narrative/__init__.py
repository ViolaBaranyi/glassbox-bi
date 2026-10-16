"""
Nyelvi réteg (M4, rendszerterv 14.): két szigorúan határolt nyelvimodell-hívás és a KAPU ②.

  client.py    vékony kliens: helyi Ollama vagy OpenAI-kompatibilis API, JSON-séma, napló
  to_spec.py   ① kérdés → QuerySpec (utána a KAPU ①, semantic/spec.py)
  to_text.py   ② eredmény → mondat, hely-kitöltéssel
  verifier.py  KAPU ② — a szöveg minden száma visszavezethető-e
  pipeline.py  a kettő egymás után, a determinisztikus réteggel középen

A modell a kérdésen kívül csak a metrikakatalógus kivonatát (①) és a lekérdezés eredményét
(②) látja; adatsort, adatbázist, modellt soha.
"""
