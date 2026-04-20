"""
FVE Simulační engine pro SVJ
- 15min rozlišení (35 040 intervalů/rok)
- PVGIS hodinová data výroby
- OTE TDD profily spotřeby
- Baterie SOC simulace
- 15letý cashflow s degradací a růstem cen
"""

import numpy as np
import requests
import datetime

# ============================================================
# TDD PROFILY SPOTŘEBY
# Zdroj: OTE ČR, třída 4 (D02d — standardní domácnost)
# Normalizovaný hodinový profil pro různé typy dní a sezón
# ============================================================

TDD_PROFIL = {
    "zima_prac": np.array([
        0.42, 0.38, 0.36, 0.35, 0.35, 0.38,
        0.52, 0.78, 0.88, 0.82, 0.76, 0.74,
        0.76, 0.74, 0.72, 0.74, 0.82, 1.12,
        1.28, 1.22, 1.08, 0.92, 0.72, 0.55,
    ], dtype=float),
    "leto_prac": np.array([
        0.38, 0.34, 0.32, 0.31, 0.32, 0.36,
        0.48, 0.68, 0.76, 0.72, 0.68, 0.66,
        0.68, 0.66, 0.64, 0.66, 0.74, 0.96,
        1.08, 1.02, 0.90, 0.76, 0.58, 0.44,
    ], dtype=float),
    "prechodne_prac": np.array([
        0.40, 0.36, 0.34, 0.33, 0.34, 0.37,
        0.50, 0.73, 0.82, 0.77, 0.72, 0.70,
        0.72, 0.70, 0.68, 0.70, 0.78, 1.04,
        1.18, 1.12, 0.99, 0.84, 0.65, 0.50,
    ], dtype=float),
    "zima_vikend": np.array([
        0.45, 0.40, 0.37, 0.36, 0.36, 0.38,
        0.42, 0.55, 0.75, 0.90, 0.95, 0.94,
        0.90, 0.86, 0.82, 0.82, 0.88, 1.05,
        1.15, 1.10, 0.98, 0.82, 0.65, 0.52,
    ], dtype=float),
    "leto_vikend": np.array([
        0.40, 0.36, 0.33, 0.32, 0.32, 0.34,
        0.38, 0.50, 0.68, 0.82, 0.86, 0.85,
        0.82, 0.78, 0.74, 0.74, 0.80, 0.95,
        1.04, 0.99, 0.88, 0.74, 0.58, 0.46,
    ], dtype=float),
    "prechodne_vikend": np.array([
        0.42, 0.38, 0.35, 0.34, 0.34, 0.36,
        0.40, 0.52, 0.72, 0.86, 0.90, 0.89,
        0.86, 0.82, 0.78, 0.78, 0.84, 1.00,
        1.10, 1.04, 0.93, 0.78, 0.62, 0.49,
    ], dtype=float),
}

PROFIL_UPRAVY = {
    "mix": np.ones(24, dtype=float),
    "seniori": np.array([
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
        1.0, 1.1, 1.3, 1.5, 1.6, 1.6,
        1.5, 1.5, 1.4, 1.4, 1.3, 1.1,
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
    ], dtype=float),
    "pracujici": np.array([
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
        1.2, 1.3, 0.7, 0.5, 0.5, 0.5,
        0.5, 0.5, 0.5, 0.6, 0.8, 1.3,
        1.4, 1.3, 1.2, 1.1, 1.0, 1.0,
    ], dtype=float),
    "rodiny": np.array([
        1.0, 1.0, 1.0, 1.0, 1.0, 1.0,
        1.1, 1.2, 0.9, 0.7, 0.7, 0.7,
        0.8, 0.8, 0.9, 1.1, 1.2, 1.2,
        1.2, 1.1, 1.1, 1.0, 1.0, 1.0,
    ], dtype=float),
    "provozovna": np.array([
        0.8, 0.8, 0.8, 0.8, 0.8, 0.9,
        1.0, 1.2, 1.5, 1.6, 1.7, 1.7,
        1.6, 1.6, 1.6, 1.5, 1.3, 1.1,
        1.0, 0.9, 0.9, 0.8, 0.8, 0.8,
    ], dtype=float),
}

CILOVA_DELKA = 365 * 96  # 35 040


def _get_sezona(mesic):
    if mesic in [11, 12, 1, 2]:
        return "zima"
    elif mesic in [5, 6, 7, 8]:
        return "leto"
    return "prechodne"


def generuj_profil_spotreby_rocni(rocni_spotreba_kwh, profil_obyvatel="mix", sazba="D02d"):
    upravy = PROFIL_UPRAVY.get(profil_obyvatel, np.ones(24, dtype=float))
    hodnoty = []
    den = datetime.date(2026, 1, 1)
    for _ in range(365):
        sezona = _get_sezona(den.month)
        typ = "vikend" if den.weekday() >= 5 else "prac"
        profil = TDD_PROFIL[f"{sezona}_{typ}"].copy() * upravy
        profil = profil / profil.sum() * 24.0
        for h in range(24):
            val = float(profil[h]) / 4.0
            hodnoty.extend([val, val, val, val])
        den += datetime.timedelta(days=1)

    arr = np.array(hodnoty, dtype=float)
    arr = arr[:CILOVA_DELKA]
    if arr.sum() > 0:
        arr = arr * (float(rocni_spotreba_kwh) / arr.sum())
    return arr


