import streamlit as st
import requests
import numpy as np
import pandas as pd
import datetime
import plotly.graph_objects as go

# ================================================================
# KONSTANTY — Ceníky, sazby, profily 2026
# ================================================================

# ================================================================
# CENÍKOVÉ TABULKY 2026
# ================================================================


# ================================================================
# CENY ELEKTŘINY 2026 — kompletní cena kWh s DPH (Kč/MWh)
# = silová elektřina + distribuce + systémové služby + daň z elektřiny
# POZE = 0 Kč/MWh od 1.1.2026 (hradí stát)
#
# Zdroj: TZB-info srovnání cen 2026 (publikováno 29.12.2025)
#   ČEZ Prodej — standardní produkt (ne "na dobu neurčitou"!)
#   E.ON Energie — produktová řada Elektřina platná 1.1.2026
#   PRE — PRE PROUD KLASIK platný 1.11.2025
# ================================================================
CENY_VT = {
    #  Kč/MWh s DPH — VT (vysoký tarif)
    "ČEZ Distribuce": {"D01d": 7320,"D02d": 6610,"D25d": 6920,"D26d": 5650,"D27d": 6920,
                       "D35d": 5410,"D45d": 5410,"D56d": 5410,"D57d": 5410,"D61d": 8050},
    "EG.D (E.ON)":    {"D01d": 7050,"D02d": 6550,"D25d": 6650,"D26d": 5430,"D27d": 6650,
                       "D35d": 4270,"D45d": 4270,"D56d": 4270,"D57d": 4270,"D61d": 7720},
    "PREdistribuce":  {"D01d": 5980,"D02d": 5570,"D25d": 5620,"D26d": 4840,"D27d": 5620,
                       "D35d": 3910,"D45d": 3910,"D56d": 3910,"D57d": 3910,"D61d": 6770},
}
CENY_NT = {
    #  Kč/MWh s DPH — NT (nízký tarif)
    "ČEZ Distribuce": {"D25d":4070,"D26d":4070,"D27d":4020,"D35d":4390,
                       "D45d":4390,"D56d":4390,"D57d":4390,"D61d":4200},
    "EG.D (E.ON)":    {"D25d":3830,"D26d":3830,"D27d":3830,"D35d":3830,
                       "D45d":3830,"D56d":3830,"D57d":3830,"D61d":3830},
    "PREdistribuce":  {"D25d":3590,"D26d":3590,"D27d":3590,"D35d":3590,
                       "D45d":3590,"D56d":3590,"D57d":3590,"D61d":3590},
}
# Stálý plat za odběrné místo (Kč/měs s DPH) — obchodní + nesíťová infrastruktura
STAY_PLAT={"ČEZ Distribuce":179,"EG.D (E.ON)":160,"PREdistribuce":157}
# ================================================================
# CENÍKY JISTIČŮ 2026 — skutečné fixní ceny dle rozsahů (s DPH)
# Zdroj: oficiální ceníky ČEZ, EG.D a PREdistribuce platné 1.1.2026
#
# JISTIC_3x25  = cena jističe 3×25A (základ pro byt) dle sazby
# JISTIC_BYT   = cena individuálního jističe bytu dle velikosti
# JISTIC_DUM   = skutečné fixní ceny jističů pro SVJ/dům (sazba D02d)
#                Klíč = ampéry (25,32,40,50,63,80,100,125)
# JISTIC_DUM_A = přírůstek Kč za každý 1A nad 3×63A (pro velké jističe)
# ================================================================

JISTIC_3x25={
    # Ceny za jistič 3×25A dle distribuční sazby — Kč/měs s DPH (2026)
    "ČEZ Distribuce":{"D01d":132,"D02d":298,"D25d":287,"D26d":422,"D27d":272,"D35d":517,"D45d":567,"D56d":567,"D57d":568,"D61d":238},
    "EG.D (E.ON)":   {"D01d":121,"D02d":303,"D25d":296,"D26d":422,"D27d":282,"D35d":575,"D45d":575,"D56d":575,"D57d":572,"D61d":271},
    "PREdistribuce": {"D01d":162,"D02d":359,"D25d":557,"D26d":1262,"D27d":529,"D35d":1545,"D45d":1545,"D56d":1545,"D57d":1545,"D61d":525},
}

# Jistič na byt (individuální odběrné místo) — Kč/měs s DPH 2026
# Zdroj: ceník ČEZ/EGD/PRE domácnosti kategorie D
JISTIC_BYT = {
    "ČEZ Distribuce": {"1×25A":132, "3×16A":190, "3×20A":238, "3×25A":298, "3×32A":381},
    "EG.D (E.ON)":    {"1×25A":121, "3×16A":193, "3×20A":242, "3×25A":303, "3×32A":387},
    "PREdistribuce":  {"1×25A":132, "3×16A":190, "3×20A":230, "3×25A":287, "3×32A":360},
}

# Skutečné fixní ceny jističů pro dům/SVJ — kategorie D (domácnost) — Kč/měs s DPH 2026
# Zdroj: ERÚ cenový výměr 14/2025, usetreno.cz k 10.2.2026
JISTIC_DUM = {
    "ČEZ Distribuce": {10:121,  16:191,  20:240,  25:309,  32:383,
                       40:479,  50:600,  63:751,  80:869, 100:989},
    "EG.D (E.ON)":    {10:116,  16:186,  20:232,  25:290,  32:373,
                       40:465,  50:581,  63:729,  80:845, 100:961},
    "PREdistribuce":  {10:106,  16:169,  20:213,  25:266,  32:339,
                       40:424,  50:530,  63:667,  80:773, 100:879},
}
# Přírůstek Kč/A nad max. hodnotu v tabulce (D tarif)
JISTIC_DUM_A = {
    "ČEZ Distribuce": 5.99,
    "EG.D (E.ON)":    5.81,
    "PREdistribuce":  5.30,
}

# ================================================================
# JISTIC_DUM_C — JOM/SVJ jako PODNIKATEL (kategorie C) — Kč/měs s DPH 2026
# SVJ po přechodu na JOM se stane podnikatelem → platí C02d ceník!
# C tarif má výrazně vyšší cenu jističe než D tarif (ČEZ +46-52%, PRE viz tabulka)
#
# Zdroj:
#   ČEZ C02d: ceník cpienergo.com platný 1.1.2026 (Kč bez DPH × 1.21)
#   EGD C02d: ERÚ výměr 14/2025 — EGD nerozlišuje D/C pro jistič, stejné jako D
#   PRE C02d: ceník ztenergy.cz platný 1.1.2026 (přímo s DPH)
# ================================================================
JISTIC_DUM_C = {
    "ČEZ Distribuce": {16:286,  20:358,  25:450,  32:572,
                       40:715,  50:894,  63:1145, 80:1265, 100:1384, 125:1549, 160:1788},
    "EG.D (E.ON)":    {10:116,  16:186,  20:232,  25:290,  32:373,   # stejné jako D
                       40:465,  50:581,  63:729,  80:845,  100:961},
    "PREdistribuce":  {10:144,  16:230,  20:288,  25:359,  32:460,
                       40:575,  50:719,  63:905,  80:1150, 100:1437, 125:1797, 160:2300},
}
# Přírůstek Kč/A nad max. hodnotu v tabulce (C tarif)
JISTIC_DUM_C_A = {
    "ČEZ Distribuce": 14.88,  # distribuce C02d koef s DPH
    "EG.D (E.ON)":     5.81,  # stejné jako D
    "PREdistribuce":  14.37,  # z ceníku PRE C02d
}


def _cena_jistice_dum(dist, sazba, ampery=63, c_tarif=False):
    """Vrátí měsíční cenu jističe domu (Kč/měs s DPH).

    c_tarif=True → použije C tarif ceník (pro JOM/SVJ jako podnikatel).
    c_tarif=False → D tarif (pro stávající stav — individuální byty).
    """
    if c_tarif:
        tab   = JISTIC_DUM_C.get(dist, JISTIC_DUM_C["ČEZ Distribuce"])
        amp_a = JISTIC_DUM_C_A.get(dist, 14.88)
    else:
        tab   = JISTIC_DUM.get(dist, JISTIC_DUM["ČEZ Distribuce"])
        amp_a = JISTIC_DUM_A.get(dist, 5.99)
    klice = sorted(tab.keys())
    for k in klice:
        if ampery <= k:
            return tab[k]
    # Nad max. hodnotou v tabulce — lineární přírůstek
    max_k = klice[-1]
    return round(tab[max_k] + (ampery - max_k) * amp_a)

def _jistic_dum_ampery(pocet_bytu, zarizeni):
    """Odhadne velikost hlavního jističe JOM (patka domu) v ampérech.

    Empirická tabulka dle praxe distributorů — odpovídá typickým
    rezervovaným příkonům SVJ.

    Sloupce (priorita shora dolů):
      elektrokotel/akum — přímotopy, akumulační kamna, elektrokotel
      TČ                — tepelné čerpadlo jako hlavní zdroj tepla
      bojler            — elektrický ohřev TUV (D25d)
      sporák            — indukce / elektrický sporák
      základní          — jen svícení, spotřebiče, plyn/dálkové teplo

    Byty  | Základní | Sporák | Bojler | TČ     | Elektrokotel/akum
    ------+----------+--------+--------+--------+------------------
    ≤10   |  3×32A   | 3×40A  | 3×40A  | 3×63A  | 3×80A
    ≤20   |  3×40A   | 3×50A  | 3×63A  | 3×80A  | 3×100A
    ≤30   |  3×50A   | 3×63A  | 3×80A  | 3×100A | 3×125A
    ≤50   |  3×63A   | 3×80A  | 3×100A | 3×125A | 3×160A
    ≤100  |  3×80A   | 3×100A | 3×125A | 3×160A | 3×200A
    ≤150  |  3×100A  | 3×125A | 3×160A | 3×200A | 3×250A
    ≤200  |  3×125A  | 3×160A | 3×200A | 3×250A | 3×315A
    >200  |  3×160A  | 3×200A | 3×250A | 3×315A | 3×400A
    """
    pb = int(pocet_bytu)
    has_ek  = "primotop" in zarizeni or "akum" in zarizeni  # elektrokotel/akumulák
    has_tc  = "tc"       in zarizeni
    has_boj = "bojler"   in zarizeni
    has_sp  = "sporak"   in zarizeni

    # Tabulka: (max_bytu, zaklad, sporak, bojler, tc, elektrokotel)
    _TAB = [
        ( 10,  32,  40,  40,  63,  80),
        ( 20,  40,  50,  63,  80, 100),
        ( 30,  50,  63,  80, 100, 125),
        ( 50,  63,  80, 100, 125, 160),
        (100,  80, 100, 125, 160, 200),
        (150, 100, 125, 160, 200, 250),
        (200, 125, 160, 200, 250, 315),
        (999, 160, 200, 250, 315, 400),
    ]

    for max_b, z, sp, boj, tc, ek in _TAB:
        if pb <= max_b:
            if has_ek:  return ek
            if has_tc:  return tc
            if has_boj: return boj
            if has_sp:  return sp
            return z

    return 160  # fallback

def _jistic_byt_typ(zarizeni):
    """Odhadne typický jistič bytu."""
    if "tc" in zarizeni or "primotop" in zarizeni or "akum" in zarizeni:
        return "3×32A"
    if "sporak" in zarizeni:
        return "3×25A"
    return "1×25A"
SAZBY_NT=["D25d","D26d","D27d","D35d","D45d","D56d","D57d","D61d"]
PODIL_NT={"D25d":0.35,"D26d":0.35,"D27d":0.35,"D35d":0.60,"D45d":0.70,"D56d":0.75,"D57d":0.75,"D61d":0.40}
POPIS_SAZEB={
    "D01d":"Malý byt — jen svícení","D02d":"Standardní domácnost",
    "D25d":"Ohřev vody bojlerem (8h NT)","D26d":"Akumulační kamna (8h NT)",
    "D27d":"Elektromobil (8h NT)","D35d":"Hybridní TČ (16h NT)",
    "D45d":"Přímotopy/elektrokotel (20h NT)","D56d":"Vytápění TČ/přímotopy (22h NT)",
    "D57d":"TČ — hlavní zdroj tepla (20h NT)","D61d":"Víkendový objekt",
}
PROFILY={
    "mix":       {"nazev":"👨‍👩‍👧 Smíšený dům",       "popis":"Mix pracujících a seniorů"},
    "seniori":   {"nazev":"👴 Převaha seniorů",     "popis":"Více doma přes den — vyšší využití FVE"},
    "pracujici": {"nazev":"🏢 Převaha pracujících", "popis":"Většina pryč přes den"},
    "rodiny":    {"nazev":"👨‍👩‍👧‍👦 Rodiny s dětmi",    "popis":"Doma odpoledne a víkendy"},
    "provozovna":{"nazev":"🏪 S provozovnou",       "popis":"Vysoká spotřeba přes den"},
}

# ================================================================
# UI


# ================================================================
# ENGINE — TDD profily, simulace, cashflow, geocoding
# ================================================================

import numpy as np
import pandas as pd
import datetime
import plotly.graph_objects as go


# ================================================================
# OTE TDD4 PROFILY — normalizované na průměr = 1.0/hodinu
# Zdroj: OTE ČR — Typové diagramy dodávek elektřiny (TDD4)
# ================================================================

_TDD4 = {
    "zima_prac":       np.array([0.412,0.371,0.348,0.339,0.343,0.377,0.524,0.784,0.883,0.819,0.762,0.741,0.758,0.738,0.717,0.739,0.820,1.118,1.284,1.222,1.082,0.917,0.718,0.551],dtype=float),
    "prechodne_prac":  np.array([0.395,0.355,0.333,0.325,0.329,0.366,0.500,0.730,0.822,0.768,0.719,0.699,0.717,0.697,0.676,0.698,0.778,1.037,1.181,1.119,0.989,0.837,0.648,0.496],dtype=float),
    "leto_prac":       np.array([0.378,0.339,0.319,0.311,0.316,0.356,0.476,0.676,0.761,0.718,0.676,0.657,0.676,0.656,0.636,0.657,0.737,0.957,1.079,1.017,0.897,0.757,0.578,0.441],dtype=float),
    "zima_vikend":     np.array([0.451,0.404,0.375,0.364,0.366,0.384,0.420,0.552,0.752,0.901,0.950,0.938,0.901,0.860,0.820,0.820,0.879,1.047,1.148,1.098,0.978,0.818,0.648,0.521],dtype=float),
    "prechodne_vikend":np.array([0.423,0.379,0.352,0.341,0.343,0.360,0.398,0.524,0.713,0.858,0.904,0.893,0.858,0.819,0.780,0.780,0.838,0.997,1.094,1.044,0.929,0.778,0.615,0.490],dtype=float),
    "leto_vikend":     np.array([0.396,0.355,0.329,0.319,0.321,0.337,0.377,0.497,0.675,0.816,0.859,0.848,0.816,0.778,0.741,0.741,0.797,0.948,1.040,0.991,0.881,0.738,0.582,0.458],dtype=float),
}
for _k in _TDD4: _TDD4[_k] = _TDD4[_k] / _TDD4[_k].mean()

_TDD_SP = {
    "zima_prac":       np.array([0.55,0.52,0.50,0.50,0.50,0.55,0.75,0.95,0.85,0.75,0.72,0.72,0.72,0.72,0.75,0.85,0.95,1.10,1.15,1.10,1.00,0.90,0.75,0.62],dtype=float),
    "prechodne_prac":  np.array([0.50,0.47,0.45,0.45,0.45,0.50,0.70,0.88,0.78,0.70,0.67,0.67,0.67,0.67,0.70,0.78,0.88,1.00,1.05,1.00,0.91,0.81,0.68,0.56],dtype=float),
    "leto_prac":       np.array([0.45,0.42,0.40,0.40,0.40,0.45,0.65,0.80,0.72,0.65,0.62,0.62,0.62,0.62,0.65,0.72,0.80,0.90,0.95,0.90,0.82,0.72,0.60,0.50],dtype=float),
    "zima_vikend":     np.array([0.58,0.54,0.52,0.51,0.51,0.54,0.62,0.78,0.90,0.95,0.95,0.93,0.90,0.88,0.85,0.88,0.92,1.05,1.10,1.05,0.95,0.85,0.72,0.63],dtype=float),
    "prechodne_vikend":np.array([0.53,0.49,0.47,0.46,0.46,0.49,0.57,0.72,0.82,0.88,0.88,0.86,0.82,0.80,0.78,0.80,0.84,0.97,1.01,0.97,0.88,0.78,0.66,0.58],dtype=float),
    "leto_vikend":     np.array([0.48,0.44,0.42,0.41,0.41,0.44,0.52,0.65,0.75,0.80,0.80,0.78,0.75,0.73,0.71,0.73,0.77,0.88,0.92,0.88,0.80,0.71,0.60,0.52],dtype=float),
}
for _k in _TDD_SP: _TDD_SP[_k] = _TDD_SP[_k] / _TDD_SP[_k].mean()

_UPRAVY = {
    # Průměr přes všechny domácnosti — bez úpravy
    "mix":        np.ones(24, dtype=float),

    # Důchodci / home office — doma celý den
    # Dopolední plateau 9–14h (vaří, TV, počítač), mírný odpolední propad,
    # večerní špička 18–20h nižší než u pracujících
    "seniori":    np.array([0.7,0.6,0.6,0.6,0.6,0.7,0.8,1.0,1.2,1.4,1.5,1.5,
                             1.4,1.4,1.3,1.3,1.2,1.2,1.3,1.2,1.1,1.0,0.9,0.8], dtype=float),

    # Pracující — pryč 8–17h, ale ne úplně nulová spotřeba (lednice, hot standby)
    # Ranní špička 7–8h, příchod 17h, večerní špička 18–21h
    "pracujici":  np.array([0.8,0.7,0.7,0.7,0.7,0.8,1.1,1.4,0.6,0.4,0.4,0.4,
                             0.4,0.4,0.4,0.6,0.9,1.4,1.6,1.5,1.3,1.1,0.9,0.8], dtype=float),

    # Rodiny s dětmi — ráno spěch, děti doma v poledne, večer všichni doma
    "rodiny":     np.array([0.8,0.7,0.7,0.7,0.7,0.8,1.1,1.3,0.9,0.7,0.7,0.8,
                             0.9,0.8,0.9,1.1,1.2,1.3,1.4,1.3,1.2,1.0,0.9,0.8], dtype=float),

    # Provozovna — kancelář/obchod, spotřeba přes pracovní dobu
    "provozovna": np.array([0.5,0.5,0.5,0.5,0.5,0.6,0.8,1.1,1.5,1.7,1.8,1.8,
                             1.7,1.7,1.7,1.6,1.4,1.1,0.8,0.6,0.6,0.5,0.5,0.5], dtype=float),
}
for _k in _UPRAVY:
    _UPRAVY[_k] = _UPRAVY[_k] / _UPRAVY[_k].mean()


def _smiseny_profil(pct_pracujici, pct_seniori, pct_rodiny):
    """
    Sestaví vážený průměr úpravového profilu dle složení SVJ.
    Vstupy jsou procenta (0–100), součet nemusí být přesně 100
    — normalizujeme. Zbytek do 100 % = mix (průměr OTE).
    """
    total = float(pct_pracujici + pct_seniori + pct_rodiny)
    p_prac = float(pct_pracujici) / 100.0
    p_sen  = float(pct_seniori)   / 100.0
    p_rod  = float(pct_rodiny)    / 100.0
    p_mix  = max(0.0, 1.0 - p_prac - p_sen - p_rod)

    uprava = (p_prac * _UPRAVY["pracujici"]
            + p_sen  * _UPRAVY["seniori"]
            + p_rod  * _UPRAVY["rodiny"]
            + p_mix  * _UPRAVY["mix"])
    mean = uprava.mean()
    return uprava / mean if mean > 0 else uprava

# NT hodiny dle sazby (set hodin kdy platí nízký tarif)
NT_HODINY = {
    "D25d": set(list(range(22,24))+list(range(0,6))),
    "D26d": set(list(range(22,24))+list(range(0,6))),
    "D27d": set(list(range(22,24))+list(range(0,6))),
    "D35d": set(list(range(22,24))+list(range(0,6))+list(range(10,14))),
    "D45d": set(range(24)),
    "D56d": set(range(24)),
    "D57d": set(list(range(22,24))+list(range(0,6))+list(range(10,14))),
    "D61d": set(list(range(22,24))+list(range(0,8))),
}

_CD = 365 * 96
_MESICE = ["Led","Úno","Bře","Dub","Kvě","Čvn","Čvc","Srp","Zář","Říj","Lis","Pro"]

# ── TDD profily zařízení ──────────────────────────────────────────
# Klimatizace — přes den v létě (překrývá se s FVE!)
_TDD_KLIMA = np.array([0.10,0.10,0.10,0.10,0.10,0.10,0.20,0.50,0.90,1.30,1.70,
                        2.00,2.00,1.80,1.60,1.40,1.10,0.80,0.50,0.30,0.20,0.15,0.12,0.10],dtype=float)
_TDD_KLIMA = _TDD_KLIMA / _TDD_KLIMA.mean()

# NT profil rovnoměrný (bojler, EV) — jen v NT hodinách
# Použijeme existující _gen_profil_nt

# Sezónní váhy pro každé zařízení (zima/prechodne/leto)
_VAHY_ZAR = {
    "zaklad":   {"zima":0.35,"prechodne":0.34,"leto":0.31},
    "sporak":   {"zima":0.35,"prechodne":0.34,"leto":0.31},
    "bojler":   {"zima":0.35,"prechodne":0.33,"leto":0.32},
    "klima":    {"zima":0.05,"prechodne":0.20,"leto":0.75},
    "akum":     {"zima":0.60,"prechodne":0.38,"leto":0.02},
    "primotop": {"zima":0.65,"prechodne":0.33,"leto":0.02},
    "tc":       {"zima":0.55,"prechodne":0.30,"leto":0.15},
    "ev":       {"zima":0.35,"prechodne":0.33,"leto":0.32},
}

