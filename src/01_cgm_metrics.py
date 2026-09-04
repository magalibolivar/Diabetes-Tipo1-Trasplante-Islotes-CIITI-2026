# -*- coding: utf-8 -*-
"""
01 - Calcula métricas de monitoreo continuo de glucosa (CGM) por paciente a partir
del archivo crudo HDeviceCGM.txt del dataset REPLACE-BG (Jaeb Center / T1D Exchange).

El archivo CGM (~837 MB, ~16 M lecturas) se procesa en STREAMING desde el ZIP, sin
extraerlo, acumulando estadísticos por paciente. Métricas (consenso internacional
de CGM, Battelino et al. 2019):
  - glucosa media, DE, %CV (coeficiente de variación = DE/media)
  - GMI (Glucose Management Indicator) = 3,31 + 0,02392 × glucosa media (mg/dL)
  - TIR  (Time In Range 70–180 mg/dL, %)
  - TBR  (Time Below Range <70 y <54 mg/dL, %)  -> exposición a hipoglucemia
  - TAR  (Time Above Range >180 y >250 mg/dL, %)

Entrada:  data/raw/ReplaceBG.zip   (no versionado; ver data/README.md)
Salida:   data/processed/cgm_metrics_paciente.csv
"""
import zipfile, io
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ZIP = ROOT / "data" / "raw" / "ReplaceBG.zip"
MEMBER = "Data Tables/HDeviceCGM.txt"
OUT = ROOT / "data" / "processed" / "cgm_metrics_paciente.csv"

# Acumuladores por paciente
acc = {}  # PtID -> [n, sum, sumsq, n<54, n<70, n_70_180, n>180, n>250]

def upd(pid, g):
    a = acc.get(pid)
    if a is None:
        a = [0, 0.0, 0.0, 0, 0, 0, 0, 0]; acc[pid] = a
    a[0] += 1; a[1] += g; a[2] += g * g
    if g < 54: a[3] += 1
    if g < 70: a[4] += 1
    if 70 <= g <= 180: a[5] += 1
    if g > 180: a[6] += 1
    if g > 250: a[7] += 1

def main():
    if not ZIP.exists():
        raise SystemExit(f"No se encontró {ZIP}. Descargar REPLACE-BG (ver data/README.md).")
    print("Procesando CGM en streaming...")
    total = 0
    with zipfile.ZipFile(ZIP) as z, z.open(MEMBER) as fh:
        reader = pd.read_csv(io.TextIOWrapper(fh, "utf-8"), sep="|",
                             usecols=["PtID", "RecordType", "GlucoseValue"],
                             chunksize=1_000_000)
        for chunk in reader:
            chunk = chunk[chunk.RecordType == "CGM"]
            g = pd.to_numeric(chunk.GlucoseValue, errors="coerce")
            pid = chunk.PtID.values
            m = g.notna().values; g = g.values
            for p, val, ok in zip(pid, g, m):
                if ok: upd(int(p), float(val))
            total += len(chunk)
            print(f"  ...{total:,} lecturas", end="\r")
    print(f"\nTotal lecturas CGM: {total:,} | pacientes: {len(acc)}")

    rows = []
    for pid, a in acc.items():
        n, s, ss = a[0], a[1], a[2]
        if n < 100:  # descartar pacientes con muy pocas lecturas
            continue
        mean = s / n
        var = max(ss / n - mean * mean, 0.0)
        sd = var ** 0.5
        rows.append(dict(
            PtID=pid, cgm_n=n,
            glucosa_media=round(mean, 1),
            glucosa_DE=round(sd, 1),
            cv_pct=round(100 * sd / mean, 1),
            gmi_pct=round(3.31 + 0.02392 * mean, 2),
            tir_70_180_pct=round(100 * a[5] / n, 1),
            tbr_70_pct=round(100 * a[4] / n, 2),
            tbr_54_pct=round(100 * a[3] / n, 2),
            tar_180_pct=round(100 * a[6] / n, 1),
            tar_250_pct=round(100 * a[7] / n, 1),
        ))
    df = pd.DataFrame(rows).sort_values("PtID")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    print(f"OK -> {OUT}  ({len(df)} pacientes)")
    print(df[["glucosa_media","cv_pct","gmi_pct","tir_70_180_pct","tbr_70_pct","tbr_54_pct"]].describe().round(1).to_string())

if __name__ == "__main__":
    main()
