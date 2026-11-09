# Un asistente de cumplimiento normativo para la investigación clínica con recuperación aumentada, rechazo calibrado y evaluación con conjunto reservado

**Discurso completo de la presentación y base para un artículo académico.** Versión extensa,
en prosa continua, de todo lo que la presentación oral pretende cubrir. La exposición en directo
(8–9 minutos, siete diapositivas) es un resumen de este texto; el guion breve está en
`docs/notas_orador_es.md`. Cada cifra procede de un archivo del repositorio, indicado en el
anexo, para que el paso a artículo no requiera reconstruir nada.

*David Naranjo Ramírez · Proyecto final del módulo de IA Generativa · Máster en Data Science &
IA, Evolve Academy · Noviembre de 2026.*

## Nota previa: cómo usar este documento

El texto está escrito para ser **dicho**: frases completas, en primera persona y en el orden de
la presentación. Al mismo tiempo, cada parte corresponde a una sección de un artículo con
estructura IMRaD (introducción, métodos, resultados y discusión). La tabla siguiente muestra la
correspondencia.

| Parte del discurso | Diapositiva | Sección del artículo |
|---|---|---|
| I. Apertura | 1 · Portada | Título y resumen |
| II. El problema | 2 · El problema | Introducción y motivación |
| III. Objetivos y preguntas | — | Introducción: objetivos y preguntas de investigación |
| IV. El corpus | 3 · Arquitectura | Métodos: corpus y preprocesado |
| V. La arquitectura | 3 · Arquitectura | Métodos: sistema |
| VI. El prompt | 4 · El system prompt | Métodos: diseño de instrucciones |
| VII. La demostración | 5 · Demo en vivo | Resultados: ejemplos cualitativos |
| VIII. Cómo evalué | 6 · Evaluación | Métodos: protocolo de evaluación |
| IX. Qué salió | 6 · Evaluación | Resultados |
| X. Qué significa y qué no | — | Discusión y amenazas a la validez |
| XI. Límites y siguientes pasos | 7 · Límites | Limitaciones y trabajo futuro |
| XII. Cierre | 7 | Conclusiones |

Leído en voz alta, el discurso completo dura unos cuarenta minutos. Para la presentación de
ocho, cada parte se reduce a su primer párrafo y a su cifra principal.

## I. Apertura

Buenos días. Voy a presentar un asistente de pregunta y respuesta para el cumplimiento normativo
en investigación clínica. Responde preguntas sobre tres normas: la guía ICH E6(R3) de Buenas
Prácticas Clínicas, la guía ICH E2A sobre la notificación expeditiva de datos de seguridad y la
Declaración de Helsinki en su revisión de 2024. Lo hace en español o en inglés, cita
literalmente el documento, la sección y la página de cada afirmación, recuerda la conversación y
rechaza lo que sus fuentes no cubren.

Técnicamente es un sistema de generación aumentada con recuperación, lo que en la literatura se
conoce como RAG, construido con los modelos Gemini de Google, la base de datos vectorial ChromaDB
y un agente orquestado con LangGraph. Pero lo que quiero contar no es la lista de herramientas,
sino tres ideas que, a mi juicio, son las que hacen que un sistema así sea fiable en un ámbito
regulado. La primera: la decisión de no responder debe tomarse **antes** de que intervenga el
modelo de lenguaje y con un umbral medido, no supuesto. La segunda: los fallos que parecen de
redacción a menudo son fallos de recuperación, y se corrigen mejor ahí. La tercera: un asistente
experto solo es tan bueno como la evaluación que lo respalda, y esa evaluación tiene que incluir
preguntas que el autor no vio mientras lo mejoraba.

## II. El problema

Empiezo por una escena. Es viernes, son las 17:50, y un monitor de ensayos clínicos, lo que en la
profesión llamamos un CRA, recibe el aviso de un acontecimiento adverso grave en uno de sus
centros. Las preguntas que tiene que responder son tres: ¿es un SUSAR, es decir, una sospecha de
reacción adversa grave e inesperada? ¿Quién debe notificarla y a quién? ¿En qué plazo?

La respuesta existe, pero está repartida. Los plazos están en la ICH E2A: siete días naturales
para las reacciones mortales o que amenazan la vida, más ocho para completar el informe, y quince
para las demás reacciones graves e inesperadas. Las obligaciones del investigador y del promotor
están en la ICH E6(R3): el investigador notifica de inmediato al promotor, y el promotor notifica
a las autoridades conforme a la E2A. Y si el participante es vulnerable, entran en juego los
principios éticos de la Declaración de Helsinki. Tres documentos, más de noventa páginas de
contenido normativo, en inglés.

Hay un segundo requisito que hace este problema distinto de una búsqueda corriente: en
investigación clínica no basta con dar la respuesta, hay que poder **demostrar de dónde sale**. En
una auditoría o en una inspección, «creo que eran quince días» no vale; vale «ICH E2A, sección
III.B, página 7». La trazabilidad no es un adorno: es el requisito.

¿Por qué no basta un asistente de inteligencia artificial generalista? Porque los modelos de
lenguaje generan texto plausible a partir de lo que aprendieron, y a veces ese texto es falso con
total aplomo. Es el fenómeno que la literatura llama alucinación. En un dominio regulado, un plazo
o un número de artículo inventado es el peor fallo posible, precisamente porque parece correcto.
Además, la ICH E6(R3) es de enero de 2025: un modelo general la conoce poco o la confunde con la
versión anterior, la R2.

La técnica RAG ataca exactamente este problema. En lugar de responder de memoria, el sistema
busca primero los pasajes pertinentes en un conjunto cerrado de documentos y obliga al modelo a
responder solo con ellos. Es la diferencia entre un examen a libro cerrado y uno a libro abierto
en el que, además, hay que indicar la página.

