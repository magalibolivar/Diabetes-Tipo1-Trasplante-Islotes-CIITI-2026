# Resultados explicados — Labilidad glucémica y candidatura a trasplante de islotes

Documento de apoyo para leer los resultados sin ser especialista. Todos los números
salen del código real (`src/`) sobre datos reales de CGM (REPLACE-BG).

---

## Glosario rápido

- **DM1 (diabetes tipo 1):** el sistema inmune destruye las células beta del páncreas; el cuerpo deja de producir insulina.
- **Trasplante de islotes (Protocolo Edmonton):** se implantan islotes de un donante para restaurar la producción de insulina. Se reserva para casos graves porque exige inmunosupresión de por vida.
- **Tegoprubart:** nuevo inmunosupresor (anti-CD40L) que busca menos toxicidad que los clásicos.
- **CGM (monitoreo continuo de glucosa):** sensor que mide la glucosa cada ~5 minutos.
- **%CV (coeficiente de variación):** mide cuánto "salta" la glucosa. Objetivo de consenso: < 36%. Más alto = más inestable (lábil).
- **TIR (tiempo en rango 70–180):** % del tiempo con glucosa en el rango sano. Objetivo: ≥ 70%.
- **TBR<54:** % del tiempo con glucosa peligrosamente baja. Objetivo: < 1%.
- **Hipoglucemia inadvertida (IAH):** el paciente ya no siente los síntomas de alarma de una baja de azúcar → muy peligroso.
- **Perfil de labilidad:** combinación de hipoglucemia inadvertida + hipoglucemia excesiva = el perfil que justifica evaluar un trasplante.
- **Odds Ratio (OR):** cuánto multiplica el riesgo una variable. OR=1,04 por año = +4% de chance por cada año.
- **VIF:** mide si las variables se "pisan" entre sí (colinealidad). VIF<10 = OK. Los nuestros < 2,4.
- **p-valor:** < 0,05 = estadísticamente significativo.

---

## De qué se trata

El trasplante de islotes puede "curar" la DM1, pero como necesita inmunosupresión tóxica,
**solo conviene en pacientes con diabetes muy inestable** (hipoglucemias graves e inadvertidas).
La pregunta del trabajo: **usando datos reales de CGM, ¿qué fracción de pacientes con DM1
realmente cumple ese perfil?** Es un problema de ciencia de datos aplicado a decidir a quién
evaluar para el trasplante.

## Los datos

- **REPLACE-BG**: 226 adultos con DM1, **14,8 millones de lecturas de CGM** (~6 meses cada uno).
- Se procesó el archivo crudo de 837 MB en *streaming* (sin cargarlo entero en memoria).

## Resultados clave

| Criterio | Prevalencia |
|---|---|
| Tiempo en rango insuficiente (TIR<70%) | 71,7% |
| Variabilidad alta (%CV≥36%) | 64,6% |
| Hipoglucemia excesiva (TBR<54>1%) | 34,5% |
| Hipoglucemia inadvertida | 17,3% |
| **Perfil de labilidad (candidatura)** | **3,5% (8 pacientes)** |

**Mensaje central:** aunque el mal control es muy común, **solo ~3,5% tiene el perfil severo**
que justifica el riesgo del trasplante. Confirma con datos que la selección debe ser estricta.

## Fenotipos (K-Means)

El algoritmo separó 3 grupos automáticamente: **buen control**, **hiperglucémico** (glucosa alta)
y **lábil** (inestable, concentra a los candidatos).

## ¿Qué predice la hipoglucemia inadvertida?

Una regresión logística mostró que la IAH se asocia a la **duración de la DM1** (OR≈1,04/año) y a
la **edad** (OR≈1,04), **no** a las métricas de CGM del momento. El modelo es sólido: significativo
en conjunto (p<0,001), sin colinealidad (VIF<2,4) y estable con errores robustos (HC1).
Interpretación: la IAH es un daño autonómico que se acumula con los años, no algo que se lea solo
en el CGM reciente → hay que combinar CGM + historia clínica + cuestionarios.

## El "factor humano de la IA" (Humanware 5.0)

El aporte no es reemplazar al médico, sino **darle una herramienta objetiva y reproducible** para
priorizar a quién evaluar: la IA/ML como **apoyo a la decisión clínica**, no como reemplazo.
