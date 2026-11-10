"""Spanish edition of the notebook: same code cells and the same executed outputs as
notebooks/compliance_assistant.ipynb, with every Markdown cell translated.

    uv run python notebooks/build_notebook_es.py            # writes notebooks/compliance_assistant_es.ipynb

The English notebook stays the executed source of truth (it is what nbconvert runs). This
script copies it and swaps the prose, so the Spanish edition never drifts from the real
outputs. Each translation is keyed by the first line of the English cell; if the English
notebook gains, loses or renames a section, the script fails loudly instead of leaving a
cell untranslated.
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat

HERE = Path(__file__).resolve().parent
SRC = HERE / "compliance_assistant.ipynb"
OUT = HERE / "compliance_assistant_es.ipynb"

# first line of the English Markdown cell -> Spanish cell
ES: dict[str, str] = {}


def tr(first_line_en: str, text_es: str) -> None:
    ES[first_line_en] = text_es.strip("\n")


tr(
    "# Clinical Research Compliance Assistant",
    r"""
# Asistente de cumplimiento en investigación clínica
### Un agente experto en ICH GCP, notificación expeditiva de seguridad y la Declaración de Helsinki — Gemini + ChromaDB + LangGraph

**Autor:** David Naranjo Ramírez · Máster en Data Science & IA, Evolve Academy · Módulo de IA Generativa, proyecto final

> **Edición en español.** Este cuaderno es la versión en español de `compliance_assistant.ipynb`: el texto explicativo está traducido y **el código y sus salidas son exactamente los mismos** que los del cuaderno original ejecutado (no se ha vuelto a ejecutar nada, así que las cifras coinciden). El código, los mensajes que imprime y las normas citadas están en inglés, que es el idioma del corpus y del proyecto; el asistente responde en el idioma de cada pregunta, y en las secciones 6.1, 7, 8 y 10 hay preguntas y respuestas en español.

**Dominio.** Las preguntas de cumplimiento normativo en ensayos clínicos se responden a partir de tres textos de referencia: **ICH E6(R3)** *Good Clinical Practice* (2025), **ICH E2A** *Clinical Safety Data Management: definitions and standards for expedited reporting* y la **Declaración de Helsinki** de la AMM (2024). El dominio no es casual: trabajé cinco años dando soporte a software de ensayos clínicos (Medidata Rave, plataformas de Pfizer y Novo Nordisk) y tengo la certificación ICH GCP E6(R2), así que puedo juzgar si una respuesta es correcta, que es lo que un asistente experto necesita de su autor.

**Qué muestra el cuaderno** (una sección por criterio de la rúbrica):

| # | Sección | Rúbrica |
|---|---|---|
| 1 | Preparación (local / Colab, higiene de la clave de API) | Requisitos |
| 2 | Base de conocimiento: fuentes, preprocesado, troceado | Base de conocimiento |
| 3 | Embeddings de Gemini + ChromaDB, construcción idempotente | Base de conocimiento |
| 4 | Comprobación de la recuperación **antes** del agente (EN/ES, fuera de dominio, umbral calibrado) | RAG |
| 5 | Prompt de sistema v4 y su justificación (v1 frente a v4, y la pregunta de varios pasos que rechazaba la v3) | Ingeniería de prompts |
| 6 | El agente LangGraph y su traza | Agente LangGraph |
| 7 | Memoria conversacional: preguntas referenciales, aislamiento de hilos | Memoria |
| 8 | Conversaciones de ejemplo documentadas | ≥ 5 ejemplos |
| 9 | Evaluación: golden set bilingüe revisado, juez LLM, conjunto held‑out | Calidad |
| 10 | Celda de chat interactiva | Celda de chat |
| 11 | Limitaciones y siguientes pasos | Documentación |

**Resultados de un vistazo** (todo se recalcula o se muestra en las secciones siguientes; mismo golden set y misma puntuación en ambas columnas):

| | Línea base (prompt v3) | **Final (prompt v4 + expansión a la sección + enrutado por documento)** |
|---|---|---|
| Cobertura de palabras clave de la respuesta, golden set (25 preguntas × EN/ES = 50 ejecuciones) | 0,815 | **0,974** |
| Correcto según el juez, golden set (38 respuestas del dominio, juez LLM) | 0,776 | **0,947** |
| Correcto según el juez, conjunto held‑out (12 preguntas nuevas, ejecutado una sola vez tras congelar el sistema) | 0,950 | **1,000** |
| Preguntas fuera de dominio rechazadas / preguntas del dominio rechazadas por error | 100 % / 0 | 100 % / 0 |

