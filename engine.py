# engine.py — Simulační engine FVE kalkulačky pro SVJ
# Čistý Python, žádné Streamlit závislosti — připravený pro FastAPI
#
# Autoritativní hodnoty: ceníky 2026 z app.py (constants.py je ZASTARALÝ — ignoruj ho)
# Zdroj ceníků: TZB-info, ERÚ výměr 14/2025, ceníky ČEZ/EGD/PRE k 1.1.2026

import datetime
import functools
import requests
import numpy as np

# ================================================================
# CENÍKOVÉ TABULKY 2026 — autoritativní hodnoty
# ================================================================

CENY_VT = {
    # Kč/MWh s DPH — VT (vysoký tarif)
    "ČEZ Distribuce": {"D01d": 7320, "D02d": 6610, "D25d": 6920, "D26d": 5650, "D27d": 6920,
                       "D35d": 5410, "D45d": 5410, "D56d": 5410, "D57d": 5410, "D61d": 8050},
    "EG.D (E.ON)":    {"D01d": 7050, "D02d": 6550, "D25d": 6650, "D26d": 5430, "D27d": 6650,
                       "D35d": 4270, "D45d": 4270, "D56d": 4270, "D57d": 4270, "D61d": 7720},
    "PREdistribuce":  {"D01d": 5980, "D02d": 5570, "D25d": 5620, "D26d": 4840, "D27d": 5620,
                       "D35d": 3910, "D45d": 3910, "D56d": 3910, "D57d": 3910, "D61d": 6770},
}

CENY_NT = {
    # Kč/MWh s DPH — NT (nízký tarif)
    "ČEZ Distribuce": {"D25d": 4070, "D26d": 4070, "D27d": 4020, "D35d": 4390,
                       "D45d": 4390, "D56d": 4390, "D57d": 4390, "D61d": 4200},
    "EG.D (E.ON)":    {"D25d": 3830, "D26d": 3830, "D27d": 3830, "D35d": 3830,
                       "D45d": 3830, "D56d": 3830, "D57d": 3830, "D61d": 3830},
    "PREdistribuce":  {"D25d": 3590, "D26d": 3590, "D27d": 3590, "D35d": 3590,
                       "D45d": 3590, "D56d": 3590, "D57d": 3590, "D61d": 3590},
}

# Stálý plat za odběrné místo (Kč/měs s DPH)
STAY_PLAT = {"ČEZ Distribuce": 179, "EG.D (E.ON)": 160, "PREdistribuce": 157}

# Jistič na byt (individuální ODM) — Kč/měs s DPH 2026
JISTIC_BYT = {
    "ČEZ Distribuce": {"1×25A": 132, "3×16A": 190, "3×20A": 238, "3×25A": 298, "3×32A": 381},
    "EG.D (E.ON)":    {"1×25A": 121, "3×16A": 193, "3×20A": 242, "3×25A": 303, "3×32A": 387},
    "PREdistribuce":  {"1×25A": 132, "3×16A": 190, "3×20A": 230, "3×25A": 287, "3×32A": 360},
}

# Jistič domu — D tarif (domácnost) — Kč/měs s DPH 2026
JISTIC_DUM = {
    "ČEZ Distribuce": {10: 121, 16: 191, 20: 240, 25: 309, 32: 383,
                       40: 479, 50: 600, 63: 751, 80: 869, 100: 989},
    "EG.D (E.ON)":    {10: 116, 16: 186, 20: 232, 25: 290, 32: 373,
                       40: 465, 50: 581, 63: 729, 80: 845, 100: 961},
    "PREdistribuce":  {10: 106, 16: 169, 20: 213, 25: 266, 32: 339,
                       40: 424, 50: 530, 63: 667, 80: 773, 100: 879},
}
JISTIC_DUM_A = {"ČEZ Distribuce": 5.99, "EG.D (E.ON)": 5.81, "PREdistribuce": 5.30}

