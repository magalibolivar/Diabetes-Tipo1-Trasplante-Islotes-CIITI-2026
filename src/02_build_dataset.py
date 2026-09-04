# -*- coding: utf-8 -*-
"""
02 - Integra las métricas de CGM con los datos clínicos y de cuestionarios de
REPLACE-BG y operacionaliza los criterios de candidatura a trasplante de islotes
pancreáticos (Protocolo Edmonton) y los objetivos del consenso internacional de CGM.

Criterios operacionalizados:
  - IAH  (hipoglucemia inadvertida): perdió síntomas de alarma (LowBGLostSymp="Yes").
  - Variabilidad glucémica alta:      %CV >= 36 %  (objetivo de consenso: < 36 %).
  - Exposición excesiva a hipoglucemia: TBR<54 > 1 %  (objetivo: < 1 %).
  - TIR insuficiente:                 TIR 70–180 < 70 % (objetivo: >= 70 %).

Perfil de labilidad glucémica (proxy de la indicación de Edmonton):
  IAH  Y  exposición excesiva a hipoglucemia (TBR<54 > 1 %).

Entrada:  data/processed/cgm_metrics_paciente.csv + tablas crudas del ZIP.
Salida:   data/processed/pacientes_dm1.csv
"""
import zipfile, sys
from pathlib import Path
import numpy as np, pandas as pd
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
ZIP = ROOT / "data" / "raw" / "ReplaceBG.zip"
CGM = ROOT / "data" / "processed" / "cgm_metrics_paciente.csv"
OUT = ROOT / "data" / "processed" / "pacientes_dm1.csv"

def rd(member):
    with zipfile.ZipFile(ZIP) as z, z.open(f"Data Tables/{member}.txt") as fh:
        return pd.read_csv(fh, sep="|", dtype=str)

def main():
    cgm = pd.read_csv(CGM)
    roster = rd("HPtRoster")[["PtID", "AgeAsOfEnrollDt", "TrtGroup"]]
    scr = rd("HScreening")[["PtID", "Gender", "Race", "DiagAge", "Weight", "Height"]]
    hu = rd("HQuestHypoUnaware")[["PtID", "LowBGSympCat", "LowBGLostSymp"]]
    a1c = rd("HLocalHbA1c")
    for d in (roster, scr, hu, a1c, cgm):
        d["PtID"] = d["PtID"].astype(str)

    # HbA1c basal: primera medición (menor día) por paciente
    a1c["day"] = pd.to_numeric(a1c["HbA1cTestDtDaysAfterEnroll"], errors="coerce")
    a1c["val"] = pd.to_numeric(a1c["HbA1cTestRes"], errors="coerce")
    a1c = a1c.dropna(subset=["val"]).sort_values("day").groupby("PtID").first().reset_index()
    a1c = a1c[["PtID", "val"]].rename(columns={"val": "hba1c_basal"})

    df = cgm.merge(roster, on="PtID", how="left").merge(scr, on="PtID", how="left") \
            .merge(hu, on="PtID", how="left").merge(a1c, on="PtID", how="left")

    df["edad"] = pd.to_numeric(df.AgeAsOfEnrollDt, errors="coerce")
    df["edad_diagnostico"] = pd.to_numeric(df.DiagAge, errors="coerce")
    df["duracion_dm1"] = df["edad"] - df["edad_diagnostico"]
    w = pd.to_numeric(df.Weight, errors="coerce"); h = pd.to_numeric(df.Height, errors="coerce") / 100
    df["imc"] = (w / (h * h)).round(1)
    df["sexo"] = df.Gender

    # --- Criterios ---
    df["iah"] = (df.LowBGLostSymp == "Yes")                      # hipoglucemia inadvertida
    df["percep_reducida"] = (df.LowBGSympCat.str.startswith("Sometimes")) | df["iah"]
    df["variabilidad_alta"] = df.cv_pct >= 36                    # %CV >= 36
    df["hipo_excesiva"] = df.tbr_54_pct > 1.0                    # TBR<54 > 1 %
    df["tir_insuficiente"] = df.tir_70_180_pct < 70             # TIR < 70 %
    df["perfil_labilidad"] = df["iah"] & df["hipo_excesiva"]     # proxy candidatura Edmonton
    # score 0-4 de carga glucémica
    df["score_riesgo"] = (df.variabilidad_alta.astype(int) + df.hipo_excesiva.astype(int)
                          + df.iah.astype(int) + df.tir_insuficiente.astype(int))

    cols = ["PtID", "edad", "sexo", "edad_diagnostico", "duracion_dm1", "imc", "hba1c_basal",
            "TrtGroup", "cgm_n", "glucosa_media", "cv_pct", "gmi_pct", "tir_70_180_pct",
            "tbr_70_pct", "tbr_54_pct", "tar_180_pct", "tar_250_pct",
            "LowBGSympCat", "iah", "percep_reducida", "variabilidad_alta", "hipo_excesiva",
            "tir_insuficiente", "perfil_labilidad", "score_riesgo"]
    df = df[cols].sort_values("PtID")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)

    n = len(df)
    print(f"OK -> {OUT}  ({n} pacientes)")
    print(f"  Edad {df.edad.mean():.1f} ± {df.edad.std():.1f} | duración DM1 {df.duracion_dm1.mean():.1f} años | "
          f"HbA1c basal {df.hba1c_basal.mean():.1f}% | IMC {df.imc.mean():.1f}")
    for c, lab in [("iah","Hipoglucemia inadvertida (IAH)"),("variabilidad_alta","Variabilidad alta (%CV≥36)"),
                   ("hipo_excesiva","Hipoglucemia excesiva (TBR<54>1%)"),("tir_insuficiente","TIR<70%"),
                   ("perfil_labilidad","PERFIL DE LABILIDAD (candidatura)")]:
        print(f"  {lab:38}: {df[c].sum():3d} ({100*df[c].mean():.1f}%)")

if __name__ == "__main__":
    main()