Base de conocimiento: 3 documentos, 801 fragmentos, umbral de rechazo 0,6885 calibrado con datos (§4). Un fallo se informa en lugar de ajustarlo: la pregunta de varios saltos sobre la cadena de notificación aún pierde un eslabón (§9, §11). El mismo agente funciona como aplicación pública de Streamlit: <https://clinical-research-compliance-assistant-eaksdytvqzbpuvthkakvrd.streamlit.app>.

**Cómo ejecutarlo.** En local: `uv sync --extra dev`, poner `GEMINI_API_KEY=...` en `.env` y lanzar `uv run jupyter lab notebooks/`. En Google Colab: ejecutar la celda de preparación (clona el repositorio y lo instala) y añadir `GEMINI_API_KEY` en *Secrets*. La caché de embeddings está en el repositorio, así que la base de conocimiento se reconstruye en segundos **sin** llamar a la API de embeddings; solo las preguntas del chat llaman a Gemini.
""",
)

tr(
    "## 1 · Setup",
    r"""
## 1 · Preparación

La clave de API se lee del entorno (`.env` en local, *Secrets* en Colab) y nunca se escribe en el código. La celda imprime su longitud como única comprobación. Una `GEMINI_API_KEY_BACKUP` opcional, de un segundo proyecto de Google Cloud, es una segunda cuota diaria: si en alguna salida aparece la línea `[llm] daily quota hit; switching to backup key`, es la conmutación automática de `agent.py` haciendo su trabajo, no un error.
""",
)

tr(
    "## 2 · Knowledge base",
    r"""
## 2 · Base de conocimiento

Tres documentos públicos, listados en `data/kb/sources.yaml` con su URL y su SHA‑256. **No se redistribuyen** en el repositorio (los textos de ICH y de la AMM se citan con atribución; véase `docs/sources.md`); la celda siguiente los descarga con `scripts/00_download_sources.py` si `data/kb/raw/` está vacío, verificando las huellas. Si solo quiere *usar* el asistente puede saltarse este paso: la caché de embeddings está en el repositorio.
""",
)

tr(
    "### 2.1 · Pre-processing: what the raw text looks like and what we keep",
    r"""
### 2.1 · Preprocesado: cómo es el texto en bruto y qué conservamos

Los PDF de ICH llevan una cabecera repetida («ICH E6(R3) Guideline») y un número de página en cada hoja, parten palabras con guion al final de línea y empiezan con un índice. `ingestion.clean_text` elimina las líneas que se repiten en ≥ 50 % de las páginas, las líneas que solo contienen un número de página y los puntos guía del índice, y vuelve a unir las palabras partidas. La Declaración de Helsinki se indexa desde la página web de la AMM porque la exportación a PDF pierde los números de párrafo y estropea las ligaduras. Cada fragmento lleva después `doc_id`, `section` («2.8.10» en ICH, «¶28» en Helsinki) y `page`, que es lo que hace posibles las citas.
""",
)

tr(
    "## 3 · Gemini embeddings + ChromaDB (idempotent build)",
    r"""
## 3 · Embeddings de Gemini + ChromaDB (construcción idempotente)

Decisión de diseño: la **caché de embeddings versionada** (`data/kb/embeddings/*.jsonl.gz`) es la fuente de verdad, no el directorio de Chroma. `manifest.json` registra, por documento, la huella del archivo, el modelo de embeddings, la dimensión y el troceado, de modo que un documento solo se vuelve a embeber cuando cambia alguno de esos datos. Chroma se reconstruye desde la caché con su `add(embeddings=…)` nativo, **sin llamadas a la API**, que es también como obtienen su colección la aplicación Streamlit y este cuaderno en una máquina nueva.

Los documentos se embeben con `task_type=RETRIEVAL_DOCUMENT` y las consultas con `RETRIEVAL_QUERY` (recuperación asimétrica). Primero `--dry-run`: contar los fragmentos y compararlos con la cuota del plan gratuito antes de gastarla.
""",
)

tr(
    "## 4 · Retrieval sanity check — before connecting the agent",
    r"""
## 4 · Comprobación de la recuperación — antes de conectar el agente

El enunciado pide verificar que la colección responde a consultas de prueba *antes* de conectar el LLM. Tres cosas que comprobar:

