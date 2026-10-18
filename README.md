# FoodScope: local food composition knowledge graph

FoodScope turns USDA food composition CSVs into RDF, validates the graph with SHACL, applies OWL RL reasoning, and answers SPARQL questions. It runs locally with Python, SQLite, Morph-KGC and RDFLib. The browser interface displays saved query answers using a local HTTP server started by Python. No Docker, external database server or API key is required.

## Setup and run

Install **Python 3.12**, clone this repository, and open PowerShell in the repository root (`knowledge-rep`). The prepared CSVs are included, so a normal run needs no data download.

```powershell
cd food_project
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install --no-deps morph-kgc==2.10.0
.\.venv\Scripts\python.exe run.py
```

Morph-KGC is installed separately because its declared dependency bounds conflict with the RDF library versions used by the project. Keep the pinned versions and separate installation above. Each teammate should create their own environment; `.venv` is not included in Git.

After the pipeline succeeds, a local server starts and your browser opens [http://127.0.0.1:8000/](http://127.0.0.1:8000/). If the browser does not open, use the URL printed in the terminal. Keep the terminal open while using the UI; press **Ctrl+C** to stop the server.

For subsequent runs, from `food_project/`:

```powershell
.\.venv\Scripts\python.exe run.py
```

Optional activation lets you use `python` directly:

```powershell
.\.venv\Scripts\Activate.ps1
python run.py
# After stopping the server with Ctrl+C:
deactivate
```

The commands calling `.venv\Scripts\python.exe` directly work without activation, including when PowerShell blocks `Activate.ps1`.

On macOS/Linux, from the repository root:

```bash
cd food_project
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pip install --no-deps morph-kgc==2.10.0
.venv/bin/python run.py
```

**Command locations:** pipeline, preparation and development commands run from `food_project/`. Manual UI-only server commands run from the repository root, as indicated below.

## Use the interface

A normal run from `food_project/` builds the graph, executes all 13 predefined queries, saves their answers, and starts the UI. With the environment activated:

```powershell
python run.py
```

In the browser:

1. Choose a question from **Choose a question**.
2. Read the result table, with readable headers such as **Food URI**, **Food name** and **Protein (g per 100 g)**. Sodium amounts use mg per 100 g.
3. Expand **View SPARQL query** to inspect the executed query text.
4. Use **Reload results** to fetch the latest saved answers after regenerating them.

The UI reads `food_project/build/answers.json`. Selecting a question and reloading results display saved answers; neither action executes SPARQL or Python. To update answers after changing inputs, mappings, ontology, shapes or queries, stop the server and run `python run.py` again. There is no custom query editor or live SPARQL endpoint.

**Project resources** links to this README, the USDA manifest and the ontology source file. These open source files rather than an interactive data or ontology browser. Missing or invalid query results display a setup message. Generated results are ignored by Git, so each teammate must run the pipeline locally.

### View existing results without rebuilding

From the **repository root** (`knowledge-rep`), run:

```powershell
.\food_project\.venv\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1
```

Open [http://127.0.0.1:8000/](http://127.0.0.1:8000/). Stop the server with **Ctrl+C**. This command needs existing `food_project/build/answers.json`; it does not generate results. Google Fonts require internet for their initial download; the pipeline uses local files.

## Run options

From **`food_project/`**, using the environment directly:

```powershell
# Run the complete pipeline without launching the UI.
.\.venv\Scripts\python.exe run.py --no-ui

# Build, validate and reason without queries or UI launch.
.\.venv\Scripts\python.exe run.py --skip-queries

# Run the pipeline and launch the UI on another port.
.\.venv\Scripts\python.exe run.py --port 8080

# Profile CSVs only; writes profile.json and constraint_inventory.csv.
.\.venv\Scripts\python.exe -m profiling.data_profile

# Show runner options.
.\.venv\Scripts\python.exe run.py --help
```

`--port` accepts 1 through 65535 (default 8000). `--no-ui` and `--skip-queries` both suppress UI launch. If a pipeline stage fails, the UI is not started.

## Folder and file guide

| Path from repository root | Purpose |
| --- | --- |
| `README.md` | Team setup and usage guide (this file). |
| `index.html` | FoodScope interface: predefined query selector, saved results and project resource links. |
| `assets/foodscope.js` | Loads saved answers and renders readable, nutrient-aware table headers and SPARQL text. |
| `assets/foodscope.css` | Query panel and result table styling. |
| `assets/lu.css` | Reused course design styles. Other course JavaScript assets are retained but are not loaded by the FoodScope page. |
| `manifest.webmanifest`, `assets/icon*.svg` | Web app metadata and icons. |
| `sw.js`, `.nojekyll` | Retained static hosting support files. The current page does not register the service worker. |
| `food_project/run.py` | Runs the graph pipeline, then serves the repository on loopback and opens the UI by default. |
| `food_project/requirements.txt` | Pinned dependencies; install Morph-KGC separately as shown above. |
| `food_project/data/` | Prepared input CSVs, preparation script, source manifests and FoodOn license. Included in Git. |
| `food_project/data/prepare.py` | Reads extracted USDA CSVs and writes the compact inputs and manifest into `data/`. |
| `food_project/data/raw/` | Optional local downloads/extracted source files; ignored by Git. |
| `food_project/profiling/` | `data_profile.py` measures source quality and records evidence for constraints. |
| `food_project/mapping/` | `mapping.ttl`: R2RML mappings from four SQLite tables to RDF resources. |
| `food_project/ontology/` | `ontology.ttl`: local OWL vocabulary and embedded FoodOn ancestor extract. |
| `food_project/shapes/` | `shapes.ttl`: SHACL constraints used to validate the graph. |
| `food_project/sparql/` | `queries.sparql`: named SELECT/ASK questions executed by the runner. |
| `food_project/build/` | Automatically created pipeline results; ignored by Git. |
| `food_project/.venv/` | Local Python environment; ignored by Git. |

### Included data

| File in `food_project/data/` | Contents |
| --- | --- |
| `foods.csv` | Food identifiers, descriptions, category references and publication dates. |
| `measurements.csv` | Recorded nutrient amounts linked to food and nutrient identifiers. |
| `nutrients.csv` | Selected nutrient identifiers, names and units. |
| `categories.csv` | USDA category identifiers and descriptions. |
| `manifest.json` | USDA release, download URL, selection, counts and original CSV SHA-256 hashes. |
| `foodon-source.json` | FoodOn source URL, version, retrieval date, source hash and extract scope. |
| `FOODON-LICENSE.txt` | License for reused FoodOn material. |

The included snapshot contains **358 foods and 1,499 observations**. Selected USDA nutrient IDs are protein (`1003`), fat (`1004`), carbohydrate (`1005`), fiber (`1079`), sodium (`1093`) and sugars (`2000`). Amounts are per **100 g edible portion**: sodium uses mg, and the other selected nutrients use g. Missing observations remain unknown; they are not replaced with zero.

## Where results are created

The pipeline is:

```text
Prepared CSVs -> SQLite -> R2RML mapping -> RDF facts
                                         + local ontology/FoodOn extract
                                         -> SHACL validation
                                         -> OWL RL reasoning
                                         -> SPARQL answers
```

All generated pipeline results go to **`food_project/build/`**, relative to the script location. Preparing source data is a separate operation that writes to **`food_project/data/`**.

| File in `build/` | Purpose |
| --- | --- |
| `profile.json` | Source counts, missing nutrient coverage and constraint evidence. |
| `constraint_inventory.csv` | Proposed rules, exception counts, evidence and severity. |
| `food.sqlite` | Four source tables rebuilt from the prepared CSVs. |
| `graph.nt` | Mapped source facts before ontology loading and reasoning. |
| `shape_coverage.json` | Number of target nodes for each SHACL shape. |
| `validation.txt`, `validation.ttl` | Human-readable and RDF SHACL reports. |
| `reasoning.json` | OWL RL counts, inferred characterized foods and contradiction diagnostics. |
| `reasoned.ttl` | Source facts, ontology and inferred triples. |
| `answers.json` | Query text and results for all 13 named questions. |
| `provenance.json` | Successful run time in UTC and SHA-256 hashes of inputs and pipeline files. |

The ontology is loaded before validation. Validation runs before reasoning: completeness warnings are allowed, but violations and empty shape targets stop execution. OWL RL is a rule-based check, not a complete OWL DL/HermiT consistency check. Queries run against the inferred graph, which is also persisted as `reasoned.ttl`.

Runs overwrite their corresponding outputs and rebuild SQLite. Failed or query-skipped runs can leave older files in `build/`; check the console result and timestamps before sharing results. Successful pipeline completion prints `Done. Results are in build/.`. A normal run then prints the UI URL and stays running until Ctrl+C; `--no-ui` and `--skip-queries` exit after the pipeline.

## Download and rebuild USDA inputs (optional)

Normal runs use the committed CSVs. To reproduce preparation, download the **April 2024 Foundation Foods CSV release** recorded in `data/manifest.json`:

- [Original USDA ZIP](https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_csv_2024-04-18.zip)
- [USDA dataset downloads](https://fdc.nal.usda.gov/download-datasets/)

Download and extract the archive manually. Pass the directory directly containing `food.csv`, `food_nutrient.csv`, `nutrient.csv` and `food_category.csv`:

```powershell
# Replace the example with your extracted source directory.
.\.venv\Scripts\python.exe data/prepare.py --source "C:\datasets\FoodData_Central_foundation_food_csv_2024-04-18"
.\.venv\Scripts\python.exe run.py
```

Alternatively, place the extracted files in this layout:

```text
food_project/data/raw/usda/<release-folder>/food.csv
food_project/data/raw/usda/<release-folder>/food_nutrient.csv
food_project/data/raw/usda/<release-folder>/nutrient.csv
food_project/data/raw/usda/<release-folder>/food_category.csv
```

Then run:

```powershell
.\.venv\Scripts\python.exe data/prepare.py
```

Without `--source`, preparation uses the first sorted `data/raw/usda/*/food.csv` match. Use `--source` when several releases are present. Preparation overwrites the four prepared CSVs and `data/manifest.json`; it does not download or extract anything. The raw files are not required for subsequent normal runs. USDA data is public domain/CC0; attribution: USDA FoodData Central.

## Ontology reuse and where it is used

The local namespace is `https://ul.edu.lb/kr/food#`. `mapping/mapping.ttl` creates instances of `food:Food`, `food:Category`, `food:Nutrient` and `food:Observation`. `run.py` adds **`ontology/ontology.ttl`** to the mapped graph before validation and reasoning.

The ontology already embeds a FoodOn ancestor extract and connects the local food class through:

```text
food:Food
  -> FOODON_00001002 (food product)
  -> FOODON_00002403 (food material)
  -> BFO_0000040 (material entity)
```

Reasoning uses this hierarchy, property domains/ranges, inverse properties and the definition of `food:CharacterizedFood` (a food with an observation). SPARQL questions use the resulting graph. The project does not assign each USDA food to a specific FoodOn product class.

The extract contains asserted named ancestors and annotations; full FoodOn imports, restrictions and disjointness are not copied. It is embedded in `ontology.ttl`. No separate `foodon-module.ttl` is required at runtime, despite the historical comment in the ontology.

- [FoodOn project](https://foodon.org/)
- [FoodOn OWL source](https://raw.githubusercontent.com/FoodOntology/foodon/master/foodon.owl)
- [Recorded version: 2026-09-20](http://purl.obolibrary.org/obo/foodon/releases/2026-09-20/foodon.owl)

`data/foodon-source.json` records the retrieval date and source hash. The upstream `master` URL can change; use the recorded version when tracing the extract. FoodOn material is attributed to the FoodOn consortium under CC BY 4.0; see `data/FOODON-LICENSE.txt`. Normal runs need no FoodOn download or network access.

## Troubleshooting and development

| Symptom | What to check |
| --- | --- |
| Cannot find `run.py` or `requirements.txt` | Run `cd food_project` from the repository root first. |
| `No module named morph_kgc` | Run the separate Morph-KGC installation using the same `.venv` Python. |
| Missing prepared CSV | Restore committed inputs or rebuild them with `data/prepare.py --source ...`. |
| Preparation cannot find `food.csv` | Pass its containing directory directly, or use the documented raw-data layout. |
| SHACL gate fails | Read `build/validation.txt` and `build/shape_coverage.json`. |
| Reasoning reports a contradiction | Read `build/reasoning.json`. |
| UI port is already in use | Stop the earlier server, or run `python run.py --port 8080` with the environment activated. |
| Browser does not open automatically | Open the UI URL printed in the terminal. |
| UI cannot load results | Run the full pipeline, serve the repository root over HTTP, and enable JavaScript. |
| UI shows older answers | Rerun the full pipeline, then click **Reload results** or refresh the page. |
| Headers still show `f` or `a` | Refresh the page to load the updated `assets/foodscope.js`. |

Format/check Python files from `food_project/`:

```powershell
.\.venv\Scripts\python.exe -m ruff format data/prepare.py profiling/data_profile.py run.py
.\.venv\Scripts\python.exe -m ruff check --select E4,E7,E9,F,I data/prepare.py profiling/data_profile.py run.py
```

Commit source changes and intentionally updated prepared inputs. `.gitignore` excludes generated results, raw downloads and virtual environments. Share generated results separately when needed.

The active repository focuses on preparation, profiling, relational mapping, ontology, constraints, reasoning and SPARQL. Earlier Docker, web/LLM, HermiT, entity-resolution and graph-learning layers are not included here. The R2RML/source naming method follows the instructor course/template. The archive mentioned in previous documentation is not included in this checkout.

## Attribution

UI styling is adapted from the [Knowledge Representation course](https://github.com/ahmabboud/course_knowledge_representation). Its original README permits reuse and adaptation of the template, stylesheet and runtime; course content belongs to its authors. Lecture sessions, course guides and defense pages are not included here. USDA and FoodOn source/license information is documented above and in `food_project/data/`.