# Jistič JOM/SVJ jako podnikatel — C tarif — Kč/měs s DPH 2026
# POZOR: C tarif je výrazně dražší než D tarif (ČEZ +46-52%)
JISTIC_DUM_C = {
    "ČEZ Distribuce": {16: 286,  20: 358,  25: 450,  32: 572,
                       40: 715,  50: 894,  63: 1145, 80: 1265, 100: 1384, 125: 1549, 160: 1788},
    "EG.D (E.ON)":    {10: 116,  16: 186,  20: 232,  25: 290,  32: 373,
                       40: 465,  50: 581,  63: 729,  80: 845,  100: 961},
    "PREdistribuce":  {10: 144,  16: 230,  20: 288,  25: 359,  32: 460,
                       40: 575,  50: 719,  63: 905,  80: 1150, 100: 1437, 125: 1797, 160: 2300},
}
JISTIC_DUM_C_A = {"ČEZ Distribuce": 14.88, "EG.D (E.ON)": 5.81, "PREdistribuce": 14.37}

JISTIC_3x25 = {
    "ČEZ Distribuce": {"D01d": 132, "D02d": 298, "D25d": 287, "D26d": 422, "D27d": 272,
                       "D35d": 517, "D45d": 567, "D56d": 567, "D57d": 568, "D61d": 238},
    "EG.D (E.ON)":    {"D01d": 121, "D02d": 303, "D25d": 296, "D26d": 422, "D27d": 282,
                       "D35d": 575, "D45d": 575, "D56d": 575, "D57d": 572, "D61d": 271},
    "PREdistribuce":  {"D01d": 162, "D02d": 359, "D25d": 557, "D26d": 1262, "D27d": 529,
                       "D35d": 1545, "D45d": 1545, "D56d": 1545, "D57d": 1545, "D61d": 525},
}

SAZBY_NT = ["D25d", "D26d", "D27d", "D35d", "D45d", "D56d", "D57d", "D61d"]

PODIL_NT = {
    "D25d": 0.35, "D26d": 0.35, "D27d": 0.35, "D35d": 0.60,
    "D45d": 0.70, "D56d": 0.75, "D57d": 0.75, "D61d": 0.40,
}

# NT hodiny dle sazby
NT_HODINY = {
    "D25d": set(list(range(22, 24)) + list(range(0, 6))),
    "D26d": set(list(range(22, 24)) + list(range(0, 6))),
    "D27d": set(list(range(22, 24)) + list(range(0, 6))),
    "D35d": set(list(range(22, 24)) + list(range(0, 6)) + list(range(10, 14))),
    "D45d": set(range(24)),
    "D56d": set(range(24)),
    "D57d": set(list(range(22, 24)) + list(range(0, 6)) + list(range(10, 14))),
    "D61d": set(list(range(22, 24)) + list(range(0, 8))),
}

# ================================================================
# TDD PROFILY — OTE ČR, normalizované na průměr = 1.0/hodinu
# ================================================================

_TDD4 = {
    "zima_prac":        np.array([0.412,0.371,0.348,0.339,0.343,0.377,0.524,0.784,0.883,0.819,0.762,0.741,0.758,0.738,0.717,0.739,0.820,1.118,1.284,1.222,1.082,0.917,0.718,0.551], dtype=float),
    "prechodne_prac":   np.array([0.395,0.355,0.333,0.325,0.329,0.366,0.500,0.730,0.822,0.768,0.719,0.699,0.717,0.697,0.676,0.698,0.778,1.037,1.181,1.119,0.989,0.837,0.648,0.496], dtype=float),
    "leto_prac":        np.array([0.378,0.339,0.319,0.311,0.316,0.356,0.476,0.676,0.761,0.718,0.676,0.657,0.676,0.656,0.636,0.657,0.737,0.957,1.079,1.017,0.897,0.757,0.578,0.441], dtype=float),
    "zima_vikend":      np.array([0.451,0.404,0.375,0.364,0.366,0.384,0.420,0.552,0.752,0.901,0.950,0.938,0.901,0.860,0.820,0.820,0.879,1.047,1.148,1.098,0.978,0.818,0.648,0.521], dtype=float),
    "prechodne_vikend": np.array([0.423,0.379,0.352,0.341,0.343,0.360,0.398,0.524,0.713,0.858,0.904,0.893,0.858,0.819,0.780,0.780,0.838,0.997,1.094,1.044,0.929,0.778,0.615,0.490], dtype=float),
    "leto_vikend":      np.array([0.396,0.355,0.329,0.319,0.321,0.337,0.377,0.497,0.675,0.816,0.859,0.848,0.816,0.778,0.741,0.741,0.797,0.948,1.040,0.991,0.881,0.738,0.582,0.458], dtype=float),
}
for _k in _TDD4:
    _TDD4[_k] = _TDD4[_k] / _TDD4[_k].mean()