1. **Precisión**: ¿apunta el top‑3 a la sección correcta?
2. **Recuperación entre idiomas**: el corpus está en inglés y los usuarios también preguntan en español. La misma pregunta en ambos idiomas debería dar con los mismos pasajes (`gemini-embedding-2` es multilingüe; además, el agente reescribe en inglés toda pregunta que no esté en inglés antes de buscar).
3. **Fuera de dominio**: un asistente de cumplimiento debe *rechazar* las preguntas que no puede fundamentar. Las puntuaciones coseno de Gemini se concentran en una banda estrecha, así que el umbral de rechazo está **calibrado**, no supuesto: `scripts/02_sanity_retrieval.py --calibrate` registra la puntuación máxima de consultas de dominio y fuera de dominio y guarda el punto medio del hueco en `data/kb/calibration.json`.
""",
)

tr(
    "### 4.1 · Context expansion: why a 500-character chunk is not enough",
    r"""
### 4.1 · Expansión del contexto: por qué un fragmento de 500 caracteres no basta

La primera ejecución completa del golden set mostró respuestas construidas sobre media lista: la definición de *grave* de la ICH E2A volvía con dos de sus cinco criterios, porque la definición está a caballo entre dos fragmentos. La recuperación amplía ahora cada fragmento a su sección completa cuando la sección es corta (≤ 4.000 caracteres: un requisito numerado, un párrafo de Helsinki, los 22 elementos del consentimiento de E6(R3) §2.8.10) y a sus fragmentos vecinos en caso contrario. Los vecinos salen de la propia colección, sin llamadas a la API. Abajo: el fragmento que elige la recuperación y el pasaje que lee realmente el modelo.
""",
)

tr(
    "## 5 · System prompt — design and justification",
    r"""
## 5 · Prompt de sistema: diseño y justificación

El prompt pasó por cuatro versiones (`src/compliance_assistant/prompts.py`; historial en `docs/prompt_iterations.md`). La **v4** es la que está en uso. Sus cláusulas y por qué existe cada una:

| Cláusula | Por qué |
|---|---|
| Papel + público (CRA, coordinadores, gestores de datos, personal de farmacovigilancia) + lista explícita de los tres documentos | Fija el registro y permite al modelo decir qué *no* cubre |
| **Fundamentación**: responder solo a partir de los pasajes numerados; citar cada frase factual como `[n]` | La trazabilidad es el sentido del RAG en un entorno regulado; los números remiten al panel de fuentes |
| **Insuficiencia graduada**: responder la parte que cubren los pasajes y decir cuál no; solo cuando nada es relevante, decir que no está en la base de conocimiento (en el idioma del usuario) y enumerar lo que cubre; nunca inventar números de sección ni plazos | La rúbrica pregunta cómo se comporta el agente sin información. La v3 rechazó entera una pregunta de varios pasos (investigador → promotor → regulador) aunque cada paso estaba en los pasajes |
| **Respuestas de varios pasos**: combinar varios pasajes paso a paso, citando cada uno | Las cadenas de notificación abarcan E6(R3) y E2A |
| **Listas completas**: dar todos los elementos que contienen los pasajes o decir que la lista continúa | La v3 presentó 4 de los 22 elementos del consentimiento como si fueran todos |
| **Fuentes que difieren**: atribuir cada postura a su documento en lugar de fundirlas | E6(R3) y Helsinki se solapan (consentimiento, participantes vulnerables) pero no son idénticas |
| **Política de idioma**: responder en el idioma del usuario, citar la redacción normativa literalmente en inglés, no traducir SAE/SUSAR/IB/IMP | El corpus está en inglés y los usuarios son hispanohablantes; la cita literal conserva la precisión legal |
| **Alcance y tono**: información regulatoria, no asesoramiento legal ni médico; redirigir las peticiones fuera de tema | Responsabilidad y foco |
| **Formato**: primero la respuesta directa, después el detalle, sin resumen final | Respuestas más cortas y legibles en una interfaz de chat |

El LLM recibe además una línea determinista `Reply in English.` / `Responde en español.` en el mensaje del usuario: en las pruebas, la regla del prompt de sistema no bastó por sí sola (una pregunta en inglés volvió una vez en español).
""",
)

tr(
    "**The question the v3 baseline refused.** The golden-set run of the v3 baseline refused a multi-step question outright — \"who reports a serious adverse reaction to whom, and within which timelines\" — although the answer is spread over E6(R3) and E2A. The saved baseline answer (`data/eval/answers_baseline_v3.jsonl`, produced before the v4 changes) is shown first, then v3 and v4 run live on today's retrieval. The point to check: does the agent answer the parts the passages cover instead of giving up?",
    r"""
