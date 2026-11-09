# Un asistente de cumplimiento normativo para la investigación clínica con recuperación aumentada, rechazo calibrado y evaluación con conjunto reservado

**Discurso completo de la presentación y base para un artículo académico.** Texto íntegro, en
prosa continua, de lo que la exposición oral cubre, calibrado para leerse en unos diez minutos a
ritmo tranquilo (partes I–XII, sin contar esta nota ni el anexo). Las siete diapositivas lo
acompañan; el guion con tiempos está en `docs/notas_orador_es.md`. Cada cifra procede de un archivo del repositorio, indicado en el
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

Leído en voz alta a ritmo tranquilo, el cuerpo del discurso dura unos diez minutos. Para la
versión de ocho, se omiten las partes III y X, cuyo contenido está pensado para el artículo.

## I. Apertura

Buenos días. Presento un asistente de pregunta y respuesta para el cumplimiento normativo en
investigación clínica, sobre tres normas: la ICH E6(R3) de Buenas Prácticas Clínicas, la ICH E2A de
notificación expeditiva de seguridad y la Declaración de Helsinki de 2024. Responde en español o en
inglés, cita literalmente documento, sección y página, recuerda la conversación y rechaza lo que
sus fuentes no cubren. Es un sistema RAG con Gemini, ChromaDB y LangGraph, y quiero contar tres
ideas: la decisión de no responder se toma antes de que intervenga el modelo; muchos fallos que
parecen de redacción son de recuperación; y la fiabilidad se demuestra con preguntas que el autor
no vio.

## II. El problema

Viernes, 17:50. Un monitor recibe el aviso de un acontecimiento adverso grave. ¿Es un SUSAR?
¿Quién lo notifica, a quién, en qué plazo? La respuesta está repartida: los plazos en la E2A, las
obligaciones de investigador y promotor en la E6(R3), los principios éticos en Helsinki. Noventa
páginas en inglés. Y en este ámbito no basta con responder: hay que demostrar de dónde sale. En una
inspección no vale «creo que eran quince días»; vale «E2A, sección III.B, página 7». La
trazabilidad es el requisito.

Un asistente generalista no sirve: un modelo de lenguaje genera texto plausible y a veces falso
con aplomo, y un plazo inventado es el peor fallo porque parece correcto. RAG ataca eso: buscar
primero en documentos cerrados y responder solo con lo encontrado. Elegí este dominio porque cinco
años de soporte a software de ensayos clínicos y la certificación ICH GCP me permiten juzgar si una
respuesta es correcta; sin eso, evaluar un asistente experto se reduce a comprobar que suena bien.

## III. Objetivos y preguntas de investigación

El objetivo fue cumplir el enunciado y demostrar con datos que el sistema es fiable. Cuatro
preguntas: ¿puede un RAG con modelos ligeros citar a nivel de sección y página? ¿Separa un umbral
calibrado, aplicado antes de generar, lo que la base cubre de lo que no? ¿Los fallos se corrigen
mejor en el prompt o en la recuperación? ¿Y se mantienen las mejoras en preguntas nuevas?

## IV. El corpus

Tres documentos públicos, 801 fragmentos de 500 caracteres, cada uno con documento, sección y
página. El preprocesado condiciona las citas: elimino cabeceras repetidas, reúno palabras partidas
y detecto el número de sección. Helsinki se indexó desde la web porque el PDF estropea los números
de párrafo: la fuente se elige por la calidad del texto. Los documentos se descargan de los
editores y se verifican con su huella SHA‑256.

## V. La arquitectura

Descarté el agente que decide si busca: el enunciado exige usar la base en cada consulta y una
topología fija se prueba con facilidad. El agente es un grafo explícito de cuatro nodos: reescribir,
recuperar, generar, rechazar. El modelo nunca decide si se consulta la base.

La reescritura convierte la pregunta, con el historial, en una pregunta autónoma en inglés: así
resuelve «¿y para las demás?» y salva el idioma del corpus. El idioma de la respuesta se impone con
una línea determinista.

La recuperación tiene cuatro etapas. Primero la puerta: si la mejor puntuación no alcanza 0,69,
la pregunta va a un rechazo con plantilla sin llamar al modelo; lo que no llega al modelo no se
puede inventar. Segundo, el enrutado: si la pregunta nombra documentos, las seis plazas se reparten
entre ellos; la puerta usa las puntuaciones sin filtrar, así que el enrutado nunca convierte un
rechazo en respuesta. Tercero, diversidad con relevancia marginal máxima. Cuarto, la etapa más
útil: cada fragmento se amplía a su sección completa si no supera los 4.000 caracteres. Nació de un
fallo real: la definición de «grave» tiene cinco criterios, el fragmento traía dos y el modelo la
daba por completa. No se arregla pidiéndoselo, porque no puede completar lo que no ve; se arregla
entregándole la sección entera.

