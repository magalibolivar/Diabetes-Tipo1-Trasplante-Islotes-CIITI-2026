# -*- coding: utf-8 -*-
"""
03 - Análisis: caracteriza la cohorte, cuantifica los criterios de candidatura a
trasplante de islotes, compara el subgrupo con perfil de labilidad vs. el resto,
segmenta fenotipos glucémicos (PCA + K-Means) y estima una regresión logística de
la hipoglucemia inadvertida (IAH) en función de las métricas de CGM.

Entrada: data/processed/pacientes_dm1.csv
Salida:  figures/*.png, tables/*.csv
"""
import warnings; warnings.filterwarnings("ignore")
import sys
try: sys.stdout.reconfigure(encoding="utf-8")
except Exception: pass
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib.pyplot as plt
import statsmodels.api as sm
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from statsmodels.stats.outliers_influence import variance_inflation_factor

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "processed" / "pacientes_dm1.csv"
FIG, TAB = ROOT / "figures", ROOT / "tables"
FIG.mkdir(exist_ok=True); TAB.mkdir(exist_ok=True)
plt.rcParams.update({"figure.dpi":150,"font.size":10,"axes.titlesize":12,"axes.titleweight":"bold"})
AZUL, NARANJA, VERDE = "#2b6cb0", "#dd6b20", "#38a169"

df = pd.read_csv(DATA)
N = len(df)
print(f"[VIDAS] pacientes: {N}")

# ---------- Tabla 1: características de la cohorte ----------
def resumen(col, dec=1):
    s = df[col].dropna()
    return f"{s.mean():.{dec}f} ± {s.std():.{dec}f}"
t1 = pd.DataFrame({
    "Característica": ["Edad (años)", "Sexo femenino, n (%)", "Edad al diagnóstico (años)",
        "Duración de la DM1 (años)", "IMC (kg/m²)", "HbA1c basal (%)",
        "Glucosa media CGM (mg/dL)", "GMI (%)", "Coef. de variación %CV (%)",
        "Tiempo en rango 70–180 (%)", "Tiempo <70 mg/dL (%)", "Tiempo <54 mg/dL (%)"],
    "Valor": [resumen("edad"), f"{(df.sexo=='F').sum()} ({100*(df.sexo=='F').mean():.1f}%)",
        resumen("edad_diagnostico"), resumen("duracion_dm1"), resumen("imc"), resumen("hba1c_basal"),
        resumen("glucosa_media",0), resumen("gmi_pct",1), resumen("cv_pct"),
        resumen("tir_70_180_pct"), resumen("tbr_70_pct",2), resumen("tbr_54_pct",2)],
})
t1.to_csv(TAB/"tabla1_cohorte.csv", index=False, encoding="utf-8")

# ---------- Tabla 2: prevalencia de criterios ----------
crit = [("iah","Hipoglucemia inadvertida (perdió síntomas de alarma)"),
        ("variabilidad_alta","Variabilidad glucémica alta (%CV ≥ 36%)"),
        ("hipo_excesiva","Exposición excesiva a hipoglucemia (TBR<54 > 1%)"),
        ("tir_insuficiente","Tiempo en rango insuficiente (TIR < 70%)"),
        ("perfil_labilidad","Perfil de labilidad glucémica (candidatura Edmonton)")]
t2 = pd.DataFrame({"Criterio":[c[1] for c in crit],
    "n":[int(df[c[0]].sum()) for c in crit],
    "Prevalencia (%)":[round(100*df[c[0]].mean(),1) for c in crit]})
t2.to_csv(TAB/"tabla2_prevalencia_criterios.csv", index=False, encoding="utf-8")

# ---------- Figura 1: prevalencia de criterios ----------
fig, ax = plt.subplots(figsize=(9,4.2))
order = t2.sort_values("Prevalencia (%)")
colors = [NARANJA if "labilidad" in c.lower() else AZUL for c in order.Criterio]
ax.barh(range(len(order)), order["Prevalencia (%)"], color=colors)
ax.set_yticks(range(len(order))); ax.set_yticklabels([c[:46] for c in order.Criterio], fontsize=8)
for i,v in enumerate(order["Prevalencia (%)"]): ax.text(v+0.6,i,f"{v:.1f}%",va="center",fontsize=8)
ax.set_xlabel("Prevalencia en la cohorte (%)")
ax.set_title(f"Prevalencia de criterios de candidatura a trasplante de islotes (N={N})")
fig.tight_layout(); fig.savefig(FIG/"fig1_prevalencia_criterios.png", bbox_inches="tight"); plt.close(fig)

# ---------- Figura 2: distribuciones con umbrales de consenso ----------
fig, ax = plt.subplots(1,3, figsize=(13,4))
specs = [("cv_pct","%CV",36,"Variabilidad (objetivo < 36%)"),
         ("tbr_54_pct","TBR <54 mg/dL (%)",1,"Hipoglucemia (objetivo < 1%)"),
         ("tir_70_180_pct","TIR 70–180 (%)",70,"Tiempo en rango (objetivo ≥ 70%)")]