**La pregunta que rechazó la línea base v3.** En la ejecución del golden set, la línea base v3 rechazó por completo una pregunta de varios pasos —«quién notifica una reacción adversa grave a quién y en qué plazos»— aunque la respuesta está repartida entre E6(R3) y E2A. Primero se muestra la respuesta guardada de la línea base (`data/eval/answers_baseline_v3.jsonl`, producida antes de los cambios de la v4); después, la v3 y la v4 ejecutadas en directo con la recuperación actual. Lo que hay que comprobar: ¿responde el agente a las partes que cubren los pasajes en lugar de rendirse?
""",
)
tr(
    "Read the three answers together. The saved v3 baseline says \"I could not find this in my knowledge base\" although the passages hold the investigator → sponsor → authority chain; v4 builds it step by step with a citation on each step. Re-running the v3 prompt over **today's** retrieval does not necessarily refuse any more, because section-level expansion (4.1) also changed what the model sees: the improvement measured in §9 is the **combined** effect of the prompt and the retrieval changes, not of the prompt alone. That is why §9 scores the whole system and not one component.",
    r"""
Lea las tres respuestas juntas. La línea base v3 guardada dice «I could not find this in my knowledge base» aunque los pasajes contienen la cadena investigador → promotor → autoridad; la v4 la construye paso a paso con una cita en cada paso. Volver a ejecutar el prompt v3 con la recuperación **actual** ya no rechaza necesariamente, porque la expansión a la sección (4.1) también cambió lo que ve el modelo: la mejora medida en la §9 es el efecto **combinado** del prompt y de los cambios de recuperación, no solo del prompt. Por eso la §9 puntúa el sistema completo y no un componente.
""",
)
tr(
    "**v1 vs v4 on the same question.** v1 is the bare \"answer from the documents\" prompt from the class notebook. Compare attribution and structure.",
    r"""
**v1 frente a v4 en la misma pregunta.** La v1 es el prompt escueto de «responde a partir de los documentos» del cuaderno de clase. Compare la atribución y la estructura.
""",
)

tr(
    "## 6 · The LangGraph agent",
    r"""
## 6 · El agente LangGraph

Un `StateGraph` explícito en lugar de un agente con herramientas: el enunciado exige usar la base de conocimiento en **cada** consulta, el plan gratuito encarece las llamadas extra al LLM y una topología fija es fácil de trazar.

```
START → rewrite_query → retrieve → (route) → generate → END
                                           ↘ refuse  → END
```

* **rewrite_query**: convierte el último mensaje en una *pregunta autónoma en inglés* usando el historial acotado (resuelve «esa situación», «la misma regla»; traduce del español). En un primer turno en inglés se ahorra la llamada al LLM.
* **retrieve**: puntúa el top‑k sobre toda la colección (`similarity_search_with_relevance_scores`) y aplica el umbral calibrado; si la pregunta **nombra documentos** («E6(R3)», «Helsinki», «E2A»; alias en `sources.yaml`), el top‑k se reparte entre ellos con un filtro de metadatos; si no, **MMR** simple (`k=6, fetch_k=24, λ=0.6`); por último, cada fragmento se **amplía** a su sección (4.1).
* **route**: `Literal["generate", "refuse"]` según `grounded`.
* **generate**: prompt de sistema v4 + historial acotado + pasajes numerados + pregunta (+ línea de idioma).
* **refuse**: respuesta con plantilla en el idioma del usuario, sin llamada al LLM.

El estado mantiene `context`/`sources` *fuera* de `messages`, de modo que la conversación persistida se mantiene pequeña y la ventana de memoria cuenta turnos, no pasajes.
""",
)

tr(
    "### 6.1 · Tracing one question through the graph",
    r"""
### 6.1 · Traza de una pregunta a través del grafo

`graph.stream(..., stream_mode="updates")` devuelve el delta de estado de cada nodo: la traza de LangGraph que el enunciado recomienda para depurar (LangSmith se activa con `LANGSMITH_TRACING=true`; esto es el equivalente sin conexión).
""",
)

tr(
    "## 7 · Conversation memory",
    r"""
## 7 · Memoria conversacional

