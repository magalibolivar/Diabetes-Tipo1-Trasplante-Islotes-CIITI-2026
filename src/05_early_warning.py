# -*- coding: utf-8 -*-
"""
05 - Alerta temprana de hipoglucemia: aprendizaje automático a escala sobre la señal
de CGM. Reencuadra el problema de 226 pacientes a MILLONES de ventanas cortas y predice
si ocurrirá una hipoglucemia (<70 mg/dL) en los próximos 30 minutos a partir de la
ventana previa de 60 minutos.

Puntos clave (rigor):
  - Ventanas construidas por paciente, ordenadas por tiempo, descartando las que
    cruzan huecos del sensor.
  - Partición POR PACIENTE (GroupShuffleSplit): ningún paciente aparece a la vez en
    entrenamiento y test -> se evita la fuga de información (data leakage).
  - Comparación contra una línea base ingenua (solo la glucosa actual) y una regresión
    logística; se reportan AUC-ROC y AUC-PR (la PR importa por el desbalance de clases).
  - Explicabilidad por importancia de permutación (qué mira el modelo para alertar).

Entrada:  data/raw/ReplaceBG.zip
Salida:   tables/tabla8_early_warning.csv, figures/fig8_roc_pr.png, figures/fig9_importancia_ew.png
"""
import warnings; warnings.filterwarnings("ignore")
import zipfile, io, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
from numpy.lib.stride_tricks import sliding_window_view
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import GroupShuffleSplit, GroupKFold
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve, precision_recall_curve
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass

ROOT = Path(__file__).resolve().parent.parent
ZIP = ROOT / "data" / "raw" / "ReplaceBG.zip"
MEMBER = "Data Tables/HDeviceCGM.txt"
FIG, TAB = ROOT / "figures", ROOT / "tables"
FIG.mkdir(exist_ok=True); TAB.mkdir(exist_ok=True)
plt.rcParams.update({"figure.dpi":150,"font.size":10,"axes.titlesize":12,"axes.titleweight":"bold"})
AZUL, NARANJA, VERDE = "#2b6cb0", "#dd6b20", "#38a169"

W_HIST = 12      # 60 min de historia (12 lecturas a 5 min)
H_FUT  = 6       # 30 min de horizonte (6 lecturas)
STRIDE = 18      # un origen de predicción cada ~90 min (reduce autocorrelación y tamaño)
HYPO   = 70.0    # umbral de hipoglucemia
FEATS = ["g_actual","g_media","g_desvio","g_min","g_max","g_pendiente",
         "g_delta","frac_<70","frac_<100","hora_del_dia"]

def cargar_series():
    """Lee el CGM crudo en streaming -> arrays (pid, t_min, glucosa)."""
    pids, ts, gs = [], [], []
    total = 0
    with zipfile.ZipFile(ZIP) as z, z.open(MEMBER) as fh:
        reader = pd.read_csv(io.TextIOWrapper(fh, "utf-8"), sep="|",
                             usecols=["PtID","DeviceDtTmDaysFromEnroll","DeviceTm","RecordType","GlucoseValue"],
                             chunksize=1_000_000)
        for chunk in reader:
            chunk = chunk[chunk.RecordType == "CGM"]
            g = pd.to_numeric(chunk.GlucoseValue, errors="coerce")
            pid = pd.to_numeric(chunk.PtID, errors="coerce")
            day = pd.to_numeric(chunk.DeviceDtTmDaysFromEnroll, errors="coerce")
            secs = pd.to_timedelta(chunk.DeviceTm, errors="coerce").dt.total_seconds()
            t = day * 1440.0 + secs / 60.0
            ok = g.notna() & pid.notna() & t.notna() & (g >= 20) & (g <= 600)
            pids.append(pid[ok].astype(np.int32).values)
            ts.append(t[ok].astype(np.float32).values)
            gs.append(g[ok].astype(np.float32).values)
            total += len(chunk); print(f"  ...{total:,} lecturas leídas", end="\r")
    print()
    return np.concatenate(pids), np.concatenate(ts), np.concatenate(gs)

