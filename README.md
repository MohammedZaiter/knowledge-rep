# FoodScope: a small local KRR project

The active code is grouped by purpose, with seven core files:

```text
food_project/
    run.py
    data/
        prepare.py
        foods.csv
        measurements.csv
        nutrients.csv
        categories.csv
    profiling/
        data_profile.py
    mapping/
        mapping.ttl
    ontology/
        ontology.ttl
    shapes/
        shapes.ttl
    sparql/
        queries.sparql
    build/              # Generated results
    requirements.txt
    README.md
```

## Run

From this folder, using the existing environment:

```powershell
.venv/Scripts/python.exe run.py
```

No Docker, web server, API key, Fuseki or external database is needed. Queries run locally with RDFLib. The existing environment was preserved when the project was moved from Desktop to Documents.

To profile without running the graph pipeline:

```powershell
.venv/Scripts/python.exe -m profiling.data_profile
```

To rebuild the prepared CSVs from the downloaded USDA archive:

```powershell
.venv/Scripts/python.exe data/prepare.py
# Or: .venv/Scripts/python.exe data/prepare.py --source "PATH/TO/EXTRACTED/USDA/FOLDER"
```

Downloading/extracting the original archive is separate from preparation. Normal runs use the compact CSVs already included under data/.

## Install on a new computer

Use Python 3.12. Morph-KGC is installed separately because its dependency bounds conflict with the RDF versions used by the course:

```powershell
py -3.12 -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install --no-deps morph-kgc==2.10.0
.venv/Scripts/python.exe run.py
```

## Outputs and interpretation

- `profile.json` and `constraint_inventory.csv`: evidence for the rules.
- `food.sqlite`: four source tables, rebuilt from CSVs.
- `graph.nt`: mapped source facts; 9,359 triples for this snapshot.
- `validation.txt` / `validation.ttl`: the complete SHACL report.
- `shape_coverage.json`: nonempty targets for each shape.
- `reasoning.json` / `reasoned.ttl`: OWL RL diagnostics and persisted inferred facts.
- `answers.json`: query text and result rows for all 13 questions.
- `provenance.json`: run time and SHA-256 hashes of inputs/code.

Amounts are per 100 g edible portion; sodium uses mg and other selected nutrients use g. Missing nutrient observations remain unknown. Validation runs before reasoning, so inferred types cannot hide mapping defects. Completeness warnings pass; violations stop execution. OWL RL is a rule-based check, not a complete OWL DL/HermiT validation. Queries use the persisted inferred graph, so the characterized-food query includes derived membership.

## Scope and previous version

The earlier Docker, web/LLM, HermiT, entity-resolution and graph-learning layers, reports, and previous generated results are preserved in `../archive/food_project_previous/`. They are outside the active project. This simplified version focuses on data preparation, profiling, relational mapping, ontology, constraints, reasoning and SPARQL; it does not contain all layers of the original six-part defense rubric.

Source: USDA FoodData Central, April 2024 Foundation Foods (public domain/CC0). FoodOn ancestor extract: FoodOn consortium, CC BY 4.0, source/version/hash in data/foodon-source.json. The R2RML and source naming method follow the instructor course/template; original attribution is preserved in the archive.

## Formatting

Python files are formatted with Ruff, including expanded statements, consistent indentation and blank lines between functions. To format/check again:

```powershell
.venv/Scripts/python.exe -m ruff format data/prepare.py profiling/data_profile.py run.py
.venv/Scripts/python.exe -m ruff check --select E4,E7,E9,F,I data/prepare.py profiling/data_profile.py run.py
```