`InMemorySaver` guarda un punto de control de todo el hilo bajo un `thread_id`; el prompt solo ve los últimos **10 mensajes** (5 turnos), recortados para empezar en un turno del usuario. Tres cosas que verificar:

1. una pregunta de seguimiento que *se refiere* a la respuesta anterior («… sobre **esa situación**?») la resuelve `rewrite_query` en una pregunta autónoma;
2. «resume lo que me has dicho» funciona en el turno 3 (mensaje 5 de la ventana);
3. la misma pregunta de seguimiento en un **hilo distinto**, sin historial, produce otra pregunta autónoma: los hilos están aislados.
""",
)

tr(
    "## 8 · Documented example conversations",
    r"""
## 8 · Conversaciones de ejemplo documentadas

Seis preguntas elegidas para ejercitar comportamientos distintos: una definición, un plazo, una síntesis entre documentos, una pregunta de responsabilidades, un rechazo fuera de dominio y una pregunta que *parece* del dominio pero trata de un documento que **no** está en la base de conocimiento. Para cada una: qué se preguntó, la respuesta, las fuentes y una nota sobre si es correcta (juzgada contra el texto de la guía).

> **Nota (autor):** las preguntas se redactaron a partir del texto indexado de las guías con ayuda de IA, y revisé cada una y su nota de corrección contra la guía; la verdad de referencia de un asistente experto tiene que comprobarla alguien capaz de juzgarla. Edite `DEMO_QUESTIONS` para probar otras.
""",
)

tr(
    "## 9 · Evaluation on the golden set",
    r"""
## 9 · Evaluación con el golden set

`data/eval/golden.jsonl` contiene 25 preguntas redactadas a partir del texto indexado (con ayuda de IA) y revisadas por el autor, cada una en **inglés y español** (50 ejecuciones): 19 del dominio con el documento y la sección que las responden (dos necesitan dos documentos), 4 fuera de dominio que deben rechazarse y 2 que *parecen* del dominio pero preguntan por documentos deliberadamente no indexados (21 CFR Part 50, EU CTR 536/2014). `tests/test_golden_consistency.py` comprueba cada referencia contra el texto indexado.

Dos capas de métricas:

* **Recuperación** (abajo, en vivo; los vectores de consulta están en caché, así que no cuesta nada): ¿contenía el top‑6 el documento y la sección esperados?, ¿quedaron las preguntas fuera de dominio por debajo del umbral y las del dominio por encima?
* **Respuestas** (`scripts/03_evaluate.py --with-answers`, ~60 llamadas al LLM, resultados en `docs/`): cobertura de palabras clave de las respuestas generadas (aceptando la forma española que usa una respuesta en español) y honestidad ante documentos no indexados. La primera ejecución completa de la v3 destapó listas truncadas, una pregunta de varios pasos rechazada y un rechazo en inglés a una pregunta en español; el prompt v4, la expansión del contexto y el enrutado por documento fueron la respuesta. La comparación usa las mismas palabras clave en ambas ejecuciones.
""",
)

tr(
    "### 9.1 · Do the improvements generalise? Held-out set and LLM judge",
    r"""
### 9.1 · ¿Generalizan las mejoras? Conjunto held‑out y juez LLM

Dos comprobaciones contra el sobreajuste al golden set:

* **Conjunto held‑out** (`data/eval/heldout.jsonl`, 12 ítems × EN/ES), escrito *después* de congelar la v4, sobre temas que el golden set no toca, ejecutado una vez por configuración y nunca usado para ajustar.
* **Juez LLM** (`scripts/05_judge.py`): compara cada respuesta del dominio con la referencia experta: correcta = 1, parcialmente correcta = 0,5, incorrecta = 0; mide corrección, que la cobertura de palabras clave solo aproxima. El juez previsto, `gemini-3.5-flash` (mayor que el modelo que responde), permite 20 peticiones al día en el plan gratuito, suficientes para un solo conjunto de respuestas; por eso los cuatro conjuntos se juzgaron con `gemini-3.5-flash-lite`, y los dos jueces se comparan en las 38 respuestas que `flash` sí juzgó.

Ambos los produjeron los scripts; la celda siguiente solo lee los resultados guardados en el repositorio.
""",
)

tr(
    "## 10 · Interactive chat",
    r"""
## 10 · Chat interactivo

Ejecute las celdas siguientes y converse con el agente: escriba una pregunta (en inglés o en español) y pulse *Ask*; *New thread* inicia una conversación nueva. Cada turno pasa por la misma función `chat()`, que imprime la respuesta de inmediato con sus fuentes.