def construir_ventanas(pid, t, g):
    """Ventanas deslizantes por paciente -> X, y, grupos (PtID)."""
    L = W_HIST + H_FUT
    X_list, y_list, grp_list = [], [], []
    order = np.lexsort((t, pid))          # ordena por (pid, t)
    pid, t, g = pid[order], t[order], g[order]
    uniq, starts = np.unique(pid, return_index=True)
    bounds = list(starts) + [len(pid)]
    for k in range(len(uniq)):
        i0, i1 = bounds[k], bounds[k+1]
        gp, tp = g[i0:i1], t[i0:i1]
        if len(gp) < L: continue
        gw = sliding_window_view(gp, L)   # (m-L+1, L)
        tw = sliding_window_view(tp, L)
        hist_g, hist_t = gw[:, :W_HIST], tw[:, :W_HIST]
        fut_g = gw[:, W_HIST:]
        origin_t = hist_t[:, -1]
        # descartar ventanas que cruzan huecos del sensor
        valido = ((hist_t[:, -1] - hist_t[:, 0]) <= 75) & ((tw[:, -1] - origin_t) <= 40)
        idx = np.where(valido)[0][::STRIDE]
        if len(idx) == 0: continue
        H, Ht, F = hist_g[idx], hist_t[idx], fut_g[idx]
        ot = origin_t[idx]
        tc = Ht - Ht.mean(1, keepdims=True)
        gc = H - H.mean(1, keepdims=True)
        slope = (tc * gc).sum(1) / np.clip((tc * tc).sum(1), 1e-6, None)
        feats = np.column_stack([
            H[:, -1], H.mean(1), H.std(1), H.min(1), H.max(1), slope,
            H[:, -1] - H[:, 0], (H < 70).mean(1), (H < 100).mean(1),
            (ot % 1440) / 60.0,
        ])
        y = (F.min(1) < HYPO).astype(np.int8)
        X_list.append(feats.astype(np.float32)); y_list.append(y)
        grp_list.append(np.full(len(y), uniq[k], dtype=np.int32))
    return np.vstack(X_list), np.concatenate(y_list), np.concatenate(grp_list)

