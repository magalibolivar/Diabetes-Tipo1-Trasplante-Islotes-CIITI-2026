# Estratificación de candidatos a trasplante de islotes en DM1 (análisis de CGM)

Pipeline reproducible de ciencia de datos que, **con datos reales de monitoreo continuo de
glucosa (CGM)**, estratifica a pacientes con diabetes tipo 1 (DM1) según los criterios de
candidatura a **trasplante de islotes pancreáticos** (Protocolo Edmonton) y los objetivos del
consenso internacional de CGM.

- **Datos:** estudio **REPLACE-BG** (Jaeb Center / T1D Exchange) — 226 adultos con DM1,
  **14,8 millones de lecturas de CGM**.
- **Marco clínico:** la labilidad glucémica / hipoglucemia inadvertida que define la indicación
  de trasplante y las nuevas terapias inmunosupresoras (tegoprubart, anti-CD40L).
- **Hallazgos:** variabilidad alta (%CV≥36%) en el 64,6% y TIR insuficiente en el 71,7%, pero
  solo el **3,5%** reúne el perfil completo de labilidad (candidatura). La hipoglucemia
  inadvertida se asocia a la duración de la DM1 y la edad, no al CGM del momento.

Trabajo del grupo CAETI — Universidad Abierta Interamericana (UAI).

## Estructura

```
vidas-diabetes-cgm/
├── paper/        # Paper final (.docx, formato UAI/CAETI)
├── src/          # Scripts reproducibles (numerados por orden de ejecución)
├── data/
│   ├── raw/          # REPLACE-BG (NO versionado; ver data/README.md)
│   └── processed/    # Métricas de CGM y dataset integrado por paciente
├── figures/      # Figuras generadas (PNG)
└── tables/       # Tablas generadas (CSV)
```

## Cómo reproducir

```bash
pip install -r requirements.txt

# 1) Descargar REPLACE-BG (ver data/README.md) y ubicarlo en data/raw/ReplaceBG.zip
# 2) Métricas de CGM por paciente (procesa 837 MB en streaming):
python src/01_cgm_metrics.py
# 3) Dataset integrado + criterios de candidatura:
python src/02_build_dataset.py
# 4) Análisis: figuras y tablas:
python src/03_pipeline.py
# 5) Paper .docx:
python src/04_build_paper.py
```

`data/processed/` ya incluye los datasets finales, de modo que los pasos 3–4 corren directamente.

## Fuentes

- REPLACE-BG (Beck et al., Diabetes Care 2017) — https://public.jaeb.org/datasets/diabetes
- Consenso CGM: Battelino et al., Diabetes Care 2019.
- Marco de trasplante: Shapiro et al. (Edmonton), NEJM 2000/2006; Paucara Saavedra (2026).