_TDD_SP = {
    "zima_prac":        np.array([0.55,0.52,0.50,0.50,0.50,0.55,0.75,0.95,0.85,0.75,0.72,0.72,0.72,0.72,0.75,0.85,0.95,1.10,1.15,1.10,1.00,0.90,0.75,0.62], dtype=float),
    "prechodne_prac":   np.array([0.50,0.47,0.45,0.45,0.45,0.50,0.70,0.88,0.78,0.70,0.67,0.67,0.67,0.67,0.70,0.78,0.88,1.00,1.05,1.00,0.91,0.81,0.68,0.56], dtype=float),
    "leto_prac":        np.array([0.45,0.42,0.40,0.40,0.40,0.45,0.65,0.80,0.72,0.65,0.62,0.62,0.62,0.62,0.65,0.72,0.80,0.90,0.95,0.90,0.82,0.72,0.60,0.50], dtype=float),
    "zima_vikend":      np.array([0.58,0.54,0.52,0.51,0.51,0.54,0.62,0.78,0.90,0.95,0.95,0.93,0.90,0.88,0.85,0.88,0.92,1.05,1.10,1.05,0.95,0.85,0.72,0.63], dtype=float),
    "prechodne_vikend": np.array([0.53,0.49,0.47,0.46,0.46,0.49,0.57,0.72,0.82,0.88,0.88,0.86,0.82,0.80,0.78,0.80,0.84,0.97,1.01,0.97,0.88,0.78,0.66,0.58], dtype=float),
    "leto_vikend":      np.array([0.48,0.44,0.42,0.41,0.41,0.44,0.52,0.65,0.75,0.80,0.80,0.78,0.75,0.73,0.71,0.73,0.77,0.88,0.92,0.88,0.80,0.71,0.60,0.52], dtype=float),
}
for _k in _TDD_SP:
    _TDD_SP[_k] = _TDD_SP[_k] / _TDD_SP[_k].mean()

_UPRAVY = {
    "mix":        np.ones(24, dtype=float),
    "seniori":    np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.1,1.3,1.5,1.6,1.6,1.5,1.5,1.4,1.4,1.3,1.1,1.0,1.0,1.0,1.0,1.0,1.0], dtype=float),
    "pracujici":  np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.2,1.3,0.7,0.5,0.5,0.5,0.5,0.5,0.5,0.6,0.8,1.3,1.4,1.3,1.2,1.1,1.0,1.0], dtype=float),
    "rodiny":     np.array([1.0,1.0,1.0,1.0,1.0,1.0,1.1,1.2,0.9,0.7,0.7,0.7,0.8,0.8,0.9,1.1,1.2,1.2,1.2,1.1,1.1,1.0,1.0,1.0], dtype=float),
    "provozovna": np.array([0.8,0.8,0.8,0.8,0.8,0.9,1.0,1.2,1.5,1.6,1.7,1.7,1.6,1.6,1.6,1.5,1.3,1.1,1.0,0.9,0.9,0.8,0.8,0.8], dtype=float),
}
for _k in _UPRAVY:
    _UPRAVY[_k] = _UPRAVY[_k] / _UPRAVY[_k].mean()

_MESICE = ["Led", "Úno", "Bře", "Dub", "Kvě", "Čvn", "Čvc", "Srp", "Zář", "Říj", "Lis", "Pro"]
_CD = 365 * 96  # počet 15min intervalů za rok

# ================================================================
# POMOCNÉ FUNKCE — JISTIČE
# ================================================================