La memoria es un checkpointer por hilo: al modelo llegan los diez últimos mensajes y los pasajes
viven fuera del historial. Y una decisión de ingeniería lo sostiene todo: el plan gratuito permite
mil textos embebidos al día y el corpus consume ochocientos, así que la fuente de verdad es una
caché de embeddings versionada; nada se re‑embebe y Chroma se reconstruye en segundos sin
llamadas. Todo con 77 pruebas sin red y desplegado en Streamlit Cloud.

## VI. El prompt de sistema

Cuatro versiones documentadas. La primera, el prompt de clase, respondía bien pero sin citas. La
tercera añadió citas por frase, atribución cuando las normas difieren y la política de idioma; al
leer todas las respuestas de la evaluación aparecieron tres fallos: una pregunta de varios pasos
rechazada entera, su rechazo en español escrito en inglés y listas cortadas dadas por completas. La
cuarta gradúa el rechazo, construye las cadenas paso a paso y exige listas completas. El principio:
las restricciones duras van en el código; el criterio, en el prompt.

## VII. La demostración

Cuatro preguntas. Primera, en inglés, el plazo de una reacción mortal inesperada: cita literal de
la E2A, siete días y ocho más para el informe completo, con sección y página en el panel de
fuentes. Segunda, en español y en el mismo hilo, «¿y para las demás?»: la reescritura resuelve la
referencia y la respuesta vuelve en español con la norma citada en inglés: quince días. Tercera, qué
exigen la E6(R3) y Helsinki para incluir a quien no puede consentir: dos documentos nombrados, dos
posturas contrastadas, cada una con su cita. Cuarta, qué fármaco GLP‑1 es mejor para adelgazar: la
puerta la rechaza con 0,64 y el modelo nunca la ve.

## VIII. Cómo evalué

Cuatro capas. Primera, la calibración antes de conectar el modelo: seis preguntas del dominio en
dos idiomas y seis ajenas; puntuaron entre 0,75 y 0,88 frente a 0,52 y 0,63, y el umbral es el
punto medio del hueco. Segunda, un golden set de 25 preguntas en ambos idiomas, 50 ejecuciones,
con preguntas del dominio, ajenas y sobre normas no indexadas; redactadas con asistencia de IA a
partir del texto verificado y revisadas por mí. Tercera, un juez: un modelo compara cada respuesta
con una referencia y la califica. El juez grande solo permite veinte peticiones al día, así que usé
el modelo ligero y medí el sesgo: 79 % de acuerdo en 38 respuestas, con el grande más estricto.
Cuarta, un conjunto reservado de doce preguntas nuevas, escritas tras congelar el sistema y
ejecutadas una sola vez.

## IX. Qué salió

Con las mismas preguntas y la misma puntuación, la corrección juzgada sube de 0,78 a 0,95 en el
golden set y de 0,95 a 1,00 en el reservado; la cobertura de palabras clave, de 0,82 a 0,97. El
acierto de documento se mantuvo en 1,0, ninguna pregunta del dominio fue rechazada y todas las
ajenas sí. El reservado mejora menos porque sus preguntas caben en una sola sección; lo relevante
es que no hubo regresión. Quedan dos fallos que informo en lugar de ajustar: la cadena de varios
saltos aún pierde un eslabón, la única respuesta incorrecta de la versión final, y el enrutado
elige a veces secciones generales en lugar del principio exacto.

## X. Qué significa y qué no

Un RAG con modelos ligeros puede citar con precisión; la clave es lo que se le entrega, no el
tamaño del modelo. La puerta separó el dominio de lo ajeno, pero el margen es de centésimas y no
basta sola: las normas no indexadas la superan y dependen del prompt. Y las limitaciones cuentan:
diseñé y evalué yo mismo, el juez es el modelo que responde, se mide corrección y no fidelidad, y
con 38 y 20 respuestas no hay intervalos de confianza.

## XI. Límites y siguientes pasos

Tres documentos, un posible salto perdido en preguntas encadenadas, un umbral que hay que
recalibrar si cambia el corpus y una memoria que vive en el proceso. Siguientes pasos, por valor:
descomponer las preguntas de varios saltos, añadir la farmacovigilancia europea y el Reglamento
536/2014, un juez de fidelidad, recuperación híbrida y memoria persistente.

## XII. Cierre

Un asistente experto en un dominio regulado no se distingue por el modelo que usa, sino por lo que
le impide equivocarse: una puerta calibrada antes de generar, pasajes completos y citas
obligatorias. Los fallos que parecen de redacción suelen ser de recuperación. Y la fiabilidad se
demuestra con preguntas que el autor no vio y con un informe honesto de lo que sigue fallando.
Gracias.

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
