# Notas del orador (español) — 7 diapositivas, 8 minutos como máximo + preguntas

Notas del orador de cada diapositiva. Hay dos decks con el mismo diseño y estas mismas notas en
la vista de presentador: el original en inglés (<https://claude.ai/artifact/FyZnhuoZ1R3cee1PtUsdgg>,
fuentes en `docs/slides/`, PDF en `docs/slides/*.pdf`) y la versión con el texto de las
diapositivas en español (<https://claude.ai/artifact/7f6S2LKkrRGGFvqDd2uVqU>, fuentes en
`docs/slides_es/`, PDF en `docs/slides_es/*.pdf`). El texto es el mismo que el cuerpo del discurso
(`docs/articulo/discurso_presentacion_es.md`, partes I–VII): unas 980 palabras, 7,5–8 minutos a
ritmo tranquilo, más el tiempo de teclear las cuatro preguntas de la demo. Los términos
regulatorios se dejan en inglés (SAE, SUSAR, IB, IRB/IEC), como en el propio asistente.

---

## 1 · Portada (0:00 – 0:30)

Buenos días. Presento un asistente de pregunta y respuesta para el cumplimiento normativo en
investigación clínica. Responde sobre tres normas —la ICH E6(R3) de Buenas Prácticas Clínicas, la
ICH E2A de notificación de seguridad y la Declaración de Helsinki—, en español o en inglés, cita
literalmente documento, sección y página, recuerda la conversación y rechaza lo que sus fuentes no
cubren. En ocho minutos: el problema, cómo está construido, el prompt, una demo y qué dicen los
números.

## 2 · El problema (0:30 – 1:20)

Viernes, 17:50. Un monitor recibe el aviso de un acontecimiento adverso grave. ¿Es un SUSAR?
¿Quién lo notifica, a quién, en qué plazo? La respuesta está repartida entre tres documentos,
noventa páginas en inglés, y en este ámbito no basta con responder: hay que demostrar de dónde
sale. En una inspección no vale «creo que eran quince días»; vale «E2A, sección III.B, página 7».
La trazabilidad es el requisito.

Un asistente generalista no sirve, porque un modelo de lenguaje puede inventar un plazo con total
aplomo. RAG ataca eso: buscar primero en documentos cerrados y responder solo con lo encontrado.
Elegí este dominio porque cinco años de soporte a software de ensayos clínicos y la certificación
ICH GCP me permiten juzgar si una respuesta es correcta.

## 3 · Arquitectura (1:20 – 3:10)

Tres documentos públicos, 801 fragmentos, cada uno con documento, sección y página. Los
documentos se descargan de los editores y se verifican con su huella; Helsinki se indexó desde la
web porque el PDF estropea los números de párrafo.

Descarté el agente que decide por sí mismo si busca: el enunciado exige usar la base en cada
consulta. El agente es un grafo fijo de cuatro nodos: reescribir, recuperar, generar, rechazar. La
reescritura convierte la pregunta, con el historial, en una pregunta autónoma en inglés: así
resuelve «¿y para las demás?» y salva el idioma del corpus.

La recuperación tiene cuatro etapas. Primero, la puerta: si la mejor puntuación no alcanza 0,69,
la pregunta se rechaza con una plantilla sin llamar al modelo; lo que no llega al modelo no se
puede inventar. Segundo, si la pregunta nombra documentos, las seis plazas se reparten entre
ellos. Tercero, diversidad. Cuarto, la etapa más útil: cada fragmento se amplía a su sección
completa. Nació de un fallo real: la definición de «grave» tiene cinco criterios, el fragmento
traía dos y el modelo la daba por completa. No se arregla pidiéndoselo, porque no puede completar
lo que no ve; se arregla entregándole la sección entera.

Tres decisiones que defiendo: una caché de embeddings versionada, porque el plan gratuito permite
mil textos al día y el corpus consume ochocientos; un umbral calibrado con datos, no fijado a ojo;
y una memoria de diez mensajes que mantiene los pasajes fuera del historial.

## 4 · El system prompt (3:10 – 3:50)

Cuatro versiones documentadas. La primera, el prompt de clase, respondía bien pero sin citas. La
tercera añadió citas por frase, atribución cuando las normas difieren y la política de idioma. Al
leer todas las respuestas de la evaluación aparecieron tres fallos: una pregunta de varios pasos
rechazada entera, su rechazo en español escrito en inglés y listas cortadas dadas por completas.
La cuarta gradúa el rechazo, construye las cadenas paso a paso y exige listas completas. El
principio: las restricciones duras van en el código; el criterio, en el prompt.

## 5 · Demo en vivo (3:50 – 5:50)

Paso a la aplicación.

**Pregunta uno** — *What is the timeline for expedited reporting of a fatal unexpected ADR?*
Fijaos en las citas y en el panel de fuentes: siete días naturales y ocho más para el informe
completo, ICH E2A.

