# Notas del orador (español) — 7 diapositivas, 8–9 minutos + preguntas

Notas del orador de cada diapositiva del deck
(<https://claude.ai/artifact/FyZnhuoZ1R3cee1PtUsdgg>; fuentes en `docs/slides/`). Las
diapositivas están en inglés; las notas que muestra la vista de presentador (`<aside>` de cada
diapositiva) son estas mismas, en español. La versión original en inglés queda en el historial
de git (hasta el commit `8ae6752`). Los términos
regulatorios se dejan en inglés (SAE, SUSAR, IB, IRB/IEC), como en el propio asistente.
Tiempos orientativos; la demo en vivo va entre la 5 y la 6.

---

## 1 · Portada (0:00 – 0:30)

Buenos días. He construido un agente de pregunta‑respuesta para el cumplimiento normativo en
investigación clínica. En los próximos ocho minutos: el problema, cómo está construido, el
prompt, una demo en vivo y qué dicen los números.

## 2 · El problema (0:30 – 1:30)

Un *clinical research associate* recibe un acontecimiento adverso grave un viernes a última
hora. ¿Es un SUSAR? ¿Quién lo notifica, a quién y en qué plazo? La respuesta está repartida
en tres documentos y hay que citarla literalmente, no parafrasearla. Eso es un problema de
recuperación de información con un requisito de trazabilidad.

Elegí este dominio porque puedo juzgar las respuestas: cinco años dando soporte a software
de ensayos clínicos —Medidata Rave, plataformas de Pfizer y Novo Nordisk—, la certificación
ICH GCP, y es la continuación natural de mi proyecto anterior sobre farmacovigilancia con la
base FAERS.

## 3 · Arquitectura (1:30 – 3:00)

¿Por qué un grafo explícito y no un agente con herramientas que decide si buscar? Tres
razones: el enunciado exige usar la base de conocimiento en cada consulta; en el plan
gratuito cada llamada extra al modelo cuesta; y una topología fija se traza y se prueba con
facilidad.

El flujo: la pregunta se reescribe como una pregunta autónoma en inglés —resuelve referencias
a turnos anteriores y traduce—; la recuperación la puntúa y aplica el umbral; y el enrutador
la manda a *generate* o a un rechazo con plantilla que nunca llega al modelo. Si la pregunta
nombra documentos, las posiciones del top‑6 se reparten entre ellos; y cada fragmento se
amplía a su sección completa, porque un fragmento de 500 caracteres había partido una
definición por la mitad.

Tres decisiones que defiendo: la caché de embeddings versionada —nada se re‑embebe y Chroma
se reconstruye sin llamadas a la API—; el umbral de rechazo calibrado con datos, no fijado a
ojo, y pasajes completos; y la memoria con ventana de diez mensajes, manteniendo el contexto
recuperado fuera del historial.

## 4 · El system prompt (3:00 – 4:00)

Cuatro versiones; enseño tres. La versión uno, el prompt de clase, respondía bien pero sin
marcas de cita: nada era trazable. La versión tres añadió citas por frase, atribución cuando
los documentos difieren y la política de idioma.

Entonces ejecuté el golden set completo y leí todas las respuestas: una pregunta de varios
pasos se rechazó aunque todos los pasos estaban en los pasajes; su rechazo en español salió
en inglés; y listas cortadas por el troceado se presentaban como completas. La versión
cuatro gradúa el rechazo —responde la parte cubierta y dice cuál no—, construye las cadenas
paso a paso y pide listas completas. El recorte de las listas lo arreglé en la recuperación,
no en el prompt: las restricciones duras van en código y el criterio va en el prompt.

## 5 · Demo en vivo (4:00 – 7:00)

Paso a la aplicación.

**Pregunta uno** — *What is the timeline for expedited reporting of a fatal unexpected ADR?*
Fijaos en las citas y en el panel de fuentes: siete días naturales más ocho para el informe
completo, ICH E2A.

**Pregunta dos**, en español y refiriéndose a la anterior — *¿Y para las demás reacciones
graves e inesperadas?* La reescritura resuelve la referencia en inglés para buscar
—se ve en "Searched as"— y la respuesta vuelve en español: quince días. Memoria y política
de idioma en un solo turno.

**Pregunta tres** — *¿Qué exigen ICH E6(R3) y la Declaración de Helsinki para incluir a
participantes que no pueden dar su consentimiento?* Nombra dos documentos, así que la
recuperación reparte las posiciones entre ambos y la respuesta contrasta E6(R3) con Helsinki,
cada uno con su cita.

**Pregunta cuatro** — *¿Qué fármaco GLP‑1 es mejor para perder peso?* Es consejo clínico:
el umbral de recuperación la rechaza antes de que intervenga el modelo. El modelo nunca vio
la pregunta.

*(Si la cuatro respondiera en vez de rechazar: "el umbral está calibrado con doce consultas
y esta es la más ajustada, 0,64 frente a 0,69; en el notebook está la distribución".)*

Y, en el notebook, la traza nodo a nodo de una pregunta: rewrite, retrieve, generate.

## 6 · Evaluación (7:00 – 8:15)

Antes de conectar el modelo comprobé la recuperación por sí sola: doce consultas de dominio,
en inglés y en español, y seis fuera de dominio. El español puntúa un poco más bajo pero
encuentra los mismos pasajes. Los dos grupos no se solapan y el umbral de rechazo es el punto
medio del hueco.

Después, el golden set: cincuenta ejecuciones. La recuperación ya era perfecta a nivel de
documento, pero al leer cada respuesta aparecieron listas partidas por el troceado, una
pregunta de varios pasos rechazada y rechazos en español escritos en inglés. La expansión por
sección, el enrutado por documento y el prompt v4 subieron la corrección juzgada de 0,78 a
0,95 y la cobertura de palabras clave de 0,82 a 0,97, con la misma puntuación.

Como diseñé las correcciones mirando ese conjunto, escribí doce preguntas nuevas después de
congelar v4 y las ejecuté una sola vez: de 0,95 a 1,00, sin regresión. El acierto de documento
se mantuvo en 1,0 y ninguna pregunta de dominio fue rechazada en ninguna de las dos versiones.

El juez es *flash‑lite*, el mismo modelo que responde, porque el juez grande permite veinte
llamadas al día; en las 38 respuestas que juzgaron ambos coinciden en el 79 % y el grande es
más estricto, así que las cifras absolutas hay que leerlas como optimistas. Lo que queda: una
cadena de notificación de varios saltos aún pierde un paso, y el enrutado perdió un acierto
de sección en la pregunta que compara los dos documentos, en ambos idiomas, aunque la
respuesta en español sigue citando el Principio 2.1.

## 7 · Límites y siguientes pasos (8:15 – 9:00)

Lo que no hace: solo tres documentos; una pregunta de varios saltos aún pierde un paso,
porque una sola pasada de recuperación no trae todos los saltos; el umbral hay que
recalibrarlo si cambia el corpus o el modelo; la memoria vive en el proceso; y el plan
gratuito cuenta textos embebidos por día.

Siguientes pasos, por orden de valor: descomponer las preguntas de varios saltos en una
búsqueda por paso; añadir los textos europeos de farmacovigilancia y de ensayos clínicos (GVP
VI, Reglamento 536/2014); un juez de fidelidad respuesta‑frente‑a‑pasajes; recuperación
híbrida; y después un guardián de entrada y memoria persistente.

Gracias. ¿Preguntas?

---

## Preguntas probables y respuestas cortas

- **¿Por qué no `create_agent` con una herramienta de búsqueda, como en clase?** El enunciado
  pide usar la base en cada consulta; un grafo fijo son una o dos llamadas por turno en vez de
  dos o más por bucle ReAct, y es trazable.
- **¿Cómo sabes que el umbral es correcto?** Se lee de los datos: el hueco entre la consulta de
  dominio más baja y la de fuera de dominio más alta. Se guarda junto al nombre del modelo de
  embeddings; si cambia el modelo, se recalibra.
- **¿Qué pasa con una norma que no está indexada, como 21 CFR?** La recuperación encuentra
  pasajes de consentimiento (0,77), pero el modelo responde que no está en su base, porque el
  prompt prohíbe conocimiento externo. Está en el notebook, sección 8, con comprobación.
- **¿El juez es el mismo modelo que responde?** Sí, por cuota. Comparado con el juez grande en
  38 respuestas: 79 % de acuerdo exacto y el grande es más estricto (0,70 frente a 0,78). La
  comparación v3→v4 usa el mismo juez en todo.
- **¿Cuánto cuesta?** Embeber el corpus: 17 peticiones, una sola vez (unos 800 textos de la
  cuota diaria de 1.000). Cada turno: 1–2 llamadas al modelo y un embedding de consulta,
  que además se cachea.
- **¿Por qué el modelo añade una coletilla de "no es asesoramiento legal" si el prompt lo
  prohíbe?** Es un residuo documentado; en este dominio es deseable, y corregirlo obliga a
  repetir la evaluación, así que queda para después de la entrega.
