# 🏀 CourtFatigue: ¿Cuándo deja de rendir un jugador y dónde lo nota la cancha?

> **Proyecto desarrollado para el AQX Sports Analytics Data Bowl 4.0**  
> *Concurso de análisis de datos deportivos de código abierto.*

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-FF4B4B.svg)](https://streamlit.io/)
[![Plotly](https://img.shields.io/badge/Plotly-Interactive-3F51B5.svg)](https://plotly.com/)
[![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-xShot_Model-F7931E.svg)](https://scikit-learn.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📌 Resumen en una Línea

Una herramienta de análisis e interfaz interactiva que estima cómo decae la eficiencia de tiro de un jugador de la NBA según los minutos seguidos que acumula en cancha (*stints*), controlando por la dificultad intrínseca de cada lanzamiento ($xShot$), y muestra en mapas de calor qué zonas sufren mayor deterioro para guiar las decisiones de sustitución del cuerpo técnico.

---

## ⚠️ El Problema

En el baloncesto profesional, las rotaciones se deciden tradicionalmente por **intuición visual**: el entrenador "nota cansado" a un jugador y lo sustituye. 

Sin embargo:
1. No existe una guía objetiva y cuantitativa de **cuántos minutos seguidos** puede rendir cada jugador a su máximo nivel antes de que su mecánica de tiro se degrade.
2. Sustituir demasiado pronto desperdicia minutos valiosos de tus mejores estrellas.
3. Sustituir demasiado tarde cuesta canastas fáciles y puntos decisivos en momentos críticos del partido (*clutch time*).

---

## 💡 La Solución: CourtFatigue

**CourtFatigue** reconstruye cronológicamente segundo a segundo la permanencia de cada jugador en pista en el instante exacto de cada tiro, y evalúa el impacto de la fatiga en tres vistas intuitivas:

1. **Curva de Fatiga con Intervalos de Confianza (95% CI):** Gráfico interactivo que muestra la evolución del porcentaje de tiro frente a los minutos continuos en pista, comparando el rendimiento real con el tiro esperado ($xShot$).
2. **Mapa de Calor Comparativo de Cancha:** Visualización de dos medias canchas lado a lado que compara la distribución espacial de aciertos y fallos cuando el jugador está **Descansado (< 4 min)** frente a cuando está **Cansado (≥ 8 min)**.
3. **Recomendación Táctica de Rotación:** Una lectura clara y directa para el entrenador: *"Sustituir a este jugador en el minuto X de stint continuo (Confianza: Alta/Moderada)"*.

---

## 📊 Datos Utilizados

* **Fuente:** Datos oficiales de la Temporada Regular de la NBA 2023–24 (1,230 partidos).
* **Datasets integrados:**
  * **`nbastats_2024.csv` (Play-by-Play):** Rastrear sustituciones (`EVENTMSGTYPE = 8`), cuartos y reloj de posesión.
  * **`shotdetail_2024.csv` (Shot Chart Detail):** 219,527 tiros registrados con coordenadas cartesianas exactas (`LOC_X`, `LOC_Y`), distancias en pies, zonas geométricas y resultado de la jugada.

---

## 🔬 Metodología Científica

```
┌───────────────────────────────────────┐
│     1. RECONSTRUCCIÓN DE STINTS       │
│  Sustituciones PBP -> Minutos en pista│
└──────────────────┬────────────────────┘
                   ▼
┌───────────────────────────────────────┐
│     2. MODELO DE TIRO ESPERADO        │
│  xShot = f(Distancia, Zona, Mecánica) │
└──────────────────┬────────────────────┘
                   ▼
┌───────────────────────────────────────┐
│     3. RESIDUO & EFECTOS FIJOS        │
│  Δ = (Real - xShot) - Media_Jugador   │
│  (Compara al jugador consigo mismo)   │
└──────────────────┬────────────────────┘
                   ▼
┌───────────────────────────────────────┐
│     4. UMBRAL DE RECOMENDACIÓN DT     │
│  Punto de caída persistente > 3.5%    │
└───────────────────────────────────────┘
```

1. **Reconstrucción de Stints:** Cada sustitución a la banca congela el tiempo del jugador; al reingresar, su contador de minutos seguidos arranca en `0.0 min`. El descanso de medio tiempo reinicia el cronómetro de fatiga.
2. **Modelo de Tiro Esperado ($xShot$):** Entrenado con **Regresión Logística calibrada** sobre más de 200,000 tiros considerando distancia euclidiana, zona geométrica (`Restricted Area`, `Paint`, `Mid-Range`, `3PT`), tipo de acción (`Pullup`, `Step Back`, `Layup`, `Dunk`) y periodo. Esto aísla si el jugador falló por fatiga o porque el tiro era intrínsecamente más difícil.
3. **Efectos Fijos por Jugador:** Cada jugador se compara contra **su propia media habitual**, evitando el sesgo de que las estrellas jueguen más tiempo y asuman tiros más complejos.
4. **Tratamiento de Incertidumbre:** Se calculan intervalos de confianza al 95%. Si un tramo tiene menos de 20 tiros, se marca explícitamente con advertencia de muestra insuficiente.

---

## 🏆 Criterios de Evaluación (AQX Data Bowl)

### 1. Aplicación Práctica
* **Para Entrenadores:** Proporciona un umbral numérico objetivo para planificar sustituciones en los tiempos muertos.
* **Para Preparadores Físicos:** Identifica qué jugadores toleran mejor los minutos prolongados y quiénes necesitan rotaciones cortas de 5–6 minutos.
* **Para Analistas y Directiva:** Evaluar el valor real de los jugadores según su dosificación en cancha (*load management* táctico).

### 2. Análisis Exhaustivo
* No se limita a estadísticas superficiales (como puntos por partido). Modela probabilidades condicionadas ($xShot$), intervalos de confianza y residuos de rendimiento.

### 3. Presentación de Datos
* Panel interactivo en **Streamlit** con modo oscuro deportivo, escudos oficiales, fotos de las estrellas desde el CDN de la NBA y gráficos responsivos en **Plotly**.

---

## 🚀 Instalación y Uso Local

### 1. Clonar el repositorio
```bash
git clone https://github.com/TU-USUARIO/courtfatigue.git
cd courtfatigue
```

### 2. Crear y activar entorno virtual
```bash
python -m venv venv
# En Windows:
.\venv\Scripts\activate
# En Linux/Mac:
source venv/bin/activate
```

### 3. Instalar dependencias
```bash
pip install -r requirements.txt
```

### 4. Iniciar la aplicación web
```bash
streamlit run app.py
```
Abre tu navegador en `http://localhost:8501`.

---

## 📁 Estructura del Código

```text
courtfatigue/
├── data/
│   ├── raw/                 # Datasets originales (Play-by-play y Tiros)
│   ├── processed/           # Tiros procesados con stints y xShot
│   └── README.md            # Diccionario completo de variables
├── src/
│   ├── stint_calculator.py  # Algoritmo de reconstrucción de minutos continuos
│   ├── xshot_model.py       # Modelo de tiro esperado y residuos de fatiga
│   └── visualizations.py    # Dibujante de cancha NBA y curvas en Plotly
├── app.py                   # Aplicación Web Interactiva (Streamlit)
├── requirements.txt         # Dependencias del proyecto
└── README.md                # Portada del proyecto
```

---

## ⚠️ Limitaciones Declaradas

1. **Sesgo de Supervivencia en Rotaciones:** Los entrenadores en la NBA ya sustituyen cuando perciben cansancio evidente; por ende, los tramos de más de 10 minutos continuos tienen menor volumen de tiros.
2. **Asociación vs. Causalidad:** La fatiga física es un factor determinante, pero factores situacionales como la presión defensiva en minutos finales también inciden en el tiro.
3. **Temporada Única:** El modelo actual analiza la temporada 2023–24.

---

## 🔮 Trabajo Futuro

* Incorporar fatiga acumulada por calendario (*back-to-backs*, viajes y husos horarios).
* Medir el impacto de la fatiga en la defensa (tiros concedidos y faltas personales).
* Adaptar el sistema a la WNBA y la EuroLeague.

---

**Autor:** Equipo CourtFatigue  
**Hackathon:** AQX Sports Analytics Data Bowl 4.0  
**Licencia:** Código Abierto (MIT)