# Spotřeba VT a NT na byt/rok pro každé zařízení (kWh)
_SP_ZAR = {
    "zaklad":   {"vt":1200,"nt":0,   "nazev":"☑️ Svícení, spotřebiče, pračka, sušička","sazba":None},
    "sporak":   {"vt":400, "nt":0,   "nazev":"🍳 Elektrický sporák / indukce","sazba":None},
    "bojler":   {"vt":0,   "nt":800, "nazev":"🚿 Bojler — ohřev TUV elektřinou","sazba":"D25d"},
    "klima":    {"vt":400, "nt":0,   "nazev":"❄️ Klimatizace (chlazení v létě)","sazba":None},
    "akum":     {"vt":0,   "nt":2000,"nazev":"🔥 Akumulační kamna (topení)","sazba":"D26d"},
    "primotop": {"vt":0,   "nt":2500,"nazev":"⚡ Přímotopy / elektrokotel","sazba":"D45d"},
    "tc":       {"vt":0,   "nt":3000,"nazev":"♨️ Tepelné čerpadlo (vytápění + TUV)","sazba":"D57d"},
    "ev":       {"vt":0,   "nt":1500,"nazev":"🚗 Elektromobil (dobíjení doma)","sazba":"D27d"},
}

def _doporucena_sazba(zarizeni):
    """Doporučí sazbu dle vybraných zařízení."""
    if "tc"      in zarizeni: return "D57d"
    if "primotop"in zarizeni: return "D45d"
    if "akum"    in zarizeni: return "D26d"
    if "ev"      in zarizeni and "bojler" not in zarizeni: return "D27d"
    if "bojler"  in zarizeni or "ev" in zarizeni: return "D25d"
    return "D02d"

def _doporuceny_jistic(pocet_bytu, zarizeni):
    """Doporučí velikost hlavního jističe SVJ (patka domu).
    Individuální jistič bytu (1×25A) se nemění — to si řeší každý byt zvlášť.
    Hlavní jistič SVJ = pro společné prostory nebo JOM (celý dům).
    Pro JOM závisí na celkové spotřebě domu.
    """
    has_tc     = "tc"       in zarizeni
    has_primo  = "primotop" in zarizeni
    has_akum   = "akum"     in zarizeni
    has_sporak = "sporak"   in zarizeni
    has_bojler = "bojler"   in zarizeni
    has_ev     = "ev"       in zarizeni
    pb = int(pocet_bytu)

    # TČ pro celý dům — velký příkon
    if has_tc:
        if pb <= 8:    return "3×50A", 5
        elif pb <= 16: return "3×63A", 6
        else:          return "3×63A", 6

    # Přímotopy nebo akumulační kamna
    if has_primo or has_akum:
        if pb <= 6:    return "3×40A", 4
        elif pb <= 12: return "3×50A", 5
        else:          return "3×63A", 6

    # Indukce + bojler (typická plně elektrická domácnost)
    if has_sporak and has_bojler:
        if pb <= 8:    return "3×32A", 3
        elif pb <= 16: return "3×40A", 4
        elif pb <= 24: return "3×50A", 5
        else:          return "3×63A", 6

    # Jen indukce nebo jen bojler/EV
    if has_sporak or has_bojler or has_ev:
        if pb <= 12:   return "3×32A", 3
        elif pb <= 24: return "3×40A", 4
        else:          return "3×50A", 5

    # Základní — svícení, spotřebiče, pračka (bez vaření elektřinou)
    # Většina panelových domů — plynové vaření, dálkové teplo
    if pb <= 10:   return "3×25A", 2
    elif pb <= 20: return "3×32A", 3
    elif pb <= 40: return "3×40A", 4
    elif pb <= 60: return "3×50A", 5
    else:          return "3×63A", 6

    # Základní — jen svícení, spotřebiče, pračka, sušička
    # 1×25A pro malé domy, 3×25A pro větší
    if pb <= 3:   return "1×25A", 0
    elif pb <= 20: return "3×25A", 2
    else:          return "3×32A", 3

def _sp_z_zarizeni(zarizeni, pocet_bytu):
    """Vypočítá celkovou VT a NT spotřebu domu dle výběru zařízení."""
    vt = sum(_SP_ZAR[z]["vt"] for z in zarizeni if z in _SP_ZAR) * float(pocet_bytu)
    nt = sum(_SP_ZAR[z]["nt"] for z in zarizeni if z in _SP_ZAR) * float(pocet_bytu)
    return vt/1000.0, nt/1000.0  # MWh/rok


def _sp_sp_vypocet(pocet_bytu, pocet_pater, ma_vytah, pocet_vytahu,
                   ma_tuv_central, ma_tc_dum, pocet_ev_nabijec,
                   pocet_cerpadel=0):
    """
    Vypočítá roční spotřebu a parametry společných prostor (SP).

    Vzorce:
      Osvětlení:   patra × 200 + byty × 2 + 100 kWh/rok
      Výtah:       3000 kWh/výtah × (1 + patra/20)   [základ 3000 kWh]
      Čerpadla:    800 kWh/čerpadlo × (1 + patra/30)  [oběhová čerpadla]
      TUV central: 800 kWh/byt/rok (NT)
      TČ domu:     3000 kWh/byt/rok (NT)
      EV nabíječky:1500 kWh/nabíječka/rok (NT)

    Jistič SP — dle příkonu zařízení:
      Výtah 7.5 kW + čerpadla 0.25 kW × N + osvětlení → odpovídá ampérům
    """
    pb = int(pocet_bytu)
    pp = int(pocet_pater)
    pv = int(pocet_vytahu)
    pc = int(pocet_cerpadel)

    # --- VT spotřeba ---
    sp_osvetleni = pp * 200 + pb * 2 + 100          # kWh/rok
    sp_vytah     = (3000 * pv * (1 + pp / 20.0)
                    if ma_vytah else 0.0)             # kWh/rok
    # Oběhová čerpadla — topná sezóna září–květen = 8 měsíců = 67 % roku
    # Základ 800 kWh/čerpadlo/rok při celoroční práci → 800×0.67 = 536 kWh/rok
    # Korekce na počet pater (delší rozvody = vyšší příkon)
    sp_cerpadla  = (536 * pc * (1 + pp / 30.0)
                    if pc > 0 else 0.0)               # kWh/rok (VT)
    sp_vt = sp_osvetleni + sp_vytah + sp_cerpadla

    # --- NT spotřeba ---
    sp_tuv = 800  * pb if ma_tuv_central else 0.0   # kWh/rok
    sp_tc  = 3000 * pb if ma_tc_dum      else 0.0   # kWh/rok
    sp_ev  = 1500 * int(pocet_ev_nabijec)            # kWh/rok
    sp_nt  = sp_tuv + sp_tc + sp_ev

    sp_celkem = sp_vt + sp_nt  # kWh/rok

    # --- Sazba SP ---
    if ma_tc_dum:
        sazba_sp = "D57d"
    elif ma_tuv_central:
        sazba_sp = "D25d"
    else:
        sazba_sp = "D02d"

    # --- Jistič SP — dle součtu příkonů zařízení ---
    # Výtah: 7.5 kW/výtah, čerpadlo: 0.25 kW, osvětlení: ~1 kW, TUV/TČ: velký příkon
    P_sp_kw = (pv * 7.5 if ma_vytah else 0.0) + pc * 0.25 + 1.0
    if ma_tc_dum:
        P_sp_kw += pb * 3.0   # TČ domu — velký příkon
    elif ma_tuv_central:
        P_sp_kw += pb * 0.5   # bojler přes NT — menší soudobý příkon
    if pocet_ev_nabijec > 0:
        P_sp_kw += pocet_ev_nabijec * 7.4  # 7.4 kW / nabíječka (wallbox)

    # Proud SP: P / (√3 × 0.4 kV)
    import math
    I_sp = P_sp_kw * 1000 / (math.sqrt(3) * 400)
    _std = [25, 32, 40, 50, 63, 80, 100]
    jistic_sp_a = next((j for j in _std if j >= I_sp), 100)
    jistic_sp   = f"3×{jistic_sp_a}A"

    # --- Přehled položek ---
    popis = []
    popis.append(f"Osvětlení chodeb: {sp_osvetleni:.0f} kWh/rok")
    if ma_vytah:
        popis.append(f"Výtah ({pv}×): {sp_vytah:.0f} kWh/rok")
    if pc > 0:
        popis.append(f"Oběhová čerpadla ({pc}×): {sp_cerpadla:.0f} kWh/rok")
    if ma_tuv_central:
        popis.append(f"Centrální TUV: {sp_tuv:.0f} kWh/rok (NT)")
    if ma_tc_dum:
        popis.append(f"TČ domu: {sp_tc:.0f} kWh/rok (NT)")
    if pocet_ev_nabijec > 0:
        popis.append(f"EV nabíječky ({pocet_ev_nabijec}×): {sp_ev:.0f} kWh/rok (NT)")

    return {
        "sp_mwh":      sp_celkem / 1000.0,
        "sp_vt_mwh":   sp_vt     / 1000.0,
        "sp_nt_mwh":   sp_nt     / 1000.0,
        "sazba_sp":    sazba_sp,
        "jistic_sp":   jistic_sp,
        "jistic_sp_a": jistic_sp_a,
        "popis":       popis,
        "P_sp_kw":     P_sp_kw,   # pro debug/zobrazení
        "I_sp_a":      round(I_sp, 1),
    }


def _sezona(m):
    if m in [11,12,1,2]: return "zima"
    if m in [5,6,7,8]: return "leto"
    return "prechodne"


def _tdd4_klic(sezona, vikend):
    """Bezpečný výběr TDD4 klíče bez f-stringu."""
    tp = "vikend" if vikend else "prac"
    if sezona == "zima" and not vikend:    return "zima_prac"
    if sezona == "zima" and vikend:        return "zima_vikend"
    if sezona == "leto" and not vikend:    return "leto_prac"
    if sezona == "leto" and vikend:        return "leto_vikend"
    if sezona == "prechodne" and not vikend: return "prechodne_prac"
    if sezona == "prechodne" and vikend:   return "prechodne_vikend"
    return "prechodne_prac"


def _gen_profil_vt(kwh, tdd, uprava=None):
    """Generuje 15min profil VT spotřeby."""
    vals = []
    den = datetime.date(2026,1,1)
    for _ in range(365):
        sz = _sezona(den.month)
        vi = den.weekday() >= 5
        klic = _tdd4_klic(sz, vi) if tdd is _TDD4 else (
            "zima_prac" if sz=="zima" and not vi else
            "zima_vikend" if sz=="zima" else
            "leto_prac" if sz=="leto" and not vi else
            "leto_vikend" if sz=="leto" else
            "prechodne_prac" if not vi else "prechodne_vikend"
        )
        p = tdd[klic].copy()
        if uprava is not None:
            p = p * uprava; p = p / p.mean()
        for h in range(24):
            v = float(p[h]) / 4.0
            vals.extend([v,v,v,v])
        den += datetime.timedelta(days=1)
    arr = np.array(vals,dtype=float)[:_CD]
    if arr.sum() > 0: arr = arr * (float(kwh) / arr.sum())
    return arr


def _gen_profil_nt(kwh, sazba):
    """Generuje 15min profil NT spotřeby — jen v NT hodinách."""
    nt_h = NT_HODINY.get(sazba, set())
    if not nt_h or kwh <= 0:
        return np.zeros(_CD, dtype=float)
    vals = []
    for _ in range(365):
        for h in range(24):
            v = 1.0 / 4.0 if h in nt_h else 0.0
            vals.extend([v,v,v,v])
    arr = np.array(vals,dtype=float)[:_CD]
    if arr.sum() > 0: arr = arr * (float(kwh) / arr.sum())
    return arr


def _gen_vyroba_fallback(kwp, sklon=35, azimut=0):
    vh = np.zeros(8760,dtype=float)
    for h in range(8760):
        dr=h//24; hod=h%24
        uhel=2*np.pi*(dr-80)/365.0
        delka=12+4.5*np.sin(uhel)
        vychod=12-delka/2; zapad=12+delka/2
        if vychod<=hod<=zapad:
            t=(hod-vychod)/delka; elev=np.sin(np.pi*t)
            sezon=max(0.3,min(1.0,0.5+0.5*np.sin(uhel+np.pi/2)))
            koef=1.0+0.15*np.sin(np.pi*float(sklon)/90.0)
            vh[h]=float(kwp)*elev*sezon*koef*0.85
    if vh.sum()>0: vh=vh*(float(kwp)*1050.0/vh.sum())
    return vh


def _interpoluj(hod):
    """
    Převede hodinová data (8760 hodnot) na 15minutová (35040 hodnot).

    Pro výrobu FVE: každou hodinovou hodnotu rozdělíme na 4 stejné 15min díly
    (každý = 1/4 hodinové hodnoty). To zachovává energii přesně.

    Lineární interpolace mezi hodinami by byla nepřesná pro FVE — způsobuje
    záporné hodnoty při přechodu noc→ráno a ráno→noc.
    Numpy repeat je rychlejší a energeticky konzervativní.
    """
    h = np.array(hod, dtype=float)
    # Každou hodinovou hodnotu rozděl na 4 čtvrthodinové díly (energie = h/4 kWh per 15min)
    res = np.repeat(h, 4) / 4.0
    return res[:_CD]


def _simuluj(vyroba_15, sp_vt15, sp_nt15, bat=0.0, model="edc", edc_ztrata=0.0):
    """
    Přesná 15min simulace FVE s oddělenou VT a NT spotřebou.
    Baterie: nabíjí se z přetoků FVE (VT), vybíjí do NT spotřeby.
    """
    v   = np.array(vyroba_15, dtype=float)
    svt = np.array(sp_vt15,   dtype=float)
    snt = np.array(sp_nt15,   dtype=float)
    bat = float(bat)

    # Pro model "spolecne" — NT je nulová (společné prostory NT nemají)
    if model == "spolecne":
        snt = np.zeros(len(v), dtype=float)

    n = int(min(len(v), len(svt), len(snt)))
    v, svt, snt = v[:n], svt[:n], snt[:n]

    bmin, bmax, bkwh = bat*0.10, bat*0.90, bat*0.50
    eta = 0.92

    vl_vt  = np.zeros(n, dtype=float)  # vlastní spotřeba z FVE (VT)
    vl_nt  = np.zeros(n, dtype=float)  # vlastní spotřeba z baterie (NT)
    pr     = np.zeros(n, dtype=float)  # přetoky do sítě
    od_vt  = np.zeros(n, dtype=float)  # odběr ze sítě VT
    od_nt  = np.zeros(n, dtype=float)  # odběr ze sítě NT

    for i in range(n):
        vi   = float(v[i])
        svti = float(svt[i])
        snti = float(snt[i])

        # 1. FVE pokryje VT spotřebu přímo
        prime = min(vi, svti)
        vl_vt[i] = prime
        zbyla_v = vi - prime
        zbyla_svt = svti - prime

        # 2. Přebytek výroby → nabít baterii
        if zbyla_v > 0.0 and bat > 0.0:
            nab = min(zbyla_v * eta, bmax - bkwh)
            bkwh += nab
            zbyla_v -= nab / eta

        # 3. Zbylá výroba → přetoky
        pr[i] = zbyla_v

        # 4. Zbylá VT spotřeba → vybít baterii (VT tarif = dražší → priorita!)
        if zbyla_svt > 0.0 and bat > 0.0:
            dos = (bkwh - bmin) * eta
            vyb = min(zbyla_svt, dos)
            bkwh -= vyb / eta
            zbyla_svt -= vyb
            vl_vt[i] += vyb  # z baterie do VT spotřeby → úspora VT cena

        # 5. Zbylá VT spotřeba → ze sítě
        od_vt[i] = zbyla_svt

        # 6. NT spotřeba → vybít zbylou baterii (VT spotřeba měla prioritu)
        if snti > 0.0 and bat > 0.0:
            dos = (bkwh - bmin) * eta
            vyb = min(snti, dos)
            bkwh -= vyb / eta
            snti -= vyb
            vl_nt[i] = vyb

        # 7. Zbylá NT spotřeba → ze sítě
        od_nt[i] = snti

    tv   = float(v.sum())
    tvl  = float(vl_vt.sum()) + float(vl_nt.sum())
    tpr  = float(pr.sum())
    tsp  = float(svt.sum()) + float(snt.sum())

    # EDC — dynamická efektivita sdílení
    # Míra časového překryvu výroby a spotřeby (bez baterie)
    # = kolik % výroby FVE nastane ve stejný čas jako poptávka domu
    # Nezávislé na baterii, max 100 %
    casovy_prekryv = float(np.minimum(v[:n], (svt+snt)[:n]).sum()) / float(v[:n].sum()) if float(v[:n].sum()) > 0 else 1.0
    casovy_prekryv = min(1.0, casovy_prekryv)  # cap na 100%
    edc_efektivita = casovy_prekryv  # přejmenováno pro zpětnou kompatibilitu

    if model == "edc":
        # Aplikuj uživatelsky nastavitelnou ztrátu sdílení
        if edc_ztrata > 0:
            korekce = 1.0 - float(edc_ztrata) / 100.0
            tvl *= korekce
            tpr = tv - tvl

    mv,ms,mvl,mpr = [],[],[],[]
    for m in range(12):
        a,b = m*30*96, min((m+1)*30*96,n)
        mv.append(float(v[a:b].sum()))
        ms.append(float(svt[a:b].sum())+float(snt[a:b].sum()))
        mvl.append(float(vl_vt[a:b].sum())+float(vl_nt[a:b].sum()))
        mpr.append(float(pr[a:b].sum()))

    return {
        "vlastni_vt_kwh":  float(vl_vt.sum()),
        "vlastni_nt_kwh":  float(vl_nt.sum()),
        "vlastni_kwh":     tvl,
        "pretoky_kwh":     tpr,
        "odber_vt_kwh":    float(od_vt.sum()),
        "odber_nt_kwh":    float(od_nt.sum()),
        "vyroba_kwh":      tv,
        "spotreba_kwh":    tsp,
        "mira_vs":         tvl/tv  if tv>0  else 0.0,
        "mira_sob":        min(1.0, tvl/tsp) if tsp>0 else 0.0,  # max 100%
        "edc_efektivita":  edc_efektivita,
        "mesice_vyroba":   mv,
        "mesice_spotreba": ms,
        "mesice_vlastni":  mvl,
        "mesice_pretoky":  mpr,
    }


def _cashflow(vl_vt, vl_nt, pr, cvt, cnt, cpr,
              vlast, uver, spl, splat,
              rust=3.0, deg=0.5, leta=25, jist=0.0, bonus=0.0, deg_bat=2.0):
    res=[]; kum=-(float(vlast)+float(uver)-float(bonus))
    for rok in range(1,int(leta)+1):
        d=(1.0-float(deg)/100.0)**(rok-1)
        d_bat=(1.0-float(deg_bat)/100.0)**(rok-1)  # degradace baterie
        c=(1.0+float(rust)/100.0)**(rok-1)
        # NT úspora z baterie degraduje rychleji než panely
        u = (float(vl_vt)*d*float(cvt)*c +
             float(vl_nt)*d_bat*float(cnt)*c +
             float(pr)*d*float(cpr)*c +
             float(jist)*c)
        s = float(spl) if rok<=int(splat) else 0.0
        kum += u-s
        res.append({"rok":rok,
                    "vyroba_mwh":round((float(vl_vt)+float(vl_nt)+float(pr))*d/1000.0,2),
                    "vlastni_mwh":round((float(vl_vt)+float(vl_nt))*d/1000.0,2),
                    "pretoky_mwh":round(float(pr)*d/1000.0,2),
                    "uspora_vt":round(float(vl_vt)*d*float(cvt)*c),
                    "uspora_nt":round(float(vl_nt)*d*float(cnt)*c),
                    "uspora_pretoky":round(float(pr)*d*float(cpr)*c),
                    "uspora_jom":round(float(jist)*c),
                    "uspora_fve":round(float(vl_vt)*d*float(cvt)*c +
                                       float(vl_nt)*d*float(cnt)*c +
                                       float(pr)*d*float(cpr)*c),
                    "uspora_celkem":round(u),
                    "splatka":round(s),
                    "cisty_prinos":round(u-s),
                    "kumulativni":round(kum),
                    "cena_vt":round(float(cvt)*c,3)})
    return res