Cuando el cuaderno se ejecuta sin interfaz (`NB_INTERACTIVE=0`, como en las salidas guardadas) no hay nadie que escriba, así que la celda envía en su lugar una conversación corta de dos turnos por esa misma función: lo que se ve abajo es un intercambio real, no una grabación. Sin widgets (algunas configuraciones de Colab o VS Code), llame a `chat_loop()` para un diálogo en texto plano.
""",
)

tr(
    "## 11 · Limitations and next steps",
    r"""
## 11 · Limitaciones y siguientes pasos

**Limitaciones**
- *Tres documentos.* Suficientes para GCP, notificación expeditiva de seguridad y ética de la investigación; las preguntas sobre el EU CTR 536/2014, los módulos GVP o la regulación de la FDA se rechazan o se responden solo con lo que dice la E6(R3).
- *Extracción de PDF.* Las tablas de ICH (registros esenciales, apéndice C de la E6(R3)) se aplanan en prosa; el limpiador elimina cabeceras repetidas y líneas de índice, pero no puede restaurar la estructura de las tablas.
- *Preguntas de varios saltos.* «Del investigador al regulador, ¿quién notifica a quién y cuándo?» necesita juntas la E6(R3) §2.7.2, la §3.13.2 y la E2A; una sola pasada de recuperación no trae todos los saltos, así que la respuesta puede omitir un paso (el único veredicto *incorrecto* del juez en la ejecución de v4, en español; sección 9.1).
- *El enrutado por documento tiene un coste.* En la comparación E6(R3) frente a Helsinki, las plazas filtradas para la E6(R3) eligen la §2.8.1 y el glosario en lugar del principio 2.1 (los dos fallos de sección de la sección 9), aunque las respuestas generadas siguen citándolo.
- *El umbral depende del corpus.* La puerta de rechazo calibrada (0,69) se leyó de seis consultas del dominio y seis fuera de dominio, una de las cuales (la pregunta sobre GLP‑1) aparece también en el golden set y en la demo; hay que recalibrarla si cambia el corpus o el modelo de embeddings. Las preguntas del dominio formuladas de manera muy distinta al texto pueden rechazarse.
- *La memoria es por proceso.* `InMemorySaver` vive en RAM; la aplicación Streamlit da a cada sesión del navegador su propio `thread_id`, pero un reinicio lo olvida todo. Un `SqliteSaver` haría persistentes los hilos.
- *Juez.* El juez es el mismo modelo que responde; el mayor, `gemini-3.5-flash`, coincidió con él en el 78,9 % de 38 respuestas y fue más estricto, así que las puntuaciones absolutas se leen como optimistas (sección 9.1).
- *Plan gratuito.* Embeber el corpus cuesta ~17 peticiones; cada turno de chat cuesta 1–2 llamadas al LLM. La construcción es reanudable y está en caché, así que la cuota nunca se gasta dos veces.

**Siguientes pasos (por orden de valor)**
1. Descomposición de consultas: una recuperación por paso en las preguntas de varios saltos.
2. Añadir el Módulo VI de GVP de la EMA y el EU CTR 536/2014 (la ingesta es por documento e idempotente; recalibrar el umbral y ampliar el golden set).
3. Un juez de fidelidad (respuesta frente a pasajes recuperados); el juez actual mide corrección frente a referencias expertas.
4. Recuperación híbrida (BM25 + vectores) para números de sección y acrónimos exactos.
5. Un nodo `guard_input` (inyección de prompt y datos personales) antes de `rewrite_query`, y un checkpointer persistente.
""",
)


def main() -> int:
    nb = nbformat.read(SRC, as_version=4)
    used: set[str] = set()
    for cell in nb.cells:
        if cell.cell_type != "markdown":
            continue
        first = cell.source.splitlines()[0]
        if first not in ES:
            print(f"no Spanish text for the cell starting: {first!r}", file=sys.stderr)
            return 1
        cell.source = ES[first]
        used.add(first)
    unused = set(ES) - used
    if unused:
        print(f"translations with no matching cell: {sorted(unused)}", file=sys.stderr)
        return 1
    nb.metadata["language_info"] = {**nb.metadata.get("language_info", {}), "name": "python"}
    nbformat.write(nb, OUT)
    print(f"wrote {OUT.relative_to(HERE.parent)} ({len(nb.cells)} cells, outputs copied from the English notebook)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
