# CourtFatigue: ¿cuándo deja de rendir un jugador y dónde lo nota la cancha?

Oct 27, 2026 · @juan

## Resumen

CourtFatigue es una herramienta de análisis que estima cómo cae el rendimiento de tiro de un jugador de la NBA según los minutos seguidos que lleva en cancha, y muestra en qué zonas de la cancha se nota más el cansancio. Su objetivo es ayudar al entrenador a decidir cuándo sustituir.

*El nombre es una propuesta; puedes cambiarlo.*

## El problema

Las rotaciones en el baloncesto profesional se deciden en gran parte por intuición: el entrenador "ve" cansado a un jugador y lo cambia. No existe una guía clara, basada en datos, de cuántos minutos seguidos puede rendir cada jugador antes de bajar de nivel, ni de qué tipo de tiros se deterioran primero.

Sustituir demasiado pronto desperdicia a los mejores jugadores. Sustituir tarde cuesta puntos en momentos clave.

## La solución

CourtFatigue reconstruye cuántos minutos seguidos lleva cada jugador en cancha en el momento de cada tiro, y mide cómo cambia su acierto respecto a lo esperado conforme aumenta ese tiempo. El resultado se presenta en tres vistas pensadas para una persona sin formación técnica:

1. **Curva de fatiga:** rendimiento del jugador frente a minutos seguidos en cancha, con intervalo de confianza.
2. **Mapa de calor comparativo:** acierto de tiro por zona de la cancha cuando el jugador está descansado frente a cuando está cansado, para ver qué zonas se deterioran más.
3. **Recomendación de rotación:** una lectura simple del tipo "este jugador empieza a bajar de forma notable pasado el minuto X", acompañada de una advertencia sobre cuánta confianza hay en esa cifra.

## Datos

El análisis usa datos públicos de la NBA obtenidos con la librería `nba_api`:

- **Play-by-play:** eventos de sustitución y tiempos de juego.
- **ShotChartDetail:** coordenadas del tiro, resultado, periodo y tiempo restante.

**Alcance:** una temporada completa, centrada en los jugadores con más minutos. *\[Indicar número de jugadores y de tiros analizados.\]*

## Metodología

El análisis sigue cinco pasos, de la reconstrucción de los datos a la presentación de la incertidumbre.

1. **Reconstrucción de stints:** a partir de los eventos de sustitución se calcula, para cada tiro, los minutos seguidos que el jugador lleva en cancha. El descanso entre cuartos y el medio tiempo reinician o reducen el contador. *\[Definir la regla elegida.\]*
2. **Modelo base de tiro esperado:** se estima la probabilidad de acierto de cada tiro según distancia, zona y tipo de tiro. Así se separa "tiró peor" de "tomó tiros más difíciles".
3. **Análisis del residuo:** se estudia la diferencia entre el acierto real y el esperado según los minutos seguidos en cancha. Se usan efectos por jugador, de modo que cada jugador se compara consigo mismo y se evita el sesgo de que las estrellas juegan más tiempo.
4. **Mapas por zona:** los tiros se agrupan en 5 o 6 zonas grandes y las estimaciones se suavizan para evitar conclusiones con pocos datos.
5. **Incertidumbre:** todos los resultados se muestran con intervalos de confianza, y los tramos con pocos datos se marcan como poco fiables.

## Hallazgos

*Esta sección se llena con los resultados reales una vez que corra el análisis; no se anticipan conclusiones.*

- **Efecto promedio de la fatiga:** \[cuánto cae el acierto por cada X minutos seguidos en cancha\].
- **Zonas más afectadas:** \[por ejemplo, media distancia frente a cerca del aro, solo si los datos lo confirman\].
- **Diferencias entre jugadores:** \[casos destacados\].

Si el efecto resulta pequeño, también es un hallazgo válido: las rotaciones actuales ya serían bastante eficientes.

## Impacto práctico

La herramienta ofrece una referencia objetiva para las rotaciones y sirve a varios perfiles:

| Perfil | Cómo lo usa |
| --- | --- |
| Entrenadores | Referencia objetiva para decidir sustituciones, complementaria a su criterio. |
| Preparadores físicos | Identificar qué jugadores toleran menos los minutos seguidos. |
| Analistas y gerencia | Detectar jugadores cuyo valor depende de ser usados en bloques cortos. |
| Aficionados y medios | Visualizar y contar el cansancio en el juego de forma clara. |

## Limitaciones

El análisis mide asociación y no demuestra por sí solo que la fatiga sea la causa. Conviene declarar estas limitaciones de forma explícita:

- Los entrenadores ya sustituyen cuando perciben fatiga, así que los stints muy largos son raros y ruidosos.
- Otros factores, como la defensa rival o el rol del jugador en la jugada, pueden influir en el acierto.
- Algunas zonas y jugadores tienen pocos tiros, lo que limita la precisión.
- Se basa en una sola temporada; los resultados pueden cambiar con otras.

## Tecnologías

Python, `nba_api`, `pandas`, `statsmodels` o `scikit-learn`, `plotly` o `matplotlib`, Streamlit para el panel interactivo, GitHub para el código abierto y Streamlit Cloud para la demo en línea.

## Trabajo futuro

- Incluir la fatiga acumulada por viajes y *back-to-backs*.
- Ampliar el análisis a la WNBA o la EuroLeague.
- Medir también el impacto defensivo y no solo el tiro.

## Versión corta para Devpost

CourtFatigue mide cómo cae el rendimiento de tiro de los jugadores de la NBA según los minutos seguidos que llevan en cancha y muestra, con mapas de calor por zona, dónde se nota más el cansancio. Controla la dificultad de cada tiro y compara a cada jugador consigo mismo, para darle al entrenador una guía basada en datos sobre cuándo sustituir.