@st.cache_data(ttl=300)
def _geocode_search(dotaz):
    """Hledá lokality pro našeptávání."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{dotaz}, Česká republika", "format":"json",
                    "limit":5, "addressdetails":1, "countrycodes":"cz"},
            headers={"User-Agent":"FVE-SVJ-Kalkulacka/1.0"},
            timeout=5)
        if r.status_code == 200 and r.text.strip():
            return r.json()
    except: pass
    return []


@st.cache_data(ttl=3600)
def _geocode(dotaz):
    _FB = {
        "praha":(50.08,14.44),"brno":(49.19,16.61),"ostrava":(49.83,18.29),
        "plzeň":(49.74,13.37),"třinec":(49.68,18.67),"liberec":(50.77,15.06),
        "olomouc":(49.59,17.25),"zlín":(49.22,17.66),"znojmo":(48.86,16.05),
        "hradec králové":(50.21,15.83),"pardubice":(50.04,15.78),
        "české budějovice":(48.97,14.47),"ústí nad labem":(50.66,14.03),
        "havířov":(49.78,18.43),"karviná":(49.85,18.54),"opava":(49.94,17.90),
        "frýdek-místek":(49.68,18.35),"jihlava":(49.40,15.59),
    }
    try:
        r=requests.get("https://nominatim.openstreetmap.org/search",
                       params={"q":f"{dotaz}, Česká republika","format":"json",
                               "limit":1,"addressdetails":1,"countrycodes":"cz"},
                       headers={"User-Agent":"FVE-SVJ-Kalkulacka/1.0"},timeout=10)
        if r.status_code==200 and r.text.strip():
            res=r.json()
            if res:
                addr=res[0].get("address",{})
                m=(addr.get("road","") + " " + addr.get("house_number","")).strip()
                m = m or addr.get("city") or addr.get("town") or addr.get("village") or dotaz
                return float(res[0]["lat"]),float(res[0]["lon"]),m,None
    except: pass
    klic=dotaz.lower().strip().split(",")[0].strip()
    if klic in _FB: return _FB[klic][0],_FB[klic][1],dotaz,None
    return None,None,None,"Nenalezeno — zkuste jiný formát adresy"


@st.cache_data(ttl=86400, show_spinner=False)
def _pvgis(lat, lon, kwp, sklon, azimut):
    """
    Stáhne hodinová TMY data výroby FVE z PVGIS API (EU JRC).

    Speciální hodnoty azimut:
      999 = V+Z  → dvě volání: −90° (východ) + +90° (západ), každé s kwp/2
      998 = JZ+JV → dvě volání: −45° (JV)   + +45° (JZ),    každé s kwp/2
    Výsledky se sečtou → reálný tvar se dvěma ranními/večerními kopci.

    Standardní hodnoty: 0=Jih, −90=Východ, +90=Západ (PVGIS konvence)
    Cache: 24 hodin.
    Returns: (array 8760 hodnot v kWh/h, error_string nebo None)
    """
    def _jedno(az, vykon):
        r = requests.get(
            "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc",
            params={
                "lat": float(lat), "lon": float(lon),
                "peakpower": float(vykon), "loss": 14,
                "angle": int(sklon), "aspect": int(az),
                "outputformat": "json", "browser": 0,
                "pvcalculation": 1, "pvtechchoice": "crystSi",
                "mountingplace": "building", "trackingtype": 0,
                "usehorizon": 1, "tmy": 1,
            },
            timeout=30
        )
        r.raise_for_status()
        return np.array(
            [float(h["P"]) / 1000.0 for h in r.json()["outputs"]["hourly"]],
            dtype=float
        )[:8760]

    try:
        if azimut == 999:
            # V+Z: polovina na východ, polovina na západ
            return _jedno(-90, kwp / 2.0) + _jedno(90, kwp / 2.0), None
        elif azimut == 998:
            # JZ+JV: polovina na JV (−45°), polovina na JZ (+45°)
            return _jedno(-45, kwp / 2.0) + _jedno(45, kwp / 2.0), None
        else:
            return _jedno(azimut, kwp), None
    except Exception as e:
        return None, str(e)


def _gen_vyroba_den(kwp, sezona, pocasi):
    koef = {"jasno":1.0,"polojasno":0.5,"zatazeno":0.15}[pocasi]
    intenzita = {"zima":0.220,"prechodne":0.408,"leto":0.647}[sezona]
    delka = {"zima":8.0,"prechodne":12.0,"leto":15.0}[sezona]
    vychod=12-delka/2; zapad=12+delka/2
    v=np.zeros(96,dtype=float)
    for i in range(96):
        h=i/4.0
        if vychod<=h<=zapad:
            t=(h-vychod)/delka; elev=np.sin(np.pi*t)
            v[i]=float(kwp)*elev*intenzita*koef*0.85*0.25
    return v


def _gen_spotreba_den(kwh_rok, sezona, profil, vikend=False):
    klic = _tdd4_klic(sezona, vikend)
    uprava = _UPRAVY.get(str(profil), np.ones(24,dtype=float))
    p = _TDD4[klic].copy() * uprava
    p = p / p.mean()
    vals = np.zeros(96,dtype=float)
    for h in range(24):
        for j in range(4):
            vals[h*4+j] = float(p[h]) / 4.0
    kwh_den = float(kwh_rok)/365.0
    if vals.sum()>0: vals = vals*(kwh_den/vals.sum())
    return vals


# Plotly config
_CFG = {"scrollZoom":False,"displayModeBar":False}
_LAY = dict(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=10,r=10,t=30,b=10),
            legend=dict(orientation="h",yanchor="bottom",y=1.02,xanchor="right",x=1),
            xaxis=dict(fixedrange=True),yaxis=dict(fixedrange=True))



# ================================================================
# UI — Streamlit rozhraní
# ================================================================

import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="FVE Kalkulačka pro SVJ", page_icon="☀️", layout="wide")

# ================================================================

st.title("☀️ FVE Kalkulačka pro SVJ")
st.caption("Přesná 15minutová simulace · OTE TDD profily · Ceny dle ceníků 2026")

# ── PŘEPÍNAČ WIZARD / EXPERT ──────────────────────────────────────
_mod_col1, _mod_col2 = st.columns([3,1])
with _mod_col2:
    expert_mod = st.toggle("⚙️ Expert mód",
                           value=st.session_state.get("expert_mod_val", False),
                           key="expert_mod_toggle",
                           help="Zobrazí všechny parametry najednou")
# Uložíme stav toggleu — při přepnutí se výsledky zachovají
st.session_state["expert_mod_val"] = expert_mod

if expert_mod:
    # Expert mód — načteme výchozí hodnoty z wizard_data nebo params
    _wd_e = st.session_state.get("wizard_data", {})
    _p_e  = st.session_state.get("res", {}).get("params", {})
    def _wg(key, default, src="wd"):
        """Načte hodnotu z wizard_data nebo params."""
        if src=="wd": return _wd_e.get(key, _p_e.get(key, default))
        return _p_e.get(key, _wd_e.get(key, default))

    st.divider()
    # ── 1. ZÁKLADNÍ ÚDAJE ────────────────────────────────────────────
    st.subheader("🏠 Základní údaje o domě")
    c1,c2,c3=st.columns(3)
    with c1:
        pocet_bytu=st.number_input("Počet bytů",2,200,int(_wg("pocet_bytu",12)),1,key="e_pocet_bytu")
        pocet_vchodu=st.number_input("Počet vchodů",1,10,int(_wg("pocet_vchodu",1)),1,key="e_pocet_vchodu",
                                      help="Ovlivňuje náklady na rozvod instalace — každý vchod má svůj rozvaděč")
        # ── Společné prostory ─────────────────────────────────────
        _sp_znam_e = st.toggle("📋 Spotřebu SP znám", value=bool(_wg("sp_znam_spotreba", False)),
                                key="e_sp_znam", help="Zapněte pokud máte fakturu za SP")
        if _sp_znam_e:
            sp_sp_mwh = st.number_input("Spotřeba SP — VT (MWh/rok)", 0.1, 50.0,
                                         float(_wg("sp_sp_mwh", 3.5)), 0.1, format="%.1f", key="e_sp_sp",
                                         help="Z faktury SP: kWh VT ÷ 1000")
            _sp_sazby_e = list(CENY_VT["ČEZ Distribuce"].keys())
            _sp_sazba_e = st.selectbox("Sazba SP", _sp_sazby_e,
                                        index=_sp_sazby_e.index(_wg("sazba_sp","D02d")) if _wg("sazba_sp","D02d") in _sp_sazby_e else 1,
                                        key="e_sp_sazba", format_func=lambda x: f"{x} — {POPIS_SAZEB.get(x,'')}")
            _sp_jistice_e = ["3×25A","3×32A","3×40A","3×50A","3×63A","3×80A","3×100A"]
            _sp_jistic_e = st.selectbox("Jistič SP", _sp_jistice_e,
                                         index=_sp_jistice_e.index(_wg("jistic_sp","3×25A")) if _wg("jistic_sp","3×25A") in _sp_jistice_e else 0,
                                         key="e_sp_jistic")
            _sp_jistic_a_map = {"3×25A":25,"3×32A":32,"3×40A":40,"3×50A":50,"3×63A":63,"3×80A":80,"3×100A":100}
            _sp_jistic_a_e = _sp_jistic_a_map[_sp_jistic_e]
        else:
            with st.expander("🏢 Dopočítat spotřebu SP ze zařízení", expanded=False):
                _sp_ep1, _sp_ep2 = st.columns(2)
                with _sp_ep1:
                    _e_pp = st.number_input("Počet pater", 1, 30, int(_wg("sp_pocet_pater",4)), 1, key="e_sp_pp")
                    _e_mv = st.checkbox("🛗 Výtah", value=bool(_wg("sp_ma_vytah",False)), key="e_sp_mv")
                    if _e_mv:
                        _e_pv = st.number_input("Počet výtahů", 1, 10, int(_wg("sp_pocet_vytahu",1)), 1, key="e_sp_pv")
                    else:
                        _e_pv = 0
                    _e_mt = st.checkbox("🚿 Centrální TUV", value=bool(_wg("sp_ma_tuv",False)), key="e_sp_mt")
                with _sp_ep2:
                    _e_tc = st.checkbox("♨️ TČ domu", value=bool(_wg("sp_ma_tc",False)), key="e_sp_tc")
                    _e_ev = st.number_input("🔌 Nabíječky EV", 0, 50, int(_wg("sp_pocet_ev",0)), 1, key="e_sp_ev")
                    _e_cp = st.number_input("🔄 Oběhová čerpadla", 0, 20, int(_wg("sp_pocet_cerpadel",0)), 1, key="e_sp_cp")
            _sp_res_e = _sp_sp_vypocet(
                pocet_bytu=pocet_bytu, pocet_pater=_wg("sp_pocet_pater",4),
                ma_vytah=_wg("sp_ma_vytah",False), pocet_vytahu=_wg("sp_pocet_vytahu",1),
                ma_tuv_central=_wg("sp_ma_tuv",False), ma_tc_dum=_wg("sp_ma_tc",False),
                pocet_ev_nabijec=_wg("sp_pocet_ev",0), pocet_cerpadel=_wg("sp_pocet_cerpadel",0),
            )
            sp_sp_mwh   = _sp_res_e["sp_mwh"]
            _sp_sazba_e = _sp_res_e["sazba_sp"]
            _sp_jistic_e = _sp_res_e["jistic_sp"]
            _sp_jistic_a_e = _sp_res_e["jistic_sp_a"]
            st.caption(f"🏢 SP: **{sp_sp_mwh:.2f} MWh/rok** · Sazba: **{_sp_sazba_e}** · Jistič: **{_sp_jistic_e}**")

        # Checkboxy zařízení — automatická spotřeba
        st.markdown("**Co v domě používáte na elektřinu?**")
        zarizeni_sel = ["zaklad"]  # základní vždy
        st.caption("☑️ Svícení, spotřebiče, pračka, sušička — vždy zahrnuto")
        for zar_key in ["sporak","bojler","klima","akum","primotop","tc","ev"]:
            zar = _SP_ZAR[zar_key]
            label = zar["nazev"]
            nt_info = f" (+{zar['nt']} kWh NT/byt)" if zar["nt"]>0 else f" (+{zar['vt']} kWh VT/byt)"
            if st.checkbox(f"{label}{nt_info}", key=f"zar_{zar_key}"):
                zarizeni_sel.append(zar_key)

        # Vypočítej spotřebu automaticky
        _vt_auto, _nt_auto = _sp_z_zarizeni(zarizeni_sel, pocet_bytu)
        _sazba_auto = _doporucena_sazba(zarizeni_sel)

        # Ruční přepsání
        rucne_sp = st.checkbox("✏️ Zadat spotřebu ručně", value=False, key="e_rucne_sp")
        if rucne_sp:
            sp_by_vt_mwh=st.number_input("Spotřeba bytů VT (MWh/rok)",0.5,400.0,
                                          max(0.5,round(_vt_auto,1)),0.5,format="%.1f")
        else:
            sp_by_vt_mwh = round(_vt_auto, 1)
            st.caption(f"Odhadovaná spotřeba VT: **{sp_by_vt_mwh:.1f} MWh/rok** ({sp_by_vt_mwh/pocet_bytu*1000:.0f} kWh/byt)")
    with c2:
        dist=st.selectbox("Distributor",list(CENY_VT.keys()),index=list(CENY_VT.keys()).index(_wg("dist",list(CENY_VT.keys())[0])) if _wg("dist","") in CENY_VT else 0,key="e_dist",
                          help="ČEZ = většina ČR | EG.D = Morava/jih Čech | PRE = Praha")
        # Automatická sazba dle zařízení — lze přepsat
        _sazba_idx = list(CENY_VT[dist].keys()).index(_sazba_auto) if _sazba_auto in CENY_VT[dist] else 1
        rucne_sazba = st.checkbox("✏️ Změnit sazbu ručně", value=False, key="e_rucne_sazba")
        if rucne_sazba:
            sazba=st.selectbox("Distribuční sazba",list(CENY_VT[dist].keys()),key="e_sazba",
                               format_func=lambda x:f"{x} — {POPIS_SAZEB[x]}",index=_sazba_idx)
        else:
            sazba = _sazba_auto
            st.success(f"✅ Odhadovaná sazba: **{sazba}** — {POPIS_SAZEB.get(sazba,'')}")

    with c3:
        # Automatický jistič dle počtu bytů a zařízení
        _jistic_auto, _jistic_idx = _doporuceny_jistic(pocet_bytu, zarizeni_sel)
        _jistice = ["1×25A","3×16A","3×20A","3×25A","3×32A","3×40A","3×50A","3×63A"]
        rucne_jistic = st.checkbox("✏️ Změnit jistič ručně", value=False, key="e_rucne_jistic")
        if rucne_jistic:
            _jistic_vyber = st.selectbox("Hlavní jistič", _jistice, key="e_jistic",
                                          index=min(_jistic_idx+1, len(_jistice)-1))
        else:
            _jistic_vyber = _jistic_auto
            st.success(f"✅ Jistič dle výkonu: **{_jistic_auto}**")
            st.caption("Hlavní jistič SVJ na patce domu. Jistič bytu (typicky 1×25A) se SVJ netýká.")

        st.markdown("**Složení domácností**")
        _profil_mix_def = int(_wg("profil_mix", 50))
        profil_mix = st.slider(
            "🏠 Doma přes den ◄──────────────► Pryč přes den 💼",
            0, 100, _profil_mix_def, 5,
            key="e_profil_mix",
            help="Vlevo = důchodci/home office (doma přes den, překryv s FVE lepší). "
                 "Vpravo = pracující (pryč 8–17h, FVE vyrábí do prázdného domu)."
        )
        # Převod slideru na složení pro _smiseny_profil
        # 0 = 100% důchodci, 50 = mix, 100 = 100% pracující
        pct_seniori   = max(0, 100 - 2 * profil_mix)      # 0→100, 50→0, 100→0
        pct_pracujici = max(0, 2 * profil_mix - 100)       # 0→0, 50→0, 100→100
        pct_rodiny    = max(0, 50 - abs(profil_mix - 50))  # 0→0, 50→50, 100→0 (rodiny = střed)
        # Normalizace
        _pct_sum = pct_seniori + pct_pracujici + pct_rodiny
        if _pct_sum > 0:
            _f = 100.0 / _pct_sum
            pct_seniori   = int(pct_seniori   * _f)
            pct_pracujici = int(pct_pracujici * _f)
            pct_rodiny    = max(0, 100 - pct_seniori - pct_pracujici)

        if profil_mix <= 20:
            _popis = f"🏠 Převaha důchodců/HO — spotřeba přes den → dobrý překryv s FVE"
        elif profil_mix <= 40:
            _popis = f"🏠 Spíše doma přes den (důchodci + rodiny)"
        elif profil_mix <= 60:
            _popis = f"⚖️ Smíšené složení — průměrný tvar spotřeby"
        elif profil_mix <= 80:
            _popis = f"💼 Spíše pracující — FVE vyrábí přes den do prázdného domu"
        else:
            _popis = f"💼 Převaha pracujících — baterie výrazně pomůže zachytit denní přebytky"
        st.caption(_popis)
        profil = "mix"  # zpětná kompatibilita — uprava se počítá zvlášť

    # NT spotřeba — jen pro sazby s NT tarifem
    ma_nt = sazba in SAZBY_NT
    sp_by_nt_mwh = 0.0
    if ma_nt:
        nt_h_count = len(NT_HODINY.get(sazba,set()))
        st.info(f"📌 Sazba **{sazba}** má NT tarif ({nt_h_count} hodin/den). "
                f"NT spotřeba (bojler, TČ) probíhá v noci — FVE ji nepokrývá přímo, "
                f"ale **baterie ji může pokrýt z denních přebytků**.")
        if rucne_sp:
            sp_by_nt_mwh = st.number_input(
                f"Spotřeba bytů NT (MWh/rok)",0.0,200.0,
                round(float(_nt_auto),1),0.5,format="%.1f",
                help=f"Spotřeba v nízkém tarifu ({nt_h_count}h/den)")
        else:
            sp_by_nt_mwh = round(float(_nt_auto),1)
            st.caption(f"Odhadovaná spotřeba NT: **{sp_by_nt_mwh:.1f} MWh/rok** ({sp_by_nt_mwh/pocet_bytu*1000:.0f} kWh/byt)")

    sp_sp  = float(sp_sp_mwh)*1000
    sp_by_vt = float(sp_by_vt_mwh)*1000
    sp_by_nt = float(sp_by_nt_mwh)*1000
    sp_cel = sp_sp + sp_by_vt + sp_by_nt
    st.caption(f"Celková spotřeba domu: **{sp_cel/1000:.1f} MWh/rok** "
               f"(VT: {(sp_sp+sp_by_vt)/1000:.1f} MWh · NT: {sp_by_nt/1000:.1f} MWh)")

    cena_vt  = float(CENY_VT[dist][sazba])/1000.0
    cena_nt  = float(CENY_NT[dist].get(sazba, CENY_VT[dist][sazba]))/1000.0
    # SP — sazba a jistič z nové SP sekce (ne z wizard_data)
    cena_vt_sp = float(CENY_VT[dist].get(_sp_sazba_e, CENY_VT[dist][sazba]))/1000.0
    cena_nt_sp = float(CENY_NT[dist].get(_sp_sazba_e, CENY_VT[dist].get(_sp_sazba_e, CENY_VT[dist][sazba])))/1000.0
    stay     = float(STAY_PLAT[dist])
    jistic   = float(JISTIC_3x25[dist][sazba])
    naklad   = (sp_by_vt*cena_vt + sp_by_nt*cena_nt
                + sp_sp*cena_vt_sp
                + (stay+jistic)*12.0)

    # Průměrná vs. mezní cena kWh
    _cena_prumerna = naklad / (sp_cel/1000.0) if sp_cel > 0 else cena_vt
    st.info(
        f"💡 **{dist}** · **{sazba}** · s DPH · POZE=0 Kč od 2026 | "
        f"Byty VT: **{cena_vt:.2f} Kč/kWh** (mezní)"
        + (f" · NT: **{cena_nt:.2f} Kč/kWh**" if ma_nt else "")
        + (f" | SP: **{_sp_sazba_e}** · **{cena_vt_sp:.2f} Kč/kWh** · jistič **{_sp_jistic_e}**"
           if _sp_sazba_e != sazba else f" | SP jistič: **{_sp_jistic_e}**")
        + f"\n\n📊 Stálé platy: **{stay+jistic:.0f} Kč/měs** · "
        f"Roční náklad: **{naklad:,.0f} Kč** · "
        f"Průměrná cena kWh: **{_cena_prumerna:.2f} Kč** (vč. fixních plateb)"
    )

    with st.expander("✏️ Upravit ceny ručně"):
        u1,u2=st.columns(2)
        with u1: cena_vt=st.number_input("Cena VT (Kč/kWh)",1.0,15.0,round(cena_vt,2),0.01,format="%.2f",key="e_cena_vt")
        with u2:
            if ma_nt:
                cena_nt=st.number_input("Cena NT (Kč/kWh)",1.0,12.0,round(cena_nt,2),0.01,format="%.2f")

    st.divider()

    # ── 2. FVE A BATERIE ─────────────────────────────────────────────
    st.subheader("⚡ Parametry FVE a baterie")
    c1,c2=st.columns(2)
    with c1:
        vykon=st.number_input("Výkon FVE (kWp)",1.0,200.0,float(_wg("vykon",20.0)),0.5,format="%.1f",key="e_vykon")
        # Automatická cena dle výkonu (množstevní sleva)
        def _cena_kwp_auto(kw):
            if kw < 10:   return 38000
            elif kw < 20: return 33000
            elif kw < 40: return 28000
            elif kw < 80: return 24000
            else:         return 21000
        _cena_auto = _cena_kwp_auto(float(vykon))
        rucne = st.checkbox("Upravit cenu ručně", value=False, key="e_rucne_cena")
        if rucne:
            cena_kwp = st.slider("Cena FVE (Kč/kWp)",20000,50000,_cena_auto,500,key="e_cena_kwp")
        else:
            cena_kwp = _cena_auto
            st.caption(f"Cena dle výkonu: **{cena_kwp:,} Kč/kWp** (množstevní sleva)")
        cena_fve=int(float(vykon)*float(cena_kwp))
        st.caption(f"Odhadovaná cena FVE: **{cena_fve:,.0f} Kč**")
    with c2:
        bat=st.number_input("Kapacita baterie (kWh)",0,200,int(_wg("bat",0)),5,key="e_bat",
                             help="Nabíjí se z přetoků FVE přes den, vybíjí do NT spotřeby v noci" if ma_nt else "Nabíjí z přetoků FVE, vybíjí při nedostatku")
        if bat>0:
            cena_kwh_bat=st.slider("Cena baterie (Kč/kWh)",10000,20000,15000,500,key="e_cena_bat")
            cena_bat=int(float(bat)*float(cena_kwh_bat))
            st.caption(f"Odhadovaná cena baterie: **{cena_bat:,.0f} Kč**")
            if ma_nt and bat>0:
                st.success(f"🔋 Baterie přemostí denní přebytky FVE do noční NT spotřeby "
                           f"(úspora NT: {cena_nt:.2f} Kč/kWh místo ceny ze sítě).")
        else:
            cena_bat=0

    st.divider()

    # ── 3. MODEL SDÍLENÍ ─────────────────────────────────────────────
    st.subheader("🔗 Model sdílení energie")
    model=st.radio("Model",["spolecne","jom","edc"],horizontal=True,key="e_model",
                   format_func=lambda x:{"spolecne":"🏢 Jen společné prostory",
                                         "jom":"⚡ Sjednocení odběrných míst",
                                         "edc":"🔗 EDC komunitní sdílení (iterační)"}[x])
    # JOM: měřiče + paušál projekt/přepojení
    _jom_merici = int(pocet_bytu)*10000
    _jom_projekt = 75000  # paušál projekt elektro + přepojení
    cena_mericu = (_jom_merici + _jom_projekt) if model=="jom" else 0

    # Náklady na rozvod dle počtu vchodů (každý vchod = extra rozvaděč + kabeláž)
    _vchod_extra = max(0, int(pocet_vchodu)-1) * 30000  # každý další vchod +30k
    cena_mericu += _vchod_extra if model!="spolecne" else 0
    # Úspora JOM = (N bytů × platby_byt) + platby_SP - platby_JOM_dům
    # Stávající stav: N ODM bytů + 1 ODM SP = (N+1) stálých plateb + N×jistič_byt + jistič_SP
    # JOM stav:       1 ODM dům = 1 stálá platba + 1 velký jistič_domu
    if model=="jom":
        _jbyt_typ  = _jistic_byt_typ(zarizeni_sel if "zarizeni_sel" in dir() else ["zaklad"])
        _jbyt_cena = JISTIC_BYT.get(dist, JISTIC_BYT["ČEZ Distribuce"]).get(_jbyt_typ, jistic)
        # Jistič SP (stávající stav — samostatné ODM SP)
        _jsp_a     = int(st.session_state.get("wizard_data", {}).get("jistic_sp_a", 25))
        _jsp_cena  = _cena_jistice_dum(dist, sazba, _jsp_a)
        # JOM — jeden velký jistič pro celý dům (byty + SP)
        _jdum_amp  = _jistic_dum_ampery(pocet_bytu, zarizeni_sel if "zarizeni_sel" in dir() else ["zaklad"])
        _jdum_cena = _cena_jistice_dum(dist, sazba, _jdum_amp, c_tarif=True)
        # Stávající platby: (N bytů + SP) × stálé + N×jistič_byt + jistič_SP
        _platby_ted_r = (int(pocet_bytu) + 1) * stay + int(pocet_bytu) * _jbyt_cena + _jsp_cena
        # JOM platby: 1 stálá + 1 velký jistič
        _platby_jom_r = stay + _jdum_cena
        uspora_jist = (_platby_ted_r - _platby_jom_r) * 12.0
    else:
        uspora_jist = 0.0
    if model=="spolecne":
        st.info(f"🏢 FVE pokrývá jen společnou spotřebu ({sp_sp_mwh:.1f} MWh/rok VT). Nejjednodušší realizace, žádné extra náklady.")
    elif model=="jom":
        st.info(f"⚡ Jeden elektroměr pro celý dům. "
                f"Náklady navíc: měřiče **{_jom_merici:,} Kč** + projekt/přepojení **{_jom_projekt:,} Kč** = **{cena_mericu:,} Kč**. "
                f"Úspora distribuce: **{uspora_jist:,.0f} Kč/rok**.")
    else:
        st.info("🔗 Každý byt si zachovává dodavatele. Chytré měřiče zdarma od distributora. Registrace na edc.cz.")

    st.divider()

    # ── 4. LOKALITA A STŘECHA ────────────────────────────────────────
    st.subheader("🌍 Lokalita a střecha")
    lc1,lc2=st.columns([2,1])

    with lc1:
        lokace=st.text_input("Adresa nebo město",key="e_lokace",
                              placeholder="např. Náměstí Míru 5, Praha 2",
                              help="Zadejte přesnou adresu nebo název města pro přesnější výsledky")

        # Našeptávání adres
        if lokace and len(lokace) >= 4:
            with st.spinner("Hledám adresu..."):
                navrhys = _geocode_search(lokace)
            if navrhys:
                moznosti = []
                for n in navrhys[:5]:
                    addr = n.get("address",{})
                    parts = []
                    if addr.get("road"): parts.append(addr["road"])
                    if addr.get("house_number"): parts.append(addr["house_number"])
                    if addr.get("city") or addr.get("town") or addr.get("village"):
                        parts.append(addr.get("city") or addr.get("town") or addr.get("village",""))
                    if addr.get("postcode"): parts.append(addr["postcode"])
                    label = ", ".join(parts) if parts else n.get("display_name","")[:60]
                    moznosti.append(label)
                if moznosti:
                    vyber = st.selectbox("Vyberte adresu ze seznamu:", ["— zadejte výše —"] + moznosti, key="e_vyber_addr")
                    if vyber != "— zadejte výše —":
                        lokace = vyber

    with lc2:
        typ_str=st.radio("Typ střechy",["sikma","plocha"],key="e_typ_str",
                         format_func=lambda x:"🏠 Šikmá" if x=="sikma" else "🏢 Plochá",
                         horizontal=True)

    if typ_str=="sikma":
        sc1,sc2=st.columns(2)
        with sc1: sklon=st.slider("Sklon (°)",15,60,35,key="e_sklon")
        with sc2: azimut=st.select_slider("Orientace",[-90,-45,0,45,90],0,key="e_azimut",
                                           format_func=lambda x:{-90:"⬅️ Východ",-45:"↙️ JV",0:"⬆️ Jih",45:"↗️ JZ",90:"➡️ Západ"}[x])
        koef_str=1.0
    else:
        pc1,pc2=st.columns(2)
        with pc1: sklon=st.slider("Sklon panelů (°)",5,20,10,key="e_sklon_pl")
        with pc2: sys_pl=st.radio("Systém",["jih","jz_jv","vz"],key="e_sys_pl",
                        format_func=lambda x:{"jih":"⬆️ Jih","jz_jv":"↗️ JZ+JV","vz":"↔️ V+Z"}[x])
        # PVGIS konvence: 0=Jih, −90=Východ, +90=Západ
        # 999 = V+Z  → dvě volání PVGIS (−90° + +90°), výsledky sečteny
        # 998 = JZ+JV → dvě volání PVGIS (−45° + +45°), výsledky sečteny
        azimut = {"jih": 0, "jz_jv": 998, "vz": 999}[sys_pl]
        koef_str = {"jih":1.0,"jz_jv":1.0,"vz":1.0}[sys_pl]  # korekce řeší PVGIS, ne koef
        if sys_pl != "jih":
            st.caption({"jz_jv": "↗️ PVGIS simuluje JV+JZ jako dvě plochy — ranní i odpolední slunce",
                        "vz":    "↔️ PVGIS simuluje Východ+Západ jako dvě plochy — ranní i večerní slunce"}[sys_pl])

    st.divider()

    # ── 5. FINANCOVÁNÍ ───────────────────────────────────────────────
    st.subheader("💰 Financování")
    fc1,fc2=st.columns(2)
    with fc1:
        scenar=st.radio("Scénář",["uver","vlastni","kombinace"],key="e_scenar",
                        format_func=lambda x:{"uver":"🏦 Bezúročný úvěr NZÚ (od září 2026)",
                                              "vlastni":"💵 Vlastní zdroje (fond oprav)",
                                              "kombinace":"🔀 Kombinace vlastní + úvěr"}[x])
    with fc2:
        if scenar=="uver":
            splatnost=st.slider("Doba splácení (let)",5,25,15,key="e_spl"); vlastni_pct=0
            st.info("✅ Úroky hradí stát. SVJ splácí jen jistinu. Standardně 15 let — přesné podmínky NZÚ v září 2026.")
        elif scenar=="vlastni":
            splatnost=0; vlastni_pct=100; st.info("💡 SVJ hradí vše z fondu oprav.")
        else:
            vlastni_pct=st.slider("Vlastní zdroje (%)",10,90,30,10,key="e_vl_pct")
            splatnost=st.slider("Doba splácení (let)",5,25,15,key="e_spl_k")

    st.markdown("**Nízkopříjmové domácnosti**")
    nb1,nb2=st.columns(2)
    with nb1: pocet_nizko=st.number_input("Bytů s bonusem",0,int(pocet_bytu),0,1,key="e_nizko")
    with nb2: bonus_byt=st.number_input("Bonus na byt (Kč)",0,150000,100000,5000,key="e_bonus_byt",
                                         help="Přímý bonus NZÚ pro zranitelnou domácnost — snižuje její podíl splátky. Max avizováno 150 000 Kč/byt.")
    bonus=int(pocet_nizko)*int(bonus_byt)  # celkový bonus pro SVJ

    st.divider()

    # ── 6. PARAMETRY SIMULACE ────────────────────────────────────────
    st.subheader("⚙️ Parametry simulace")
    sc1,sc2,sc3=st.columns(3)
    with sc1: cena_pretoky=st.number_input("Výkupní cena přetoků (Kč/kWh)",0.30,2.50,0.95,0.05,format="%.2f",key="e_pretoky")
    with sc2: rust_cen=st.slider("Růst cen elektřiny (%/rok)",0.0,8.0,3.0,0.5,key="e_rust")
    with sc3: deg_pan=st.slider("Degradace panelů (%/rok)",0.2,1.0,0.5,0.1,key="e_deg")

    with st.expander("⚙️ Pokročilé parametry"):
        ap1,ap2=st.columns(2)
        with ap1:
            deg_bat_val=st.slider("Degradace baterie (%/rok)",0.5,5.0,2.0,0.5,key="e_deg_bat",
                                  help="Baterie ztrácí kapacitu ~2% ročně (výchozí)")
        with ap2:
            # EDC ztráta sdílení — výchozí z počtu bytů
            _edc_default=min(5.0,round(10.0/pocet_bytu**0.5,1))
            edc_ztrata_val=st.slider("Ztráta sdílení EDC (%)",0.0,10.0,_edc_default,0.5,key="e_edc",
                                      help=f"Ztráta alokace pro {pocet_bytu} bytů. "
                                           f"Výchozí {_edc_default}% (menší dům = vyšší ztráta). "
                                           f"S chytrým řízením může být nižší.")

    st.divider()

    # Výchozí hodnoty pokročilých parametrů (pokud expander nebyl otevřen)
    if 'deg_bat_val' not in dir(): deg_bat_val=2.0
    if 'edc_ztrata_val' not in dir(): edc_ztrata_val=min(5.0,round(10.0/pocet_bytu**0.5,1))

    # VÝPOČET INVESTICE
    cena_invest = cena_fve + cena_bat + cena_mericu

    # Správná logika NZÚ:
    # SVJ si vezme bezúročný úvěr na celou investici (mínus vlastní zdroje)
    # Bonus jde přímo konkrétnímu bytu — NESNIŽUJE celkový úvěr SVJ
    vlastni_cast = float(cena_invest) * float(vlastni_pct) / 100.0
    uver_cast = max(0.0, float(cena_invest) - vlastni_cast)  # bonus neodečítáme z úvěru
    rocni_spl = uver_cast / float(splatnost) if (scenar!="vlastni" and splatnost>0) else 0.0

    # Splátka na byt a efekt bonusu
    podil_bytu_uver = uver_cast / float(pocet_bytu)  # podíl jednoho bytu na úvěru
    splatka_byt_std = podil_bytu_uver / float(splatnost) / 12.0 if (scenar!="vlastni" and splatnost>0) else 0.0
    # Bonus snižuje splátku konkrétního bytu (max do výše jeho podílu)
    bonus_efekt_byt = min(float(bonus_byt), podil_bytu_uver)
    zbytek_super = max(0.0, podil_bytu_uver - bonus_efekt_byt)
    splatka_byt_super = zbytek_super / float(splatnost) / 12.0 if (scenar!="vlastni" and splatnost>0) else 0.0

    bc1,bc2=st.columns([1,3])
    with bc1: spustit=st.button("🔄 Spočítat simulaci",type="primary",use_container_width=True)
    with bc2: st.caption("Stáhne hodinová solární data z PVGIS a provede přesný 15minutový výpočet. Trvá 5–20 s.")

    if spustit:
        with st.spinner(f"Hledám {lokace}..."):
            lat,lon,mesto,geo_err=_geocode(lokace)
        if geo_err: st.error(f"Lokalita nenalezena: {geo_err}"); st.stop()

        kwp_eff=float(vykon)*float(koef_str)
        with st.spinner(f"Stahuji solární TMY data pro {mesto} z PVGIS (EU JRC)..."):
            vyroba_hod,pvgis_err=_pvgis(lat,lon,kwp_eff,sklon,azimut)
        if pvgis_err:
            st.warning(
                f"⚠️ PVGIS nedostupné ({pvgis_err[:80]}) — používám záložní matematický model. "
                f"Výsledky mohou být méně přesné, zejména v zimních měsících."
            )
            vyroba_hod=_gen_vyroba_fallback(kwp_eff,sklon,azimut); pvgis_ok=False
        else:
            pvgis_ok=True
            # Zobraz měsíční výrobu z PVGIS jako kontrolu
            _mes_kwh=[]; _h=0
            for _d in [31,28,31,30,31,30,31,31,30,31,30,31]:
                _mes_kwh.append(round(float(vyroba_hod[_h:_h+_d*24].sum())))
                _h+=_d*24
            _rocni=sum(_mes_kwh)
            st.success(
                f"☀️ **PVGIS TMY data načtena** — {mesto} · {kwp_eff:.1f} kWp · "
                f"sklon {sklon}° · azimut {azimut}° | "
                f"Roční výroba: **{_rocni:,} kWh** ({_rocni/kwp_eff:.0f} kWh/kWp) · "
                f"Měsíce: {' '.join(f'{m}:{v}' for m,v in zip(_MESICE,_mes_kwh))}"
            )

        with st.spinner("Simuluji v 15minutových intervalech..."):
            vyroba_15=_interpoluj(vyroba_hod)
            _pm = int(st.session_state.get("e_profil_mix", 50))
            uprava = _smiseny_profil(
                pct_pracujici=max(0, int(2*_pm - 100)),
                pct_seniori=max(0, int(100 - 2*_pm)),
                pct_rodiny=max(0, int(50 - abs(_pm - 50))),
            )

            # Společné prostory — jen VT (žádný NT)
            sp_sp15 = _gen_profil_vt(sp_sp, _TDD_SP)

            # Byty VT + NT
            sp_by_vt15 = _gen_profil_vt(sp_by_vt, _TDD4, uprava)
            sp_by_nt15 = _gen_profil_nt(sp_by_nt, sazba)

            # Spotřeba pro vybraný model (hlavní simulace)
            if model == "spolecne":
                sp_vt15 = sp_sp15
                sp_nt15 = np.zeros(_CD, dtype=float)
            else:
                sp_vt15 = sp_sp15 + sp_by_vt15
                sp_nt15 = sp_by_nt15

            _edc_ztrata = float(edc_ztrata_val) if model=="edc" else 0.0
            sim=_simuluj(vyroba_15, sp_vt15, sp_nt15, float(bat), model, _edc_ztrata)
            # Cashflow SVJ: bonus nesnižuje úvěr — jde přímo konkrétnímu bytu
            cf=_cashflow(
                vl_vt=sim["vlastni_vt_kwh"], vl_nt=sim["vlastni_nt_kwh"],
                pr=sim["pretoky_kwh"],
                cvt=float(cena_vt), cnt=float(cena_nt), cpr=float(cena_pretoky),
                vlast=vlastni_cast, uver=uver_cast, spl=rocni_spl, splat=int(splatnost),
                rust=float(rust_cen), deg=float(deg_pan), leta=25,
                jist=float(uspora_jist), bonus=0.0, deg_bat=float(deg_bat_val))

            # Porovnání modelů — FIXNI vstupy, kazdy model ma sve vlastni naklady
            sp_vt_celkem = sp_sp15 + sp_by_vt15  # celý dům VT
            sp_nt_celkem = sp_by_nt15              # celý dům NT
            srovnani={}
            _vchod_extra_srov = max(0,int(pocet_vchodu)-1)*30000
            for mk in ["spolecne","jom","edc"]:
                # Každý model má své náklady na investici (shodné s cena_invest)
                _mericu_mk = (int(pocet_bytu)*10000+75000) if mk=="jom" else 0
                _mericu_mk += _vchod_extra_srov if mk!="spolecne" else 0
                if mk=="jom":
                    _jbyt_c3   = JISTIC_BYT.get(dist,JISTIC_BYT["ČEZ Distribuce"]).get(
                                     _jistic_byt_typ(zarizeni_sel), 132)
                    _jsp_a3    = int(st.session_state.get("wizard_data", {}).get("jistic_sp_a", 25))
                    _jsp_c3    = _cena_jistice_dum(dist, sazba, _jsp_a3)
                    _jdum_a3   = _jistic_dum_ampery(pocet_bytu, zarizeni_sel)
                    _jdum_c3   = _cena_jistice_dum(dist, sazba, _jdum_a3, c_tarif=True)
                    # (N+1 ODM stávající) vs (1 ODM JOM)
                    _platby_ted3 = (int(pocet_bytu)+1)*stay + int(pocet_bytu)*_jbyt_c3 + _jsp_c3
                    _platby_jom3 = stay + _jdum_c3
                    _jist_mk   = (_platby_ted3 - _platby_jom3) * 12.0
                else:
                    _jist_mk  = 0.0
                _invest_mk = cena_fve + cena_bat + _mericu_mk
                _vlast_mk  = float(_invest_mk)*float(vlastni_pct)/100.0
                _uver_mk   = max(0.0, float(_invest_mk) - _vlast_mk)
                _spl_mk    = _uver_mk/float(splatnost) if (scenar!="vlastni" and splatnost>0) else 0.0

                if mk=="spolecne":
                    svt=sp_sp15; snt=np.zeros(_CD,dtype=float)
                else:
                    svt=sp_vt_celkem; snt=sp_nt_celkem
                _ez_mk = float(edc_ztrata_val) if mk=="edc" else 0.0
                sm=_simuluj(vyroba_15,svt,snt,float(bat),mk,_ez_mk)
                cfm=_cashflow(vl_vt=sm["vlastni_vt_kwh"],vl_nt=sm["vlastni_nt_kwh"],
                              pr=sm["pretoky_kwh"],cvt=float(cena_vt),cnt=float(cena_nt),
                              cpr=float(cena_pretoky),vlast=_vlast_mk,uver=_uver_mk,
                              spl=_spl_mk,splat=int(splatnost),rust=float(rust_cen),
                              deg=float(deg_pan),leta=25,
                              jist=_jist_mk,bonus=float(bonus),deg_bat=float(deg_bat_val))
                nav_m=next((r["rok"] for r in cfm if r["kumulativni"]>=0),None)
                stat_m=float(_invest_mk)/cfm[0]["uspora_celkem"] if cfm[0]["uspora_celkem"]>0 else 999
                splatka_mk=_spl_mk/float(pocet_bytu)/12.0
                cisty_byt_mk=cfm[0]["uspora_celkem"]/float(pocet_bytu)/12.0-splatka_mk
                srovnani[mk]={"sim":sm,"cf":cfm,"nav":nav_m,"stat":stat_m,"rok1":cfm[0],
                              "invest":_invest_mk,"splatka_byt":splatka_mk,
                              "cisty_byt":cisty_byt_mk}

        st.session_state["res"]={
            "sim":sim,"cf":cf,"vyroba_15":vyroba_15,
            "sp_vt15":sp_vt15,"sp_nt15":sp_nt15,
            "pvgis_ok":pvgis_ok,"mesto":mesto,"lat":lat,"lon":lon,
            "srovnani":srovnani,"cena_invest":cena_invest,
            "params":{
                "pocet_bytu":pocet_bytu,"scenar":scenar,"splatnost":splatnost,
                "vlastni_pct":vlastni_pct,"bonus_byt":bonus_byt,"pocet_nizko":pocet_nizko,
                "bat":bat,"ma_nt":ma_nt,"sp_by_vt_mwh":sp_by_vt_mwh,
                "sp_by_nt_mwh":sp_by_nt_mwh,"rust_cen":rust_cen,"deg_pan":deg_pan,
                "cena_pretoky":cena_pretoky,"splatka_byt_std":splatka_byt_std,
                "splatka_byt_super":splatka_byt_super,"sp_cel":sp_cel,
                "model":model,"vykon":float(vykon),
                "koef_str":float(koef_str),"typ_str":typ_str,
                "sklon":sklon,"azimut":azimut,"profil":profil,"sazba":sazba,
                "sp_sp_mwh":sp_sp_mwh,"sp_by_nt_mwh":float(sp_by_nt_mwh),
            }}
        st.success(f"✅ Hotovo — {mesto} ({lat:.2f}°N, {lon:.2f}°E) {'· PVGIS data' if pvgis_ok else '· záložní model'}")


else:
    # ════════════════════════════════════════════════════════════════
    # WIZARD MÓD — krok za krokem
    # ════════════════════════════════════════════════════════════════

    # Session state pro wizard
    if "wizard_krok" not in st.session_state:
        st.session_state.wizard_krok = 1
    if "wizard_data" not in st.session_state:
        st.session_state.wizard_data = {}

    krok = st.session_state.wizard_krok

    # Progress bar
    st.progress(krok/5, text=f"Krok {krok} z 5")

    # ── KROK 1: DŮM ──────────────────────────────────────────────
    if krok == 1:
        st.subheader("🏠 Krok 1: Váš dům")

        w1c1, w1c2 = st.columns(2)
        with w1c1:
            _def_bytu = st.session_state.wizard_data.get("pocet_bytu", 12)
            pocet_bytu = st.number_input("Počet bytů", 2, 200, _def_bytu, 1, key="w_pocet_bytu")
            _def_vchodu = st.session_state.wizard_data.get("pocet_vchodu", 1)
            pocet_vchodu = st.number_input("Počet vchodů", 1, 10, _def_vchodu, 1, key="w_pocet_vchodu")

        with w1c2:
            # Toggle: odhadnout dle spotřebičů, nebo zadat ručně ze faktury
            _byt_znam = st.session_state.wizard_data.get("byt_znam_spotreba", False)
            byt_znam = st.toggle(
                "📋 Spotřebu bytů znám ze faktury",
                value=_byt_znam, key="w_byt_znam",
                help="Zapněte pokud máte roční spotřebu z faktury nebo vyúčtování")

        if byt_znam:
            # ── Ruční zadání spotřeby bytů ──────────────────────────
            st.markdown("**📋 Zadejte roční spotřebu bytů (celkem za celý dům)**")
            bk1, bk2 = st.columns(2)
            with bk1:
                _vt_rucne = st.number_input(
                    "Spotřeba VT (MWh/rok)", 0.0, 2000.0,
                    float(st.session_state.wizard_data.get("vt_mwh", 15.0)), 0.5,
                    format="%.1f", key="w_byt_vt_rucne",
                    help="Součet VT kWh všech bytů ÷ 1000 (z faktury/vyúčtování)")
            with bk2:
                _nt_rucne = st.number_input(
                    "Spotřeba NT (MWh/rok)", 0.0, 2000.0,
                    float(st.session_state.wizard_data.get("nt_mwh", 0.0)), 0.5,
                    format="%.1f", key="w_byt_nt_rucne",
                    help="Součet NT kWh ÷ 1000. Zadejte 0 pokud nemáte dvoutarif.")
            bk3, bk4 = st.columns(2)
            with bk3:
                _sazby_list = list(CENY_VT["ČEZ Distribuce"].keys())
                _sazba_prev = st.session_state.wizard_data.get("sazba", "D02d")
                _sazba_idx = _sazby_list.index(_sazba_prev) if _sazba_prev in _sazby_list else 1
                _sazba_rucne = st.selectbox("Sazba bytů", _sazby_list,
                    index=_sazba_idx, key="w_byt_sazba_rucne",
                    format_func=lambda x: f"{x} — {POPIS_SAZEB.get(x,'')}")
            with bk4:
                _jistice_byt = ["1×25A","3×16A","3×20A","3×25A","3×32A"]
                _jbyt_prev = st.session_state.wizard_data.get("jistic_byt_typ", "1×25A")
                _jbyt_idx = _jistice_byt.index(_jbyt_prev) if _jbyt_prev in _jistice_byt else 0
                _jbyt_rucne = st.selectbox("Typický jistič bytu", _jistice_byt,
                    index=_jbyt_idx, key="w_byt_jistic_rucne",
                    help="Nejběžnější: 1×25A (jen svícení), 3×25A (sporák/indukce), 3×32A (TČ)")
            zarizeni_sel = st.session_state.wizard_data.get("zarizeni_sel", ["zaklad"])
            _vt_auto    = float(_vt_rucne)
            _nt_auto    = float(_nt_rucne)
            _sazba_auto = _sazba_rucne
            _jbyt_w     = _jbyt_rucne
            _jistic_auto, _ = _doporuceny_jistic(pocet_bytu, zarizeni_sel)
            st.info(
                f"📊 Zadaná spotřeba bytů: **{_vt_auto:.1f} MWh VT** + **{_nt_auto:.1f} MWh NT** · "
                f"Sazba: **{_sazba_auto}** · Jistič bytu: **{_jbyt_w}**"
            )
        else:
            # ── Odhadnout dle spotřebičů ─────────────────────────────
            with w1c2:
                st.markdown("**Co v domě používáte na elektřinu?**")
                zarizeni_sel = ["zaklad"]
                st.caption("☑️ Svícení, spotřebiče, pračka, sušička — vždy zahrnuto")
                _prev_zar = st.session_state.wizard_data.get("zarizeni_sel", ["zaklad"])
                for zar_key in ["sporak","bojler","klima","akum","primotop","tc","ev"]:
                    zar = _SP_ZAR[zar_key]
                    nt_info = f" (+{zar['nt']} kWh NT/byt)" if zar["nt"]>0 else f" (+{zar['vt']} kWh VT/byt)"
                    _default_zar = zar_key in _prev_zar
                    if st.checkbox(f"{zar['nazev']}{nt_info}", key=f"w_zar_{zar_key}", value=_default_zar):
                        zarizeni_sel.append(zar_key)
            _vt_auto, _nt_auto = _sp_z_zarizeni(zarizeni_sel, pocet_bytu)
            _sazba_auto = _doporucena_sazba(zarizeni_sel)
            _jistic_auto, _ = _doporuceny_jistic(pocet_bytu, zarizeni_sel)
            _jbyt_w = _jistic_byt_typ(zarizeni_sel)
            st.info(
                f"📊 Odhadovaná spotřeba bytů: **{_vt_auto:.1f} MWh VT** + **{_nt_auto:.1f} MWh NT** · "
                f"Odhadovaná sazba: **{_sazba_auto}** · Jistič bytu: **{_jbyt_w}**"
            )

        # ── SPOLEČNÉ PROSTORY ────────────────────────────────────────
        st.divider()
        st.markdown("### 🏢 Společné prostory")

        _wd = st.session_state.wizard_data
        _sp_znam = _wd.get("sp_znam_spotreba", False)
        sp_znam = st.toggle(
            "📋 Spotřebu SP znám ze faktury",
            value=_sp_znam, key="w_sp_znam",
            help="Zapněte pokud máte fakturu za společné prostory")

        if sp_znam:
            # ── Ruční zadání SP ─────────────────────────────────────
            st.caption("Zadejte roční spotřebu společných prostor z faktury SVJ.")
            sp_k1, sp_k2 = st.columns(2)
            with sp_k1:
                _sp_vt_r = st.number_input(
                    "Spotřeba SP — VT (MWh/rok)", 0.0, 500.0,
                    float(_wd.get("sp_sp_vt_mwh", 2.0)), 0.1,
                    format="%.1f", key="w_sp_vt_rucne",
                    help="Z faktury SP: kWh VT ÷ 1000")
                _sp_nt_r = st.number_input(
                    "Spotřeba SP — NT (MWh/rok)", 0.0, 500.0,
                    float(_wd.get("sp_sp_nt_mwh", 0.0)), 0.1,
                    format="%.1f", key="w_sp_nt_rucne",
                    help="Z faktury SP: kWh NT ÷ 1000. 0 pokud nemáte NT.")
            with sp_k2:
                _sp_sazby = list(CENY_VT["ČEZ Distribuce"].keys())
                _sp_sazba_prev = _wd.get("sazba_sp", "D02d")
                _sp_sazba_idx = _sp_sazby.index(_sp_sazba_prev) if _sp_sazba_prev in _sp_sazby else 1
                _sp_sazba_r = st.selectbox("Sazba SP", _sp_sazby,
                    index=_sp_sazba_idx, key="w_sp_sazba_rucne",
                    format_func=lambda x: f"{x} — {POPIS_SAZEB.get(x,'')}")
                _sp_jistice = ["3×25A","3×32A","3×40A","3×50A","3×63A","3×80A","3×100A"]
                _sp_jistic_prev = _wd.get("jistic_sp", "3×25A")
                _sp_jistic_idx = _sp_jistice.index(_sp_jistic_prev) if _sp_jistic_prev in _sp_jistice else 0
                _sp_jistic_r = st.selectbox("Jistič SP", _sp_jistice,
                    index=_sp_jistic_idx, key="w_sp_jistic_rucne",
                    help="Jistič na odběrném místě společných prostor")
            _sp_jistic_a_map = {"3×25A":25,"3×32A":32,"3×40A":40,"3×50A":50,"3×63A":63,"3×80A":80,"3×100A":100}
            _sp_res = {
                "sp_mwh":      float(_sp_vt_r) + float(_sp_nt_r),
                "sp_vt_mwh":   float(_sp_vt_r),
                "sp_nt_mwh":   float(_sp_nt_r),
                "sazba_sp":    _sp_sazba_r,
                "jistic_sp":   _sp_jistic_r,
                "jistic_sp_a": _sp_jistic_a_map.get(_sp_jistic_r, 25),
                "popis":       [f"Zadáno ručně: {float(_sp_vt_r):.1f} MWh VT + {float(_sp_nt_r):.1f} MWh NT"],
            }
            # uložit vstupy pro navigaci zpět
            w_pocet_pater = int(_wd.get("sp_pocet_pater", 4))
            w_ma_vytah = bool(_wd.get("sp_ma_vytah", False))
            w_pocet_vytahu = int(_wd.get("sp_pocet_vytahu", 1))
            w_ma_tuv = bool(_wd.get("sp_ma_tuv", False))
            w_ma_tc = bool(_wd.get("sp_ma_tc", False))
            w_pocet_ev = int(_wd.get("sp_pocet_ev", 0))
            w_pocet_cerpadel = int(_wd.get("sp_pocet_cerpadel", 0))
        else:
            # ── Odhadnout SP dle vybavení ────────────────────────────
            st.caption("Výtah, osvětlení chodeb, centrální kotelna — spotřeba se počítá automaticky.")
            sp_c1, sp_c2 = st.columns(2)
            with sp_c1:
                w_pocet_pater = st.number_input(
                    "Počet nadzemních pater", 1, 30,
                    int(_wd.get("sp_pocet_pater", 4)), 1,
                    key="w_sp_pocet_pater",
                    help="Ovlivňuje spotřebu výtahu a osvětlení chodeb")
                w_ma_vytah = st.checkbox(
                    "🛗 Výtah", value=bool(_wd.get("sp_ma_vytah", False)),
                    key="w_sp_ma_vytah")
                if w_ma_vytah:
                    w_pocet_vytahu = st.number_input(
                        "Počet výtahů", 1, 10,
                        int(_wd.get("sp_pocet_vytahu", 1)), 1,
                        key="w_sp_pocet_vytahu")
                else:
                    w_pocet_vytahu = 0
                w_ma_tuv = st.checkbox(
                    "🚿 Centrální ohřev TUV (bojler/teplovod)",
                    value=bool(_wd.get("sp_ma_tuv", False)),
                    key="w_sp_ma_tuv",
                    help="Společný elektrický ohřev teplé vody pro celý dům")
            with sp_c2:
                w_ma_tc = st.checkbox(
                    "♨️ Tepelné čerpadlo pro dům",
                    value=bool(_wd.get("sp_ma_tc", False)),
                    key="w_sp_ma_tc",
                    help="TČ jako hlavní zdroj tepla pro celý dům (ne bytová TČ)")
                w_pocet_ev = st.number_input(
                    "🔌 Nabíječky EV v garážích (počet)", 0, 50,
                    int(_wd.get("sp_pocet_ev", 0)), 1,
                    key="w_sp_pocet_ev",
                    help="Počet nabíjecích stanic pro elektromobily ve společných garážích")
                w_pocet_cerpadel = st.number_input(
                    "🔄 Oběhová čerpadla (počet)", 0, 20,
                    int(_wd.get("sp_pocet_cerpadel", 0)), 1,
                    key="w_sp_pocet_cerpadel",
                    help="Čerpadla ústředního topení, cirkulace TUV — spotřeba závisí na počtu pater")

            _sp_res = _sp_sp_vypocet(
                pocet_bytu=pocet_bytu, pocet_pater=w_pocet_pater,
                ma_vytah=w_ma_vytah, pocet_vytahu=w_pocet_vytahu,
                ma_tuv_central=w_ma_tuv, ma_tc_dum=w_ma_tc,
                pocet_ev_nabijec=w_pocet_ev,
                pocet_cerpadel=w_pocet_cerpadel,
            )

        # ── Výsledek SP ─────────────────────────────────────────────
        _sp_radky = " · ".join(_sp_res["popis"]) if _sp_res["popis"] else "pouze osvětlení chodeb"
        st.success(
            f"🏢 **Společné prostory:** {_sp_res['sp_mwh']:.2f} MWh/rok "
            f"(VT {_sp_res['sp_vt_mwh']:.2f} + NT {_sp_res['sp_nt_mwh']:.2f}) · "
            f"Sazba: **{_sp_res['sazba_sp']}** · Jistič SP: **{_sp_res['jistic_sp']}** "
            f"(příkon SP ≈ {_sp_res['P_sp_kw']:.1f} kW → {_sp_res['I_sp_a']} A)\n\n"
            f"📋 {_sp_radky}"
        )

        # ── DISTRIBUTOR + PROFIL ──────────────────────────────────────
        st.divider()
        _prev_dist = _wd.get("dist", list(CENY_VT.keys())[0])
        _dist_idx = list(CENY_VT.keys()).index(_prev_dist) if _prev_dist in CENY_VT else 0
        dist = st.selectbox("Distributor", list(CENY_VT.keys()),
                             index=_dist_idx,
                             key="w_dist",
                             help="ČEZ = většina ČR | EG.D = Morava/jih Čech | PRE = Praha")
        st.markdown("**Složení domácností**")
        _w_profil_mix_def = int(_wd.get("profil_mix", 50))
        w_profil_mix = st.slider(
            "🏠 Doma přes den ◄──────────────► Pryč přes den 💼",
            0, 100, _w_profil_mix_def, 5, key="w_profil_mix",
            help="Vlevo = důchodci/HO (překryv s FVE lepší). Vpravo = pracující (baterie pomůže)."
        )
        w_pct_sen  = max(0, 100 - 2 * w_profil_mix)
        w_pct_prac = max(0, 2 * w_profil_mix - 100)
        w_pct_rod  = max(0, 50 - abs(w_profil_mix - 50))
        _ws = w_pct_sen + w_pct_prac + w_pct_rod
        if _ws > 0:
            _wf = 100.0 / _ws
            w_pct_sen  = int(w_pct_sen  * _wf)
            w_pct_prac = int(w_pct_prac * _wf)
            w_pct_rod  = max(0, 100 - w_pct_sen - w_pct_prac)
        if w_profil_mix <= 20:
            st.caption("🏠 Převaha důchodců/HO — dobrý přirozený překryv s FVE přes den")
        elif w_profil_mix <= 40:
            st.caption("🏠 Spíše doma přes den")
        elif w_profil_mix <= 60:
            st.caption("⚖️ Smíšené složení")
        elif w_profil_mix <= 80:
            st.caption("💼 Spíše pracující")
        else:
            st.caption("💼 Převaha pracujících — baterie výrazně pomůže zachytit denní přebytky FVE")
        profil = "mix"

        # ── JOM info box — až po výběru distributora (přesná čísla) ──
        _stay_d   = STAY_PLAT.get(dist, 163)
        _jbyt_cena_d = JISTIC_BYT.get(dist, JISTIC_BYT["ČEZ Distribuce"]).get(_jbyt_w, 132)
        _sazba_d  = _sazba_auto  # sazba bytů
        _jdom_amp = _jistic_dum_ampery(pocet_bytu, zarizeni_sel)
        _jdom_cena = _cena_jistice_dum(dist, _sazba_d, _jdom_amp, c_tarif=True)
        _platby_ted = (int(pocet_bytu) * (_stay_d + _jbyt_cena_d)
                       + (_stay_d + _cena_jistice_dum(dist, _sazba_d, _sp_res["jistic_sp_a"])))
        _platby_jom = _stay_d + _jdom_cena
        _uspora_jom_mes = _platby_ted - _platby_jom

        with st.expander("⚡ Co je JOM a kolik ušetří?", expanded=False):
            st.markdown(
                f"**JOM = Jedno Odběrné Místo** — celý dům má jeden jistič místo "
                f"{int(pocet_bytu)+1} individuálních.\n\n"
                f"| | Stávající stav | Po přechodu na JOM |\n"
                f"|---|---|---|\n"
                f"| Odběrná místa | {int(pocet_bytu)+1}× (byty + SP) | 1× (dům) |\n"
                f"| Jistič bytů | {int(pocet_bytu)}× **{_jbyt_w}** = {int(pocet_bytu)*_jbyt_cena_d:,} Kč/měs | — |\n"
                f"| Jistič SP | **{_sp_res['jistic_sp']}** = {_cena_jistice_dum(dist,_sazba_d,_sp_res['jistic_sp_a']):,} Kč/měs | — |\n"
                f"| Jistič JOM | — | **3×{_jdom_amp}A** = **{_jdom_cena:,} Kč/měs** |\n"
                f"| Stálé platby | {int(pocet_bytu)+1}× {_stay_d} = {(int(pocet_bytu)+1)*_stay_d:,} Kč/měs | 1× {_stay_d} Kč/měs |\n"
                f"| **Celkem** | **{_platby_ted:,} Kč/měs** | **{_platby_jom:,} Kč/měs** |\n"
                f"| **Úspora JOM** | | **{_uspora_jom_mes:,} Kč/měs · {_uspora_jom_mes*12:,} Kč/rok** |\n\n"
                f"*Distributor: {dist} · Sazba: {_sazba_d} · "
                f"Jistič JOM odhadnut dle počtu bytů a vybavení.*"
            )

        if st.button("Další →", type="primary", use_container_width=True):
            st.session_state.wizard_data.update({
                "pocet_bytu":           pocet_bytu,
                "pocet_vchodu":         pocet_vchodu,
                "sp_sp_mwh":            _sp_res["sp_mwh"],
                "sp_sp_vt_mwh":         _sp_res["sp_vt_mwh"],
                "sp_sp_nt_mwh":         _sp_res["sp_nt_mwh"],
                "sazba_sp":             _sp_res["sazba_sp"],
                "jistic_sp":            _sp_res["jistic_sp"],
                "jistic_sp_a":          _sp_res["jistic_sp_a"],
                "zarizeni_sel":         zarizeni_sel,
                "vt_mwh":               _vt_auto,
                "nt_mwh":               _nt_auto,
                "sazba":                _sazba_auto,
                "dist":                 dist,
                "profil":               profil,
                "profil_mix":           w_profil_mix,
                "pct_pracujici":        w_pct_prac,
                "pct_seniori":          w_pct_sen,
                "pct_rodiny":           w_pct_rod,
                "jistic":               _jistic_auto,
                "jistic_byt_typ":       _jbyt_w,
                "byt_znam_spotreba":    byt_znam,
                "sp_znam_spotreba":     sp_znam,
                # SP vstupy — pro navigaci zpět
                "sp_pocet_pater":       w_pocet_pater,
                "sp_ma_vytah":          w_ma_vytah,
                "sp_pocet_vytahu":      w_pocet_vytahu,
                "sp_ma_tuv":            w_ma_tuv,
                "sp_ma_tc":             w_ma_tc,
                "sp_pocet_ev":          w_pocet_ev,
                "sp_pocet_cerpadel":    w_pocet_cerpadel,
            })
            st.session_state.wizard_krok = 2
            st.rerun()

    # ── KROK 2: ADRESA + STŘECHA ─────────────────────────────────
    elif krok == 2:
        st.subheader("🌍 Krok 2: Adresa a střecha")

        _def_lok = st.session_state.wizard_data.get("lokace", "")
        lokace = st.text_input("Adresa nebo město",
                                value=_def_lok,
                                key="w_lokace",
                                placeholder="např. Náměstí Míru 5, Praha 2",
                                help="Zadejte adresu a stiskněte Enter — zobrazí se návrhy")
        if lokace and len(lokace) >= 4:
            with st.spinner("Hledám adresu..."):
                navrhys = _geocode_search(lokace)
            if navrhys:
                moznosti = []
                for n in navrhys[:5]:
                    addr = n.get("address", {})
                    parts = []
                    if addr.get("road"): parts.append(addr["road"])
                    if addr.get("house_number"): parts.append(addr["house_number"])
                    mesto = addr.get("city") or addr.get("town") or addr.get("village","")
                    if mesto: parts.append(mesto)
                    if addr.get("postcode"): parts.append(addr["postcode"])
                    label = ", ".join(parts) if parts else n.get("display_name","")[:60]
                    moznosti.append(label)
                if moznosti:
                    vyber = st.selectbox("Vyberte adresu:", ["— zadejte výše —"] + moznosti, key="w_vyber_addr")
                    if vyber != "— zadejte výše —":
                        lokace = vyber

        _prev_typ = st.session_state.wizard_data.get("typ_str", "sikma")
        typ_str = st.radio("Typ střechy", ["sikma","plocha"],
                            index=0 if _prev_typ=="sikma" else 1,
                            key="w_typ_str2",
                            format_func=lambda x: "🏠 Šikmá" if x=="sikma" else "🏢 Plochá",
                            horizontal=True)
        if typ_str == "sikma":
            sc1,sc2 = st.columns(2)
            _prev_sklon = st.session_state.wizard_data.get("sklon", 35)
            _prev_azimut = st.session_state.wizard_data.get("azimut", 0)
            with sc1: sklon = st.slider("Sklon (°)", 15, 60, int(_prev_sklon), key="w_sklon_sikma")
            with sc2: azimut = st.select_slider("Orientace",[-90,-45,0,45,90],_prev_azimut,key="w_azimut",
                                format_func=lambda x:{-90:"⬅️ Východ",-45:"↙️ JV",0:"⬆️ Jih",45:"↗️ JZ",90:"➡️ Západ"}[x])
            koef_str = 1.0
        else:
            pc1,pc2 = st.columns(2)
            _prev_sklon_pl = st.session_state.wizard_data.get("sklon", 10)
            _prev_sys_pl = st.session_state.wizard_data.get("sys_pl", "jih")
            _sys_pl_idx = ["jih","jz_jv","vz"].index(_prev_sys_pl) if _prev_sys_pl in ["jih","jz_jv","vz"] else 0
            with pc1: sklon = st.slider("Sklon panelů (°)", 5, 20, int(_prev_sklon_pl), key="w_sklon_plocha")
            with pc2: sys_pl = st.radio("Systém",["jih","jz_jv","vz"],index=_sys_pl_idx,key="w_sys_pl",
                        format_func=lambda x:{"jih":"⬆️ Jih","jz_jv":"↗️ JZ+JV","vz":"↔️ V+Z"}[x])
            azimut = {"jih": 0, "jz_jv": 998, "vz": 999}[sys_pl]
            koef_str = {"jih":1.0,"jz_jv":1.0,"vz":1.0}[sys_pl]

        col_back, col_next = st.columns(2)
        with col_back:
            if st.button("← Zpět", use_container_width=True):
                st.session_state.wizard_krok = 1; st.rerun()
        with col_next:
            if st.button("Spočítat doporučení →", type="primary", use_container_width=True):
                if not lokace:
                    st.error("Zadejte prosím adresu nebo město.")
                else:
                    _sys_pl_save = sys_pl if typ_str=="plocha" else "jih"
                    st.session_state.wizard_data.update({
                        "lokace": lokace, "typ_str": typ_str,
                        "sklon": sklon, "azimut": azimut, "koef_str": koef_str,
                        "sys_pl": _sys_pl_save,
                    })
                    st.session_state.wizard_krok = 3; st.rerun()

    # ── KROK 3: DOPORUČENÍ ───────────────────────────────────────
    elif krok == 3:
        st.subheader("🎯 Krok 3: Doporučená konfigurace")

        wd = st.session_state.wizard_data
        pocet_bytu = wd["pocet_bytu"]
        sp_vt = wd["vt_mwh"]*1000 + wd["sp_sp_mwh"]*1000
        sp_nt = wd["nt_mwh"]*1000

        with st.spinner("Stahuji solární data a počítám optimální konfiguraci..."):
            lat,lon,mesto,geo_err = _geocode(wd["lokace"])
            if geo_err:
                st.error(f"Lokalita nenalezena: {geo_err}")
                st.stop()

            # Pomocná funkce cena/kWp
            def _ckwp(kw):
                if kw<10: return 38000
                elif kw<20: return 33000
                elif kw<40: return 28000
                elif kw<80: return 24000
                else: return 21000

            # Algoritmus doporučení: 75% VT spotřeby, baterie 1.5× výkon FVE
            # Zdroj: praxe instalačních firem, optimalizace vlastní spotřeby
            sp_total_vt_kwh = sp_vt / 1000.0  # MWh/rok
            # FVE: 75% VT spotřeby, max 1:1 (nepřekračovat roční spotřebu)
            kwp_75_min = max(5.0, sp_total_vt_kwh / 1.05 * 0.75)  # 75% pokrytí
            kwp_75_max = max(5.0, sp_total_vt_kwh / 1.05 * 1.0)   # max 1:1
            kwp_75 = round(kwp_75_min / 5) * 5  # zaokrouhlit na 5 kWp
            kwp_75 = max(5.0, min(kwp_75_max, kwp_75))

            # Baterie: 1.5× výkon FVE (kWh), zaokrouhleno na 5 kWh
            bat_75 = round(kwp_75 * 1.4 / 5) * 5

            # Testovací výkon pro PVGIS (doporučený výkon)
            kwp_test = kwp_75
            vyroba_hod,pvgis_err = _pvgis(lat,lon,kwp_test*wd["koef_str"],wd["sklon"],wd["azimut"])
            if pvgis_err:
                vyroba_hod = _gen_vyroba_fallback(kwp_test*wd["koef_str"],wd["sklon"],wd["azimut"])

            # Profily spotřeby
            sazba = wd["sazba"]
            dist_w = wd["dist"]
            cena_vt_w = float(CENY_VT[dist_w][sazba])/1000
            cena_nt_w = float(CENY_NT[dist_w].get(sazba,CENY_VT[dist_w][sazba]))/1000
            profil_w = wd["profil"]
            uprava_w = _smiseny_profil(
                pct_pracujici=wd.get("pct_pracujici", max(0, int(2*wd.get("profil_mix",50)-100))),
                pct_seniori=wd.get("pct_seniori",   max(0, int(100-2*wd.get("profil_mix",50)))),
                pct_rodiny=wd.get("pct_rodiny",     max(0, int(50-abs(wd.get("profil_mix",50)-50)))),
            )
            sp_sp15 = _gen_profil_vt(wd["sp_sp_mwh"]*1000, _TDD_SP)
            sp_by_vt15 = _gen_profil_vt(wd["vt_mwh"]*1000, _TDD4, uprava_w)
            sp_by_nt15 = _gen_profil_nt(sp_nt, sazba)
            sp_vt15 = sp_sp15 + sp_by_vt15
            vchod_extra = max(0,int(wd.get("pocet_vchodu",1))-1)*30000

            # Simulujeme doporučenou konfiguraci
            vyr_opt = _interpoluj(vyroba_hod)
            ez = min(5.0, round(10.0/pocet_bytu**0.5,1))
            sim_opt = _simuluj(vyr_opt, sp_vt15, sp_by_nt15, float(bat_75), "edc", ez)
            inv_edc = kwp_test*_ckwp(kwp_test) + bat_75*15000 + vchod_extra
            cf_opt = _cashflow(
                vl_vt=sim_opt["vlastni_vt_kwh"],vl_nt=sim_opt["vlastni_nt_kwh"],
                pr=sim_opt["pretoky_kwh"],cvt=cena_vt_w,cnt=cena_nt_w,
                cpr=0.95,vlast=0.0,uver=inv_edc,spl=inv_edc/15,splat=15,
                rust=3.0,deg=0.5,leta=25,deg_bat=2.0)
            nav_opt = next((r["rok"] for r in cf_opt if r["kumulativni"]>=0),None)

            # Zkontroluj statickou návratnost a uprav výkon pokud > 10 let
            stat_nav_opt = inv_edc / cf_opt[0]["uspora_celkem"] if cf_opt[0]["uspora_celkem"]>0 else 99
            _iter = 0
            while stat_nav_opt > 10.0 and _iter < 5:
                # Snižujeme baterii jako první (dražší poměrově)
                if bat_75 > 0:
                    bat_75 = max(0, bat_75 - 5)
                else:
                    kwp_test = max(5.0, kwp_test - 5)
                inv_edc = kwp_test*_ckwp(kwp_test) + bat_75*15000 + vchod_extra
                vyr_opt = _interpoluj(vyroba_hod * (kwp_test/kwp_75 if kwp_75>0 else 1))
                sim_opt = _simuluj(vyr_opt, sp_vt15, sp_by_nt15, float(bat_75), "edc", ez)
                cf_opt = _cashflow(
                    vl_vt=sim_opt["vlastni_vt_kwh"],vl_nt=sim_opt["vlastni_nt_kwh"],
                    pr=sim_opt["pretoky_kwh"],cvt=cena_vt_w,cnt=cena_nt_w,
                    cpr=0.95,vlast=0.0,uver=inv_edc,spl=inv_edc/15,splat=15,
                    rust=3.0,deg=0.5,leta=25,deg_bat=2.0)
                nav_opt = next((r["rok"] for r in cf_opt if r["kumulativni"]>=0),None)
                stat_nav_opt = inv_edc / cf_opt[0]["uspora_celkem"] if cf_opt[0]["uspora_celkem"]>0 else 99
                _iter += 1

            nejlepsi = {"kwp":kwp_test,"bat":bat_75,"model":"edc",
                       "nav":nav_opt,"uspora":cf_opt[0]["uspora_celkem"],
                       "invest":inv_edc,"sim":sim_opt,"skore":1.0,
                       "mira_vs":sim_opt["mira_vs"],"mira_sob":sim_opt["mira_sob"],
                       "stat_nav":stat_nav_opt}

        # Zobrazit 3 varianty
        st.success(f"✅ Solární data pro **{mesto}** stažena")

        # Insight o baterii dle složení
        _pm_w = int(wd.get("profil_mix", 50))
        if _pm_w >= 70:
            st.info("🔋 **Převaha pracujících → baterie výrazně pomůže** — "
                    "přes den FVE vyrábí do prázdného domu, baterie zachytí přebytky pro večerní špičku.")
        elif _pm_w <= 30:
            st.info("☀️ **Převaha důchodců/HO → přirozený překryv s FVE** — "
                    "spotřeba přes den se kryje s výrobou. Větší FVE bez baterie může být výhodnější.")
        else:
            st.info("⚡ **Smíšené složení** — baterie pomůže zachytit polední přebytky pro večerní spotřebu.")

        st.markdown("### Doporučené varianty:")

        # Varianta 1: Základní (jen společné)
        v1_kwp = max(5, round(wd["sp_sp_mwh"]/1.05*10)/10)
        # Varianta 2: Optimální (nejlepší výsledek)
        v2 = nejlepsi
        # Varianta 3: Premium (větší FVE + baterie)
        v3_kwp = min(v2["kwp"]+10, 80)

        # 4 varianty: Základní / EDC bez bat / JOM / Doporučené (nejlepší)
        kv1,kv2,kv3,kv4 = st.columns(4)
        _var_list = [
            (kv1,"🏢 Jen společné",v1_kwp,0,"spolecne",False),
            (kv2,"🔗 EDC bez baterie",v2["kwp"],0,"edc",False),
            (kv3,"⚡ JOM",v2["kwp"],v2["bat"],"jom",False),
            (kv4,f"⭐ Nejlepší",v2["kwp"],v2["bat"],v2["model"],True),
        ]
        for _var_idx,(col,label,kwp,bat_v,model_v,highlight) in enumerate(_var_list):
            _inv = kwp*_ckwp(kwp)+(bat_v*15000)
            if model_v=="jom": _inv+=pocet_bytu*10000+75000+max(0,int(wd.get("pocet_vchodu",1))-1)*30000
            # Spočítáme simulaci pro tuto variantu
            _faktor = kwp/kwp_test if kwp_test>0 else 1
            _vyr_v = _interpoluj(vyroba_hod*_faktor)
            _ez = min(5.0,round(10.0/pocet_bytu**0.5,1)) if model_v=="edc" else 0.0
            _sv = sp_vt15 if model_v!="spolecne" else sp_sp15
            _sn = sp_by_nt15 if model_v!="spolecne" else np.zeros(_CD,dtype=float)
            _sm_v = _simuluj(_vyr_v,_sv,_sn,float(bat_v),model_v,_ez)
            # Úspora za jistič pro JOM — klíčový benefit!
            _jist_v = float(JISTIC_3x25.get(dist_w,JISTIC_3x25["ČEZ Distribuce"]).get(sazba,298))
            _uspora_jist_v = _jist_v*(int(pocet_bytu)-1)*12.0 if model_v=="jom" else 0.0
            _cf_v = _cashflow(vl_vt=_sm_v["vlastni_vt_kwh"],vl_nt=_sm_v["vlastni_nt_kwh"],
                              pr=_sm_v["pretoky_kwh"],cvt=cena_vt_w,cnt=cena_nt_w,
                              cpr=0.95,vlast=0.0,uver=_inv,spl=_inv/15,splat=15,
                              rust=3.0,deg=0.5,leta=25,jist=_uspora_jist_v,deg_bat=2.0)
            _nav_v = next((r["rok"] for r in _cf_v if r["kumulativni"]>=0),None)
            _us25 = sum(_cf_v[r-1]["uspora_celkem"] for r in range(1,26))
            with col:
                if highlight:
                    st.markdown(f"### {label}")
                else:
                    st.markdown(f"**{label}**")
                st.caption(f"Model: {model_v.upper()}")
                st.metric("Výkon FVE",f"{kwp} kWp")
                st.metric("Baterie",f"{bat_v} kWh" if bat_v>0 else "bez baterie")
                st.metric("Investice",f"{_inv:,.0f} Kč")
                st.metric("Vlastní spotřeba",f"{_sm_v['mira_vs']*100:.1f} %",
                          help="% výroby spotřebované v domě")
                st.metric("Soběstačnost",f"{_sm_v['mira_sob']*100:.1f} %")
                st.metric("Roční úspora",f"{_cf_v[0]['uspora_celkem']:,.0f} Kč")
                st.metric("Cashflow návratnost",f"{_nav_v} let" if _nav_v else ">25 let")
                st.metric("Úspora za 25 let",f"{_us25:,.0f} Kč")
                if st.button(f"{'✅ ' if highlight else ''}Vybrat",
                             key=f"vybrat_{_var_idx}_{model_v}_{kwp}_{bat_v}",
                             type="primary" if highlight else "secondary",
                             use_container_width=True):
                    st.session_state.wizard_data.update({
                        "vykon":float(kwp),"bat":bat_v,"model":model_v,
                        "lat":lat,"lon":lon,"mesto":mesto,
                        "vyroba_hod":vyroba_hod*_faktor,
                        "cena_invest":_inv,
                    })
                    st.session_state.wizard_krok = 4; st.rerun()

        # Tip o strategii EDC → JOM
        st.info("💡 **Tip:** Začněte s EDC (minimální investice, žádné stavební práce). "
                "Za 3–5 let při rekonstrukci domu můžete přejít na JOM a získat úsporu na distribuci.")

        col_back2, _ = st.columns(2)
        with col_back2:
            if st.button("← Zpět", use_container_width=True):
                st.session_state.wizard_krok = 2; st.rerun()

    # ── KROK 4: FINANCOVÁNÍ ──────────────────────────────────────
    elif krok == 4:
        st.subheader("💰 Krok 4: Financování")
        wd = st.session_state.wizard_data

        fc1,fc2 = st.columns(2)
        with fc1:
            scenar = st.radio("Scénář financování",["uver","vlastni","kombinace"],key="w_scenar",
                format_func=lambda x:{"uver":"🏦 Bezúročný úvěr NZÚ (od září 2026)",
                                      "vlastni":"💵 Vlastní zdroje (fond oprav)",
                                      "kombinace":"🔀 Kombinace vlastní + úvěr"}[x])
        with fc2:
            if scenar=="uver":
                splatnost=st.slider("Doba splácení (let)",5,25,15,key="w_splatnost_uver")
                vlastni_pct=0
                st.info("✅ Úroky hradí stát. SVJ splácí jen jistinu. Standardně 15 let.")
            elif scenar=="vlastni":
                splatnost=0; vlastni_pct=100
                st.info("💡 SVJ hradí vše z fondu oprav.")
            else:
                vlastni_pct=st.slider("Vlastní zdroje (%)",10,90,30,10,key="w_vlastni_pct")
                splatnost=st.slider("Doba splácení (let)",5,25,15,key="w_splatnost_komb")

        st.markdown("**Nízkopříjmové domácnosti (NZÚ bonus)**")
        nb1,nb2 = st.columns(2)
        with nb1: pocet_nizko=st.number_input("Bytů s bonusem",0,int(wd["pocet_bytu"]),0,1,key="w_pocet_nizko")
        with nb2: bonus_byt=st.number_input("Bonus na byt (Kč)",0,150000,100000,5000,key="w_bonus_byt")

        col_back3,col_next3 = st.columns(2)
        with col_back3:
            if st.button("← Zpět", use_container_width=True):
                st.session_state.wizard_krok = 3; st.rerun()
        with col_next3:
            if st.button("Spočítat výsledky →", type="primary", use_container_width=True):
                st.session_state.wizard_data.update({
                    "scenar":scenar,"splatnost":splatnost,"vlastni_pct":vlastni_pct,
                    "pocet_nizko":pocet_nizko,"bonus_byt":bonus_byt,
                })
                st.session_state.wizard_krok = 5; st.rerun()

    # ── KROK 5: VÝSLEDKY ─────────────────────────────────────────
    elif krok == 5:
        wd = st.session_state.wizard_data

        # Nastavíme všechny proměnné z wizard_data
        pocet_bytu    = wd["pocet_bytu"]
        pocet_vchodu  = wd.get("pocet_vchodu",1)
        sp_sp_mwh     = wd["sp_sp_mwh"]
        zarizeni_sel  = wd["zarizeni_sel"]
        dist          = wd["dist"]
        sazba         = wd["sazba"]
        profil        = wd["profil"]
        vykon         = wd["vykon"]
        bat           = wd["bat"]
        model         = wd["model"]
        scenar        = wd["scenar"]
        splatnost     = wd["splatnost"]
        vlastni_pct   = wd["vlastni_pct"]
        pocet_nizko   = wd["pocet_nizko"]
        bonus_byt     = wd["bonus_byt"]
        lokace        = wd["lokace"]
        sklon         = wd["sklon"]
        azimut        = wd["azimut"]
        koef_str      = wd["koef_str"]
        typ_str       = wd["typ_str"]
        rust_cen      = 3.0
        deg_pan       = 0.5
        cena_pretoky  = 0.95
        deg_bat_val   = 2.0
        edc_ztrata_val= min(5.0,round(10.0/pocet_bytu**0.5,1))

        sp_sp    = sp_sp_mwh*1000
        sp_by_vt = wd["vt_mwh"]*1000
        sp_by_nt = wd["nt_mwh"]*1000
        sp_cel   = sp_sp+sp_by_vt+sp_by_nt
        sp_by_vt_mwh = wd["vt_mwh"]
        sp_by_nt_mwh = wd["nt_mwh"]
        ma_nt    = sazba in SAZBY_NT
        # Investice
        def _ckwp_w5(kw):
            if kw<10: return 38000
            elif kw<20: return 33000
            elif kw<40: return 28000
            elif kw<80: return 24000
            else: return 21000
        cena_kwp     = _ckwp_w5(float(vykon))
        cena_fve     = int(float(vykon)*cena_kwp)
        cena_bat     = int(float(bat)*15000)
        _jom_merici  = int(pocet_bytu)*10000
        _jom_projekt = 75000
        cena_mericu  = (_jom_merici+_jom_projekt) if model=="jom" else 0
        _vchod_extra = max(0,int(pocet_vchodu)-1)*30000
        cena_mericu += _vchod_extra if model!="spolecne" else 0
        cena_invest  = cena_fve+cena_bat+cena_mericu
        vlastni_cast = float(cena_invest)*float(vlastni_pct)/100
        uver_cast    = max(0.0, float(cena_invest)-vlastni_cast)
        rocni_spl    = uver_cast/float(max(splatnost,1)) if scenar!="vlastni" else 0.0
        # Ceny elektřiny
        cena_vt  = float(CENY_VT.get(dist,CENY_VT["ČEZ Distribuce"]).get(sazba,7493))/1000
        cena_nt  = float(CENY_NT.get(dist,{}).get(sazba,7493))/1000
        jistic   = float(JISTIC_3x25.get(dist,JISTIC_3x25["ČEZ Distribuce"]).get(sazba,298))
        stay     = float(STAY_PLAT.get(dist, 163))
        # Úspora JOM — stávající: (N bytů + SP) × stálé + N×jistič_byt + jistič_SP
        #              JOM:      1× stálé + 1× velký jistič domu
        if model=="jom":
            _jbyt_cena2 = JISTIC_BYT.get(dist,JISTIC_BYT["ČEZ Distribuce"]).get(
                              _jistic_byt_typ(zarizeni_sel), 132)
            _jsp_a2     = int(wd.get("jistic_sp_a", 25))
            _jsp_cena2  = _cena_jistice_dum(dist, sazba, _jsp_a2)
            _jdum_amp2  = _jistic_dum_ampery(pocet_bytu, zarizeni_sel)
            _jdum_cena2 = _cena_jistice_dum(dist, sazba, _jdum_amp2, c_tarif=True)
            _platby_ted2 = (int(pocet_bytu)+1)*stay + int(pocet_bytu)*_jbyt_cena2 + _jsp_cena2
            _platby_jom2 = stay + _jdum_cena2
            uspora_jist = (_platby_ted2 - _platby_jom2) * 12.0
        else:
            uspora_jist = 0.0
        # Splátky
        podil_bytu_uver = uver_cast/float(pocet_bytu) if pocet_bytu>0 else 0
        bonus_efekt_byt = min(float(bonus_byt), podil_bytu_uver)
        zbytek_super    = max(0.0, podil_bytu_uver-bonus_efekt_byt)
        splatka_byt_std  = podil_bytu_uver/float(max(splatnost,1))/12 if scenar!="vlastni" else 0.0
        splatka_byt_super= zbytek_super/float(max(splatnost,1))/12 if scenar!="vlastni" else 0.0

        # Spustit simulaci
        with st.spinner("Simuluji..."):
            vyroba_hod = wd["vyroba_hod"]
            kwp_eff = float(vykon)*float(koef_str)
            vyroba_15 = _interpoluj(vyroba_hod)
            uprava = _smiseny_profil(
                pct_pracujici=wd.get("pct_pracujici", max(0, int(2*wd.get("profil_mix",50)-100))),
                pct_seniori=wd.get("pct_seniori",   max(0, int(100-2*wd.get("profil_mix",50)))),
                pct_rodiny=wd.get("pct_rodiny",     max(0, int(50-abs(wd.get("profil_mix",50)-50)))),
            )
            sp_sp15    = _gen_profil_vt(sp_sp,_TDD_SP)
            sp_by_vt15 = _gen_profil_vt(sp_by_vt,_TDD4,uprava)
            sp_by_nt15 = _gen_profil_nt(sp_by_nt,sazba)
            if model=="spolecne":
                sp_vt15=sp_sp15; sp_nt15=np.zeros(_CD,dtype=float)
            else:
                sp_vt15=sp_sp15+sp_by_vt15; sp_nt15=sp_by_nt15
            _edc_ztrata=float(edc_ztrata_val) if model=="edc" else 0.0
            sim=_simuluj(vyroba_15,sp_vt15,sp_nt15,float(bat),model,_edc_ztrata)
            cf=_cashflow(
                vl_vt=sim["vlastni_vt_kwh"],vl_nt=sim["vlastni_nt_kwh"],
                pr=sim["pretoky_kwh"],cvt=float(cena_vt),cnt=float(cena_nt),
                cpr=float(cena_pretoky),vlast=vlastni_cast,uver=uver_cast,
                spl=rocni_spl,splat=int(splatnost),rust=float(rust_cen),
                deg=float(deg_pan),leta=25,jist=float(uspora_jist),
                bonus=0.0,deg_bat=float(deg_bat_val))
            sp_vt_celkem=sp_sp15+sp_by_vt15; sp_nt_celkem=sp_by_nt15
            srovnani={}
            for mk in ["spolecne","jom","edc"]:
                _mericu_mk=int(pocet_bytu)*10000+75000 if mk=="jom" else 0
                _mericu_mk+=_vchod_extra if mk!="spolecne" else 0
                _jist_mk=jistic*(int(pocet_bytu)-1)*12.0 if mk=="jom" else 0.0
                _invest_mk=cena_fve+cena_bat+_mericu_mk
                _vlast_mk=float(_invest_mk)*float(vlastni_pct)/100
                _uver_mk=max(0.0,float(_invest_mk)-_vlast_mk)
                _spl_mk=_uver_mk/float(splatnost) if (scenar!="vlastni" and splatnost>0) else 0.0
                _ez_mk=float(edc_ztrata_val) if mk=="edc" else 0.0
                svt=sp_sp15 if mk=="spolecne" else sp_vt_celkem
                snt=np.zeros(_CD,dtype=float) if mk=="spolecne" else sp_nt_celkem
                sm=_simuluj(vyroba_15,svt,snt,float(bat),mk,_ez_mk)
                cfm=_cashflow(vl_vt=sm["vlastni_vt_kwh"],vl_nt=sm["vlastni_nt_kwh"],
                              pr=sm["pretoky_kwh"],cvt=float(cena_vt),cnt=float(cena_nt),
                              cpr=float(cena_pretoky),vlast=_vlast_mk,uver=_uver_mk,
                              spl=_spl_mk,splat=int(splatnost),rust=float(rust_cen),
                              deg=float(deg_pan),leta=25,jist=_jist_mk,bonus=0.0,
                              deg_bat=float(deg_bat_val))
                nav_m=next((r["rok"] for r in cfm if r["kumulativni"]>=0),None)
                stat_m=float(_invest_mk)/cfm[0]["uspora_celkem"] if cfm[0]["uspora_celkem"]>0 else 999
                splatka_mk=_spl_mk/float(pocet_bytu)/12
                cisty_byt_mk=cfm[0]["uspora_celkem"]/float(pocet_bytu)/12-splatka_mk
                srovnani[mk]={"sim":sm,"cf":cfm,"nav":nav_m,"stat":stat_m,
                              "rok1":cfm[0],"invest":_invest_mk,
                              "splatka_byt":splatka_mk,"cisty_byt":cisty_byt_mk}
            st.session_state["res"]={
                "sim":sim,"cf":cf,"vyroba_15":vyroba_15,
                "sp_vt15":sp_vt15,"sp_nt15":sp_nt15,
                "pvgis_ok":True,"mesto":wd["mesto"],"lat":wd["lat"],"lon":wd["lon"],
                "srovnani":srovnani,"cena_invest":cena_invest,
                "params":{
                    "pocet_bytu":pocet_bytu,"scenar":scenar,"splatnost":splatnost,
                    "vlastni_pct":vlastni_pct,"bonus_byt":bonus_byt,"pocet_nizko":pocet_nizko,
                    "bat":bat,"ma_nt":ma_nt,"sp_by_vt_mwh":sp_by_vt_mwh,
                    "sp_by_nt_mwh":sp_by_nt_mwh,"rust_cen":3.0,"deg_pan":0.5,
                    "cena_pretoky":0.95,"splatka_byt_std":splatka_byt_std,
                    "splatka_byt_super":splatka_byt_super,"sp_cel":float(sp_sp+sp_by_vt+sp_by_nt),
                    "model":model,"vykon":float(vykon),
                    "koef_str":float(koef_str),"typ_str":typ_str,
                    "sklon":sklon,"azimut":azimut,"profil":profil,"sazba":sazba,
                    "sp_sp_mwh":sp_sp_mwh,"sp_by_nt_mwh":float(sp_by_nt_mwh),
                }}

        st.button("← Upravit parametry", on_click=lambda: st.session_state.update({"wizard_krok":1}))
        st.divider()

# Zobrazit výsledky (pro oba módy)
if "res" not in st.session_state:
    st.info("👆 Vyplňte parametry a klikněte na **Spočítat simulaci**.")
    st.stop()

# ================================================================
# VÝSLEDKY
# ================================================================

d=st.session_state["res"]
sim=d["sim"]; cf=d["cf"]; srovnani=d["srovnani"]
rok1=cf[0]
nav=next((r["rok"] for r in cf if r["kumulativni"]>=0),None)

# === Načtení všech parametrů z session_state ===
cena_invest = d.get("cena_invest", 0)
_p = d.get("params", {})
_wd_fb = st.session_state.get("wizard_data", {})

def _pg(key, default):
    if _p and key in _p: return _p[key]
    _map = {"vt_mwh":"sp_by_vt_mwh","nt_mwh":"sp_by_nt_mwh"}
    k2 = _map.get(key,key)
    if _p and k2 in _p: return _p[k2]
    if key in _wd_fb: return _wd_fb[key]
    if k2 in _wd_fb: return _wd_fb[k2]
    return default

pocet_bytu      = int(_pg("pocet_bytu", 12))
pocet_nizko     = int(_pg("pocet_nizko", 0))
bonus_byt       = int(_pg("bonus_byt", 100000))
splatnost       = int(_pg("splatnost", 15))
scenar          = str(_pg("scenar", "uver"))
vlastni_pct     = float(_pg("vlastni_pct", 0))
bat             = int(_pg("bat", 0))
ma_nt           = bool(_pg("ma_nt", False))
sp_by_vt_mwh    = float(_pg("sp_by_vt_mwh", 0))
sp_by_nt_mwh    = float(_pg("sp_by_nt_mwh", 0))
rust_cen        = float(_pg("rust_cen", 3.0))
deg_pan         = float(_pg("deg_pan", 0.5))
cena_pretoky    = float(_pg("cena_pretoky", 0.95))
deg_bat_val     = 2.0
model           = str(_pg("model", "edc"))
sp_cel          = float(_pg("sp_cel", 0)) or float(sim.get("spotreba_kwh", 0))
splatka_byt_std = float(_pg("splatka_byt_std", 0))
splatka_byt_super = float(_pg("splatka_byt_super", 0))
vykon           = float(_pg("vykon", 20.0))
koef_str        = float(_pg("koef_str", 1.0))
profil          = str(_pg("profil", "mix"))
sazba           = str(_pg("sazba", "D02d"))
dist            = str(_pg("dist", "ČEZ Distribuce"))
pocet_vchodu    = int(_pg("pocet_vchodu", 1))
sp_sp_mwh       = float(_pg("sp_sp_mwh", 3.5))
sp_sp           = sp_sp_mwh * 1000
sp_by_vt        = sp_by_vt_mwh * 1000
sp_by_nt        = sp_by_nt_mwh * 1000
typ_str         = str(_pg("typ_str", "sikma"))
sklon           = int(_pg("sklon", 35))
azimut          = int(_pg("azimut", 0))
# Ceny
cena_vt   = float(CENY_VT.get(dist, CENY_VT["ČEZ Distribuce"]).get(sazba, 7493)) / 1000
cena_nt   = float(CENY_NT.get(dist, {}).get(sazba, 7493)) / 1000
stay      = float(STAY_PLAT.get(dist, 163))
jistic    = float(JISTIC_3x25.get(dist, JISTIC_3x25["ČEZ Distribuce"]).get(sazba, 298))

# Průměrná vs. mezní cena kWh
_naklad_fixni = (stay + jistic) * 12.0          # Kč/rok — fixní (nemění se s spotřebou)
_naklad_var   = (sp_by_vt * cena_vt             # variabilní (FVE šetří tuto část)
               + sp_by_nt * cena_nt
               + sp_sp    * cena_vt)
_naklad_celk  = _naklad_fixni + _naklad_var
_cena_mezni   = cena_vt                          # Kč/kWh — FVE šetří tuto cenu za každou kWh
_sp_cel_kwh   = sp_by_vt + sp_by_nt + sp_sp
_cena_prumerna = _naklad_celk / (_sp_cel_kwh / 1000.0) / 1000.0 if _sp_cel_kwh > 0 else cena_vt
# Úspora JOM — stávající: (N+1) ODM × stálé + N×jistič_byt + jistič_SP
#              JOM:      1 ODM × stálé + 1× velký jistič domu
if model=="jom":
    _zar_r       = _pg("zarizeni_sel", ["zaklad"])
    _jbyt_typ_r  = _jistic_byt_typ(_zar_r) if isinstance(_zar_r, list) else "1×25A"
    _jbyt_cena_r = JISTIC_BYT.get(dist,JISTIC_BYT["ČEZ Distribuce"]).get(_jbyt_typ_r, 132)
    _jsp_a_r     = int(_pg("jistic_sp_a", 25))
    _jsp_cena_r  = _cena_jistice_dum(dist, sazba, _jsp_a_r)
    _jdum_amp_r  = _jistic_dum_ampery(pocet_bytu, _zar_r if isinstance(_zar_r, list) else [])
    _jdum_cena_r = _cena_jistice_dum(dist, sazba, _jdum_amp_r, c_tarif=True)
    _platby_ted_res = (int(pocet_bytu)+1)*stay + int(pocet_bytu)*_jbyt_cena_r + _jsp_cena_r
    _platby_jom_res = stay + _jdum_cena_r
    uspora_jist = (_platby_ted_res - _platby_jom_res) * 12.0
else:
    uspora_jist = 0.0
# Investice
def _ckwp_res(kw):
    if kw<10: return 38000
    elif kw<20: return 33000
    elif kw<40: return 28000
    elif kw<80: return 24000
    else: return 21000
cena_kwp    = _ckwp_res(float(vykon))
cena_fve    = int(float(vykon)*cena_kwp)
cena_bat    = int(float(bat)*15000)
_jom_m      = int(pocet_bytu)*10000+75000
_vchod_e    = max(0,int(pocet_vchodu)-1)*30000
cena_mericu = (_jom_m if model=="jom" else 0) + (_vchod_e if model!="spolecne" else 0)
if cena_invest == 0:
    cena_invest = cena_fve + cena_bat + cena_mericu
# Splátky
vlastni_cast = float(cena_invest)*float(vlastni_pct)/100
uver_cast    = max(0.0, float(cena_invest)-vlastni_cast)
rocni_spl    = uver_cast/float(max(splatnost,1)) if scenar!="vlastni" else 0.0
podil_bytu_uver = uver_cast/float(pocet_bytu) if pocet_bytu>0 else 0
bonus_efekt_byt = min(float(bonus_byt), podil_bytu_uver)
zbytek_super = max(0.0, podil_bytu_uver-bonus_efekt_byt)
if splatka_byt_std == 0:
    splatka_byt_std = podil_bytu_uver/float(max(splatnost,1))/12 if scenar!="vlastni" else 0.0
    splatka_byt_super = zbytek_super/float(max(splatnost,1))/12 if scenar!="vlastni" else 0.0
splatka_vsichni = splatka_byt_std
uspora_diky_bonusu = splatka_byt_std - splatka_byt_super
bonus = int(pocet_nizko) * int(bonus_byt)
# Korekce sp_cel
if sp_cel == 0:
    sp_cel = float(sim.get("spotreba_kwh", sp_sp+sp_by_vt+sp_by_nt))
_sp_cel_res = sp_cel if sp_cel>0 else 1.0

stat_nav=float(cena_invest)/rok1["uspora_celkem"] if rok1["uspora_celkem"]>0 else 999
bonus = int(pocet_nizko) * int(bonus_byt)
# Splátky a bonus — bezpečný výpočet
_uver_res = cena_invest * (1 - float(_p.get("vlastni_pct",0)/100)) if _p else cena_invest
podil_bytu_uver = _uver_res / float(pocet_bytu) if pocet_bytu > 0 else 0
bonus_efekt_byt = min(float(bonus_byt), podil_bytu_uver)
zbytek_super = max(0.0, podil_bytu_uver - bonus_efekt_byt)
if splatka_byt_std == 0 and podil_bytu_uver > 0:
    _sl_r = _p.get("splatnost",15) if _p else 15
    _sc_r = _p.get("scenar","uver") if _p else "uver"
    splatka_byt_std = podil_bytu_uver/max(_sl_r,1)/12 if _sc_r!="vlastni" else 0.0
    splatka_byt_super = zbytek_super/max(_sl_r,1)/12 if _sc_r!="vlastni" else 0.0
splatka_vsichni = splatka_byt_std
cista_splatka_super = splatka_byt_super
uspora_byt_mesic = rok1["uspora_celkem"] / float(pocet_bytu) / 12.0
uspora_diky_bonusu = splatka_byt_std - splatka_byt_super

st.divider()
st.subheader("📊 Výsledky simulace")

# Killer metrika nahoře — kolik % výroby se využije
util_pct = sim["mira_vs"]*100
if util_pct >= 70:
    util_delta = "výborné využití ✅"
elif util_pct >= 50:
    util_delta = "dobré využití"
else:
    util_delta = "zvažte baterii"

# Soběstačnost — vždy vůči celkové spotřebě domu (i pro model "spolecne")
_sp_cel_res = float(sp_cel) if sp_cel > 0 else float(sim.get("spotreba_kwh", sim["vlastni_kwh"]+sim["odber_vt_kwh"]+sim.get("odber_nt_kwh",0)))
mira_sob_real = min(1.0, sim["vlastni_kwh"] / _sp_cel_res) if _sp_cel_res > 0 else 0.0

r1,r2,r3,r4,r5,r6,r7=st.columns(7)
with r1: st.metric("Roční výroba FVE",f"{sim['vyroba_kwh']/1000:.1f} MWh")
with r2: st.metric("Využití výroby v domě",f"{util_pct:.1f} %",
                   delta=util_delta,
                   help="Klíčová metrika: kolik % výroby FVE se spotřebuje přímo v domě nebo přes baterii. Zbytek jde za nízkou výkupní cenu.")
with r3: st.metric("Soběstačnost",f"{mira_sob_real*100:.1f} %",help="% celkové spotřeby domu (vč. bytů) pokryté FVE")
with r4: st.metric("Úspora FVE (rok 1)",
                   f"{rok1.get('uspora_fve', rok1['uspora_celkem']-rok1.get('uspora_jom',0)):,.0f} Kč",
                   help="Úspora z vyrobené elektřiny (přímá spotřeba VT, baterie NT, přetoky)")
with r5: st.metric("Úspora JOM (rok 1)",
                   f"{rok1.get('uspora_jom', 0):,.0f} Kč" if rok1.get('uspora_jom', 0) > 0 else "—",
                   help="Úspora ze zrušení individuálních odběrných míst (jističe + stálé platby)")
with r6: st.metric("Orientační návratnost",
                   f"{stat_nav:.1f} let" if stat_nav > 0.1 else "—",
                   help="Investice ÷ roční úspora — pouze orientačně, bez vlivu růstu cen")
with r7: st.metric("Cashflow návratnost",f"{nav} let" if nav else ">25 let",
                   help="Realistická návratnost: kdy kumulativní cashflow přejde do kladných čísel")

# JOM detail — zobrazit přímo (ne v expanderu) pokud je model JOM
if model == "jom" and uspora_jist > 0:
    st.info(
        f"⚡ **JOM — Jedno odběrné místo** · "
        f"Nový jistič: **3×{_jdum_amp_r}A** ({_jdum_cena_r:,} Kč/měs) · "
        f"Sazba domu: **{sazba}** · "
        f"Rušíte: {int(pocet_bytu)+1} ODM → 1 ODM · "
        f"Úspora na jističích a stálých: **{uspora_jist/12:,.0f} Kč/měs · {uspora_jist:,.0f} Kč/rok**"
    )

# Míra časového překryvu — zobrazit vždy (pro všechny modely)
prekryv = sim.get("edc_efektivita", 1.0) * 100
if prekryv >= 70:
    prekryv_hod = "výborné — výroba a spotřeba jsou dobře sladěny"
elif prekryv >= 50:
    prekryv_hod = "dobré — baterie může pomoci s nesouladem"
else:
    prekryv_hod = "nízké — velká část výroby jde mimo dobu spotřeby, baterie velmi doporučena"
st.info(f"⏱️ **Míra časového sladění výroby a spotřeby: {prekryv:.1f} %** — "
        f"{prekryv_hod}. "
        f"Závisí na profilu: senioři = vyšší, pracující = nižší.")

# Rozpad úspory — FVE vs JOM zvlášť
_uspora_fve1  = rok1.get("uspora_fve",  rok1["uspora_vt"] + rok1["uspora_nt"] + rok1["uspora_pretoky"])
_uspora_jom1  = rok1.get("uspora_jom", 0)

_radky = []
if _uspora_fve1 > 0:
    _detail = f"(VT {rok1['uspora_vt']:,.0f} + NT {rok1['uspora_nt']:,.0f} + přetoky {rok1['uspora_pretoky']:,.0f} Kč)"
    _radky.append(f"☀️ **Úspora z FVE: {_uspora_fve1:,.0f} Kč/rok** {_detail}")
if _uspora_jom1 > 0:
    _radky.append(f"⚡ **Úspora z JOM: {_uspora_jom1:,.0f} Kč/rok** "
                  f"(zrušení {int(pocet_bytu)+1} ODM → 1 ODM, ušetřené jističe + stálé platby)")
if _radky:
    st.info("🔍 **Rozpad roční úspory (rok 1):**\n\n" + "\n\n".join(_radky))

# Průměrná vs. mezní cena kWh
st.info(
    f"💰 **Cena elektřiny ({dist}, {sazba}):** "
    f"Mezní cena: **{_cena_mezni:.2f} Kč/kWh** — tolik ušetří každá kWh vyrobená FVE. "
    f"Průměrná cena: **{_cena_prumerna:.2f} Kč/kWh** — reálná cena po rozpuštění fixních plateb "
    f"({_naklad_fixni:,.0f} Kč/rok) do celkové spotřeby {_sp_cel_kwh/1000:.1f} MWh. "
    f"Rozdíl: **{_cena_prumerna - _cena_mezni:.2f} Kč/kWh** tvoří fixní složka (jistič + stálý plat)."
)

st.divider()

# ── POROVNÁNÍ MODELŮ ──────────────────────────────────────────────
st.subheader("📊 Porovnání modelů sdílení")
st.caption("Stejná FVE a baterie pro všechny modely — mění se jen model sdílení, investice a úspory. "
           "⚡ JOM: vyšší investice (měřiče +{:,} Kč) ale ušetří {:,.0f} Kč/rok na distribuci → proto může vycházet lépe než EDC.".format(
               int(pocet_bytu)*10000+75000,
               float(uspora_jist)
           ))
nazvy={"spolecne":"🏢 Jen společné","jom":"⚡ JOM","edc":"🔗 EDC"}
# Najdi nejlepší model dle cashflow návratnosti
best_mk = min(["spolecne","jom","edc"],
              key=lambda x: srovnani[x]["nav"] if srovnani[x]["nav"] else 999)
sc1,sc2,sc3=st.columns(3)
for col,mk in zip([sc1,sc2,sc3],["spolecne","jom","edc"]):
    sv=srovnani[mk]
    cisty_byt=sv["cisty_byt"]        # počítáno s vlastní investicí modelu
    splatka_byt_mk=sv["splatka_byt"] # splátka pro tento konkrétní model
    je_vybran = mk == model
    je_nejlepsi = mk == best_mk
    with col:
        hlavicka = nazvy[mk]
        if je_nejlepsi: hlavicka += " ⭐"
        if je_vybran:   hlavicka += " ✓"
        st.markdown(f"**{hlavicka}**")
        if mk=="jom":
            st.caption(f"Investice: {sv['invest']:,.0f} Kč (vč. měřičů)")
        else:
            st.caption(f"Investice: {sv['invest']:,.0f} Kč")
        st.metric("Roční úspora",f"{sv['rok1']['uspora_celkem']:,.0f} Kč")
        st.metric("Vlastní spotřeba",f"{sv['sim']['mira_vs']*100:.1f} %")
        # Pro "spolecne" počítáme soběstačnost vůči celé spotřebě domu
        _sp_cel_srov = sp_cel if sp_cel>0 else float(sim.get("spotreba_kwh",1))
        _sob = min(1.0, sv["sim"]["vlastni_kwh"] / _sp_cel_srov) if _sp_cel_srov>0 else 0.0
        st.metric("Soběstačnost",f"{_sob*100:.1f} %",
                  help="% celkové spotřeby domu pokryté FVE" if mk!="spolecne" else "% celkové spotřeby domu — FVE kryje jen společné prostory")
        st.metric("Statická návratnost",f"{sv['stat']:.1f} let")
        st.metric("Cashflow návratnost",f"{sv['nav']} let" if sv['nav'] else ">25 let")
        st.metric("Splátka/byt",f"{splatka_byt_mk:.0f} Kč/měs")
        if cisty_byt>=0:
            st.metric("Čistý přínos/byt",f"+{cisty_byt:.0f} Kč/měs",delta="kladný")
        else:
            st.metric("Čistý náklad/byt",f"{cisty_byt:.0f} Kč/měs",delta_color="inverse")
        if je_vybran:
            st.info("✓ Váš výběr")

st.divider()

# ── PŘEHLED NA BYT ────────────────────────────────────────────────
st.subheader("🏠 Přehled na jednotlivý byt (měsíčně)")
ba1,ba2=st.columns(2)
with ba1:
    st.markdown("**Standardní byt**")
    cisty_std=uspora_byt_mesic-splatka_vsichni
    st.metric("Úspora z FVE",f"{uspora_byt_mesic:.0f} Kč/měs")
    st.metric("Splátka úvěru",f"{splatka_vsichni:.0f} Kč/měs")
    if cisty_std>=0:
        st.metric("Čistý měsíční přínos",f"+{cisty_std:.0f} Kč/měs",delta="kladný od roku 1")
    else:
        st.metric("Čistý měsíční náklad",f"{cisty_std:.0f} Kč/měs")
    # Bonus pomáhá jen bytu se superdávkou — nezobrazujeme pro standardní byt
with ba2:
    if pocet_nizko>0:
        st.markdown(f"**Byt se superdávkou** ({pocet_nizko}× v domě)")
        cisty_super=uspora_byt_mesic-cista_splatka_super
        st.metric("Úspora z FVE",f"{uspora_byt_mesic:.0f} Kč/měs")
        st.metric("Podíl na úvěru (celkem)",f"{podil_bytu_uver:,.0f} Kč",
                  help="Podíl tohoto bytu na celkovém úvěru SVJ")
        st.metric("Přímý bonus NZÚ",f"{bonus_efekt_byt:,.0f} Kč",
                  delta=f"pokryje {bonus_efekt_byt/podil_bytu_uver*100:.0f}% podílu" if podil_bytu_uver>0 else "",
                  help="Přímá platba státu na konkrétní byt — snižuje jeho zbývající dluh na úvěru")
        st.metric("Zbývající splátka",f"{cista_splatka_super:.0f} Kč/měs",
                  help=f"Splátka po odečtení bonusu. Std byt: {splatka_vsichni:.0f} Kč/měs")
        if cisty_super>=0:
            st.metric("Čistý měsíční přínos",f"+{cisty_super:.0f} Kč/měs",
                      delta=f"+{cisty_super-cisty_std:.0f} Kč vs std. byt")
        else:
            st.metric("Čistý měsíční náklad",f"{cisty_super:.0f} Kč/měs")
        st.divider()
        st.markdown("**🤝 Přínos bonusu NZÚ**")
        st.write(f"• Přímý bonus od státu: **{bonus_efekt_byt:,.0f} Kč** (na byt se superdávkou)")
        st.write(f"• Bonus pokryje: **{bonus_efekt_byt/podil_bytu_uver*100:.0f}%** podílu na úvěru")
        st.write(f"• Zbývající splátka super bytu: **{cista_splatka_super:.0f} Kč/měs** (vs {splatka_vsichni:.0f} Kč std)")
        st.write(f"• Ostatní byty: splátka **{splatka_vsichni:.0f} Kč/měs** — beze změny")
    else:
        st.markdown("**Žádné byty se superdávkou**")
        st.caption("Zadejte počet bytů s bonusem výše.")

st.divider()

# ── MILNÍKY ───────────────────────────────────────────────────────
st.markdown("**📍 Klíčové milníky**")
m1,m2,m3=st.columns(3)
with m1:
    lines=["**Rok 1**",
           f"Vlastní spotřeba VT: **{sim['vlastni_vt_kwh']:,.0f} kWh**",
           f"Vlastní spotřeba NT (bat): **{sim['vlastni_nt_kwh']:,.0f} kWh**",
           f"Přetoky do sítě: **{sim['pretoky_kwh']:,.0f} kWh**",
           f"**Celková úspora: {rok1['uspora_celkem']:,.0f} Kč/rok**",
           f"Na byt: **{uspora_byt_mesic*12:,.0f} Kč/rok** · **{uspora_byt_mesic:.0f} Kč/měs**",
           f"Splátka na byt: **{splatka_vsichni:.0f} Kč/měs**"]
    st.info("  \n".join(lines))
with m2:
    if scenar!="vlastni" and splatnost>0 and splatnost<=25:
        rs=cf[min(splatnost-1,len(cf)-1)]
        lines=[f"**Rok {splatnost} — úvěr splacen ✅**",
               f"Úspora v tom roce: **{rs['uspora_celkem']:,.0f} Kč**",
               f"(vč. růstu cen +{rust_cen}%/rok)",
               f"Poté plný přínos bez splátky:",
               f"**{rs['uspora_celkem']:,.0f} Kč/rok**"]
        st.info("  \n".join(lines))
    else:
        st.info("  \n".join(["**Vlastní financování**","Žádné splátky",
                              f"Plný přínos od roku 1:",f"**{rok1['uspora_celkem']:,.0f} Kč/rok**"]))
with m3:
    kum25=cf[-1]["kumulativni"]
    if nav:
        lines=[f"**Rok {nav} — investice se vrátí ✅**",
               f"Statická: **{stat_nav:.1f} let** · Cashflow: **{nav} let**",
               f"Za 25 let celková úspora:",
               f"**{kum25:,.0f} Kč** ({kum25/float(pocet_bytu):,.0f} Kč/byt)",
               f"→ dalších {max(0,25-nav)} let čistý zisk!"]
        st.success("  \n".join(lines))
    else:
        st.warning("  \n".join([f"**Za 25 let investice se nevrátí**",
                                f"Cashflow: **{kum25:,.0f} Kč**",
                                "Zvyšte výkon FVE nebo zvolte jiný model."]))

st.divider()

# ── GRAFY ─────────────────────────────────────────────────────────
tab1,tab2,tab3,tab4=st.tabs(["📅 Denní graf","📈 Roční přehled","💰 Cashflow 25 let","📊 Splátka vs Úspora"])

with tab1:
    st.markdown("**Průměrný den — výroba vs spotřeba**")
    gc1,gc2=st.columns(2)
    with gc1: sezona_g=st.radio("Sezóna",["zima","prechodne","leto"],index=2,horizontal=True,key="r_sezona",
                                 format_func=lambda x:{"zima":"❄️ Zima","prechodne":"🌤️ Jaro/Podzim","leto":"☀️ Léto"}[x])
    with gc2: pocasi_g=st.radio("Počasí",["jasno","polojasno","zatazeno"],index=0,horizontal=True,key="r_pocasi",
                                 format_func=lambda x:{"jasno":"☀️ Jasno","polojasno":"⛅ Polojasno","zatazeno":"☁️ Zataženo"}[x])

    kwp_eff=float(vykon)*float(koef_str)
    vyr_den=_gen_vyroba_den(kwp_eff,sezona_g,pocasi_g)
    sp_total_vt=(sp_sp+sp_by_vt) if model!="spolecne" else sp_sp
    sp_total_nt=sp_by_nt if model!="spolecne" else 0.0
    sp_den_vt=_gen_spotreba_den(sp_total_vt,sezona_g,profil,False)
    # NT profil pro den
    nt_h=NT_HODINY.get(sazba,set())
    sp_den_nt=np.zeros(96,dtype=float)
    if sp_total_nt>0 and nt_h:
        nt_den=sp_total_nt/365.0
        for i in range(96):
            if (i//4) in nt_h: sp_den_nt[i]=nt_den/len(nt_h)/4.0 if len(nt_h)>0 else 0

    hodiny=[i/4.0 for i in range(96)]
    sp_den_total=sp_den_vt+sp_den_nt

    fig=go.Figure()
    fig.add_trace(go.Scatter(x=hodiny,y=vyr_den*4,name="⚡ Výroba FVE (kW)",
                              fill="tozeroy",fillcolor="rgba(255,193,7,0.2)",
                              line=dict(color="#FFC107",width=2)))
    fig.add_trace(go.Scatter(x=hodiny,y=sp_den_vt*4,name="🏠 Spotřeba VT (kW)",
                              line=dict(color="#2196F3",width=2)))
    if ma_nt and sp_total_nt>0:
        fig.add_trace(go.Scatter(x=hodiny,y=sp_den_nt*4,name="🌙 Spotřeba NT (kW)",
                                  fill="tozeroy",fillcolor="rgba(156,39,176,0.15)",
                                  line=dict(color="#9C27B0",width=1,dash="dot")))
    # Baterie SOC — stejná logika jako hlavní simulace
    # VT spotřeba má prioritu před NT (dražší tarif)
    bat_soc=np.zeros(96)
    if bat>0:
        _bmin=float(bat)*0.10
        _bmax=float(bat)*0.90
        _eta=0.92
        # Začínáme s vybitou baterií — realisticky po noční spotřebě
        bkwh=float(bat)*0.20
        for i in range(96):
            vi   = float(vyr_den[i])
            svti = float(sp_den_vt[i])
            snti = float(sp_den_nt[i])

            # 1. FVE → VT spotřeba přímo
            prime = min(vi, svti)
            zbv   = vi - prime
            zbsvt = svti - prime

            # 2. Přebytek výroby → nabít baterii
            if zbv > 0:
                nab = min(zbv*_eta, _bmax-bkwh)
                bkwh += nab
                zbv  -= nab/_eta

            # 3. Zbylá VT spotřeba → vybít baterii (VT = dražší, priorita!)
            if zbsvt > 0:
                dos = (bkwh-_bmin)*_eta
                vyb = min(zbsvt, dos)
                bkwh -= vyb/_eta
                zbsvt -= vyb

            # 4. NT spotřeba → vybít zbylou baterii
            if snti > 0:
                dos = (bkwh-_bmin)*_eta
                vyb = min(snti, dos)
                bkwh -= vyb/_eta

            bat_soc[i] = bkwh/float(bat)*100

        fig.add_trace(go.Scatter(x=hodiny,y=bat_soc,name="🔋 Baterie SOC (%)",
                                  yaxis="y2",line=dict(color="#4CAF50",width=2,dash="dash")))

    lay=dict(_LAY); lay.update(dict(
        xaxis=dict(title="Hodina",tickmode="linear",tick0=0,dtick=2,
                   range=[0,24],fixedrange=True,
                   tickvals=list(range(0,25,2)),
                   ticktext=[f"{h}:00" for h in range(0,25,2)]),
        yaxis=dict(title="kW",fixedrange=True,rangemode="tozero"),height=380))
    if bat>0: lay["yaxis2"]=dict(title="SOC %",overlaying="y",side="right",
                                  range=[0,100],fixedrange=True)
    fig.update_layout(**lay)
    st.plotly_chart(fig,use_container_width=True,config=_CFG,key="chart_1")

with tab2:
    fig2=go.Figure()
    fig2.add_trace(go.Bar(x=_MESICE,y=[x/1000 for x in sim["mesice_vyroba"]],
                           name="Výroba FVE (MWh)",marker_color="#FFC107",opacity=0.8))
    fig2.add_trace(go.Bar(x=_MESICE,y=[x/1000 for x in sim["mesice_vlastni"]],
                           name="Vlastní spotřeba (MWh)",marker_color="#4CAF50",opacity=0.9))
    fig2.add_trace(go.Bar(x=_MESICE,y=[x/1000 for x in sim["mesice_pretoky"]],
                           name="Přetoky (MWh)",marker_color="#9E9E9E",opacity=0.7))
    lay2=dict(_LAY); lay2.update(dict(barmode="overlay",
        yaxis=dict(title="MWh",fixedrange=True),height=350))
    fig2.update_layout(**lay2)
    st.plotly_chart(fig2,use_container_width=True,config=_CFG,key="chart_2")

with tab3:
    roky=[r["rok"] for r in cf]
    kum=[r["kumulativni"] for r in cf]
    fig3=go.Figure()
    fig3.add_trace(go.Scatter(x=roky,y=kum,name="Kumulativní cashflow",
                               fill="tozeroy",fillcolor="rgba(33,150,243,0.15)",
                               line=dict(color="#2196F3",width=3)))
    fig3.add_hline(y=0,line_dash="dash",line_color="#666",line_width=1)
    if nav:
        fig3.add_vline(x=nav,line_dash="dot",line_color="#4CAF50",line_width=2,
                       annotation_text=f"Rok {nav}",annotation_position="top right")
    if scenar!="vlastni":
        fig3.add_trace(go.Bar(x=roky,y=[-r["splatka"] for r in cf],
                               name="Splátka úvěru",marker_color="rgba(244,67,54,0.4)"))
    lay3=dict(_LAY); lay3.update(dict(
        xaxis=dict(title="Rok",fixedrange=True,dtick=2),
        yaxis=dict(title="Kč",fixedrange=True,tickformat=","),
        height=380,barmode="overlay"))
    fig3.update_layout(**lay3)
    st.plotly_chart(fig3,use_container_width=True,config=_CFG,key="chart_3")

with tab4:
    st.markdown("**Splátka úvěru vs Úspora z FVE — rok po roku**")
    st.caption("Klíčová otázka: od kdy je úspora vyšší než splátka?")

    roky_g  = [r["rok"] for r in cf]
    uspora_g = [r["uspora_celkem"] for r in cf]
    splatka_g = [r["splatka"] for r in cf]
    cisty_g  = [r["cisty_prinos"] for r in cf]
    kum_g    = [r["kumulativni"] for r in cf]

    fig4 = go.Figure()

    # Úspora z FVE — roste každý rok
    fig4.add_trace(go.Bar(
        x=roky_g, y=uspora_g, name="Úspora z FVE (Kč/rok)",
        marker_color="#4CAF50", opacity=0.85))

    # Splátka úvěru — konstantní, pak 0
    fig4.add_trace(go.Bar(
        x=roky_g, y=[-s for s in splatka_g], name="Splátka úvěru (Kč/rok)",
        marker_color="#F44336", opacity=0.75))

    # Čistý přínos — linie
    fig4.add_trace(go.Scatter(
        x=roky_g, y=cisty_g, name="Čistý přínos (Kč/rok)",
        line=dict(color="#2196F3", width=3),
        mode="lines+markers", marker=dict(size=4)))

    # Nulová linie
    fig4.add_hline(y=0, line_dash="dash", line_color="#666", line_width=1)

    # Označit rok splacení úvěru
    if scenar != "vlastni" and splatnost > 0:
        fig4.add_vline(x=splatnost+0.5, line_dash="dot", line_color="#FF9800",
                       line_width=2,
                       annotation_text=f"Úvěr splacen (rok {splatnost})",
                       annotation_position="top left")

    # Označit cashflow návratnost
    if nav:
        fig4.add_vline(x=nav, line_dash="dot", line_color="#4CAF50", line_width=2,
                       annotation_text=f"Návratnost (rok {nav})",
                       annotation_position="top right")

    lay4 = dict(_LAY)
    lay4.update(dict(
        barmode="relative",
        xaxis=dict(title="Rok", fixedrange=True, dtick=2),
        yaxis=dict(title="Kč/rok", fixedrange=True, tickformat=","),
        height=420,
    ))
    fig4.update_layout(**lay4)
    st.plotly_chart(fig4, use_container_width=True, config=_CFG,key="chart_4")

    # Přehledná tabulka — jen klíčové roky
    klic_roky = [1, 5, 10, int(splatnost) if splatnost else 15, 20, 25]
    klic_roky = sorted(set(r for r in klic_roky if 1 <= r <= 25))
    st.markdown("**Klíčové roky:**")
    cols_tab4 = st.columns(len(klic_roky))
    for col, rok in zip(cols_tab4, klic_roky):
        r = cf[rok-1]
        with col:
            st.metric(f"Rok {rok}",
                      f"{r['uspora_celkem']:,.0f} Kč",
                      delta=f"splátka {r['splatka']:,.0f} Kč" if r['splatka']>0 else "bez splátky")

st.divider()

# ── VERDIKT ───────────────────────────────────────────────────────
st.subheader("🎯 Verdikt a scénáře")

# Verdikt
kum25=cf[-1]["kumulativni"]
if nav and nav <= 12:
    verdikt_text = "✅ PROJEKT SE JEDNOZNAČNĚ VYPLATÍ"
    verdikt_color = "success"
    verdikt_popis = f"Cashflow návratnost {nav} let je výborná. Investice je bezpečná i při konzervativním scénáři (+1%/rok)."
elif nav and nav <= 20:
    verdikt_text = "⚠️ PROJEKT JE HRANIČNÍ"
    verdikt_color = "warning"
    verdikt_popis = f"Cashflow návratnost {nav} let závisí na vývoji cen elektřiny. Při realistickém scénáři (+{rust_cen:.0f}%/rok) se vyplatí. Bezúročný úvěr NZÚ výrazně snižuje riziko."
elif nav:
    verdikt_text = "⚠️ PROJEKT JE RIZIKOVÝ"
    verdikt_color = "warning"
    verdikt_popis = f"Cashflow návratnost {nav} let je dlouhá. Zvažte vyšší výkon FVE, baterii nebo model JOM/EDC pro lepší využití výroby."
else:
    verdikt_text = "❌ PROJEKT SE NEVRÁTÍ ZA 25 LET"
    verdikt_color = "error"
    verdikt_popis = "Při současných parametrech se investice nevrátí za životnost panelů. Zásadně přehodnoťte výkon FVE a model sdílení."

if verdikt_color == "success":
    st.success(f"**{verdikt_text}**  \n{verdikt_popis}")
elif verdikt_color == "warning":
    st.warning(f"**{verdikt_text}**  \n{verdikt_popis}")
else:
    st.error(f"**{verdikt_text}**  \n{verdikt_popis}")

# Bez FVE vs s FVE
st.markdown("**💡 Bez FVE vs s FVE — celkové náklady za 25 let**")
bv1,bv2,bv3=st.columns(3)

for col,rust_sc,nazev in zip(
    [bv1,bv2,bv3],
    [1.0, float(rust_cen), 6.0],
    ["😐 Pesimistický (+1%/rok)","📊 Realistický (+{}%/rok)".format(rust_cen),"🔥 Krizový (+6%/rok)"]
):
    # Náklady bez FVE
    _sp_cel_sc = sp_cel if sp_cel>0 else float(sim.get("spotreba_kwh",0))
    naklad_bez=sum(_sp_cel_sc*cena_vt*(1+rust_sc/100)**(r-1) for r in range(1,26))
    # Úspory s FVE (degradace + růst cen)
    uspora_sc=sum(
        rok1["uspora_celkem"]*(1+rust_sc/100)**(r-1)*(1-float(deg_pan)/100)**(r-1)
        for r in range(1,26))
    naklad_s=max(0.0, naklad_bez-uspora_sc)
    # Cashflow návratnost pro tento scénář
    kum_sc=-(vlastni_cast+uver_cast-float(bonus))
    nav_sc=None
    for r in range(1,26):
        u_sc=rok1["uspora_celkem"]*(1+rust_sc/100)**(r-1)*(1-float(deg_pan)/100)**(r-1)
        s_sc=rocni_spl if r<=int(splatnost) else 0.0
        kum_sc+=u_sc-s_sc
        if kum_sc>=0 and nav_sc is None: nav_sc=r
    with col:
        st.markdown(f"**{nazev}**")
        st.metric("Bez FVE (25 let)",f"{naklad_bez/1e6:.2f} mil. Kč")
        st.metric("S FVE (25 let)",f"{naklad_s/1e6:.2f} mil. Kč",
                  delta=f"−{uspora_sc/1e6:.2f} mil. Kč úspora",delta_color="normal")
        st.metric("Cashflow návratnost",f"{nav_sc} let" if nav_sc else ">25 let")

st.caption(f"💡 Bez FVE zaplatíte za 25 let více na elektřině — i při pesimistickém scénáři. "
           f"Bezúročný úvěr znamená že úspory FVE začínají okamžitě pokrývat splátky.")

st.divider()

# ── CASHFLOW TABULKA ──────────────────────────────────────────────
st.subheader("📋 Cashflow rok po roku (25 let)")
df=pd.DataFrame([{"Rok":r["rok"],"Výroba MWh":r["vyroba_mwh"],"Vlastní MWh":r["vlastni_mwh"],
                   "Přetoky MWh":r["pretoky_mwh"],"Úspora VT Kč":r["uspora_vt"],
                   "Úspora NT Kč":r["uspora_nt"],"Příjem přetoky Kč":r["uspora_pretoky"],
                   "Úspora celkem Kč":r["uspora_celkem"],"Splátka Kč":r["splatka"],
                   "Čistý přínos Kč":r["cisty_prinos"],"Kumulativní Kč":r["kumulativni"],
                   "Cena VT Kč/kWh":r["cena_vt"]} for r in cf])

def hl(row):
    if nav and row["Rok"]==nav: return ["background-color:#d4edda"]*len(row)
    if row["Kumulativní Kč"]<0: return ["background-color:#fff3cd"]*len(row)
    return [""]*len(row)

# Skryjeme NT sloupec pokud není NT sazba
cols_show=["Rok","Výroba MWh","Vlastní MWh","Přetoky MWh","Úspora VT Kč"]
if ma_nt: cols_show.append("Úspora NT Kč")
cols_show+=["Příjem přetoky Kč","Úspora celkem Kč","Splátka Kč","Čistý přínos Kč","Kumulativní Kč","Cena VT Kč/kWh"]

fmt={"Výroba MWh":"{:.2f}","Vlastní MWh":"{:.2f}","Přetoky MWh":"{:.2f}",
     "Úspora VT Kč":"{:,.0f}","Úspora NT Kč":"{:,.0f}","Příjem přetoky Kč":"{:,.0f}",
     "Úspora celkem Kč":"{:,.0f}","Splátka Kč":"{:,.0f}",
     "Čistý přínos Kč":"{:,.0f}","Kumulativní Kč":"{:,.0f}","Cena VT Kč/kWh":"{:.3f}"}

st.dataframe(df[cols_show].style.apply(hl,axis=1).format({k:v for k,v in fmt.items() if k in cols_show}),
             use_container_width=True,hide_index=True)

st.divider()

# ── DETAIL INVESTICE ──────────────────────────────────────────────
st.subheader("💰 Detail investice a výnosů")
di1,di2=st.columns(2)
with di1:
    st.markdown("**Investice**")
    st.write(f"• FVE {vykon} kWp × {cena_kwp:,} Kč/kWp: **{cena_fve:,.0f} Kč**")
    _ckwh_bat = cena_bat // int(bat) if bat > 0 else 15000
    if cena_bat>0: st.write(f"• Baterie {bat} kWh × {_ckwh_bat:,} Kč/kWh: **{cena_bat:,.0f} Kč**")
    if cena_mericu>0: st.write(f"• Podružné měřiče: **{cena_mericu:,.0f} Kč**")
    st.write(f"• **Celková investice: {cena_invest:,.0f} Kč**")
    if bonus>0: st.write(f"• Bonus NZÚ: **− {bonus:,.0f} Kč**")
    if scenar!="vlastni":
        st.write(f"• Bezúročný úvěr NZÚ: **{uver_cast:,.0f} Kč**")
        st.write(f"• Roční splátka: **{rocni_spl:,.0f} Kč** ({splatnost} let)")
with di2:
    st.markdown("**Výnosy rok 1**")
    _nm={"spolecne":"Jen společné prostory","jom":"Sjednocení odběrných míst","edc":"EDC komunitní sdílení"}
    st.write(f"• Model: **{_nm[model]}** · Profil: **{PROFILY[profil]['nazev']}**")
    st.write(f"• Vlastní spotřeba VT (FVE): **{sim['vlastni_vt_kwh']:,.0f} kWh** → **{rok1['uspora_vt']:,.0f} Kč**")
    if ma_nt: st.write(f"• Vlastní spotřeba NT (baterie): **{sim['vlastni_nt_kwh']:,.0f} kWh** → **{rok1['uspora_nt']:,.0f} Kč**")
    st.write(f"• Přetoky: **{sim['pretoky_kwh']:,.0f} kWh** @ {cena_pretoky:.2f} Kč → **{rok1['uspora_pretoky']:,.0f} Kč**")
    if uspora_jist>0: st.write(f"• Úspora distribuce (JOM): **{uspora_jist:,.0f} Kč**")
    st.write(f"• **Celkem: {rok1['uspora_celkem']:,.0f} Kč/rok**")
    st.write(f"• Na byt: **{uspora_byt_mesic*12:,.0f} Kč/rok** · **{uspora_byt_mesic:.0f} Kč/měs**")

st.divider()

# ── JEDNOVĚTÝ ZÁVĚR ───────────────────────────────────────────────
kum25_final = cf[-1]["kumulativni"]
uspora_25_total = sum(r["uspora_celkem"] for r in cf)
rust_real = float(rust_cen)

# Závěr dle scénáře
if nav and nav <= 12:
    zaver = (f"✅ **Projekt se jednoznačně vyplatí** — i při konzervativním scénáři "
             f"se investice vrátí za {nav} let a za 25 let ušetříte "
             f"**{kum25_final:,.0f} Kč** ({kum25_final/float(pocet_bytu):,.0f} Kč/byt).")
elif nav and nav <= 18:
    uspora_pess = sum(
        rok1["uspora_celkem"]*(1+1.0/100)**(r-1)*(1-float(deg_pan)/100)**(r-1)
        for r in range(1,26))
    zaver = (f"⚠️ **Projekt se vyplatí při realistickém vývoji cen** (+{rust_real}%/rok) — "
             f"návratnost {nav} let. Při pesimistickém scénáři (+1%/rok) "
             f"{'se také vrátí' if uspora_pess > float(cena_invest) else 'se nemusí vrátit'}. "
             f"Bezúročný úvěr NZÚ výrazně snižuje riziko.")
elif nav:
    zaver = (f"⚠️ **Projekt je ekonomicky hraniční** — návratnost {nav} let je dlouhá. "
             f"Doporučujeme zvýšit výkon FVE, přidat baterii nebo zvolit model JOM/EDC "
             f"pro lepší využití výroby.")
else:
    zaver = (f"❌ **Projekt se za 25 let nevrátí** při současných parametrech. "
             f"Zásadně přehodnoťte výkon FVE a model sdílení.")

st.info(zaver)

# Klíčový insight o baterii
if bat > 0 and ma_nt:
    st.caption(
        f"💡 **Baterie nepřidává výrobu — jen posouvá hodnotu z dne do noci.** "
        f"Přes den zachytí přebytky FVE, v noci pokryje NT spotřebu (bojler, TČ) "
        f"za cenu VT místo NT ze sítě."
    )

st.divider()

# ── NZÚ INFO ──────────────────────────────────────────────────────
st.subheader("🏛️ Státní podpora NZÚ 2026")
ni1,ni2=st.columns(2)
with ni1:
    st.markdown("**Co existuje pro SVJ (dle sfzp.gov.cz):**")
    st.write("✅ **Bezúročný úvěr NZÚ** — od září 2026, splácení standardně 15 let (max. 25 let)")
    st.write("✅ **Bonus za zranitelné domácnosti** — za byty se superdávkou")
    st.write("✅ **NZÚ Light** — přímá dotace jen pro nízkopříjmové")
with ni2:
    st.markdown("**Další technologie (bezúročný úvěr):**")
    st.write("• Zateplení fasády a střechy · Výměna oken")
    st.write("• Tepelné čerpadlo · Rekuperace")
    st.info("📋 Vždy ověřte na **[novazelenausporam.cz](https://novazelenausporam.cz)**")

st.divider()
st.caption(
    "⚠️ Orientační výpočty — 15minutová simulace. "
    "Profily spotřeby: OTE ČR — Typové diagramy dodávek elektřiny (TDD4). "
    "Solární data: PVGIS TMY © Evropská komise, JRC. "
    "Ceny dle ceníků ČEZ, E.ON, PRE od 1.1.2026 (s DPH 21 %, POZE=0 Kč). "
    "NZÚ: sfzp.gov.cz · EDC: edc.cz"
)
