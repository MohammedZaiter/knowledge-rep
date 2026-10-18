# FoodScope

FoodScope is a USDA food-composition knowledge graph built using the [course team template](https://github.com/ahmabboud/kr-team-template) and its lecture/demo code. It maps relational data with Morph-KGC, validates it with SHACL, runs HermiT, evaluates graph models, and answers English questions with the course Gemini access layer.

The repository follows the template's root folders and three-service Compose stack. [COURSE_CODE_SOURCES.json](COURSE_CODE_SOURCES.json) records source files, hashes and the template commit. [report/TEMPLATE_COMPLIANCE.md](report/TEMPLATE_COMPLIANCE.md) distinguishes verified behavior from remaining checks.

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

The first build downloads the course dependencies. Profiling and multi-seed learning runs take longer than a query-only run. The clean Docker build and full container pipeline were verified on 18 October 2026. Fuseki returned 358 foods and 350 inferred characterized foods; the UI, predefined answers, live natural-language count and unsupported-price refusal passed. All 18 regression tests also passed in the Linux image. Evidence: [deployment smoke results](report/deployment-smoke.json).

## Run locally with Python

Use **Python 3.12** and **Java 21**. From the repository root:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r pipeline/requirements-pipeline.txt
.\.venv\Scripts\python.exe -m pip install --no-deps morph-kgc==2.10.0
.\.venv\Scripts\Activate.ps1
python run.py
```

`python run.py` runs the local pipeline, skips Fuseki loading, starts the UI and opens your browser. Keep the terminal open; **Ctrl+C** stops the server. If automatic opening fails, use the printed URL. Java must be on `PATH`, or set `JAVA_EXE` in the root `.env`. An existing portable JDK under `.tools/java/*/bin/java.exe` is also detected on Windows; it is not committed.

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

All commands below run from the **repository root**, with the environment activated.

| Command | Behavior |
| --- | --- |
| `python run.py` | Local pipeline and UI; no Fuseki required. |
| `python pipeline/run.py` | Template pipeline, including loading Fuseki; exits afterward. |
| `python pipeline/run.py --no-load` | Full local pipeline without loading an endpoint or starting the UI. |
| `python pipeline/run.py --no-load --ui` | Explicit local pipeline and UI. |
| `python run.py --skip-learning --skip-profile` | Faster graph/query/UI rebuild; still generates the constraint inventory. |
| `python run.py --no-ui` | Local pipeline only. |
| `python run.py --port 8080` | Local UI on a different port. |
| `python pipeline/run.py --no-load --skip-queries --skip-learning --skip-profile` | Map, validate, reason and record provenance; query answers are not refreshed; VoID/provenance are rebuilt. |
| `python -m data.profiling.data_profile` | Constraint inventory and compact source profile only. |
| `python model/run_learning.py` | Rebuild learning data and run the course learning experiments. |
| `python mapping/er/match_foods.py` | Measure cross-release matching at the course thresholds. |
| `python pipeline/run.py --help` | Show available flags. |

A failed gate stops reasoning, querying, endpoint loading and UI launch. A skipped or failed run can leave earlier artifacts; check timestamps and completion messages. Pipeline results are snapshots, not automatic live updates.

## Repository structure

| Folder/file | Purpose |
| --- | --- |
| `data/` | Prepared USDA CSVs, source/license records and `example.sql`, the real SQL sample loaded by the template. |
| `data/prepare.py`, `data/build_sample.py` | Rebuild compact CSVs and the SQL sample from original downloaded tables. |
| `data/profiling/` | Course ydata-profiling adaptation and the food-specific constraint inventory. |
| `ontology/` | Local OWL extension, imported FoodOn module, offline catalog, fetcher and course HermiT runner. |
| `shapes/` | SHACL constraints and [triage](shapes/triage.md). |
| `mapping/` | R2RML mapping, course database loader, Ontop comparison and two-source matching evidence. |
| `pipeline/` | Template pipeline, dependency pins, Dockerfile, course validator and PROV-O generator. |
| `model/` | Course logistic baseline, GraphSAGE and TransE adaptations; reviewed outputs in `model/results/`. |
| `access-layer/` | Template Gemini code, `prompt_rules.txt`, six examples, 11 held-out questions and genuine recorded replies. |
| `report/` | Technical report, template status and evaluation evidence. |
| `fuseki/` | The template's Apache Fuseki Dockerfile. |
| `.github/workflows/` | Template SHACL workflow with Java/CPU dependencies and regression checks. |
| `sparql/queries.sparql` | The 13 predefined questions. |
| `index.html`, `assets/` | FoodScope UI and reused course styling. |
| `build/` | Generated graph, reports, query answers and training data; ignored by Git. |
| `.env.example` | Shareable configuration names; `.env` contains local secrets and is ignored. |
| `run.py` | Local UI launcher around the canonical pipeline. |

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
| `answers.json`, `query-timings.json` | Predefined query text, rows and execution timings. |
| `void.ttl` | Class/property description used to ground the access layer. |
| `provenance.json`, `provenance.ttl` | Input/code hashes and course PROV-O source/run records. |
| `learning/` | PyTorch graph, per-experiment logs and multi-seed summaries. |
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

The recorded version URL returned 404 during verification; the recorded source URL succeeded with the expected hash. The fetcher accepts that fallback only when its SHA-256 matches. Normal pipeline runs use the committed module offline. See [ontology/competency_questions.md](ontology/competency_questions.md) for question-to-vocabulary traceability.

## Evaluation and template integration

The course GraphSAGE and TransE code is adapted to food data; no replacement model or retrieval algorithm is used. The classification task is **fat > 20 g per 100 g**. Fat itself is excluded from predictors; missing labels are excluded. Both random and category-held-out splits are reported. See [model/README.md](model/README.md) for leakage controls and results.

The template access layer is configured through `NS`, `PFX`, `prompt_rules.txt`, `examples.ttl` and `questions.yaml`. To reproduce the recorded evaluation without new API calls:

```powershell
$env:LLM_MODE="replay"
$env:VOID_FILE=(Join-Path (Get-Location) "report/access-layer-void.ttl")
python access-layer/evaluate.py
Remove-Item Env:LLM_MODE
Remove-Item Env:VOID_FILE
```

For a new live, recorded evaluation, set `LLM_MODE="record"` instead. The cache matches the exact model and prompt; changing rules/schema/examples invalidates affected recordings. The measured run and its limitations are in [report/access-layer-score.txt](report/access-layer-score.txt).

The course PostgreSQL/Ontop comparison commands are in [mapping/README.md](mapping/README.md). The PostgreSQL/Ontop count comparison has passed (358 foods in both views). Ontop warns that the CharacterizedFood equivalence is outside OWL 2 QL, so this is not proof of full reasoning equivalence. The clean Compose startup is being verified separately; see the status file.

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
| Port occupied | Use `python run.py --port 8080` or stop the earlier server. |
| Docker cannot connect | Start Docker Desktop's engine before running Compose. |

Generated build/raw/environment files stay out of Git. Reviewed experiment outputs, the genuine replay cache and source manifests are intentionally shareable. Never commit `.env` or generated JDBC credentials.

## Attribution

Pipeline/access code follows [kr-team-template](https://github.com/ahmabboud/kr-team-template) and the [course demos](https://github.com/ahmabboud/course_knowledge_representation). UI styles are adapted from the course, whose README permits reuse/adaptation of its template, stylesheet and runtime. Course content belongs to its authors. USDA data is public domain/CC0; FoodOn material is CC BY 4.0 with attribution to the FoodOn consortium. See `data/FOODON-LICENSE.txt` and the report licence table.

For score replay, the archived VoID context is pinned in `report/access-layer-void.ttl`, with context hashes in `report/access-layer-context.json`. The original template SAMPLE-based generator is retained; regenerating VoID can change the exact prompt.