def _cena_jistice_dum(dist: str, sazba: str, ampery: int = 63, c_tarif: bool = False) -> int:
    """Vrátí měsíční cenu jističe domu (Kč/měs s DPH).
    c_tarif=True → C tarif (JOM/SVJ jako podnikatel — vždy dražší).
    c_tarif=False → D tarif (stávající stav).
    """
    if c_tarif:
        tab = JISTIC_DUM_C.get(dist, JISTIC_DUM_C["ČEZ Distribuce"])
        amp_a = JISTIC_DUM_C_A.get(dist, 14.88)
    else:
        tab = JISTIC_DUM.get(dist, JISTIC_DUM["ČEZ Distribuce"])
        amp_a = JISTIC_DUM_A.get(dist, 5.99)
    klice = sorted(tab.keys())
    for k in klice:
        if ampery <= k:
            return tab[k]
    max_k = klice[-1]
    return round(tab[max_k] + (ampery - max_k) * amp_a)


def _jistic_dum_ampery(pocet_bytu: int, zarizeni: str) -> int:
    """Odhadne potřebné ampéry hlavního jističe domu."""
    byt_a = 25
    if "elektromobil" in zarizeni.lower(): byt_a = 32
    if "tepelné čerpadlo" in zarizeni.lower(): byt_a = 32
    total = pocet_bytu * byt_a
    for a in [25, 32, 40, 50, 63, 80, 100, 125, 160]:
        if total <= a * pocet_bytu:
            return a
    return 63


# ================================================================
# PROFILY SPOTŘEBY
# ================================================================

def _sezona(m: int) -> str:
    if m in [11, 12, 1, 2]: return "zima"
    if m in [5, 6, 7, 8]:   return "leto"
    return "prechodne"


def _tdd4_klic(sezona: str, vikend: bool) -> str:
    if sezona == "zima" and not vikend:       return "zima_prac"
    if sezona == "zima" and vikend:           return "zima_vikend"
    if sezona == "leto" and not vikend:       return "leto_prac"
    if sezona == "leto" and vikend:           return "leto_vikend"
    if sezona == "prechodne" and not vikend:  return "prechodne_prac"
    if sezona == "prechodne" and vikend:      return "prechodne_vikend"
    return "prechodne_prac"


def _smiseny_profil(pct_pracujici: float, pct_seniori: float, pct_rodiny: float) -> np.ndarray:
    """Vážený průměr tří profilů spotřeby (hodnoty 0–100, suma nemusí být 100)."""
    total = pct_pracujici + pct_seniori + pct_rodiny
    if total <= 0:
        return _UPRAVY["mix"].copy()
    p = (_UPRAVY["pracujici"] * pct_pracujici +
         _UPRAVY["seniori"]   * pct_seniori +
         _UPRAVY["rodiny"]    * pct_rodiny) / total
    return p / p.mean()


def _gen_profil_vt(kwh: float, tdd: dict, uprava: np.ndarray = None) -> np.ndarray:
    """Generuje 15min profil VT spotřeby za rok (pole délky _CD)."""
    vals = []
    den = datetime.date(2026, 1, 1)
    for _ in range(365):
        sz = _sezona(den.month)
        vi = den.weekday() >= 5
        klic = _tdd4_klic(sz, vi)
        p = tdd[klic].copy()
        if uprava is not None:
            p = p * uprava
            p = p / p.mean()
        for h in range(24):
            v = float(p[h]) / 4.0
            vals.extend([v, v, v, v])
        den += datetime.timedelta(days=1)
    arr = np.array(vals, dtype=float)[:_CD]
    if arr.sum() > 0:
        arr = arr * (float(kwh) / arr.sum())
    return arr


def _gen_profil_nt(kwh: float, sazba: str) -> np.ndarray:
    """Generuje 15min profil NT spotřeby — jen v NT hodinách."""
    nt_h = NT_HODINY.get(sazba, set())
    if not nt_h or kwh <= 0:
        return np.zeros(_CD, dtype=float)
    vals = []
    for _ in range(365):
        for h in range(24):
            v = 1.0 / 4.0 if h in nt_h else 0.0
            vals.extend([v, v, v, v])
    arr = np.array(vals, dtype=float)[:_CD]
    if arr.sum() > 0:
        arr = arr * (float(kwh) / arr.sum())
    return arr


def _interpoluj(hod: list) -> np.ndarray:
    """Interpoluje hodinová data na 15min rozlišení."""
    h = np.array(hod, dtype=float)
    n = len(h)
    res = np.zeros(n * 4, dtype=float)
    for i in range(n):
        ni = (i + 1) % n
        for j in range(4):
            t = j / 4.0
            res[i * 4 + j] = (h[i] * (1.0 - t) + h[ni] * t) / 4.0
    return res[:_CD]