for k,(col,lab,thr,tit) in enumerate(specs):
    ax[k].hist(df[col].dropna(), bins=25, color=AZUL, alpha=0.8, edgecolor="white")
    ax[k].axvline(thr, ls="--", color=NARANJA, lw=2, label=f"umbral {thr}")
    ax[k].set_xlabel(lab); ax[k].set_ylabel("N pacientes"); ax[k].set_title(tit); ax[k].legend(fontsize=8)
fig.suptitle("Distribución de métricas de CGM frente a los objetivos del consenso internacional",
             fontweight="bold", y=1.02)
fig.tight_layout(); fig.savefig(FIG/"fig2_distribuciones.png", bbox_inches="tight"); plt.close(fig)

# ---------- Figura 3: mapa de riesgo %CV vs TBR<54 ----------
fig, ax = plt.subplots(figsize=(7.5,5.8))
sin = df[~df.perfil_labilidad]; con = df[df.perfil_labilidad]
ax.scatter(sin.cv_pct, sin.tbr_54_pct, s=35, color=AZUL, alpha=0.55, edgecolor="white", label="Resto de la cohorte")
ax.scatter(con.cv_pct, con.tbr_54_pct, s=95, color=NARANJA, edgecolor="black", zorder=5, label="Perfil de labilidad")
ax.axvline(36, ls="--", color="gray", lw=1); ax.axhline(1, ls="--", color="gray", lw=1)
ax.set_xlabel("Coeficiente de variación %CV (%)"); ax.set_ylabel("Tiempo <54 mg/dL (%)")
ax.set_title("Mapa de riesgo glucémico: variabilidad vs. hipoglucemia\n(líneas: umbrales de consenso)")
ax.legend()
fig.tight_layout(); fig.savefig(FIG/"fig3_mapa_riesgo.png", bbox_inches="tight"); plt.close(fig)

# ---------- Fenotipos: PCA + K-Means ----------
FEAT = ["glucosa_media","cv_pct","tir_70_180_pct","tbr_54_pct","tar_250_pct"]
Xs = StandardScaler().fit_transform(df[FEAT])
pca = PCA(n_components=2, random_state=42); Xp = pca.fit_transform(Xs)
k = 3; cl = KMeans(n_clusters=k, n_init=20, random_state=42).fit_predict(Xs)
df["fenotipo"] = cl
prof = df.groupby("fenotipo")[FEAT+["iah","perfil_labilidad"]].mean().round(2)
prof["n"] = df.groupby("fenotipo").size()
prof.to_csv(TAB/"tabla4_fenotipos.csv", encoding="utf-8")
fig, ax = plt.subplots(figsize=(7,5.5))
pal=[AZUL,NARANJA,VERDE]
for c in range(k):
    m = cl==c
    ax.scatter(Xp[m,0], Xp[m,1], s=55, color=pal[c], alpha=0.75, edgecolor="white",
               label=f"Fenotipo {c} (n={m.sum()})")
ax.set_xlabel(f"Componente 1 ({pca.explained_variance_ratio_[0]*100:.0f}% var.)")
ax.set_ylabel(f"Componente 2 ({pca.explained_variance_ratio_[1]*100:.0f}% var.)")
ax.set_title("Fenotipos glucémicos (K-Means, k=3) sobre métricas de CGM"); ax.legend(fontsize=8)
fig.tight_layout(); fig.savefig(FIG/"fig4_fenotipos_pca.png", bbox_inches="tight"); plt.close(fig)

# ---------- Tabla 3: labilidad vs resto (con p-valor) ----------
def pval(col):
    a = df[df.perfil_labilidad][col].dropna(); b = df[~df.perfil_labilidad][col].dropna()
    return stats.ttest_ind(a, b, equal_var=False).pvalue
comp_vars = [("cv_pct","%CV (%)"),("tbr_54_pct","TBR<54 (%)"),("tbr_70_pct","TBR<70 (%)"),
             ("tir_70_180_pct","TIR (%)"),("gmi_pct","GMI (%)"),("hba1c_basal","HbA1c (%)"),
             ("duracion_dm1","Duración DM1 (años)"),("edad","Edad (años)")]
t3 = pd.DataFrame({
    "Variable":[v[1] for v in comp_vars],
    "Perfil labilidad":[f"{df[df.perfil_labilidad][v[0]].mean():.1f}" for v in comp_vars],
    "Resto":[f"{df[~df.perfil_labilidad][v[0]].mean():.1f}" for v in comp_vars],
    "p":[f"{pval(v[0]):.3f}" if pval(v[0])>=0.001 else "<0.001" for v in comp_vars]})
t3.to_csv(TAB/"tabla3_labilidad_vs_resto.csv", index=False, encoding="utf-8")