Elegí este dominio por una razón metodológica, no solo personal. He pasado cinco años dando
soporte a software de ensayos clínicos, con Medidata Rave y plataformas de Pfizer y Novo Nordisk,
tengo la certificación ICH GCP y mi proyecto anterior del máster analizaba la farmacovigilancia de
los fármacos GLP‑1 en la base FAERS. Eso me permite algo imprescindible para evaluar un asistente
experto: **juzgar si una respuesta es correcta**. Sin conocimiento del dominio, la evaluación se
reduce a comprobar que el texto suena bien.

## III. Objetivos y preguntas de investigación

El objetivo general fue construir un asistente experto que cumpliera los requisitos del enunciado
del máster (una base de conocimiento propia en ChromaDB con embeddings de Gemini, un agente en
LangGraph con memoria conversacional, un prompt de sistema justificado y una interfaz de
conversación) y, además, demostrar con datos que es fiable. De ahí salen cuatro preguntas que
estructuran el resto de la exposición y que son las que propondría como preguntas de investigación
en el artículo:

1. **Trazabilidad.** ¿Puede un sistema RAG construido con modelos ligeros y de uso gratuito
   responder preguntas normativas con citas verificables a nivel de documento, sección y página?
2. **Abstención.** ¿Se puede separar de forma fiable lo que la base de conocimiento cubre de lo que
   no cubre mediante un umbral sobre la similitud de recuperación, calibrado empíricamente y
   aplicado antes de la generación?
3. **Diagnóstico.** ¿Qué fallos aparecen al evaluar con un conjunto de preguntas de referencia, y
   qué intervenciones los corrigen mejor: cambios en las instrucciones del modelo o cambios en la
   recuperación?
4. **Generalización.** ¿Se mantienen las mejoras en preguntas nuevas, redactadas después de cerrar
   el sistema?

## IV. El corpus

La base de conocimiento son tres documentos públicos.

- La **ICH E2A**, *Clinical Safety Data Management: Definitions and Standards for Expedited
  Reporting*, publicada por el Consejo Internacional de Armonización en 1994 y todavía vigente.
  Indexé las páginas 3 a 12, que dan 68 fragmentos.
- La **ICH E6(R3)**, *Guideline for Good Clinical Practice*, en su versión definitiva del 6 de enero
  de 2025. Páginas 8 a 86, 665 fragmentos.
- La **Declaración de Helsinki** de la Asociación Médica Mundial, revisión de octubre de 2024, con
  sus 37 párrafos numerados: 68 fragmentos.

En total, unas noventa páginas de contenido y **801 fragmentos**. Excluí portadas, historiales de
versiones e índices, porque no aportan contenido normativo y contaminan la búsqueda con
coincidencias de títulos.

El preprocesado merece una mención, porque en documentos regulatorios la calidad del texto
condiciona directamente la calidad de las citas. Un PDF está diseñado para imprimirse: repite
cabeceras y números de página en cada hoja, parte palabras con guion al final de línea y llena los
índices de puntos guía. Mi canal de ingesta elimina las líneas que se repiten en muchas páginas,
reúne las palabras partidas, quita los puntos guía y detecta el número de sección de cada párrafo
con patrones propios de las guías ICH (2.8.10, A.1.1, numeración romana) y de los párrafos
numerados de Helsinki. Un ejemplo de por qué esto importa: el detector de cabeceras repetidas
borraba al principio líneas de contenido que solo se diferenciaban en un número; lo corregí para
que enmascarara los dígitos solo en líneas muy cortas.

Con la Declaración de Helsinki tomé una decisión que ilustra el criterio general. El PDF que genera
la web de la Asociación Médica Mundial separa los números de párrafo de su texto y estropea las
ligaduras tipográficas: aparecen cadenas como «Clari6cation» o «su=cient». En la página web, en
cambio, los párrafos están marcados con su número en el propio HTML. Así que indexé la página web
y reconstruí cada párrafo con su número. **La fuente se elige por la calidad del texto, no por el
formato**.

El troceado usa la configuración vista en clase: fragmentos de 500 caracteres con 50 de
solapamiento, mediante un divisor recursivo. Cada fragmento lleva como metadatos su documento, su
sección, su página y su posición, y un identificador determinista construido con esos datos y un
resumen criptográfico del texto. Gracias a ese identificador, volver a procesar un documento sin
cambios no duplica nada.

Por último, la procedencia. Los documentos no se redistribuyen en el repositorio: un programa los
descarga de las webs oficiales y comprueba su huella SHA‑256 contra la registrada. Si un organismo
modifica el documento, la comprobación falla a propósito, y el sistema solo vuelve a procesar ese
documento cuando se revisa y se registra la nueva huella.

## V. La arquitectura

### Una decisión de partida: un grafo explícito

En clase vimos el patrón de «RAG agéntico», en el que el modelo dispone de una herramienta de
búsqueda y decide por sí mismo si la usa. Lo descarté por tres razones. Primera, el enunciado exige
que la base de conocimiento se use en **cada** consulta, y un agente que decide puede decidir no
buscar. Segunda, en el plan gratuito cada llamada al modelo consume cuota, y un bucle de
razonamiento y acción hace dos o más llamadas por turno. Tercera, una topología fija se traza y se
prueba con facilidad, algo que valoro especialmente en un entorno regulado.

El agente es, por tanto, un grafo de estados explícito con cuatro nodos: `rewrite_query`,
`retrieve`, `generate` y `refuse`. Toda pregunta recorre `rewrite_query → retrieve` y, según el
resultado de la recuperación, termina en `generate` o en `refuse`. El modelo de lenguaje nunca
decide si se consulta la base de conocimiento.

### Reescritura de la consulta y política de idioma

El primer nodo resuelve dos problemas a la vez. En una conversación, las preguntas de seguimiento
son elípticas: «¿Y para las demás reacciones graves e inesperadas?» no significa nada sin el turno
anterior. Y el corpus está en inglés, mientras que los usuarios, en mi contexto, escriben a menudo
en español. El nodo convierte la última pregunta, con ayuda del historial, en **una pregunta
autónoma en inglés**, que es la que se usa para buscar. En el primer turno, si la pregunta ya está
en inglés, se usa tal cual y se ahorra una llamada al modelo.