def _gen_vyroba_fallback(kwp: float, sklon: int = 35, azimut: int = 0) -> np.ndarray:
    """Záložní výpočet výroby bez PVGIS (pouze orientační)."""
    vh = np.zeros(8760, dtype=float)
    for h in range(8760):
        dr = h // 24
        hod = h % 24
        uhel = 2 * np.pi * (dr - 80) / 365.0
        delka = 12 + 4.5 * np.sin(uhel)
        vychod = 12 - delka / 2
        zapad = 12 + delka / 2
        if vychod <= hod <= zapad:
            t = (hod - vychod) / delka
            elev = np.sin(np.pi * t)
            sezon = max(0.3, min(1.0, 0.5 + 0.5 * np.sin(uhel + np.pi / 2)))
            koef = 1.0 + 0.15 * np.sin(np.pi * float(sklon) / 90.0)
            vh[h] = float(kwp) * elev * sezon * koef * 0.85
    if vh.sum() > 0:
        vh = vh * (float(kwp) * 1050.0 / vh.sum())
    return vh


# ================================================================
# HLAVNÍ SIMULACE
# ================================================================

def simuluj(
    vyroba_15: np.ndarray,
    sp_vt15: np.ndarray,
    sp_nt15: np.ndarray,
    bat: float = 0.0,
    model: str = "edc",
    edc_ztrata: float = 0.0,
) -> dict:
    """
    Přesná 15min simulace FVE s oddělenou VT a NT spotřebou.

    Baterie: nabíjí se z přetoků FVE (VT priorita), vybíjí do VT pak NT spotřeby.
    Model:
        'spolecne' — jen společné prostory, NT = 0
        'jom'      — celý dům jako jedno ODM
        'edc'      — sdílení přes EDC (aplikuje ztrátu sdílení)
    """
    v   = np.array(vyroba_15, dtype=float)
    svt = np.array(sp_vt15,   dtype=float)
    snt = np.array(sp_nt15,   dtype=float)
    bat = float(bat)

    if model == "spolecne":
        snt = np.zeros(len(v), dtype=float)

    n = int(min(len(v), len(svt), len(snt)))
    v, svt, snt = v[:n], svt[:n], snt[:n]

    bmin, bmax, bkwh = bat * 0.10, bat * 0.90, bat * 0.50
    eta = 0.92

    vl_vt = np.zeros(n, dtype=float)
    vl_nt = np.zeros(n, dtype=float)
    pr    = np.zeros(n, dtype=float)
    od_vt = np.zeros(n, dtype=float)
    od_nt = np.zeros(n, dtype=float)

    for i in range(n):
        vi   = float(v[i])
        svti = float(svt[i])
        snti = float(snt[i])

        # 1. FVE pokryje VT spotřebu přímo
        prime = min(vi, svti)
        vl_vt[i] = prime
        zbyla_v   = vi   - prime
        zbyla_svt = svti - prime

        # 2. Přebytek výroby → nabít baterii
        if zbyla_v > 0.0 and bat > 0.0:
            nab = min(zbyla_v * eta, bmax - bkwh)
            bkwh += nab
            zbyla_v -= nab / eta

        # 3. Zbylá výroba → přetoky
        pr[i] = zbyla_v

        # 4. Zbylá VT spotřeba → vybít baterii (VT = dražší → priorita)
        if zbyla_svt > 0.0 and bat > 0.0:
            dos = (bkwh - bmin) * eta
            vyb = min(zbyla_svt, dos)
            bkwh -= vyb / eta
            zbyla_svt -= vyb
            vl_vt[i] += vyb

        # 5. Zbylá VT spotřeba → ze sítě
        od_vt[i] = zbyla_svt

        # 6. NT spotřeba → vybít zbylou baterii
        if snti > 0.0 and bat > 0.0:
            dos = (bkwh - bmin) * eta
            vyb = min(snti, dos)
            bkwh -= vyb / eta
            snti -= vyb
            vl_nt[i] = vyb

        # 7. Zbylá NT spotřeba → ze sítě
        od_nt[i] = snti

    tv  = float(v.sum())
    tvl = float(vl_vt.sum()) + float(vl_nt.sum())
    tpr = float(pr.sum())
    tsp = float(svt.sum()) + float(snt.sum())

    casovy_prekryv = (
        float(np.minimum(v[:n], (svt + snt)[:n]).sum()) / float(tv)
        if tv > 0 else 1.0
    )
    casovy_prekryv = min(1.0, casovy_prekryv)

    if model == "edc" and edc_ztrata > 0:
        korekce = 1.0 - float(edc_ztrata) / 100.0
        tvl *= korekce
        tpr = tv - tvl

    mv, ms, mvl, mpr = [], [], [], []
    for m in range(12):
        a, b = m * 30 * 96, min((m + 1) * 30 * 96, n)
        mv.append(float(v[a:b].sum()))
        ms.append(float(svt[a:b].sum()) + float(snt[a:b].sum()))
        mvl.append(float(vl_vt[a:b].sum()) + float(vl_nt[a:b].sum()))
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
        "mira_vs":         tvl / tv   if tv  > 0 else 0.0,
        "mira_sob":        min(1.0, tvl / tsp) if tsp > 0 else 0.0,
        "edc_efektivita":  casovy_prekryv,
        "mesice_vyroba":   mv,
        "mesice_spotreba": ms,
        "mesice_vlastni":  mvl,
        "mesice_pretoky":  mpr,
        "mesice_nazvy":    _MESICE,
    }


