# FoodScope

FoodScope is a USDA food-composition knowledge graph built using the [course team template](https://github.com/ahmabboud/kr-team-template) and its lecture/demo code. It maps relational data with Morph-KGC, validates it with SHACL, runs HermiT, evaluates graph models, and answers English questions with the course Gemini access layer.

The repository follows the template's root folders and three-service Compose stack. [COURSE_CODE_SOURCES.json](COURSE_CODE_SOURCES.json) records source files, hashes and the template commit. Verification status and remaining checks are documented below.

## Contents

- [Run with Docker](#run-the-template-stack) or [Python](#run-locally-with-python)
- [UI and natural-language configuration](#ui-and-natural-language-configuration)
- [Repository structure](#repository-structure)
- [Data and generated outputs](#data-and-generated-outputs)
- [FoodOn reuse](#foodon-reuse) and [competency questions](#competency-questions)
- [System walkthrough](#how-the-system-processes-a-food) and [technology roles](#technologies-and-their-roles)
- [SHACL constraints](#shacl-constraints)
- [Mapping, PostgreSQL and Ontop](#mapping-and-integration)
- [Learning experiments](#learning-experiments) and [measured results](#measured-learning-results)
- [Access-layer evaluation](#access-layer-evaluation)
- [Course source alignment](#course-source-alignment) and [verification status](#verification-status)
- [Open problem](#open-problem-query-correctness) and [licences](#licences)

## Run the template stack

Install Docker Desktop and start its engine. From the **repository root**, on a fresh checkout:

```powershell
Copy-Item .env.example .env
# Edit .env locally and set GOOGLE_API_KEY.
docker compose up --build
```

Keep an existing `.env`; do not overwrite it. The local key configured before the folder migration was moved to the repository root.

The pipeline first builds and validates the data, then loads Fuseki. The access service starts only after the pipeline exits successfully.

- UI: [http://127.0.0.1:8000/](http://127.0.0.1:8000/)
- Fuseki: [http://127.0.0.1:3030/](http://127.0.0.1:3030/), dataset `kr`
- Stop: press **Ctrl+C**, then `docker compose down`.

The first build downloads the course dependencies. Profiling and multi-seed learning runs take longer than a query-only run. The clean Docker build and full container pipeline were verified on 18 October 2026. Fuseki returned 358 foods and 350 inferred characterized foods; the UI, predefined answers, live natural-language count and unsupported-price refusal passed. All 18 regression tests also passed in the Linux image.

## Run locally with Python

Use **Python 3.12** and **Java 21**. From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r pipeline/requirements-pipeline.txt
.\.venv\Scripts\python.exe -m pip install --no-deps morph-kgc==2.10.0
.\.venv\Scripts\Activate.ps1
python run.py
```

`python run.py` runs the local pipeline, skips Fuseki loading, starts the UI. Open the printed localhost URL in your browser. Keep the terminal open; **Ctrl+C** stops the server. Java must be on `PATH`, or set `JAVA_EXE` in the root `.env`. An existing portable JDK under `.tools/java/*/bin/java.exe` is also detected on Windows; it is not committed.

Morph-KGC's declared RDF dependency bounds differ from the versions pinned by the course. The separate `--no-deps` installation is intentional and matches the demos. The two associated `pip check` dependency warnings are expected with these course pins.

The canonical pipeline is **`pipeline/run.py`**; `run.py` is the local UI shortcut. The Python environment belongs in root `.venv`.

On macOS/Linux, use `python3.12 -m venv .venv` and `.venv/bin/python`. On Linux, install the course CPU build **before** the shared requirements:

```bash
.venv/bin/python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m pip install -r pipeline/requirements-pipeline.txt
.venv/bin/python -m pip install --no-deps morph-kgc==2.10.0
.venv/bin/python run.py
```

## UI and natural-language configuration

Create a key in [Google AI Studio](https://aistudio.google.com/apikey) and save it only in the root `.env`:

```dotenv
GOOGLE_API_KEY=your_key_here
LLM_MODEL=gemini-3.5-flash-lite
LLM_MODE=live
```

The model name and Gemini HTTP interface are taken from the course code. The predefined queries, HermiT and graph models run locally without a model key. English questions use the configured Gemini API; pricing and quotas depend on your Google project/model.

The interface provides:

1. **Ask graph:** English questions pass through the template's VoID grounding, lexical example selection, schema checks, up to two repairs, and refusal path. Generated SPARQL executes against the local graph or configured `SPARQL_ENDPOINT`.
2. **Predefined queries:** select one of 13 questions to view saved answers, readable column labels and SPARQL text. Sodium uses mg per 100 g; other selected nutrient amounts use g per 100 g.
3. **Reload results:** reads the latest `build/answers.json`; it does not rerun the pipeline.
4. **Project resources:** links to this README, the data manifest and ontology source. These are source-file views, not an ontology editor.

Questions, schema and selected examples are sent to Gemini for live requests. The browser never receives the key. The application handler blocks hidden files such as `.env` and `.git`.

To serve existing results without rebuilding:

```powershell
python access-layer/serve.py
```

This requires existing validated graph/VoID outputs. For a fresh run, use `python run.py`.

## Commands and run options

Only the template's `--no-load` pipeline option is supported. Custom skip/UI/port flags were removed. The requested browser UI remains a separate project adapter. See [Course source alignment](#course-source-alignment) for retained food-specific adaptations.

All commands below run from the **repository root**, with the environment activated.

| Command | Behavior |
| --- | --- |
| `python run.py` | Local pipeline and UI; no Fuseki required. |
| `python pipeline/run.py` | Template pipeline, including loading Fuseki; exits afterward. |
| `python pipeline/run.py --no-load` | Full local pipeline without loading an endpoint or starting the UI. |
| `python -m data.profiling.data_profile` | Constraint inventory and compact source profile only. |
| `python mapping/er/match_foods.py` | Measure cross-release matching at the course thresholds. |
| `python pipeline/run.py --help` | Show available flags. |

A failed gate stops reasoning, querying, endpoint loading and UI launch. A failed run can leave earlier artifacts; check timestamps and completion messages. Pipeline results are snapshots, not automatic live updates.

## Repository structure

| Folder | What it contains and why it exists |
| --- | --- |
| `data/` | The four prepared CSV tables, SQL sample, source manifests, licence record and preparation scripts. This is the source layer, before graph conversion. |
| `data/profiling/` | Source profiling and the food-specific constraint inventory generator. The inventory expresses the constraints of our food source. |
| `data/raw/` | Ignored original downloads, when present. Not needed to run the committed sample. |
| `ontology/` | Our OWL vocabulary, FoodOn extract, offline import catalog, fetcher, reviewed reasoner evidence; competency questions are documented below. |
| `shapes/` | Executable SHACL requirements; accepted warnings and rejected errors are explained in this README. |
| `mapping/` | R2RML conversion rules, PostgreSQL loading code and the materialized/virtualized comparison. |
| `mapping/er/` | A real Foundation/SR Legacy matching sample, gold labels, course matcher and measured matching results. |
| `mapping/ontop/` | Optional Ontop/JDBC setup, connection helpers and the shared count query. Downloaded CLI binaries are ignored. |
| `pipeline/` | The canonical orchestrator, runtime requirements, container definition and supporting validation/provenance code. Root Compose runs this pipeline once per job. |
| `pipeline/validation/` | The course validator helpers, including subclass-aware counts of nodes targeted by a shape. |
| `pipeline/provenance/` | The course PROV-O generation code for source and processing-run traceability. |
| `sparql/` | The 13 maintained predefined questions and their SPARQL query definitions. |
| `model/` | Learning-data construction, logistic baseline, GraphSAGE, TransE/popularity comparison and shared split/metric helpers. |
| `model/results/` | Reviewed experiment snapshots and reproducibility metadata. New working outputs go under `build/learning/`. |
| `access-layer/` | English-to-SPARQL logic, HTTP server, examples, prompt rules, evaluation questions and genuine recorded model replies. |
| `fuseki/` | The template's Fuseki image definition. Runtime graph storage is in a Docker volume, not in this source folder. |
| `assets/` | FoodScope JavaScript/CSS, reused course stylesheet and application icons. |
| `presentation/` | [PowerPoint deck](presentation/FoodScope_KRR.pptx) with animations, editable diagrams/charts and speaker notes for Mohammed Zaiter and Ali Tarhini; [read-aloud script](presentation/Speaker_Notes.txt). |
| `report/` | Recorded language evaluation evidence and reproducibility context. Documentation is consolidated in this README. |
| `tests/` | Regression checks for validation, query checking, HTTP behavior, source consistency and learning split isolation. |
| `.github/workflows/` | The committed automated validation workflow. A workflow file alone is not evidence of a successful hosted run. |
| `build/` | Ignored generated artifacts: database, graphs, reports, answers, VoID, provenance, learning data and temporary Ontop properties. |
| `.venv/` | Ignored local Python environment. It is machine-specific; teammates create their own using the README. |
| `.tools/` | Ignored local tooling/downloads, including the portable Java runtime when present. Docker supplies its own Java. |
| `.git/` | Git's version history and working-copy metadata. It is not application code. |

Interpreter and linter cache folders such as `__pycache__` and `.ruff_cache` are disposable and can reappear after execution.

### Root files

| File | Meaning |
| --- | --- |
| `README.md` | Setup, run commands, source downloads and troubleshooting. |
| `run.py` | Local shortcut: runs the canonical pipeline with no endpoint load and requests the UI. |
| `docker-compose.yml` | Defines Fuseki, the pipeline job and the access/UI service. |
| `index.html` | The browser interface and its query-mode dropdown. |
| `manifest.webmanifest`, `sw.js` | Browser application metadata and offline caching; query requests and generated build data bypass the offline cache. |
| `.env.example` | Shareable configuration template with no real secrets. |
| `.env` | Local model key and optional database credentials; ignored and blocked by the HTTP handler. |
| `.gitignore`, `.dockerignore` | Keep local secrets, environments, large downloads and generated artifacts out of Git or the Docker build context. |
| `COURSE_CODE_SOURCES.json` | Original source lineage, hashes, adaptations and the pinned template commit. |
| `.nojekyll` | Static-hosting metadata. Static hosting alone cannot execute the Python access API. |

## Data and generated outputs

The included April 2024 Foundation Foods snapshot has **358 foods**, **1,499 observations**, **six nutrients** and **28 category definitions**. The CSVs are `foods.csv`, `measurements.csv`, `nutrients.csv` and `categories.csv`.

Selected USDA nutrient IDs: protein `1003`, fat `1004`, carbohydrate `1005`, fiber `1079`, sodium `1093`, sugars `2000`. Amounts refer to 100 g edible portion. Missing observations remain unknown, not zero. Source publication dates remain dates in CSV/SQL and are mapped to midnight `xsd:dateTime` values for HermiT compatibility; midnight is a representation of the source date, not an observed publication time.

| Output under `build/` | Contents |
| --- | --- |
| `profiling/` | Four ydata HTML reports and per-column quality CSVs. |
| `profile.json`, `constraint_inventory.csv` | Food-specific rules, evidence, exception counts and missingness. |
| `example.sqlite` | Database rebuilt from committed `data/example.sql` unless `DB_URL` is configured. |
| `graph.nt`, `food.trig` | Mapped facts and their named source-table graphs. |
| `validation-input.ttl` | Mapped facts plus the locally resolved ontology/module. |
| `shacl-report.txt`, `validation.txt`, `validation.ttl` | SHACL reports; `shape_coverage.json` records targets. |
| `reasoning.json`, `reasoned.ttl`, `reasoned.nt` | HermiT diagnostics and graph with inferred membership. |
| `answers.json` | Predefined query text and rows exported for the requested UI. |
| `void.ttl` | Class/property description used to ground the access layer. |
| `provenance.ttl` | Course PROV-O source-file hashes and processing-run records. |
| `learning/` | Generated PyTorch graph and library working files. Course experiment scores print to the terminal; reviewed snapshots remain in `model/results/`. |
| `access/` | Generated evaluation metadata. Reviewed scores are saved in `report/`. |

## Rebuild original USDA inputs

Normal runs need no data download. Sources and hashes are recorded in [data/manifest.json](data/manifest.json).

- [April 2024 Foundation Foods ZIP](https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_csv_2024-04-18.zip)
- [USDA downloads](https://fdc.nal.usda.gov/download-datasets/)

Download/extract manually, then pass the folder directly containing `food.csv`, `food_nutrient.csv`, `nutrient.csv` and `food_category.csv`:

```powershell
python data/prepare.py --source "C:\datasets\FoodData_Central_foundation_food_csv_2024-04-18"
python run.py
```

Without `--source`, preparation selects the first sorted `data/raw/usda/*/food.csv` match. It overwrites the prepared CSVs, manifest and SQL sample. If you edit prepared CSVs manually, run `python data/build_sample.py` before the pipeline; the template source loads `example.sql`, not the CSVs directly. Raw archives under `data/raw/` are ignored. The small real SR Legacy matching sample and its source hashes are committed separately under `mapping/er/`.

## FoodOn reuse

[ontology/ontology.ttl](ontology/ontology.ttl) declares `owl:imports` for our documented FoodOn ancestor module. [ontology/catalog-v001.xml](ontology/catalog-v001.xml) resolves that module locally, using the course import-loader code.

```turtle
food:Food rdfs:subClassOf obo:FOODON_00001002 .
```

The module's hierarchy is **food product -> food material -> material entity**. We add local food-composition classes/properties and `CharacterizedFood`, defined by having an observation. This is a three-class asserted extract, not the complete FoodOn ontology or its full import closure.

[data/foodon-source.json](data/foodon-source.json) records the source/version/hash/license. To fetch and reproduce the extract:

```powershell
python ontology/fetch_ontologies.py
# Or verify an existing original download:
python ontology/fetch_ontologies.py --source "C:\datasets\foodon.owl"
```

The recorded version URL returned 404 during verification; the recorded source URL succeeded with the expected hash. The fetcher accepts that fallback only when its SHA-256 matches. Normal pipeline runs use the committed module offline. See [Competency questions](#competency-questions) for question-to-vocabulary traceability.

## Evaluation and template integration

The course GraphSAGE and TransE code is adapted to food data; no replacement model or retrieval algorithm is used. The classification task is **fat > 20 g per 100 g**. Fat itself is excluded from predictors; missing labels are excluded. Both random and category-held-out splits are reported. See [Learning experiments](#learning-experiments) for leakage controls and results.

The template access layer is configured through `NS`, `PFX`, `prompt_rules.txt`, `examples.ttl` and `questions.yaml`. To reproduce the recorded evaluation without new API calls:

```powershell
$env:LLM_MODE="replay"
$env:VOID_FILE=(Join-Path (Get-Location) "report/access-layer-void.ttl")
python access-layer/evaluate.py
Remove-Item Env:LLM_MODE
Remove-Item Env:VOID_FILE
```

For a new live, recorded evaluation, set `LLM_MODE="record"` instead. The cache matches the exact model and prompt; changing rules/schema/examples invalidates affected recordings. The measured run and its limitations are in [report/access-layer-score.txt](report/access-layer-score.txt).

The course PostgreSQL/Ontop comparison commands are included under [Mapping and integration](#mapping-and-integration). The PostgreSQL/Ontop count comparison has passed (358 foods in both views). Ontop warns that the CharacterizedFood equivalence is outside OWL 2 QL, so this is not proof of full reasoning equivalence. The clean Compose build and runtime checks passed; see [Verification status](#verification-status).

## Validation and troubleshooting

```powershell
python -m unittest discover -s tests -v
docker compose config --quiet
```

| Symptom | Action |
| --- | --- |
| Missing Morph-KGC | Run its separate `--no-deps` install with the same environment. |
| Java/HermiT cannot start | Install Java 21 or set `JAVA_EXE` in root `.env`. |
| SHACL gate fails | Read `build/shacl-report.txt` and `build/shape_coverage.json`. |
| Missing or invalid query results | Run the full pipeline, then refresh or click Reload results. |
| API key/configuration error | Check root `.env`; do not put the key in frontend files. |
| Replay cache miss | Restore the recorded model/rules/schema/examples or create a new live recording. |
| Port occupied | For local Python mode, stop the earlier server or set `PORT=8080` in root `.env`. For Docker, adjust the Compose port mapping to match the configured container port. |
| Docker cannot connect | Start Docker Desktop's engine before running Compose. |

Generated build/raw/environment files stay out of Git. Reviewed experiment outputs, the genuine replay cache and source manifests are intentionally shareable. Never commit `.env` or generated JDBC credentials.

## Attribution

Pipeline/access code follows [kr-team-template](https://github.com/ahmabboud/kr-team-template) and the [course demos](https://github.com/ahmabboud/course_knowledge_representation). UI styles are adapted from the course, whose README permits reuse/adaptation of its template, stylesheet and runtime. Course content belongs to its authors. USDA data is public domain/CC0; FoodOn material is CC BY 4.0 with attribution to the FoodOn consortium. See `data/FOODON-LICENSE.txt` and the licence table below.

For score replay, the archived VoID context is pinned in `report/access-layer-void.ttl`, with context hashes in `report/access-layer-context.json`. The original template SAMPLE-based generator is retained; regenerating VoID can change the exact prompt.

## How the system processes a food

1. A row in `data/foods.csv` identifies a USDA food. Rows in `data/measurements.csv` associate it with nutrient IDs and amounts.
2. `data/build_sample.py` turns the four prepared CSV tables into `data/example.sql`. This committed SQL sample makes a fresh checkout runnable without downloading the original archives.
3. `pipeline/run.py` builds `build/example.sqlite` from that SQL, unless `DB_URL` selects an external database.
4. Morph-KGC reads the database through `mapping/mapping.ttl` and creates RDF statements. Stable resource identifiers include the source and record ID.
5. The pipeline combines those statements with the local ontology and its imported FoodOn module. SHACL checks the resulting data before reasoning.
6. HermiT checks consistency and infers classifications. A Food with an Observation meets the definition of CharacterizedFood. The measured snapshot has 350 such foods.
7. The pipeline runs the 13 predefined queries and saves their answers, runs the matching and learning experiments, and creates a VoID description. In the Compose stack it also loads the reasoned graph into Fuseki. Provenance records document the run and its inputs.
8. The browser displays saved answers or calls the access layer for a new English question.

A validation violation stops the downstream work. An incomplete six-nutrient panel is a warning: a partial source record is retained without inventing measurements.

## Graph vocabulary and file formats

An RDF statement has a subject, a property and an object. For example: a particular food **hasObservation** a particular measurement. That observation **nutrient** protein and **amount** a decimal value. The nutrient definition supplies the unit.

| Local class | Meaning | Important properties |
| --- | --- | --- |
| `food:Food` | A USDA food record | `food:name`, `food:sourceId`, `food:category`, `food:publishedOn`, `food:hasObservation` |
| `food:Category` | A source category such as Dairy and Egg Products | `food:name` |
| `food:Nutrient` | A nutrient definition such as protein | `food:name`, `food:unit` |
| `food:Observation` | One amount of one nutrient in one food | `food:ofFood`, `food:nutrient`, `food:amount` |
| `food:CharacterizedFood` | A Food with at least one Observation | Inferred from the OWL class definition |

The `food:` prefix abbreviates `https://ul.edu.lb/kr/food#`. Data instances use separate identifiers under `https://ul.edu.lb/kr/id/`. These URLs identify graph resources; their use does not mean the application is hosted at those URLs. The running UI is on localhost.

Turtle (`.ttl`), N-Triples (`.nt`) and TriG (`.trig`) are RDF file formats. Turtle is readable and supports prefixes. N-Triples writes individual statements explicitly. TriG can group statements into named graphs, which this project uses to record source-table provenance.

## Technologies and their roles

| Technology | Role in this repository | Where to look |
| --- | --- | --- |
| Python 3.12 | Runs preparation, orchestration, validation, evaluation and the HTTP service | Root `run.py`, `pipeline/`, `access-layer/` |
| SQLite | Holds the small relational sample during normal local runs | `build/example.sqlite`, generated from `data/example.sql` |
| R2RML | Describes how SQL rows become RDF subjects, properties and values | `mapping/mapping.ttl` |
| Morph-KGC | Executes that mapping and materializes RDF statements | `pipeline/run.py`, `materialize()` |
| RDFLib | Reads, builds and serializes RDF graphs; also supports query/schema utilities | Pipeline and access-layer Python code |
| SHACL and pySHACL | Define and execute data-quality constraints | `shapes/shapes.ttl`, `pipeline/validation/` |
| OWL | Expresses ontology classes, relationships and logical definitions | `ontology/ontology.ttl` |
| HermiT through Owlready2 | Checks ontology consistency and computes logical classifications | `ontology/local_reasoner.py` |
| Java 21 | Runs the Java-based HermiT, Fuseki and optional Ontop tools | Dockerfiles and local Java configuration |
| SPARQL | Queries RDF graphs, including joins, filters, counts and rankings | `sparql/queries.sparql` and generated queries |
| Oxigraph through pyoxigraph | Executes queries in process without a separate server | Predefined-query execution and local access backend |
| Apache Jena Fuseki | Stores and serves the graph through an HTTP SPARQL endpoint in Compose | `fuseki/`, `docker-compose.yml` |
| VoID | Describes the graph's classes/properties for language-model grounding | `access-layer/make_void.py`, `build/void.ttl` |
| Gemini | Translates an English question into SPARQL or a refusal | `access-layer/access_layer.py` |
| PROV-O | Describes source files, processing runs and derivation | `pipeline/provenance/`, generated provenance files |
| ydata-profiling | Produces source-table quality reports | `data/profiling/`, `build/profiling/` |
| scikit-learn | Runs the course logistic-regression baseline and metrics | `model/baseline.py` |
| PyTorch and PyTorch Geometric | Represent the learning graph and train GraphSAGE | `model/build_graph.py`, `model/gnn.py` |
| PyKEEN | Runs the course TransE link-prediction experiment | `model/link_prediction.py` |
| PostgreSQL and Ontop | Support the optional relational-versus-virtual-graph comparison | `mapping/ontop/`, separate mapping Compose file |
| Docker Compose | Builds and orders the application's services | Root `docker-compose.yml` |

### Fuseki versus Oxigraph

Fuseki is a separate graph server. In Compose it listens on localhost port 3030, hosts dataset `kr`, and answers SPARQL at `/kr/sparql`. The pipeline loads the materialized, reasoned snapshot into it. Its `fuseki-data` Docker volume persists independently of the pipeline container.

Oxigraph runs inside Python. With the local shortcut, the access layer loads `build/reasoned.ttl` into memory, so no Fuseki service is needed. Setting `SPARQL_ENDPOINT` makes the access layer use an endpoint instead; Compose sets it to the Fuseki service address. Predefined answers are generated using Oxigraph during the pipeline and displayed from a saved JSON file.

Neither server startup nor opening a saved answer reruns HermiT. Reasoning happens in the pipeline before the reasoned snapshot is served. If the source changes, rebuild the pipeline outputs and reload the running backend. Restart a local access server to refresh its in-memory store.

### Neo4j in the course demos

The course's shared demo stack also starts Neo4j for the Session 2 comparison exercise: similar questions are run against a property graph using Cypher and an RDF graph using SPARQL. The team template and this application use Fuseki without Neo4j. That optional Neo4j comparison has not been implemented here; using the course methods does not mean every demo exercise is reproduced.

### SHACL versus HermiT

SHACL asks whether this submitted dataset meets our explicit requirements: is an amount nonnegative, does a food have a name, and does a reference resolve? HermiT asks whether the logical ontology is consistent and which class memberships follow from its definitions.

These checks answer different questions. Missing source values can fail a SHACL requirement without creating an OWL inconsistency. Here, violations and empty shape targets block the pipeline; the 353 incomplete-panel results are retained as warnings. Read [SHACL constraints](#shacl-constraints) for each rule and its rationale.

## Query handling

The dropdown selects one of two views in the same panel. Each view has its own results container and SPARQL display.

**Predefined queries:** choosing a question displays its saved entry from `build/answers.json`. Reload results fetches that file again. It does not rerun the SQL mapping, reasoning, SPARQL or model experiments.

**Ask the food graph:** the submit handler calls `/api/ask?question=...` in the background. The Python server returns JSON, and JavaScript renders a table in Food graph answer without navigating away.

For a live English question, the access layer:

1. Reads the graph schema summary from VoID and the external prompt rules.
2. Selects three examples by word overlap with the question, using the course method.
3. Sends the question, schema and examples to the configured Gemini model.
4. Checks that the reply is valid SPARQL and uses permitted vocabulary. It can request up to two repairs or retain an explicit refusal.
5. Executes an accepted query using Fuseki or local Oxigraph, then returns the rows, query and attempt information.

For example, asking how many foods have more than 25 g protein selects protein ID `1003`, joins foods to their observations and filters `food:amount > 25`. The observed snapshot answer is 29. That number comes from query execution, not a generated prose estimate. Missing protein measurements do not satisfy the filter.

A valid query can still misunderstand the question. Schema checks do not prove the intended nutrient, threshold or projection was selected. The UI exposes the query for inspection, and the held-out evaluation measures actual answers. Unsupported questions such as food prices should be refused because that data is absent.

## Competency questions

The local OWL extension declares an OWL 2 DL profile and uses HermiT as in Session 3. Version 1.1.0 introduces the explicit offline FoodOn-module import and HermiT-compatible publication datatype. The imported module is an asserted named-ancestor extract, not the full FoodOn closure.

| CQ | Question family | Local vocabulary | Predefined query positions |
| --- | --- | --- | --- |
| CQ1 | Which foods and source identifiers are present? | `Food`, `sourceId`, `name` | 1 |
| CQ2 | Which foods belong to a category? | `Category`, `category`, `name` | 11 |
| CQ3 | What composition observations, nutrients and units are recorded? | `Observation`, `Nutrient`, `hasObservation`, `ofFood`, `nutrient`, `amount`, `unit`, `name` | 2, 8, 12 |
| CQ4 | Which foods satisfy nutrient thresholds or rankings? | Observation/nutrient properties, `amount`, `unit` | 3, 4, 9, 10 |
| CQ5 | How are foods distributed by category and publication date? | `Category`, `category`, `publishedOn`, `name` | 6, 7 |
| CQ6 | Which observations are missing, and which foods are characterized? | `hasObservation`, `Observation`, `CharacterizedFood` | 5, 13 |

The `food:answersCQ` annotations attach these families to the added classes/properties. The annotation property itself supports traceability, not a domain query. The mapping creates instances; SHACL checks their constraints; HermiT classifies a food with an observation as CharacterizedFood.

`food:Food rdfs:subClassOf obo:FOODON_00001002` connects every local food to FoodOn food product, whose imported ancestors are food material and BFO material entity. HermiT's direct inferred types and the class hierarchy are preserved; it does not materialize every possible ancestor type as an explicit assertion. To query ancestors, follow `rdf:type/rdfs:subClassOf*`.

Run the integrated check with `python pipeline/run.py --no-load`. The reviewed reasoner output is `ontology/reasoner-run.json`; current diagnostics are regenerated in `build/reasoning.json`.

## SHACL constraints

The rule inventory is generated by `data/profiling/data_profile.py`. Counts below describe the committed April 2024 snapshot, not universal USDA rules.

| Rule | Snapshot exceptions | Where enforced | Why SHACL/source checks rather than OWL |
| --- | --- | --- | --- |
| C1: unique nonempty food ID | 0 | Source inventory, FoodShape sourceId constraints/SPARQL uniqueness | Source-key completeness and uniqueness are closed-world checks. RDF resource identity alone can merge duplicate rows. |
| C2: nonempty food name | 0 | FoodShape name | A missing string is a validation problem, not an OWL inconsistency. |
| C3: category reference resolves | 0 | FoodShape category class/cardinality | The dataset must contain the referenced category explicitly. |
| C4: nonnegative amount | 0 | ObservationShape amount | Validates concrete source amounts and their decimal datatype. |
| C5: one observation per food/nutrient | 0 | ObservationShape SPARQL | Detects repeated observations without relying on open-world identity assumptions. |
| C6: gram amount at most 100 per 100 g | 0 | ObservationShape SPARQL with nutrient unit | Conditional on unit G; applying this bound to sodium in MG would be a wrong rule. |
| C7: all six selected nutrients present | 353 | CoverageShape, Warning | Requiring completeness as a hard violation would reject legitimate partial source panels. Missing is unknown, not zero. |
| C8: observation food reference resolves | 0 | ObservationShape ofFood class/cardinality | Requires an explicit food in the graph. |

Other property constraints cover dateTime, numeric identifiers, names and allowed units. The pipeline validates mapped facts with the resolved vocabulary before reasoning. Subclass-aware focus counts reuse the course validator; zero targets stop the run. Violations stop endpoint loading and UI launch. Warnings remain in the report.

TRIAGE C7: the 353 results are source incompleteness under our six-nutrient selection. They are retained as warnings, not repaired with fabricated measurements. A pipeline pass therefore means no violations, not complete nutrient coverage.

TRIAGE publication datatype: xsd:date was unsupported by the course HermiT version. The mapping now represents the same date at midnight as xsd:dateTime; the ontology range and SHACL datatype changed together. Source date strings are preserved, and no actual publication time is claimed.

`tests/test_course_pipeline.py` exercises a passing graph, an incomplete-panel warning, a negative-amount violation and an empty target. The CI workflow is committed; a hosted red/green Actions run must still be collected after a push. No hosted CI run is claimed from local tests.

## Mapping and integration

`mapping.ttl` uses the template's R2RML/Morph-KGC materialization approach over four USDA tables. Stable IRIs include kind, source and source key. The food SQL view converts publication dates to midnight `xsd:dateTime` for HermiT compatibility. Source CSV/SQL dates remain unchanged.

The deployed configuration materializes a release snapshot: validation, reproducible queries and a small fixed graph matter more here than minute-by-minute source freshness. `DB_URL` follows the template contract and can point at the same four-table schema in PostgreSQL. Keep credentials in root `.env`.

### Two-source matching

Run `python mapping/er/match_foods.py` from the repository root. It adapts the course Fellegi-Sunter/Jaro-Winkler code to genuine USDA Foundation/SR Legacy names and category blocks. The 40 SR sample records are compared with 358 Foundation candidates. `er/truth.csv` labels 32 shared-NDB records and 8 without a corresponding NDB record; NDB identifiers are not matching features. `er/sources.json` records exact source hashes and the gold-label scope.

The target is a corresponding USDA NDB concept across releases, not identical nutrient composition. The course's stated weights are retained and are not calibrated to food names. `er/results.json` records false positives/negatives and precision/recall at thresholds 4 and 8. These imperfect links are evaluation evidence and are not automatically asserted as `owl:sameAs` in the food graph.

### Materialized versus Ontop

This uses the course PostgreSQL 16, Ontop 5.5.0 and PostgreSQL JDBC code. It requires Java 21 and a running Docker engine. Add `POSTGRES_USER=kr` and a local `POSTGRES_PASSWORD` to root `.env`; do not commit the password. Leave `DB_URL` unset to use these values, or set it to the same PostgreSQL database.

From the repository root, with the environment active:

```powershell
docker compose --env-file .env -f mapping/docker-compose.yml up -d
python mapping/load_database.py
python mapping/ontop/setup_ontop.py
python mapping/compare_virtualized.py
```

The loader uses the same four committed CSVs as the SQL sample. The comparison runs one shared count query against `build/graph.nt` and virtualized PostgreSQL data, checks equal rows and writes `mapping/virtualization-comparison.json`. Ontop/JDBC binaries are ignored. JDBC properties are generated under the ignored `build/ontop/.food.properties`, which the UI cannot serve.

The timing report explicitly distinguishes JVM startup from the materialized engine's already-loaded query time; it is not an engine-only latency benchmark. The comparison completed on 2026-10-18: both views returned 358 foods. This verifies that shared count query, not every possible query. Ontop logged that the CharacterizedFood equivalence is outside OWL 2 QL; the materialized HermiT view is therefore retained for the application. The profile warning is preserved in the result JSON.

## Learning experiments

The algorithms come from `build_graph.py`, `baseline.py`, `gnn.py`, `learning_utils.py` and `link_prediction.py` in Session 6. Source hashes are in `COURSE_CODE_SOURCES.json`.

### Classification

Predict whether a food has more than 20 g fat per 100 g. There are 348 labelled foods, 55 positives; 10 foods with missing fat observations are excluded.

- Predictors: log1p protein, carbohydrate, fiber, sodium and sugars; five availability flags. Numerical zero with an unavailable flag is a model encoding, not an imputed source observation.
- Label leakage removed: fat amount is not a feature. The full observation graph, identifiers and names are not model inputs. Fat is retained separately only for the intentional leak demonstration.
- Graph: food/category HeteroData, category identity features, reverse edges via the demo's ToUndirected transform. No class labels are fed into message passing.
- Splits: the course stratified random split plus five category-held-out splits; no category occurs on both sides. This is a transductive graph experiment, not a fully inductive deployment benchmark.
- Baseline: course balanced logistic regression, train-fitted one-hot categories.
- GNN: course two-layer GraphSAGE, hidden 32, 100 epochs, Adam 0.01, weighted binary loss; three random-split training seeds and five group-split seeds.

Seed 2 has no positive test examples. Its PR-AUC is unscoreable and explicitly recorded, rather than substituted with a favorable number. The reported mean/spread uses the other four group seeds. Publication dates are snapshot metadata; category grouping tests transfer to different food groups rather than forecasting future foods.

### Link prediction

The exact course TransE/popularity evaluation is adapted from plant/product links to category/food membership. Hide 10% test and 10% validation membership links. Side information is observed food/nutrient links; inverse category facts are withheld. TransE uses dimension 32, 150 epochs and three seeds. Report filtered MRR/Hits@1; cold test entities are excluded and counted by the original course procedure. The held-out graph retains observed nutrient-presence facts, so it is a transductive task.

### Run and inspect

From the repository root, run `python model/build_graph.py`, then `python model/baseline.py`, `python model/gnn.py` and `python model/link_prediction.py`, as separate scripts like Session 6. The full pipeline invokes those same four scripts in order. Generated learning inputs are in `build/learning/`; scores print to the terminal. Reviewed snapshots, package versions and input hashes are in `model/results/`. These are experiments; the UI does not use model predictions as food or medical advice.

## Measured learning results

The Session 6 data conversion, logistic regression, GraphSAGE, TransE and split/ranking code is reused with domain adaptations recorded in `COURSE_CODE_SOURCES.json`. All reviewed outputs and package versions are saved in `model/results/`.

Classification predicts fat >20 g per 100 g. There are 348 labelled foods, including 55 positives; 10 missing-fat foods are excluded. Predictors are non-fat nutrient log1p amounts and availability flags. Category membership supplies the graph structure/group split. Fat is stored separately only for the intentional leak demonstration. No target amount, food name or source identifier becomes a predictor.

The leaky logistic-regression demonstration reaches PR-AUC 1.000, illustrating why that feature must be removed. Random-split scores are shown but are not the generalization claim. Across the four scoreable category-held-out seeds, mean PR-AUC is 0.392 (population SD 0.260) for logistic regression and 0.440 (SD 0.325) for GraphSAGE. The fifth seed has no positive test foods and is explicitly unscoreable. These high variances and the small sample do not establish reliable superiority. Publication dates describe releases, so category grouping is used to test new food groups; this is not a forecasting claim.

Link prediction hides category-contains-food links, retaining observed nutrient links and withholding inverse membership. Three seeds use the course TransE and filtered ranking protocol. Mean MRR is 0.339 for TransE versus 0.448 for popularity. Cold held-out entities are excluded and counted. The graph model loses to the baseline, which is reported rather than concealed. Classification and link prediction are transductive experiments, not validated inductive production models.

## Access-layer evaluation

The active implementation comes directly from the team template, configured through NS/PFX, prompt_rules.txt, six examples and 11 held-out questions. The graph description is VoID. The course lexical retrieval picks three examples; property/class checks and up to two repairs precede query execution, or the model refuses.

The configured model was gemini-3.5-flash-lite. Live replies were recorded on 2026-10-18 and replayed under the template implementation. The test set contains eight answerable questions and three questions requiring refusal. Mean course set-of-values F1 is 0.856 with schema only, 0.954 with examples and 0.954 with checking/repair. All three required refusals were correct, with no wrong refusal of an answerable question. No successful answer in this recorded run required repair; a regression test separately verifies the repair branch.

The remaining score error includes projecting identifiers as well as requested names. This illustrates a metric/semantic issue rather than a parser failure. A live API check returned 358 foods and refused a price question with reason `price`. `report/access-layer-score.txt`, its JSON metadata and the genuine prompt-keyed cache preserve evidence. Replay is exact for this prompt/model/schema setup; it is not evidence of another fresh live run or arbitrary question coverage.

## Open problem: query correctness

Our position is that schema grounding and query repair are necessary but insufficient for faithful natural-language answers. The recorded run contains executable queries using real vocabulary that still return the wrong projection for the requested question.

SPARQL defines how graph patterns and projections produce answers; it does not establish that a generated query expresses a user's intent. This explains why two syntactically valid queries can differ in the values they return. [W3C SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/)

SHACL checks graph constraints against shapes. A dataset passing those checks can still be queried incorrectly, so a validation gate cannot certify language-to-query correctness. [W3C SHACL Recommendation](https://www.w3.org/TR/shacl/)

OWL defines the structural semantics used for ontology reasoning. Consistency and inferred types likewise do not settle whether the model chose the right nutrient, threshold, projection or missing-data interpretation. [W3C OWL 2 Structural Specification](https://www.w3.org/TR/owl2-syntax/)

For this system we therefore retain explicit questions, gold queries, refusals, generated SPARQL and measured answer scores. Future work should test paraphrases, variable projection, zero versus missing values and distribution changes, while distinguishing data validation, inference and question fidelity. We have not implemented or measured that future work.

## Course source alignment

Reviewed on 18 October 2026 against the local course demos and team template. This is an audit of executable source code, not a claim that every lecture slide was searched. Source commits and hashes are in [COURSE_CODE_SOURCES.json](COURSE_CODE_SOURCES.json). The completed review recorded 32 successful function/class AST comparisons and 31 verified original source-file hashes.

### Agreed scope

Keep the requested FoodScope browser UI and remove unnecessary custom backend additions. Retain the course methods and domain/path/configuration changes required for USDA data. This is not a byte-for-byte copy of the supply-chain demos: the template asks teams to replace the source data, ontology, shapes, mappings and questions.

### Removed

- The six custom pipeline options: `--skip-queries`, `--no-ui`, `--port`, `--skip-learning`, `--skip-profile` and `--ui`. Only the template's `--no-load` and standard argparse help remain.
- Automatic browser opening and HTTP-server construction inside the pipeline. The separate root UI adapter starts the access-layer server after a successful pipeline run.
- `model/run_learning.py`, including custom log capture, output scraping and mean/spread JSON aggregation. The four Session 6 scripts now run directly and print their results.
- The duplicate code/input hash collector that wrote `provenance.json`. The course PROV-O generator retains source hashes and processing-run metadata in `provenance.ttl`.
- Custom predefined-query timing JSON; the requested UI only needs question, query and rows.
- Extra single-class classifier guards, empty link-evaluation guards and the mapped-food-count guard absent from the demos.
- The extra ConfigParser/StringIO mapping configuration builder, replaced with the template's simple configuration string.

Earlier ignored build artifacts and reviewed result snapshots may still contain outputs from the removed wrappers. They are historical evidence, not promised outputs of the simplified runner. Published results have not been silently recalculated or relabelled.

### Course implementation retained

| Area | Source | Retained method and domain adaptation |
| --- | --- | --- |
| Pipeline | Team template `pipeline/run.py` | SQL source, Morph-KGC, SHACL gate, VoID and endpoint loading. Integration invokes the separate course stages in order. |
| Profiling | Session 1 `profiling.py` | Same pandas quality summaries and ydata ProfileReport; USDA tables, output paths and headless figure saving. |
| Mapping | Team template and Session 5 | Same R2RML/Morph-KGC approach; food mapping and single worker for Windows. |
| Validation | Session 4 validator and template gate | Same pySHACL and violation gate, with course subclass-aware focus counting; food shapes and locally resolved imports. |
| Reasoning | Session 3 `local_reasoner.py` | Same catalog/import resolution and HermiT call; FoodOn paths, Java configuration, temporary-file cleanup and Windows file-stream loading. |
| Classification | Session 6 baseline/GNN/helpers | Same logistic regression, GraphSAGE architecture/training loop, splits and metrics. Food replaces order; category replaces customer group. |
| Learning inputs | Session 6 `build_graph.py` | Same RDF-to-HeteroData structure and log1p numeric features. Food/category nodes, high-fat target, non-fat predictors and predictor availability flags adapt the task to this incomplete USDA source. These features are domain adaptations, not literal demo features. |
| Link prediction | Session 6 `link_prediction.py` | Same TransE/popularity, seeds, cold-entity filtering and filtered ranking. Category/food membership replaces plant/product links. |
| English access | Team template and Session 7 | Same VoID grounding, word-overlap example selection, Gemini calls, query checks, two-repair limit, refusal and genuine record/replay. Namespace, dataset, graph path, examples and questions change. |
| Matching | Session 5 `er/match_customers.py` | Same Jaro-Winkler, weighted score and thresholds; food descriptions/categories and NDB-derived truth labels. |
| Provenance | Session 4 `add_provenance.py` | Same PROV-O entities, activities, hashes and derivation; USDA source-table graph names and paths. |
| Ontop | Session 5 PostgreSQL/JDBC/Ontop scripts | Same virtual-mapping approach; food schema, paths, environment credentials and log redaction. |
| Fuseki | Course `demos/fuseki/Dockerfile` | Unchanged course Dockerfile. |

The AST comparisons ignore docstrings/formatting and the domain identifier substitutions: food for order, category for customer/plant, and the corresponding function/argument names. They establish the named bodies, not equality of every adapted file or experimental outcome. The Gemini `ask_model` implementation has a food-project configuration message; its calls/record/replay are retained.

### Necessary project code still present

The following is explicitly identified as project code rather than verbatim demo source:

- `data/prepare.py` and `data/build_sample.py`: select real USDA records and generate the committed SQL sample.
- `data/profiling/data_profile.py`: measure the food constraint inventory.
- `ontology/fetch_ontologies.py`: reproduce the documented FoodOn extract with hash verification. The course fetcher downloads IOF/GS1; this FoodOn-specific downloader is a maintenance adaptation.
- Ontology, shapes, mapping, competency questions, SPARQL, prompt rules, examples and test questions: the team's domain content required by the template.
- Root `run.py`, `index.html`, FoodScope assets, static/API additions in `access-layer/serve.py`, and predefined-answer export: the UI explicitly retained by the user. Secret-file rejection remains necessary when serving project files.
- Named source-graph construction and pipeline stage orchestration: integration needed for the one-command application and course PROV-O demonstration. This orchestration is not claimed to be unchanged template code.
- `mapping/ontop/connection.py` and `mapping/compare_virtualized.py`: local credential/path adapters and comparison evidence around the course runner.
- Regression tests and container/CI dependency adaptations: verification/deployment support, separate from the runtime algorithms.

### Run commands

With the root environment activated:

```powershell
python pipeline/run.py --no-load
python access-layer/serve.py
```

`python run.py` performs those two steps in order through the retained UI adapter. It does not open a browser automatically. Open the printed localhost address. Docker Compose still runs the pipeline and then the UI service.

The separate Session 6 sequence is:

```powershell
python model/build_graph.py
python model/baseline.py
python model/gnn.py
python model/link_prediction.py
```

The access server still supports its existing `PORT` environment setting; there is no custom pipeline port flag.

### Verification after simplification

All 18 regression tests and lint checks passed. The full Docker pipeline exited 0, loaded Fuseki and started the UI. The endpoint returned 358 foods and 350 characterized foods; 13 predefined answers were available. A live protein-above-25-g query returned 29, and hidden-file requests returned 404. The full console log is generated locally at `build/source-alignment-full-run.log`. Hosted CI evidence remains separate.

## Verification status

Template: https://github.com/ahmabboud/kr-team-template, commit `0b1804188bf8c84b41debb523d140abb9aa47bc5`.

| Template requirement | Implementation/evidence | Status |
| --- | --- | --- |
| Root layer folders | data, ontology, shapes, mapping, pipeline, model, access-layer, report, fuseki | Implemented |
| Real committed SQL sample or DB_URL | data/example.sql; template source() function | Local run passed |
| Reused vocabulary, profile, version, CQs, reasoner | Explicit FoodOn module import/catalog; OWL 2 DL version 1.1.0; README competency-question section; reasoner-run.json | Implemented; local HermiT run verified |
| SHACL inventory/triage/gate | README SHACL section, data/constraint_inventory.csv, reports, regression cases | Local pass and rejection cases verified |
| CI gate and hosted blocked commit | Template workflow + regression checks | Workflow added; hosted red/green run not yet collected |
| R2RML materialization | Course Morph-KGC over template SQL source | Local run verified |
| Materialized/virtualized comparison | Course PostgreSQL/Ontop setup and mapping/compare_virtualized.py | Verified for the shared count query: 358 foods in each view; OWL 2 QL warning retained |
| Two-source entity resolution | Real Foundation/SR sample, NDB-labelled truth, course matcher and er/results.json | Measured; imperfect results retained |
| Classification/link prediction and baselines | Course logistic regression, GraphSAGE, TransE and popularity; model/results | Multi-seed runs verified; limitations documented |
| Grounded NL access, refusal and before/after score | Template code, six examples, 11 test questions, real cache and report/access-layer-score.txt | Live smoke tests passed; full recorded evaluation replay verified |
| One-command Compose stack | Template service ordering, root .env, localhost ports | Clean build and full pipeline passed; UI/API and Fuseki checked |
| Report and open problem | README technical explanations and open problem and three primary standards references | Draft completed from measured evidence |
| Individual branches/teammate reviews | Team workflow | Requires actual teammate contributions/reviews; not fabricated by this change |


All 18 regression tests passed, as did the full simplified Docker pipeline. The endpoint returned 358 foods and 350 characterized foods, all 13 predefined answers were available, and a live protein-above-25-g query returned 29. Hosted CI red/green runs and actual teammate reviews remain outstanding. Temporary smoke/audit JSON files were removed after documenting these results here.

## Licences

| Ontology, vocabulary or dataset | Licence/source record | Where used |
| --- | --- | --- |
| USDA Foundation Foods April 2024 | Public domain/CC0; data/manifest.json | Primary source tables, graph and learning inputs |
| USDA SR Legacy April 2018 | Public domain/CC0; mapping/er/sources.json | Real cross-release matching sample |
| FoodOn/BFO asserted ancestor extract | CC BY 4.0; data/FOODON-LICENSE.txt and foodon-source.json | Imported module and local subclass alignment |
| Course template/demo code and UI assets | Original authors credited; source hashes and template commit recorded | Layer implementations; UI reuse permission retained from the original course README |

The [team template](https://github.com/ahmabboud/kr-team-template) and [course demos](https://github.com/ahmabboud/course_knowledge_representation) are implementation sources. Third-party library code remains subject to its own licences; this report does not relicense it.

The access-layer scorer compares sets of returned values rather than ordered rows. An executable query can lose F1 if it projects additional identifiers. When deliberately testing a broken SQL sample, do not regenerate `data/example.sql` from CSVs before the gate test; doing so would replace the intended bad input.