El idioma de la respuesta se decide con una heurística barata (acentos y palabras funcionales
propias de cada lengua) y se impone de forma **determinista**: el mensaje que recibe el modelo
termina siempre con «Reply in English.» o «Responde en español.». Lo hice así porque, en las
primeras pruebas, la instrucción del prompt de sistema no bastó: una pregunta en inglés recibió
una vez respuesta en español. La política completa es: responder en el idioma del usuario, citar
el texto normativo literalmente en inglés y no traducir los términos regulatorios como SAE, SUSAR
o IRB/IEC.

### Recuperación en cuatro etapas

La recuperación es el corazón del sistema y tiene cuatro etapas, en un orden que no es casual.

**Primero, la puerta.** Se buscan los seis fragmentos más similares a la pregunta en toda la
colección y se toma la mejor puntuación de relevancia. Si no alcanza el umbral calibrado, 0,6885,
la pregunta se considera fuera del alcance y el grafo va directamente a `refuse`, que devuelve un
texto fijo en el idioma del usuario **sin llamar al modelo**. Cómo se calibró el umbral lo cuento en
la parte VIII. La idea de diseño es que lo que nunca llega al modelo no se puede inventar.

**Segundo, el enrutado por documento.** Si la pregunta nombra documentos (detectados con alias como
«E2A», «E6», «GCP», «Helsinki»), las seis plazas se reparten entre ellos con un filtro de metadatos:
tres y tres si nombra dos; cuatro filtradas y dos libres si nombra uno, para que un pasaje relevante
de otro documento todavía pueda aparecer. Esta etapa nació de un fallo observado: al pedir una
comparación entre la E6(R3) y Helsinki sobre participantes que no pueden consentir, los párrafos de
Helsinki puntuaban más alto y ocupaban todas las plazas, y la respuesta no podía comparar nada.
Importante: la puerta usa siempre las puntuaciones **sin filtrar**, de modo que el enrutado nunca
puede convertir un rechazo en una respuesta, ni al revés, y la calibración sigue siendo válida.

**Tercero, la diversidad.** Dentro de las plazas disponibles se aplica relevancia marginal máxima
(MMR), que elige entre los 24 candidatos más similares los 6 que mejor equilibran parecido con la
pregunta y diferencia entre sí, con un parámetro de 0,6. Evita que seis fragmentos casi idénticos
desperdicien el contexto.

**Cuarto, la expansión a la sección.** Esta etapa es, probablemente, la contribución más útil del
proyecto. Al leer las respuestas de la evaluación descubrí que los fragmentos de 500 caracteres
cortaban listas: la definición de «grave» de la E2A tiene cinco criterios y el fragmento recuperado
contenía dos; los elementos del consentimiento informado de la E6(R3), del (a) al (v), llegaban
hasta el (d). Y el modelo presentaba esas listas como completas. La solución no fue pedirle al
modelo que no lo hiciera, porque no puede completar lo que no ve, sino **ampliar cada fragmento
recuperado a su sección completa** cuando esta no supera 4.000 caracteres y, si la supera, a sus
fragmentos vecinos. El límite no es arbitrario: la sección más larga que un usuario puede pedir
entera, la §2.8.10 con los 22 elementos del consentimiento, mide 3.653 caracteres, y 393 de las 399
secciones del corpus caben. La expansión se hace leyendo la colección local, sin ninguna llamada a
la API.

El resultado son pasajes numerados con su cita legible: «ICH E6(R3) §2.8.10, pp. 24–26» o
«Declaration of Helsinki (2024) ¶28».

### Generación y memoria

El nodo `generate` recibe el prompt de sistema, los diez últimos mensajes de la conversación, los
pasajes numerados, la pregunta original y la línea de idioma. La memoria es un *checkpointer* de
LangGraph en memoria, con un identificador de hilo por conversación: cada hilo guarda la
conversación completa, pero al modelo solo llegan los diez últimos mensajes. Los pasajes
recuperados viven en el estado del grafo y **no** en el historial, de modo que la ventana de memoria
cuenta turnos y no páginas de normas, y cada turno vuelve a buscar.

El coste por turno es, por tanto, una búsqueda vectorial con un embedding de consulta (que además se
guarda en caché para no repetirlo) y una o dos llamadas al modelo de lenguaje; los rechazos no hacen
ninguna.

### Ingeniería para el plan gratuito y la reproducibilidad

Hay una parte del trabajo que no se ve en la demostración pero sin la cual el proyecto no
funcionaría. El plan gratuito de embeddings permite **1.000 textos al día por proyecto de Google
Cloud**, y un lote de 50 cuenta como 50; la construcción del corpus consume unos 800. Descubrí ese
límite agotándolo. A partir de ahí tomé tres decisiones.

La primera: la **fuente de verdad es una caché versionada de embeddings**, comprimida y guardada en
el repositorio, no el directorio de Chroma. Un manifiesto registra, para cada documento, su huella,
el modelo y la dimensión de los embeddings y la configuración de troceado. Un documento se vuelve a
procesar solo si cambia alguno de esos datos, y la construcción es reanudable: si se interrumpe por
la cuota, el siguiente intento continúa donde lo dejó. Chroma se reconstruye desde la caché en
segundos y sin ninguna llamada, en local, en el cuaderno y en Streamlit Cloud.

La segunda: los embeddings son **asimétricos**: los documentos se codifican en modo documento y las
preguntas en modo consulta, como recomienda el proveedor, con 768 dimensiones.

La tercera: una **segunda clave** de otro proyecto de Google, con conmutación automática solo ante
errores de cuota diaria, y un modo de **reproducción sin conexión** con las respuestas de la
demostración grabadas, por si la cuota se agota el día de la presentación.

Todo el código está tipado y cubierto por **77 pruebas automáticas** que se ejecutan sin red, con
modelos simulados, y la aplicación está desplegada en Streamlit Cloud. Una anécdota del despliegue
ilustra el tipo de problema que aparece en producción: Streamlit Cloud aplica los cambios sin
reiniciar el proceso, así que el agente en caché de la versión anterior siguió respondiendo con el
canal viejo. Lo resolví con una huella del código que invalida la caché cuando cambia.