def get_pvgis_hodinova_data(lat, lon, vykon_kwp, sklon, azimut):
    url = "https://re.jrc.ec.europa.eu/api/v5_2/seriescalc"
    params = {
        "lat": float(lat), "lon": float(lon),
        "peakpower": float(vykon_kwp),
        "loss": 14, "angle": int(sklon), "aspect": int(azimut),
        "outputformat": "json", "browser": 0,
        "startyear": 2020, "endyear": 2020,
        "pvcalculation": 1, "pvtechchoice": "crystSi",
        "mountingplace": "building", "trackingtype": 0,
    }
    try:
        r = requests.get(url, params=params, timeout=30)
        r.raise_for_status()
        hourly = r.json()["outputs"]["hourly"]
        arr = np.array([float(h["P"]) / 1000.0 for h in hourly], dtype=float)
        return arr[:8760], None
    except Exception as e:
        return None, str(e)


def interpoluj_na_15min(hodinova_data):
    hod = np.array(hodinova_data, dtype=float)
    n = len(hod)
    result = np.zeros(n * 4, dtype=float)
    for i in range(n):
        ni = (i + 1) % n
        for j in range(4):
            t = j / 4.0
            result[i * 4 + j] = (hod[i] * (1.0 - t) + hod[ni] * t) / 4.0
    return result[:CILOVA_DELKA]


def simuluj_fve(vyroba_15min, spotreba_15min, baterie_kapacita_kwh=0.0,
                baterie_min_soc=0.10, baterie_max_soc=0.90, baterie_ucinnost=0.92):
    v = np.array(vyroba_15min, dtype=float)
    s = np.array(spotreba_15min, dtype=float)
    bat_kap = float(baterie_kapacita_kwh)

    n = int(min(len(v), len(s)))
    v = v[:n]
    s = s[:n]

    bat_min = bat_kap * float(baterie_min_soc)
    bat_max = bat_kap * float(baterie_max_soc)
    bat_kwh = bat_kap * 0.5

    vlastni = np.zeros(n, dtype=float)
    pretoky = np.zeros(n, dtype=float)
    odber = np.zeros(n, dtype=float)

    for i in range(n):
        vi = float(v[i])
        si = float(s[i])
        if vi >= si:
            vlastni[i] = si
            prebyt = vi - si
            if bat_kap > 0.0:
                misto = bat_max - bat_kwh
                nab = min(prebyt * float(baterie_ucinnost), misto)
                bat_kwh += nab
                prebyt -= nab / float(baterie_ucinnost)
            pretoky[i] = prebyt
        else:
            vlastni[i] = vi
            ned = si - vi
            if bat_kap > 0.0:
                dos = bat_kwh - bat_min
                vyb = min(ned, dos * float(baterie_ucinnost))
                bat_kwh -= vyb / float(baterie_ucinnost)
                ned -= vyb
            odber[i] = ned

    vyr = float(v.sum())
    vl = float(vlastni.sum())
    pr = float(pretoky.sum())
    od = float(odber.sum())
    sp = float(s.sum())

    mesice = []
    for m in range(12):
        a = m * 30 * 96
        b = min((m + 1) * 30 * 96, n)
        mesice.append({
            "vlastni": float(vlastni[a:b].sum()),
            "pretoky": float(pretoky[a:b].sum()),
            "odber": float(odber[a:b].sum()),
            "vyroba": float(v[a:b].sum()),
        })

    return {
        "vlastni_spotreba_kwh": vl,
        "pretoky_kwh": pr,
        "odber_kwh": od,
        "vyroba_kwh": vyr,
        "spotreba_kwh": sp,
        "mira_vlastni_spotreby": vl / vyr if vyr > 0 else 0.0,
        "mira_sobestacnosti": vl / sp if sp > 0 else 0.0,
        "mesice": mesice,
    }


def simuluj_15let(vlastni_spotreba_1rok, pretoky_1rok, cena_vt_kwh,
                  cena_pretoky_kwh, cena_instalace, vlastni_castka,
                  uver_castka, rocni_splatka, splatnost,
                  rust_cen_pct=3.0, degradace_pct=0.5, leta=15,
                  uspora_jistic_rocni=0.0, bonus_celkem=0.0):
    vysledky = []
    kum = -(float(vlastni_castka) + float(uver_castka) - float(bonus_celkem))

    for rok in range(1, int(leta) + 1):
        deg = (1.0 - float(degradace_pct) / 100.0) ** (rok - 1)
        cen = (1.0 + float(rust_cen_pct) / 100.0) ** (rok - 1)

        vl = float(vlastni_spotreba_1rok) * deg
        pr = float(pretoky_1rok) * deg
        cv = float(cena_vt_kwh) * cen
        cp = float(cena_pretoky_kwh) * cen

        u_el = vl * cv
        u_pr = pr * cp
        u_di = float(uspora_jistic_rocni) * cen
        u_cel = u_el + u_pr + u_di

        spl = float(rocni_splatka) if rok <= int(splatnost) else 0.0
        cisty = u_cel - spl
        kum += cisty

        vysledky.append({
            "rok": rok,
            "vyroba_mwh": round((vl + pr) / 1000.0, 2),
            "vlastni_spotreba_mwh": round(vl / 1000.0, 2),
            "pretoky_mwh": round(pr / 1000.0, 2),
            "uspora_elektrina": round(u_el),
            "uspora_pretoky": round(u_pr),
            "uspora_distribuce": round(u_di),
            "uspora_celkem": round(u_cel),
            "splatka": round(spl),
            "cisty_prinos": round(cisty),
            "kumulativni_cashflow": round(kum),
            "cena_vt_rok": round(cv, 3),
            "degradacni_faktor": round(deg, 4),
        })

    return vysledky
