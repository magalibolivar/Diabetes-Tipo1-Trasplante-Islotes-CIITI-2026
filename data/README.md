# Datos

## `processed/` — datasets finales (versionados)
- **`cgm_metrics_paciente.csv`** — métricas de CGM por paciente (glucosa media, %CV, GMI, TIR,
  TBR, TAR), calculadas desde el CGM crudo. Lo genera `src/01_cgm_metrics.py`.
- **`pacientes_dm1.csv`** — dataset integrado por paciente: métricas de CGM + demografía + HbA1c +
  cuestionarios + criterios de candidatura. Lo genera `src/02_build_dataset.py`.

## `raw/` — datos crudos (NO versionados)
- **`ReplaceBG.zip`** — dataset REPLACE-BG (Jaeb Center for Health Research / T1D Exchange),
  ~167 MB comprimido; el CGM crudo (`HDeviceCGM.txt`) pesa ~837 MB. Es de **descarga directa**:
  https://public.jaeb.org/datasets/diabetes → *Replace-BG Dataset*.
  Descargarlo y colocarlo como `data/raw/ReplaceBG.zip`.

El pipeline procesa el CGM en *streaming* desde el ZIP, sin extraerlo. Por tamaño y licencia,
los datos crudos no se incluyen en el repositorio; sí se versionan los datasets procesados
(agregados por paciente, sin datos individuales identificables a nivel de lectura).