## VI. El prompt de sistema

El enunciado pide un prompt de sistema justificado. Escribí cuatro versiones y documenté qué se
**observó** en cada una, separándolo de lo que solo se razonó, para no atribuir a una versión
fallos que nunca vi.

La **versión 1** es el prompt de clase: «usa la información de los documentos para responder de
forma concisa y clara». Sobre una pregunta de plazos de SUSAR dio una respuesta correcta y fluida,
pero **sin una sola marca de cita**: el panel de fuentes mostraba seis pasajes y nada en el texto
decía qué pasaje respaldaba qué frase. Para un CRA eso significa releer la guía para comprobar cada
afirmación.

La **versión 2** añadió el papel, el público, el alcance y la regla de decir «no lo encuentro en mi
base de conocimiento». Fue un paso de diseño intermedio y no la evalué por separado.

La **versión 3** introdujo el protocolo de citas, una cita numerada en cada frase con contenido, la
regla de atribuir por separado las posturas de documentos que difieren, la política de idioma y el
formato: primero la respuesta directa y después el detalle.

Con la versión 3 ejecuté el conjunto de evaluación completo y **leí todas las respuestas**. Aparecieron
tres fallos. Una pregunta de varios pasos, del investigador a la autoridad reguladora, se rechazó
entera aunque todos los pasos estaban en los pasajes: la regla de insuficiencia era de todo o nada.
Su versión en español se rechazó **en inglés**, porque la regla citaba la frase inglesa y el modelo la
copiaba, por encima de la línea de idioma. Y las listas cortadas por el troceado se presentaban como
completas.

La **versión 4**, la que está en uso, gradúa el rechazo: responde la parte cubierta y dice
explícitamente cuál no, y solo cuando nada es relevante dice que no lo encuentra, en el idioma del
usuario. Construye las cadenas paso a paso, citando cada paso. Y da todos los elementos de las listas
que aparecen en los pasajes o avisa de que la lista continúa.

De este proceso extraigo un principio que creo transferible: **las restricciones duras van en el
código y el criterio va en el prompt**. El idioma de la respuesta es una línea determinista. Las
preguntas fuera de dominio no llegan al modelo. Las listas cortadas se arreglaron en la recuperación.
Al prompt le dejé lo que requiere juicio: cómo combinar pasajes, cómo graduar una respuesta parcial,
cómo atribuir posturas.

Queda un residuo conocido que prefiero declarar: el modelo suele añadir al final una nota de «esto es
información regulatoria, no asesoramiento legal ni médico», aunque el formato le pide no añadir
avisos. En este dominio es deseable, y corregirlo obligaría a repetir toda la evaluación, así que lo
dejé documentado para después de la entrega.

## VII. La demostración

La demostración consta de cuatro preguntas, elegidas para que cada una muestre un comportamiento
distinto.

**Primera pregunta, en inglés:** *What is the timeline for expedited reporting of a fatal unexpected
ADR?* Es una pregunta directa de plazos. La mejor puntuación de recuperación es 0,87, muy por encima
del umbral. La respuesta cita literalmente la E2A: «as soon as possible but no later than 7 calendar
days after first knowledge by the sponsor that a case qualifies», seguido de «as complete a report
as possible within 8 additional calendar days». Cada frase lleva su número, y el panel de fuentes
muestra el pasaje, la sección, la página y la puntuación.

**Segunda pregunta, en español y en el mismo hilo:** *¿Y para las demás reacciones graves e
inesperadas?* Aquí se ven dos cosas a la vez. La memoria: el nodo de reescritura resuelve «las
demás» y busca con *What is the timeline for expedited reporting of other serious and unexpected
adverse drug reactions?*, que la aplicación muestra bajo la respuesta. Y la política de idioma: la
respuesta llega en español, con el texto de la norma entre comillas en inglés: quince días naturales.

**Tercera pregunta, que nombra dos documentos:** *¿Qué exigen ICH E6(R3) y la Declaración de Helsinki
para incluir a participantes que no pueden dar su consentimiento?* El enrutado reparte las seis
plazas entre las dos normas, y la respuesta contrasta la E6(R3), que habla del representante
legalmente aceptable que actúa en el mejor interés del participante y del asentimiento del menor, con
Helsinki, que habla del representante legalmente autorizado y de tener en cuenta las preferencias y
valores expresados por el participante. Cada postura con su cita, sin fundirlas en una sola
afirmación.

**Cuarta pregunta:** *¿Qué fármaco GLP‑1 es mejor para perder peso?* Es consejo clínico, no una
cuestión normativa. La mejor puntuación queda alrededor de 0,64, por debajo de 0,69, y la puerta la
rechaza con el texto fijo. **El modelo de lenguaje nunca vio la pregunta.** Si en directo respondiera
en lugar de rechazar, la explicación honesta es que es la consulta más ajustada de la calibración y
que su distribución está en el cuaderno.

Completo la demostración en el cuaderno con una traza nodo a nodo de una pregunta, en la que se ve
qué escribe cada nodo en el estado del grafo.

## VIII. Cómo evalué

La evaluación tiene cuatro capas, cada una diseñada para responder a una debilidad de la anterior.

### Capa 1: comprobar la recuperación antes de conectar el modelo

El enunciado pide verificar la colección antes de conectar el agente, y lo convertí en la
calibración del umbral. Usé **seis preguntas del dominio**, cada una en inglés y en español, y **seis
preguntas ajenas**: qué fármaco GLP‑1 es mejor para adelgazar, la receta de la paella, un esquema de
almacén de datos, la capital de Bulgaria, cómo funciona la atención en los transformers y el ganador
de la Champions League. Para cada una registré la mejor puntuación de relevancia entre los tres
primeros resultados.