def main():
    if not ZIP.exists(): raise SystemExit(f"No se encontró {ZIP}.")
    print("Cargando serie de CGM...")
    pid, t, g = cargar_series()
    print(f"Lecturas válidas: {len(g):,}. Construyendo ventanas (hist 60' -> horizonte 30')...")
    X, y, grp = construir_ventanas(pid, t, g)
    base = y.mean()
    print(f"Ventanas: {len(y):,} | pacientes: {len(np.unique(grp))} | prevalencia de hipoglucemia: {100*base:.1f}%")

    # --- Partición POR PACIENTE (sin fuga de información) ---
    gss = GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=42)
    tr, te = next(gss.split(X, y, groups=grp))
    Xtr, Xte, ytr, yte = X[tr], X[te], y[tr], y[te]
    print(f"Train: {len(tr):,} ventanas ({len(np.unique(grp[tr]))} pac.) | Test: {len(te):,} ({len(np.unique(grp[te]))} pac.)")

    modelos = {}
    # Baseline ingenuo: solo la glucosa actual (score = -glucosa, más bajo => más riesgo)
    modelos["Baseline (glucosa actual)"] = (-Xte[:, 0], None)
    # Regresión logística
    lr = LogisticRegression(max_iter=1000, class_weight="balanced").fit(Xtr, ytr)
    modelos["Regresión logística"] = (lr.predict_proba(Xte)[:, 1], lr)
    # Gradient Boosting (modelo principal)
    gb = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.08,
                                        max_depth=6, random_state=42).fit(Xtr, ytr)
    modelos["Gradient Boosting"] = (gb.predict_proba(Xte)[:, 1], gb)

    filas = []
    for nombre, (score, _) in modelos.items():
        filas.append({"Modelo": nombre,
                      "AUC-ROC": round(roc_auc_score(yte, score), 3),
                      "AUC-PR": round(average_precision_score(yte, score), 3)})
    tabla = pd.DataFrame(filas)
    tabla.to_csv(TAB/"tabla8_early_warning.csv", index=False, encoding="utf-8")
    print("\n=== Alerta temprana de hipoglucemia (test por paciente) ===")
    print(tabla.to_string(index=False), f"\n(prevalencia base = {100*base:.1f}%)")

    # --- Validación cruzada por grupos (robustez del modelo principal) ---
    gkf = GroupKFold(n_splits=5); aucs = []
    for tri, tei in gkf.split(X, y, groups=grp):
        m = HistGradientBoostingClassifier(max_iter=200, learning_rate=0.08,
                                           max_depth=6, random_state=42).fit(X[tri], y[tri])
        aucs.append(roc_auc_score(y[tei], m.predict_proba(X[tei])[:, 1]))
    print(f"GBM GroupKFold(5) AUC-ROC = {np.mean(aucs):.3f} ± {np.std(aucs):.3f}")
    cv_auc = (round(float(np.mean(aucs)), 3), round(float(np.std(aucs)), 3))

    # --- Figura 8: curvas ROC y PR ---
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.6))
    col = {"Baseline (glucosa actual)": "#a0aec0", "Regresión logística": AZUL, "Gradient Boosting": NARANJA}
    for nombre, (score, _) in modelos.items():
        fpr, tpr, _ = roc_curve(yte, score)
        ax[0].plot(fpr, tpr, color=col[nombre], lw=2,
                   label=f"{nombre} (AUC={roc_auc_score(yte, score):.2f})")
        pr, rc, _ = precision_recall_curve(yte, score)
        ax[1].plot(rc, pr, color=col[nombre], lw=2,
                   label=f"{nombre} (AP={average_precision_score(yte, score):.2f})")
    ax[0].plot([0, 1], [0, 1], "--", color="gray", lw=1)
    ax[0].set_xlabel("1 - Especificidad"); ax[0].set_ylabel("Sensibilidad"); ax[0].set_title("Curva ROC"); ax[0].legend(fontsize=8)
    ax[1].axhline(base, ls="--", color="gray", lw=1, label=f"azar ({base:.2f})")
    ax[1].set_xlabel("Sensibilidad (recall)"); ax[1].set_ylabel("Precisión"); ax[1].set_title("Curva Precisión-Recall"); ax[1].legend(fontsize=8)
    fig.suptitle("Alerta temprana de hipoglucemia a 30 minutos (test por paciente)", fontweight="bold", y=1.02)
    fig.tight_layout(); fig.savefig(FIG/"fig8_roc_pr.png", bbox_inches="tight"); plt.close(fig)

    # --- Figura 9: importancia de variables (permutación) ---
    imp = permutation_importance(gb, Xte, yte, scoring="roc_auc", n_repeats=5, random_state=42, n_jobs=-1)
    ser = pd.Series(imp.importances_mean, index=FEATS).sort_values()
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    ax.barh(ser.index, ser.values, color=NARANJA)
    ax.set_xlabel("Caída de AUC al permutar la variable"); ax.set_title("¿Qué mira el modelo para alertar? (importancia de permutación)")
    fig.tight_layout(); fig.savefig(FIG/"fig9_importancia_ew.png", bbox_inches="tight"); plt.close(fig)

    print("Top variables:", ", ".join(ser.sort_values(ascending=False).index[:4]))
    print(f"OK -> tabla8, fig8, fig9  (CV AUC={cv_auc[0]}±{cv_auc[1]}, prevalencia base={100*base:.1f}%)")

if __name__ == "__main__":
    main()