**Pregunta dos**, en español y en el mismo hilo — *¿Y para las demás reacciones graves e
inesperadas?* La reescritura resuelve la referencia (se ve en «Searched as») y la respuesta vuelve
en español con la norma citada en inglés: quince días. Memoria y política de idioma en un solo
turno.

**Pregunta tres** — *¿Qué exigen ICH E6(R3) y la Declaración de Helsinki para incluir a
participantes que no pueden dar su consentimiento?* Dos documentos nombrados, dos posturas
contrastadas, cada una con su cita.

**Pregunta cuatro** — *¿Qué fármaco GLP‑1 es mejor para perder peso?* Es consejo clínico; la
puerta la rechaza con 0,64 y el modelo nunca la ve.

*(Si la cuatro respondiera en vez de rechazar: «el umbral está calibrado con doce consultas y esta
es la más ajustada, 0,64 frente a 0,69; en el notebook está la distribución».)*

## 6 · Evaluación (5:50 – 7:10)

Antes de conectar el modelo comprobé la recuperación sola: doce consultas del dominio, en inglés y
en español, y seis ajenas. Los dos grupos no se solapan y el umbral es el punto medio del hueco.

Después, un golden set de 25 preguntas en ambos idiomas, cincuenta ejecuciones, y un juez que
compara cada respuesta con una referencia. La versión final sube la corrección juzgada de 0,78 a
0,95, con el mismo juez y la misma puntuación. Como diseñé las correcciones mirando ese conjunto,
escribí doce preguntas nuevas tras congelar el sistema y las ejecuté una sola vez: de 0,95 a 1,00,
sin regresión. Ninguna pregunta del dominio fue rechazada y todas las ajenas sí.

Dos cautelas. El juez es el mismo modelo que responde, porque el grande permite veinte llamadas al
día; en 38 respuestas coinciden en el 79 % y el grande es más estricto, así que las cifras
absolutas son optimistas. Y queda un fallo que informo en lugar de ajustar: la cadena de
notificación de varios saltos aún pierde un eslabón.

## 7 · Límites y siguientes pasos (7:10 – 8:00)

Hoy el sistema conoce tres documentos, puede perder un salto en preguntas encadenadas, necesita
recalibrarse si cambia el corpus y su memoria vive en el proceso. Siguientes pasos, por valor:
descomponer las preguntas de varios saltos, añadir la farmacovigilancia europea y el Reglamento
536/2014, y un juez de fidelidad.

Cierro con tres frases. Un asistente experto en un dominio regulado no se distingue por el modelo
que usa, sino por lo que le impide equivocarse: una puerta calibrada antes de generar, pasajes
completos y citas obligatorias. Los fallos que parecen de redacción suelen ser de recuperación. Y
la fiabilidad se demuestra con preguntas que el autor no vio. Gracias. ¿Preguntas?

---

## Preguntas probables y respuestas cortas

- **¿Por qué no `create_agent` con una herramienta de búsqueda, como en clase?** El enunciado
  pide usar la base en cada consulta; un grafo fijo son una o dos llamadas por turno en vez de
  dos o más por bucle ReAct, y es trazable.
- **¿Cómo sabes que el umbral es correcto?** Se lee de los datos: el hueco entre la consulta de
  dominio más baja (0,75) y la de fuera de dominio más alta (0,63). Se guarda junto al nombre del
  modelo de embeddings; si cambia el modelo o el corpus, se recalibra.
- **¿Qué pasa con una norma que no está indexada, como 21 CFR?** La recuperación encuentra
  pasajes de consentimiento (0,77), pero el modelo responde que no está en su base, porque el
  prompt prohíbe conocimiento externo. Está en el notebook, sección 8, con comprobación.
- **¿El juez es el mismo modelo que responde?** Sí, por cuota. Comparado con el juez grande en
  38 respuestas: 79 % de acuerdo exacto y el grande es más estricto (0,70 frente a 0,78). La
  comparación v3→v4 usa el mismo juez en todo.
- **¿Las preguntas de evaluación las escribiste tú?** Se redactaron a partir del texto verificado
  de las normas, con ayuda de IA, y las revisé una a una como experto; una prueba automática
  comprueba que cada sección de referencia existe en el texto indexado.
- **¿Cuánto cuesta?** Embeber el corpus: 17 peticiones, una sola vez (unos 800 textos de la
  cuota diaria de 1.000). Cada turno: 1–2 llamadas al modelo y un embedding de consulta, que
  además se cachea.
- **¿Por qué el modelo añade una coletilla de "no es asesoramiento legal" si el prompt lo
  prohíbe?** Es un residuo documentado; en este dominio es deseable, y corregirlo obliga a
  repetir la evaluación, así que queda para después de la entrega.