# ================================================================
# CASHFLOW 25 LET
# ================================================================

def cashflow(
    vl_vt: float, vl_nt: float, pr: float,
    cvt: float, cnt: float, cpr: float,
    vlast: float, uver: float, spl: float, splat: int,
    rust: float = 3.0, deg: float = 0.5, leta: int = 25,
    jist: float = 0.0, bonus: float = 0.0, deg_bat: float = 2.0,
) -> list[dict]:
    """
    Cashflow FVE investice na 'leta' let.
    Vrátí seznam dict — jeden záznam na rok.
    """
    res = []
    kum = -(float(vlast) + float(uver) - float(bonus))
    for rok in range(1, int(leta) + 1):
        d     = (1.0 - float(deg)     / 100.0) ** (rok - 1)
        d_bat = (1.0 - float(deg_bat) / 100.0) ** (rok - 1)
        c     = (1.0 + float(rust)    / 100.0) ** (rok - 1)
        u = (float(vl_vt) * d     * float(cvt) * c +
             float(vl_nt) * d_bat * float(cnt) * c +
             float(pr)    * d     * float(cpr) * c +
             float(jist)  * c)
        s = float(spl) if rok <= int(splat) else 0.0
        kum += u - s
        res.append({
            "rok":            rok,
            "vyroba_mwh":     round((float(vl_vt) + float(vl_nt) + float(pr)) * d / 1000.0, 2),
            "vlastni_mwh":    round((float(vl_vt) + float(vl_nt)) * d / 1000.0, 2),
            "pretoky_mwh":    round(float(pr) * d / 1000.0, 2),
            "uspora_vt":      round(float(vl_vt) * d * float(cvt) * c),
            "uspora_nt":      round(float(vl_nt) * d_bat * float(cnt) * c),
            "uspora_pretoky": round(float(pr) * d * float(cpr) * c),
            "uspora_jom":     round(float(jist) * c),
            "uspora_fve":     round(float(vl_vt) * d * float(cvt) * c +
                                    float(vl_nt) * d_bat * float(cnt) * c +
                                    float(pr) * d * float(cpr) * c),
            "uspora_celkem":  round(u),
            "splatka":        round(s),
            "cisty_prinos":   round(u - s),
            "kumulativni":    round(kum),
            "cena_vt":        round(float(cvt) * c, 3),
        })
    return res


# ================================================================
# PVGIS — SOLÁRNÍ DATA (EU JRC API)
# Cache: in-memory LRU (pro FastAPI — nahraď Redis pro produkci)
# ================================================================