Las preguntas del dominio puntuaron entre 0,78 y 0,88 en inglés y entre 0,75 y 0,82 en español; las
ajenas, entre 0,52 y 0,63. Los grupos no se solapan, y fijé el umbral en **el punto medio del hueco**:
0,6885. El umbral se guarda junto al nombre del modelo de embeddings, porque las puntuaciones coseno
de Gemini se concentran en una banda estrecha y un umbral fijado a priori no tendría sentido; si
cambia el modelo o el corpus, hay que recalibrar. Esta capa también respondió a una pregunta sobre el
idioma: las consultas en español encuentran los mismos pasajes, con unas cuatro centésimas menos de
puntuación.

### Capa 2: un conjunto de referencia bilingüe

El conjunto de referencia, o *golden set*, tiene **25 preguntas**, cada una en inglés y en español, lo
que da **50 ejecuciones**:

- 19 preguntas del dominio, cada una anotada con el documento y la sección que la responden; dos de
  ellas son multifuente y exigen recuperar ambos documentos y una sección correcta de cada uno;
- 4 preguntas fuera de dominio, que deben rechazarse;
- 2 preguntas sobre documentos que **no** están indexados, la 21 CFR Part 50 estadounidense y el
  Reglamento europeo de ensayos clínicos 536/2014, que parecen del dominio, superan la puerta y deben
  responderse con un «no está en mi base de conocimiento» honesto.

Las preguntas se redactaron a partir del texto indexado y verificado, con asistencia de herramientas
de IA, y las revisé como experto; una prueba automática comprueba que cada documento y sección de
referencia existe realmente en el texto indexado. Una regla que me impuse: nunca relajar una palabra
clave para subir una puntuación, solo para aceptar una formulación correcta, como la grafía británica
o la traducción española de un término.

Las métricas son: tasa de acierto de documento y de sección entre los seis recuperados, por idioma;
precisión de rechazo en las preguntas fuera de dominio; tasa de rechazos indebidos en las del
dominio; cobertura de palabras clave en la respuesta, con variantes y coincidencia de palabra
completa; y honestidad en las preguntas sobre documentos no indexados, detectada con expresiones de
«no encontrado» en ambos idiomas.

### Capa 3: un juez con referencias

La cobertura de palabras clave es una aproximación a la corrección. Para medir corrección añadí a cada
pregunta del dominio una **respuesta de referencia** y un juez automático: un modelo de lenguaje que
compara cada respuesta con su referencia y devuelve *correcta*, *parcialmente correcta* o
*incorrecta*, con la lista de lo que falta y de los errores, en un formato JSON validado. Puntúo 1, 0,5
y 0. El juez es de referencia, no de contexto: comprueba lo que comprobaría un CRA, si el contenido
normativo es correcto y completo.

El juez previsto era `gemini-3.5-flash`, mayor que el modelo que responde, pero el plan gratuito lo
limita a veinte peticiones diarias por proyecto. En lugar de mezclar jueces, califiqué los cuatro
conjuntos de respuestas con `gemini-3.5-flash-lite`, el mismo modelo que responde, y **medí el sesgo**:
ambos jueces calificaron las mismas 38 respuestas de la versión 3, con un **78,9 % de acuerdo exacto**,
y el juez grande resultó más estricto, con una media de 0,697 frente a 0,776. Todas las salidas se
etiquetan con el modelo juez para que nunca se mezclen.

### Capa 4: un conjunto reservado

El riesgo de todo lo anterior es evidente: diseñé las correcciones leyendo las respuestas del conjunto
de referencia. Para comprobar si generalizan, cuando la versión 4 quedó cerrada redacté **12 preguntas
nuevas**, de nuevo en los dos idiomas, sobre temas que el conjunto de referencia no toca:
desenmascaramiento, comparadores activos y placebo, acontecimientos posteriores al estudio, composición
del comité de ética, cualificación del investigador, monitorización, desviaciones del protocolo,
publicación de resultados, biobancos y compensación por daños, además de una pregunta de dosificación
clínica que debe rechazarse y otra sobre la guía ICH E9(R1), que no está indexada. Las ejecuté **una sola
vez por configuración** y no cambié nada después. Una prueba automática comprueba que no repiten
ninguna pregunta del conjunto de referencia.

## IX. Qué salió

La comparación enfrenta la configuración base (prompt v3, sin expansión ni enrutado) con la final
(prompt v4, expansión a la sección y enrutado por documento), con las **mismas preguntas y la misma
puntuación**.

### Conjunto de referencia (50 ejecuciones)

| Métrica | v3 base | v4 + expansión + enrutado |
|---|---|---|
| Cobertura de palabras clave | 0,815 | **0,974** |
| Acierto de documento en el top‑6 (EN / ES) | 1,0 / 1,0 | 1,0 / 1,0 |
| Acierto de sección en el top‑6 (EN / ES) | 0,947 / 1,0 | 0,947 / 0,947 |
| Fuera de dominio rechazado (EN / ES) | 1,0 / 1,0 | 1,0 / 1,0 |
| Preguntas del dominio rechazadas por error | 0 | 0 |
| Honestidad ante documentos no indexados | 1,0 | 1,0 |

### Corrección según el juez

| Conjunto | v3 base | v4 + correcciones |
|---|---|---|
| Referencia, 38 respuestas del dominio | 0,776 (23 / 13 / 2) | **0,947** (35 / 2 / 1) |
| Reservado, 20 respuestas del dominio | 0,950 (18 / 2 / 0) | **1,000** (20 / 0 / 0) |
| Reservado: palabras clave · recuperación · rechazos · honestidad | 0,925 · 1,0 · 1,0 · 1,0 | 1,0 · 1,0 · 1,0 · 1,0 |

Entre paréntesis, respuestas correctas, parcialmente correctas e incorrectas.

### Lectura de los resultados

La recuperación ya era perfecta a nivel de documento con la configuración base, y lo siguió siendo. La
mejora está en **lo que llega al modelo y en cómo lo usa**: la corrección juzgada sube 17 puntos en el
conjunto de referencia y las respuestas parcialmente correctas caen de 13 a 2. Las listas completas
explican buena parte de la subida: la definición de «grave» pasó de dos a cinco criterios y los
elementos del consentimiento, de cuatro a veintidós.