# ---------- Regresión logística: IAH ~ métricas CGM ----------
LOGF = ["cv_pct","tbr_54_pct","tir_70_180_pct","duracion_dm1","edad"]
LLAB = {"cv_pct":"%CV","tbr_54_pct":"TBR<54","tir_70_180_pct":"TIR",
        "duracion_dm1":"Duración DM1","edad":"Edad"}
d2 = df.dropna(subset=LOGF+["iah"]).copy()
Xl = sm.add_constant(d2[LOGF]); yl = d2["iah"].astype(int)
logit = sm.Logit(yl, Xl).fit(disp=0)
logit_r = sm.Logit(yl, Xl).fit(disp=0, cov_type="HC1")   # errores robustos
vif = [variance_inflation_factor(Xl.values, i) for i in range(Xl.shape[1])]
def pf(p): return "<0.001" if p < 0.001 else f"{p:.3f}"
lt = pd.DataFrame({"variable":["Intercepto"]+[LLAB[f] for f in LOGF],
    "coef":logit.params.round(3).values,
    "OR":np.exp(logit.params).round(3).values,
    "p":[pf(p) for p in logit.pvalues],
    "p_robusto_HC1":[pf(p) for p in logit_r.pvalues],
    "VIF":[float("nan")]+[round(v,2) for v in vif[1:]]})
lt.to_csv(TAB/"tabla5_logit_iah.csv", index=False, encoding="utf-8")

# ---------- Figura 5: comparación labilidad vs resto (boxplots) ----------
fig, ax = plt.subplots(1,3, figsize=(12,4))
box_vars = [("cv_pct","%CV (%)",36),("tbr_54_pct","TBR<54 (%)",1),("tir_70_180_pct","TIR (%)",70)]
for k,(col,lab,thr) in enumerate(box_vars):
    data=[df[~df.perfil_labilidad][col].dropna(), df[df.perfil_labilidad][col].dropna()]
    bp=ax[k].boxplot(data, patch_artist=True, labels=["Resto","Labilidad"], widths=0.6)
    for patch,c in zip(bp['boxes'],[AZUL,NARANJA]): patch.set_facecolor(c); patch.set_alpha(0.8)
    for med in bp['medians']: med.set_color("black")
    ax[k].axhline(thr, ls="--", color="gray", lw=1)
    ax[k].set_ylabel(lab); ax[k].set_title(lab.split()[0])
fig.suptitle("Comparación del perfil de labilidad glucémica frente al resto de la cohorte",
             fontweight="bold", y=1.02)
fig.tight_layout(); fig.savefig(FIG/"fig5_comparacion_boxplots.png", bbox_inches="tight"); plt.close(fig)

# ---------- Figura 6: correlación entre métricas de CGM y criterios ----------
CM = ["glucosa_media","cv_pct","tir_70_180_pct","tbr_70_pct","tbr_54_pct","tar_250_pct","score_riesgo"]
CLAB = {"glucosa_media":"Glucosa media","cv_pct":"%CV","gmi_pct":"GMI","tir_70_180_pct":"TIR",
        "tbr_70_pct":"TBR<70","tbr_54_pct":"TBR<54","tar_250_pct":"TAR>250","score_riesgo":"Score riesgo"}
cc = df[CM].corr().round(2).rename(index=CLAB, columns=CLAB)
cc.to_csv(TAB/"tabla6_correlacion_cgm.csv", encoding="utf-8")
fig, ax = plt.subplots(figsize=(7.5,6.5)); im=ax.imshow(cc.values, cmap="RdBu_r", vmin=-1, vmax=1)
ax.set_xticks(range(len(cc.columns))); ax.set_yticks(range(len(cc.index)))
ax.set_xticklabels(cc.columns, rotation=45, ha="right"); ax.set_yticklabels(cc.index)
for i in range(len(cc.index)):
    for j in range(len(cc.columns)):
        ax.text(j,i,f"{cc.values[i,j]:.2f}",ha="center",va="center",fontsize=8,
                color="white" if abs(cc.values[i,j])>0.5 else "black")
fig.colorbar(im, ax=ax, shrink=0.8, label="Coeficiente de Pearson")
ax.set_title("Correlación entre las métricas de CGM y el score de riesgo glucémico")
fig.tight_layout(); fig.savefig(FIG/"fig6_correlacion.png", bbox_inches="tight"); plt.close(fig)

print("\n=== Prevalencia criterios ==="); print(t2.to_string(index=False))
print(f"\n=== Fenotipos (K-Means) ===\n{prof.to_string()}")
print(f"\n=== Logit IAH pseudo-R2={logit.prsquared:.3f} | LLR p={logit.llr_pvalue:.4f} | "
      f"VIF máx={max(vif[1:]):.2f} ===\n{lt.to_string(index=False)}")
print("\nOK - figuras en figures/, tablas en tables/")
