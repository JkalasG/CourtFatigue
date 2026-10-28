# CourtFatigue — texto para Devpost

> Copiar en los campos del formulario. Reemplazar `[URL DEMO]` y `[URL REPO]` al publicar.
> Pensado para jueces no técnicos: el lenguaje evita estadística avanzada.

## Título
CourtFatigue: ¿cuándo deja de rendir un jugador de la NBA?

## Descripción corta (tagline)
Medimos con 872 mil tiros de 4 temporadas de la NBA si el tiro cae al llevar muchos minutos seguidos en cancha, y encontramos algo distinto a lo esperado: el problema no es cuándo salen, sino cómo entran.

## El problema
Las rotaciones en la NBA se deciden en gran parte por intuición: el entrenador "ve cansado" a un jugador y lo cambia. Sustituir demasiado pronto desperdicia a los mejores; sustituir tarde cuesta puntos. No había una guía basada en datos que dijera cuántos minutos seguidos puede rendir cada jugador, ni con qué certeza.

## Qué hicimos
Con 872,158 tiros de las temporadas regulares 2021-22 a 2024-25 reconstruimos cuántos minutos seguidos llevaba cada tirador en el momento de cada lanzamiento, y descontamos la dificultad de cada tiro (un tiro forzado no es culpa del cansancio). Cada jugador se compara consigo mismo, dentro de su propia temporada. Para no confundir fatiga con "estar frío", comparamos a quien lleva muchos minutos contra jugadores que ya se calentaron.

## Qué encontramos
- **Hasta ~12 minutos seguidos no hay una caída medible del acierto:** +0.2 puntos porcentuales, con un margen que descarta caídas promedio mayores a ~0.1. Se repite en cada una de las 4 temporadas y resiste controles por partidos decididos, local o visitante, marcador y partidos seguidos.
- **Arranque frío:** en los primeros 30 segundos tras entrar, los jugadores anotan ~1.5 puntos porcentuales menos de lo normal en ellos; se normaliza hacia el minuto 2. Es negativo en las 4 temporadas (con intervalo claro en 3) y con dos reglas distintas para contar minutos.
- **Una regla popular no sirve:** "sustituir si cae 3 puntos" marca al 60% de los jugadores con datos reales y al 59% con los minutos barajados al azar. Es ruido, no fatiga.
- **Ningún jugador individual muestra una caída demostrable** (0 de 592). Con estos datos solo se detectarían caídas de ~14 puntos, así que la herramienta no etiqueta a nadie como "el que se cansa".
- **Calendario y defensa:** jugar un segundo partido seguido baja el acierto ~0.4 puntos; jugar en casa lo sube ~0.4; y hay equipos que defienden de forma estable mejor que otros (de −1.2 a +1.7 puntos entre el mejor y el peor).

## Impacto accionable
- **Entrenadores:** no acortar bloques por "cansancio de tiro" hasta ~12 min; diseñar la primera jugada tras una entrada para un tiro de ritmo (hipótesis a probar con vídeo); dosificar a los tiradores clave en el segundo partido de un back-to-back.
- **Preparadores físicos y gerencia:** no etiquetar a un jugador como "se cansa" sin evidencia propia; la carga debe medirse con datos físicos reales.
- **Analistas:** ranking defensivo de los 30 equipos con su margen de error, y el límite de lo que se puede afirmar de un jugador con los datos públicos.
- **Cualquiera:** el panel *Jugador nuevo* proyecta cómo rendiría alguien sin historial y cuánta incertidumbre hay, y se actualiza con sus tiros reales.

## Funciones
1. Resumen en lenguaje llano ("En 30 segundos"), panel para el cuerpo técnico y glosario.
2. Explorador de 643 jugadores: curva por minutos seguidos, mapas de tiro descansado vs. cansado, veredicto con su margen de error.
3. Evidencia: cobertura de datos, robustez, repetición por temporada, arranque frío, zonas de la cancha, características del jugador y ranking defensivo.
4. Proyector para jugador nuevo con intervalo de incertidumbre.
5. **Simulador 3D** donde la probabilidad de anotar suma términos medidos: acierto del jugador, distancia del tiro, **distancia del defensor**, **equipo rival**, arranque frío y fatiga. Las posiciones de los otros defensores son ilustrativas y así se rotula.

## Cómo lo construimos
Python (pandas, scikit-learn) para el análisis; interfaz en HTML, CSS y JavaScript sin librerías, con gráficos SVG propios; Three.js para el simulador. Modelo de tiro esperado validado fuera de muestra (por partido) y con una **prueba temporal** (entrenado con 3 temporadas y evaluado en la 4.ª, que no vio). Estadística: efectos fijos por jugador y temporada, errores agrupados, corrección por comparaciones múltiples, prueba placebo y pruebas con datos sintéticos. Para la defensa usamos además un registro de tiros 2014-15 con distancia al defensor (CC0).

## Rigor y límites (declarados)
Es asociación, no causalidad: los entrenadores sustituyen a quien ven cansado, lo que puede ocultar fatiga real. Las temporadas recientes no traen la posición de los defensores; en 2014-15 conocerla mejora el modelo de tiro esperado (AUC 0.617 → 0.634), y eso queda como ruido en nuestro análisis. El efecto de la distancia al defensor viene de esa otra época, y el del rival es del equipo en promedio. Casi no hay tiros con más de 12 minutos seguidos. "No detectado" no significa "no existe".

## Enlaces
- Demo: [URL DEMO]
- Código: [URL REPO]