En el conjunto reservado la mejora es menor, de 0,95 a 1,00, y la razón es interpretable: sus
preguntas se responden con una sola sección, donde el corte de listas apenas mordía. Lo relevante es
que **no hubo regresión** en preguntas que no influyeron en el diseño.

La puerta se comportó como se esperaba en los tres conjuntos: ninguna pregunta del dominio rechazada,
todas las ajenas rechazadas. Y las preguntas sobre documentos no indexados superaron la puerta, como
era previsible porque hablan de consentimiento y de notificación, pero el modelo respondió con
honestidad que no estaban en su base: es el comportamiento que la regla de insuficiencia existe para
producir, y es la razón por la que la puerta y el prompt son defensas complementarias.

### Los fallos que quedan

Informo de los fallos restantes en lugar de ajustar el sistema hasta ocultarlos.

**Preguntas de varios saltos.** «Del investigador a la autoridad reguladora, ¿quién notifica a quién y en
qué plazos?» requiere encadenar la E6(R3) §2.7.2 (el investigador notifica al promotor de inmediato), la
§3.13.2 (el promotor notifica a las autoridades conforme a la E2A) y la E2A (siete y quince días). La
versión 4 ya no la rechaza y responde paso a paso, pero **una sola pasada de recuperación no trae todos
los eslabones**: la cobertura de palabras clave es 0,67 en inglés y 0,33 en español. El juez calificó la
inglesa como correcta y la española como incorrecta, porque omite el paso del investigador al promotor.
Es la única respuesta incorrecta de la versión final. La solución natural es descomponer la pregunta y
recuperar por eslabón.

**El coste del enrutado.** En la pregunta que compara la E6(R3) y Helsinki, las plazas filtradas para la
E6(R3) eligen §2.8.1, §2.8.13 y el glosario en lugar del principio 2.1, en ambos idiomas. El acierto de
sección agregado bajó de 1,0 a 0,947 en español y se mantuvo en 0,947 en inglés solo porque el ítem de
varios saltos ganó su sección a la vez. La respuesta española sigue citando el principio 2.1, porque el
agente recupera con la pregunta reescrita en inglés y no con la española que puntúa el arnés; la inglesa
fue juzgada parcialmente correcta por omitir el mejor interés y el asentimiento.

## X. Qué significa y qué no

### Lo que creo que el proyecto muestra

Respecto a la **primera pregunta**, un sistema RAG construido con modelos ligeros y gratuitos puede
responder con citas a nivel de documento, sección y página, con una corrección juzgada alta. La clave no
es el tamaño del modelo, sino la calidad de lo que se le entrega y la disciplina del formato de cita.

Respecto a la **segunda**, una puerta de relevancia calibrada separó perfectamente el dominio de lo ajeno
en los tres conjuntos, y lo hizo antes de la generación, sin depender de que el modelo obedezca. Pero hay
que decir dos cosas con la misma claridad: el margen es estrecho, del orden de seis centésimas a cada
lado del umbral en la calibración, y la puerta no basta por sí sola, porque las preguntas sobre normas no
indexadas la superan y dependen del prompt para responder con honestidad.

Respecto a la **tercera**, la lección más clara es que **fallos que parecen de redacción eran fallos de
recuperación**. Las listas incompletas no se arreglan pidiendo listas completas, sino entregando la
sección entera. Y las restricciones que no admiten excepción, el idioma y el rechazo de lo ajeno,
funcionan mejor en código que en instrucciones.

Respecto a la **cuarta**, las mejoras se mantuvieron en preguntas que no vi al diseñarlas, aunque con un
conjunto reservado pequeño.

### Amenazas a la validez

Un artículo honesto tiene que declarar lo que limita estas conclusiones.

- **Validez interna: el autor como diseñador y evaluador.** Diseñé las correcciones leyendo el conjunto
  de referencia. El conjunto reservado mitiga este sesgo, pero es pequeño.
- **Autoría del conjunto de referencia.** Las preguntas y las referencias se redactaron con asistencia
  de IA a partir del texto verificado y las revisé yo. Una anotación independiente por otro experto
  reforzaría la validez.
- **Sesgo del juez.** El juez es el mismo modelo que responde, lo que invita a la autopreferencia que
  describe la literatura. Lo medí parcialmente: 78,9 % de acuerdo con un juez mayor y más estricto. No
  calculé un estadístico de acuerdo corregido por azar, como la kappa de Cohen, ni lo comparé con
  calificaciones humanas. La comparación entre versiones es justa porque usa el mismo juez, pero las
  cifras absolutas son optimistas.
- **Validez de constructo.** La cobertura de palabras clave aproxima la corrección, y el juez mide
  corrección frente a una referencia, no **fidelidad** frente a los pasajes recuperados. Una respuesta
  podría ser correcta por conocimiento previo del modelo sin estar respaldada por su cita. No observé
  citas inventadas, pero no lo medí de forma sistemática.
- **Atribución de la mejora.** La configuración final cambia a la vez el prompt, la expansión y el
  enrutado, porque los fallos que corrigen aparecieron juntos. No hay ablación que aísle cada efecto.
- **Solapamiento en la calibración.** La pregunta sobre el fármaco GLP‑1 para adelgazar forma parte de
  la calibración del umbral y aparece también entre las preguntas fuera de dominio del conjunto de
  referencia y en la demostración. Su rechazo no es, por tanto, una prueba independiente; la del
  conjunto reservado, sobre la dosis de semaglutida, sí lo es.
- **Validez estadística.** Con 38 y 20 respuestas juzgadas, las diferencias grandes son informativas,
  pero no calculé intervalos de confianza ni contrastes de significación.
- **Validez externa.** Tres documentos, un dominio, una familia de modelos y un modelo de embeddings. El
  umbral es específico de esa combinación.

## XI. Límites y siguientes pasos

