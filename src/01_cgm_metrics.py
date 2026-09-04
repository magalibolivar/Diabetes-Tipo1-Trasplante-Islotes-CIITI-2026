# -*- coding: utf-8 -*-
"""
01 - Calcula métricas de monitoreo continuo de glucosa (CGM) por paciente a partir
del archivo crudo HDeviceCGM.txt del dataset REPLACE-BG (Jaeb Center / T1D Exchange).

El archivo CGM (~837 MB, ~16 M lecturas) se procesa en STREAMING desde el ZIP, sin
extraerlo, acumulando estadísticos por paciente.

Métricas de consenso internacional (Battelino et al. 2019):
  - glucosa media, DE, %CV (coeficiente de variación = DE/media)
  - GMI (Glucose Management Indicator) = 3,31 + 0,02392 × glucosa media (mg/dL)
  - TIR  (Time In Range 70–180 mg/dL, %)
  - TBR  (Time Below Range <70 y <54 mg/dL, %)  -> exposición a hipoglucemia
  - TAR  (Time Above Range >180 y >250 mg/dL, %)

Índices de riesgo glucémico validados (Kovatchev et al.), calculados sobre la señal
cruda mediante la transformación simétrica de riesgo f(BG)=1,509·[(ln BG)^1,084−5,381]:
  - LBGI (Low Blood Glucose Index)  = media de r cuando f<0  -> riesgo de hipoglucemia
  - HBGI (High Blood Glucose Index) = media de r cuando f>0  -> riesgo de hiperglucemia
  - ADRR (Average Daily Risk Range) = media diaria de (máx. riesgo bajo + máx. riesgo alto)
Estos índices son la cuantificación, apropiada para CGM y validada, de la labilidad e
hipoglucemia que el Lability Index / HYPO score de Ryan et al. (grupo Edmonton) medían
originalmente con glucemias capilares para la selección de candidatos a trasplante.

Entrada:  data/raw/ReplaceBG.zip   (no versionado; ver data/README.md)
Salida:   data/processed/cgm_metrics_paciente.csv
"""
import zipfile, io
from collections import defaultdict
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ZIP = ROOT / "data" / "raw" / "ReplaceBG.zip"
MEMBER = "Data Tables/HDeviceCGM.txt"
OUT = ROOT / "data" / "processed" / "cgm_metrics_paciente.csv"

# Acumuladores por paciente: [n, sum, sumsq, n<54, n<70, n_70_180, n>180, n>250, sum_rl, sum_rh]
acc = {}
# Riesgo diario por (paciente, día): [máx r_bajo, máx r_alto]  -> para ADRR
day_risk = defaultdict(lambda: [0.0, 0.0])

def bg_risk(g):
    """Transformación de riesgo de Kovatchev. Devuelve (rl, rh) por lectura."""
    f = 1.509 * (np.log(g) ** 1.084 - 5.381)
    r = 10.0 * f * f
    rl = np.where(f < 0, r, 0.0)   # riesgo de hipoglucemia
    rh = np.where(f > 0, r, 0.0)   # riesgo de hiperglucemia
    return rl, rh

def main():
    if not ZIP.exists():
        raise SystemExit(f"No se encontró {ZIP}. Descargar REPLACE-BG (ver data/README.md).")
    print("Procesando CGM en streaming (métricas de consenso + índices de riesgo de Kovatchev)...")
    total = 0
    with zipfile.ZipFile(ZIP) as z, z.open(MEMBER) as fh:
        reader = pd.read_csv(io.TextIOWrapper(fh, "utf-8"), sep="|",
                             usecols=["PtID", "DeviceDtTmDaysFromEnroll", "RecordType", "GlucoseValue"],
                             chunksize=1_000_000)
        for chunk in reader:
            chunk = chunk[chunk.RecordType == "CGM"]
            g = pd.to_numeric(chunk.GlucoseValue, errors="coerce").values
            pid = pd.to_numeric(chunk.PtID, errors="coerce").values
            day = pd.to_numeric(chunk.DeviceDtTmDaysFromEnroll, errors="coerce").values
            ok = np.isfinite(g) & np.isfinite(pid) & (g >= 20) & (g <= 600)
            g, pid, day = g[ok], pid[ok].astype(np.int64), day[ok]
            if len(g) == 0:
                continue
            rl, rh = bg_risk(g)
            d = pd.DataFrame({"pid": pid, "day": day, "g": g, "g2": g * g,
                              "c54": g < 54, "c70": g < 70, "cin": (g >= 70) & (g <= 180),
                              "c180": g > 180, "c250": g > 250, "rl": rl, "rh": rh})
            # --- acumulación por paciente ---
            part = d.groupby("pid").agg(
                n=("g", "size"), s=("g", "sum"), ss=("g2", "sum"),
                n54=("c54", "sum"), n70=("c70", "sum"), nin=("cin", "sum"),
                n180=("c180", "sum"), n250=("c250", "sum"),
                srl=("rl", "sum"), srh=("rh", "sum"))
            for p, row in part.iterrows():
                v = np.array([row.n, row.s, row.ss, row.n54, row.n70, row.nin,
                              row.n180, row.n250, row.srl, row.srh], float)
                a = acc.get(p)
                acc[p] = v if a is None else a + v
            # --- riesgo diario máximo por (paciente, día) para ADRR ---
            dd = d.dropna(subset=["day"])
            if len(dd):
                dg = dd.groupby(["pid", "day"]).agg(mrl=("rl", "max"), mrh=("rh", "max"))
                for (p, dy), row in dg.iterrows():
                    k = (p, int(dy)); cur = day_risk[k]
                    if row.mrl > cur[0]: cur[0] = row.mrl
                    if row.mrh > cur[1]: cur[1] = row.mrh
            total += len(chunk)
            print(f"  ...{total:,} lecturas", end="\r")
    print(f"\nTotal lecturas CGM: {total:,} | pacientes: {len(acc)}")

    # ADRR por paciente: media diaria de (máx riesgo bajo + máx riesgo alto)
    adrr_vals = defaultdict(list)
    for (p, _), (mrl, mrh) in day_risk.items():
        adrr_vals[p].append(mrl + mrh)

    rows = []
    for pid, a in acc.items():
        n = a[0]
        if n < 100:  # descartar pacientes con muy pocas lecturas
            continue
        mean = a[1] / n
        var = max(a[2] / n - mean * mean, 0.0)
        sd = var ** 0.5
        adrr = float(np.mean(adrr_vals[pid])) if adrr_vals.get(pid) else np.nan
        rows.append(dict(
            PtID=pid, cgm_n=int(n),
            glucosa_media=round(mean, 1),
            glucosa_DE=round(sd, 1),
            cv_pct=round(100 * sd / mean, 1),
            gmi_pct=round(3.31 + 0.02392 * mean, 2),
            tir_70_180_pct=round(100 * a[5] / n, 1),
            tbr_70_pct=round(100 * a[4] / n, 2),
            tbr_54_pct=round(100 * a[3] / n, 2),
            tar_180_pct=round(100 * a[6] / n, 1),
            tar_250_pct=round(100 * a[7] / n, 1),
            lbgi=round(a[8] / n, 2),
            hbgi=round(a[9] / n, 2),
            adrr=round(adrr, 1),
        ))
    df = pd.DataFrame(rows).sort_values("PtID")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"OK -> {OUT}  ({len(df)} pacientes)")
    print(df[["glucosa_media", "cv_pct", "tir_70_180_pct", "tbr_54_pct", "lbgi", "hbgi", "adrr"]].describe().round(2).to_string())

if __name__ == "__main__":
    main()
