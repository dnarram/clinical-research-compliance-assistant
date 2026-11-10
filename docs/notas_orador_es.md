# Notas del orador (español) — 7 diapositivas, 8 minutos como máximo + preguntas

Notas del orador de cada diapositiva. Hay dos decks con el mismo diseño y estas mismas notas en
la vista de presentador: el original en inglés (<https://claude.ai/artifact/FyZnhuoZ1R3cee1PtUsdgg>,
fuentes en `docs/slides/`, PDF en `docs/slides/*.pdf`) y la versión con el texto de las
diapositivas en español (<https://claude.ai/artifact/7f6S2LKkrRGGFvqDd2uVqU>, fuentes en
`docs/slides_es/`, PDF en `docs/slides_es/*.pdf`). El texto es el mismo que el cuerpo del discurso
(`docs/articulo/discurso_presentacion_es.md`, partes I–VII): unas 1.040 palabras, 7,5–8 minutos a
ritmo tranquilo, más el tiempo de teclear las cuatro preguntas de la demo. Los términos
regulatorios se dejan en inglés (SAE, SUSAR, IB, IRB/IEC), como en el propio asistente.

---

## 1 · Portada (0:00 – 0:30)

Buenos días. Voy a contaros cómo he construido un asistente que responde sobre normativa de
investigación clínica y, sobre todo, por qué me fío de lo que dice. Conoce tres textos: la ICH
E6(R3) de Buenas Prácticas Clínicas, la ICH E2A de notificación de seguridad y la Declaración de
Helsinki. Contesta en español o en inglés, cita documento, sección y página, recuerda la
conversación y, cuando no sabe, lo dice en lugar de inventar. En ocho minutos: el problema, cómo
está hecho, el prompt, una demo y qué dicen los números.

## 2 · El problema (0:30 – 1:20)

Imaginad un viernes, 17:50. Eres monitor de un ensayo clínico y te llega el aviso de un
acontecimiento adverso grave. ¿Es un SUSAR? ¿Quién lo notifica, a quién, en cuánto tiempo? La
respuesta existe, pero está repartida entre tres documentos, noventa páginas en inglés. Y aquí no
basta con acertar: hay que demostrar de dónde sale. En una inspección, «creo que eran quince días»
no vale. Vale «E2A, sección III.B, página 7». La trazabilidad no es un extra: es el requisito.

Un chatbot generalista no sirve, porque un modelo de lenguaje es capaz de inventarse un plazo con
total seguridad. La idea de RAG es sencilla: buscar primero en documentos cerrados y contestar solo
con lo encontrado. Elegí este dominio porque lo conozco: cinco años en soporte de software de
ensayos clínicos y certificación ICH GCP me permiten distinguir una respuesta correcta de una que
solo suena bien.

## 3 · Arquitectura (1:20 – 3:10)

Por dentro hay tres documentos públicos, troceados en 801 fragmentos, cada uno con su documento, su
sección y su página. Los descargo de los editores y verifico su huella digital; Helsinki lo indexé
desde la web, porque el PDF me estropeaba los números de párrafo.

Descarté el agente que decide si busca o no: el enunciado pide usar la base en cada consulta. Es un
grafo fijo de cuatro nodos: reescribir, recuperar, generar o rechazar. El primero convierte tu
pregunta, con el historial, en una pregunta completa y en inglés. Por eso entiende un «¿y para las
demás?» y, de paso, busca en el idioma del corpus.

La recuperación tiene cuatro etapas. La primera es una puerta: si la mejor coincidencia no llega a
0,69, la pregunta se rechaza con una plantilla y el modelo ni la ve. Lo que no llega al modelo no se
puede inventar. Segunda: si preguntas por varios documentos, las seis plazas se reparten entre
ellos. Tercera: variedad, para no traer seis veces lo mismo. Y la cuarta, la que más me ha enseñado:
cada fragmento se amplía a su sección completa. Nació de un fallo real. La definición de «grave»
tiene cinco criterios; el fragmento traía dos y el modelo la daba por completa. Pedirle que no lo
hiciera no sirve: nadie completa lo que no ve. Hay que dárselo entero.