Lo que el sistema no hace hoy: conoce solo tres documentos, de modo que la normativa europea, los módulos
de farmacovigilancia de la Agencia Europea del Medicamento o la regulación estadounidense se rechazan o
se responden únicamente con lo que dice la E6(R3), y lo advierte. Una pregunta de varios saltos todavía
puede perder un eslabón. El umbral debe recalibrarse si cambia el corpus o el modelo. La memoria vive en
el proceso, así que un reinicio olvida las conversaciones, y en la aplicación pública los hilos se
comparten en un mismo proceso. Y el plan gratuito limita los embeddings diarios.

Los siguientes pasos, por orden de valor:

1. **Descomposición de consultas**: dividir las preguntas de varios saltos y recuperar por eslabón,
   en la línea de los métodos que intercalan recuperación y razonamiento.
2. **Ampliar el corpus** con el Módulo VI de las Buenas Prácticas de Farmacovigilancia de la Agencia
   Europea del Medicamento y el Reglamento europeo 536/2014. La ingesta es por documento e idempotente,
   pero exige recalibrar y ampliar la evaluación.
3. **Un juez de fidelidad** que compare cada afirmación con el pasaje que cita.
4. **Recuperación híbrida**, combinando vectores con búsqueda léxica tipo BM25, para números de sección y
   acrónimos exactos.
5. **Un nodo de control de entrada** (inyección de instrucciones, datos personales) y memoria persistente
   con caducidad.

## XII. Cierre

Resumo en tres frases. Un asistente experto en un dominio regulado no se distingue por el modelo que usa,
sino por lo que le impide equivocarse: una puerta calibrada antes de generar, pasajes completos y citas
obligatorias. Los fallos que parecen de redacción suelen ser de recuperación, y se corrigen ahí. Y la
fiabilidad se demuestra con una evaluación que incluye preguntas que el autor no vio y que informa de lo
que sigue fallando.

Gracias. Quedo a su disposición para las preguntas.

## Anexo. Del discurso al artículo

### Títulos propuestos

- **Español**: *Rechazo calibrado y expansión a la sección en un asistente RAG de cumplimiento
  normativo para la investigación clínica: diseño y evaluación con conjunto reservado.*
- **Inglés**: *Calibrated Abstention and Section-Level Context Expansion in a Retrieval-Augmented
  Assistant for Clinical Research Compliance: Design and Held-Out Evaluation.*

### Resumen (borrador, español)

Los modelos de lenguaje generan respuestas plausibles pero no siempre verificables, un riesgo crítico en
dominios regulados como la investigación clínica. Presentamos un asistente de generación aumentada con
recuperación sobre tres normas (ICH E6(R3), ICH E2A y la Declaración de Helsinki de 2024; 801
fragmentos) que cita cada afirmación a nivel de documento, sección y página, responde en español o en
inglés y se abstiene cuando su base no cubre la pregunta. El sistema combina una puerta de relevancia
calibrada empíricamente y aplicada antes de la generación, enrutado por documento, selección por
relevancia marginal máxima y expansión de cada fragmento a su sección normativa, orquestados en un grafo
de estados explícito con memoria conversacional. Lo evaluamos con un conjunto bilingüe de 25 preguntas
(50 ejecuciones), un juez basado en referencias y un conjunto reservado de 12 preguntas redactado tras
congelar el sistema. Frente a una configuración base, la corrección juzgada pasó de 0,78 a 0,95 en el
conjunto de referencia y de 0,95 a 1,00 en el reservado, sin rechazos indebidos y con todas las
preguntas ajenas rechazadas. El análisis de errores muestra que los fallos aparentemente de redacción
(listas incompletas) se originaban en la recuperación, y que las preguntas de varios saltos siguen siendo
la principal limitación. Discutimos el sesgo de autopreferencia del juez (78,9 % de acuerdo con un juez
mayor y más estricto) y otras amenazas a la validez.

### Abstract (draft, English)

Large language models produce fluent but not always verifiable answers, a critical risk in regulated
domains such as clinical research. We present a retrieval-augmented assistant over three regulatory
texts (ICH E6(R3), ICH E2A and the 2024 Declaration of Helsinki; 801 chunks) that cites every claim at
document, section and page level, answers in Spanish or English, and abstains when its knowledge base
does not cover the question. The system combines an empirically calibrated relevance gate applied before
generation, document routing, maximal marginal relevance selection and section-level context expansion,
orchestrated as an explicit state graph with conversational memory. We evaluate it with a bilingual
golden set of 25 questions (50 runs), a reference-based LLM judge, and a 12-question held-out set
written after the system was frozen. Compared with a baseline configuration, judged correctness rose
from 0.78 to 0.95 on the golden set and from 0.95 to 1.00 on the held-out set, with no false refusals
and all out-of-domain questions refused. Error analysis shows that apparent generation failures
(truncated lists) originated in retrieval, and that multi-hop questions remain the main limitation. We
discuss judge self-preference (78.9 % exact agreement with a larger, stricter judge) and other threats to
validity.

### Palabras clave

Generación aumentada con recuperación; abstención; investigación clínica; Buenas Prácticas Clínicas;
cumplimiento normativo; evaluación de modelos de lenguaje; LLM como juez.

### Contribuciones que defendería el artículo

1. Una arquitectura RAG para cumplimiento normativo con **abstención previa a la generación** mediante un
   umbral calibrado sobre la distribución de puntuaciones de consultas del dominio y ajenas.
2. La **expansión a la sección normativa** como corrección de la truncación de listas, con su
   justificación cuantitativa (presupuesto de 4.000 caracteres; 393 de 399 secciones).
3. Un **protocolo de evaluación en cuatro capas** (calibración, conjunto de referencia bilingüe, juez con
   referencias y conjunto reservado) aplicable con recursos gratuitos.
4. Un **análisis de errores** que separa fallos de recuperación y de generación, con el principio de
   diseño «restricciones duras en código, criterio en el prompt».
5. Un **artefacto reproducible**: código abierto, caché de embeddings versionada, respuestas y veredictos
   guardados.

### Estructura propuesta