@functools.lru_cache(maxsize=256)
def pvgis(lat: float, lon: float, kwp: float, sklon: int, azimut: int) -> tuple:
    """
    Stáhne hodinová TMY data výroby FVE z PVGIS API.

    Speciální hodnoty azimut:
        999 = V+Z  → 2 volání (kwp/2 na -90° + kwp/2 na +90°)
        998 = JZ+JV → 2 volání (kwp/2 na -45° + kwp/2 na +45°)
    Vrátí (np.ndarray[8760], error_str | None)
    Cache: LRU 256 položek (v produkci vyměnit za Redis s TTL 24h)
    """
    def _jedno_volani(latt, lonn, kwpp, sklonn, azimut_v):
        r = requests.get(
            "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc",
            params={
                "lat": float(latt), "lon": float(lonn),
                "peakpower": float(kwpp), "loss": 14,
                "angle": int(sklonn), "aspect": int(azimut_v),
                "outputformat": "json", "browser": 0,
                "startyear": 2020, "endyear": 2020,
                "pvcalculation": 1, "pvtechchoice": "crystSi",
                "mountingplace": "building", "trackingtype": 0,
            },
            timeout=30,
        )
        r.raise_for_status()
        return np.array(
            [float(h["P"]) / 1000.0 for h in r.json()["outputs"]["hourly"]],
            dtype=float,
        )[:8760]

    try:
        if azimut == 999:   # V + Z
            a = _jedno_volani(lat, lon, kwp / 2, sklon, -90)
            b = _jedno_volani(lat, lon, kwp / 2, sklon, +90)
            return (a + b), None
        elif azimut == 998:  # JZ + JV
            a = _jedno_volani(lat, lon, kwp / 2, sklon, -45)
            b = _jedno_volani(lat, lon, kwp / 2, sklon, +45)
            return (a + b), None
        else:
            return _jedno_volani(lat, lon, kwp, sklon, azimut), None
    except Exception as e:
        return None, str(e)


# ================================================================
# GEOCODING
# ================================================================

_GEOCODE_FB = {
    "praha": (50.08, 14.44), "brno": (49.19, 16.61), "ostrava": (49.83, 18.29),
    "plzeň": (49.74, 13.37), "třinec": (49.68, 18.67), "liberec": (50.77, 15.06),
    "olomouc": (49.59, 17.25), "zlín": (49.22, 17.66), "znojmo": (48.86, 16.05),
    "hradec králové": (50.21, 15.83), "pardubice": (50.04, 15.78),
    "české budějovice": (48.97, 14.47), "ústí nad labem": (50.66, 14.03),
    "havířov": (49.78, 18.43), "karviná": (49.85, 18.54), "opava": (49.94, 17.90),
    "frýdek-místek": (49.68, 18.35), "jihlava": (49.40, 15.59),
}


def geocode(dotaz: str) -> tuple:
    """Vrátí (lat, lon, nazev, error). Nominatim + fallback na slovník."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{dotaz}, Česká republika", "format": "json",
                    "limit": 1, "addressdetails": 1, "countrycodes": "cz"},
            headers={"User-Agent": "FVE-SVJ-Kalkulacka/1.0"},
            timeout=10,
        )
        if r.status_code == 200 and r.text.strip():
            res = r.json()
            if res:
                addr = res[0].get("address", {})
                nazev = (addr.get("road", "") + " " + addr.get("house_number", "")).strip()
                nazev = nazev or addr.get("city") or addr.get("town") or addr.get("village") or dotaz
                return float(res[0]["lat"]), float(res[0]["lon"]), nazev, None
    except Exception:
        pass
    klic = dotaz.lower().strip().split(",")[0].strip()
    if klic in _GEOCODE_FB:
        lat, lon = _GEOCODE_FB[klic]
        return lat, lon, dotaz, None
    return None, None, None, "Nenalezeno — zkuste jiný formát adresy"


def geocode_search(dotaz: str) -> list:
    """Vrátí seznam návrhů pro autocomplete (max 5 výsledků)."""
    try:
        r = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{dotaz}, Česká republika", "format": "json",
                    "limit": 5, "addressdetails": 1, "countrycodes": "cz"},
            headers={"User-Agent": "FVE-SVJ-Kalkulacka/1.0"},
            timeout=5,
        )
        if r.status_code == 200 and r.text.strip():
            return r.json()
    except Exception:
        pass
    return []