Tres decisiones más: una caché de embeddings versionada, porque el plan gratuito da mil textos al
día y el corpus gasta ochocientos; un umbral calibrado con datos, no a ojo; y una memoria de diez
mensajes que deja los pasajes fuera del historial.

## 4 · El system prompt (3:10 – 3:50)

El prompt tiene cuatro versiones documentadas. La primera, la de clase, respondía bien pero sin
citas. La tercera añadió una cita por frase, atribución cuando las normas discrepan y política de
idioma. Entonces leí una a una las respuestas de la evaluación y aparecieron tres fallos: una
pregunta de varios pasos rechazada entera, un rechazo en español escrito en inglés y listas cortadas
dadas por completas. La cuarta rechaza con matices, construye las cadenas paso a paso y exige listas
completas. Mi principio: las restricciones duras van en el código; el criterio, en el prompt.

## 5 · Demo en vivo (3:50 – 5:50)

Os lo enseño.

**Pregunta uno** — *What is the timeline for expedited reporting of a fatal unexpected ADR?*
Mirad las citas: siete días, y ocho más para completar el informe.

**Pregunta dos**, en español y en el mismo hilo — *¿Y para las demás reacciones graves e
inesperadas?* No repito nada: la reescritura entiende la referencia (se ve en «Searched as») y la
respuesta llega en español, con la norma citada en inglés: quince días. Memoria e idioma, en un
solo turno.

**Pregunta tres** — *¿Qué exigen ICH E6(R3) y la Declaración de Helsinki para incluir a
participantes que no pueden dar su consentimiento?* Dos documentos, dos posturas contrastadas,
cada una con su cita.

**Pregunta cuatro** — *¿Qué fármaco GLP‑1 es mejor para perder peso?* Es consejo clínico, no está
en sus fuentes. La puerta lo rechaza con un 0,64, por debajo del 0,69, y el modelo ni se entera.

*(Si la cuatro respondiera en vez de rechazar: «el umbral está calibrado con doce consultas y esta es la más ajustada, 0,64 frente a 0,69; en el notebook está la distribución».)*

## 6 · Evaluación (5:50 – 7:10)

¿Y cómo sé que funciona? Antes de conectar el modelo probé solo la recuperación: doce consultas del
dominio, en inglés y en español, y seis ajenas. Los dos grupos no se solapan, y el umbral es el
punto medio del hueco.

Después, 25 preguntas en ambos idiomas, cincuenta ejecuciones y un juez que compara cada respuesta
con una de referencia. Entre la versión tercera y la final, la corrección sube de 0,78 a 0,95, con
el mismo juez y la misma puntuación. Pero había ajustado el sistema mirando ese conjunto. Así que,
ya congelado, escribí doce preguntas nuevas y las pasé una sola vez: de 0,95 a 1,00, sin retrocesos.
Ninguna pregunta del dominio fue rechazada; todas las ajenas, sí.

Dos cautelas, que prefiero contaros yo. El juez es el mismo modelo que responde, porque el grande
solo permite veinte llamadas al día; en 38 respuestas coinciden el 79 % y el grande es más estricto,
así que las cifras absolutas son algo optimistas. Y queda un fallo que cuento en lugar de maquillar:
la cadena de notificación de varios saltos todavía pierde un eslabón.

## 7 · Límites y siguientes pasos (7:10 – 8:00)

Los límites, con franqueza: solo conoce tres documentos, puede perder un salto en preguntas
encadenadas, hay que recalibrarlo si cambia el corpus y su memoria vive en el proceso. Lo siguiente:
descomponer las preguntas de varios saltos, añadir la farmacovigilancia europea y el Reglamento
536/2014, y un juez de fidelidad a las fuentes.

Me llevo tres ideas. Un asistente experto en un ámbito regulado no se distingue por el modelo que
usa, sino por lo que le impide equivocarse: una puerta calibrada, pasajes completos y citas
obligatorias. Muchos fallos que parecen de redacción son de recuperación. Y la fiabilidad se
demuestra con preguntas que el autor no ha visto. Gracias. ¿Preguntas?

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