| Sección del artículo | Contenido | Partes del discurso |
|---|---|---|
| 1. Introducción | Problema, trazabilidad, alucinación, preguntas de investigación | II, III |
| 2. Trabajo relacionado | RAG, abstención, MMR, evaluación de RAG, LLM como juez, recuperación multisalto | (por redactar) |
| 3. Corpus | Fuentes, preprocesado, troceado, procedencia | IV |
| 4. Sistema | Grafo, reescritura e idioma, recuperación en cuatro etapas, memoria, ingeniería | V |
| 5. Diseño de instrucciones | Versiones v1–v4 y observaciones | VI |
| 6. Evaluación | Calibración, conjunto de referencia, juez, conjunto reservado, métricas | VIII |
| 7. Resultados | Tablas, ejemplos cualitativos, análisis de errores | VII, IX |
| 8. Discusión | Respuesta a las preguntas, amenazas a la validez | X |
| 9. Limitaciones y trabajo futuro | | XI |
| 10. Conclusiones | | XII |

### Tablas y figuras disponibles

| Elemento | Archivo de origen |
|---|---|
| Diagrama del grafo | `docs/img/graph.png` |
| Distribución de puntuaciones y umbral | `docs/img/calibration.png`; datos en `data/kb/calibration.json` |
| Captura de la aplicación | `docs/img/app.png` |
| Resultados por pregunta, configuración final | `docs/evaluation.md`, `data/eval/answers.jsonl` |
| Resultados por pregunta, configuración base | `docs/evaluation_baseline_v3.md`, `data/eval/answers_baseline_v3.jsonl` |
| Conjunto reservado | `docs/heldout_evaluation.md`, `docs/heldout_baseline_v3.md`, `data/eval/heldout*.jsonl` |
| Veredictos del juez | `data/eval/*.judge-gemini-3.5-flash-lite.jsonl` y `.md`; comparación con el juez mayor en `*.judge-gemini-3.5-flash.jsonl` |
| Prompts completos | `src/compliance_assistant/prompts.py`; observaciones en `docs/prompt_iterations.md` |
| Registro de decisiones | `docs/decisions.md` |

### Trabajo pendiente antes de enviar

1. **Ablación**: evaluar el prompt v4 sin expansión ni enrutado para aislar su efecto
   (`scripts/03_evaluate.py --prompt-version v4 --no-expand --no-routing --with-answers`).
2. **Acuerdo entre jueces**: calcular la kappa de Cohen y calificar a mano una submuestra para medir el
   acuerdo humano‑juez.
3. **Incertidumbre**: intervalos de confianza por *bootstrap* para la corrección juzgada y un contraste
   pareado entre configuraciones.
4. **Fidelidad**: un juez de afirmación frente a pasaje citado sobre todas las respuestas.
5. **Calibración independiente**: separar las consultas de calibración de las de evaluación y de la demo.
6. **Ampliar el conjunto reservado** y, si es posible, que lo redacte o revise otro experto.
7. **Trabajo relacionado**: redactar la sección 2 con las referencias de abajo y otras recientes.

### Declaraciones

- **Disponibilidad**: código, caché de embeddings, conjuntos de evaluación, respuestas y veredictos en
  <https://github.com/dnarram/clinical-research-compliance-assistant>. Los documentos fuente no se
  redistribuyen; se descargan de sus editores y se verifican con SHA‑256.
- **Uso de IA**: el desarrollo contó con un asistente de programación basado en IA, y el conjunto de
  referencia y las respuestas de referencia se redactaron con asistencia de IA a partir del texto
  verificado y fueron revisados por el autor. Conviene declararlo según la política de la revista o del
  congreso elegido.
- **Destinos posibles**: congresos y revistas de informática médica o biomédica, por ejemplo *Medical
  Informatics Europe* (MIE) o el *Journal of Biomedical Informatics*. Conviene revisar su alcance y sus
  normas antes de decidir.

### Referencias

Verificar DOI, páginas y ediciones antes del envío.

- Carbonell, J. y Goldstein, J. (1998). The use of MMR, diversity-based reranking for reordering
  documents and producing summaries. *Proceedings of SIGIR '98*.
- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological
  Measurement*, 20(1).
- Es, S., James, J., Espinosa-Anke, L. y Schockaert, S. (2024). RAGAS: Automated evaluation of
  retrieval augmented generation. *Proceedings of EACL 2024: System Demonstrations*.
- Gao, Y. et al. (2023). Retrieval-augmented generation for large language models: A survey.
  *arXiv:2312.10997*.
- International Council for Harmonisation (1994). *ICH E2A: Clinical Safety Data Management:
  Definitions and Standards for Expedited Reporting*.
- International Council for Harmonisation (2025). *ICH E6(R3): Guideline for Good Clinical Practice*,
  Step 4, 6 de enero de 2025.
- Ji, Z. et al. (2023). Survey of hallucination in natural language generation. *ACM Computing
  Surveys*, 55(12).
- Lewis, P. et al. (2020). Retrieval-augmented generation for knowledge-intensive NLP tasks.
  *Advances in Neural Information Processing Systems 33*.
- Liu, N. F. et al. (2024). Lost in the middle: How language models use long contexts. *Transactions
  of the Association for Computational Linguistics*, 12.
- Panickssery, A., Bowman, S. R. y Feng, S. (2024). LLM evaluators recognize and favor their own
  generations. *Advances in Neural Information Processing Systems 37*.
- Robertson, S. y Zaragoza, H. (2009). The probabilistic relevance framework: BM25 and beyond.
  *Foundations and Trends in Information Retrieval*, 3(4).
- Trivedi, H. et al. (2023). Interleaving retrieval with chain-of-thought reasoning for
  knowledge-intensive multi-step questions. *Proceedings of ACL 2023*.
- World Medical Association (2024). *Declaration of Helsinki: Ethical Principles for Medical Research
  Involving Human Participants*, 75.ª Asamblea General, Helsinki, octubre de 2024.
- Zheng, L. et al. (2023). Judging LLM-as-a-judge with MT-Bench and Chatbot Arena. *Advances in
  Neural Information Processing Systems 36, Datasets and Benchmarks Track*.
