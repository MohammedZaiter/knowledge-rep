# Technical report: FoodScope

Implementation review: 2026-10-18. Structure follows `kr-team-template` commit `0b1804188bf8c84b41debb523d140abb9aa47bc5`. This report describes measured local behavior and marks deployment checks that have not passed. Evidence files, rather than planned features, support the numbers below.

## 1. Problem framing and scope

FoodScope answers questions about a fixed USDA food-composition release: food identity/category, recorded nutrient quantities and units, thresholds/rankings, missing observations, publication dates and inferred characterized-food membership. Six competency-question families and their vocabulary/query links are documented in `ontology/competency_questions.md`.

The system is a composition-data demonstration. It does not contain prices, allergens, personal records or disease-treatment evidence, and those questions are part of the refusal test set. Prediction experiments are separate from factual graph answers. They are not nutrition or medical recommendations.

## 2. Data understanding and constraint discovery

The primary snapshot is April 2024 USDA Foundation Foods: 358 foods, 1,499 observations, six selected nutrient definitions and 28 category definitions. A food row identifies a USDA food; a measurement row records one food/nutrient amount per 100 g edible portion. Sodium uses MG; the other selected nutrients use G. Missing observations are not replaced with zero.

`data/manifest.json` records the archive and original-table hashes. `data/example.sql` is generated directly from the committed CSVs and provides the template's clean-checkout source. The Session 1 ydata-profiling adaptation generates four HTML reports. `data/constraint_inventory.csv` preserves the measured rule inventory: no exceptions to C1–C6 or C8; 353 foods have incomplete six-nutrient panels under C7. These are retained as warnings.

The separate entity-resolution sample uses actual Foundation and SR Legacy rows. Its 32 shared-NDB labels and eight non-shared-NDB labels are independent of the matcher's description/category features. Source hashes and the precise meaning of a gold match are in `mapping/er/sources.json`.

## 3. Ontology

FoodOn fits the food-product domain. `food:Food rdfs:subClassOf obo:FOODON_00001002` aligns the local class to food product. The imported asserted module continues through food material to BFO material entity. We do not claim to import the whole FoodOn ontology or assign each food to a detailed FoodOn product category.

The local extension adds Food, Category, Nutrient, Observation and CharacterizedFood, their composition properties, and `food:answersCQ` traceability annotations. CharacterizedFood is equivalent to a Food with an Observation. The declared profile is OWL 2 DL, checked using the course's HermiT/owlready2 code, with offline imports resolved by the catalog. Version 1.1.0 identifies the explicit module import and publication datatype change. Publication dates are represented at midnight as xsd:dateTime because HermiT rejects xsd:date; this does not assert that midnight was an observed publication time.

The reviewed HermiT diagnostics are `ontology/reasoner-run.json`. The run found no inconsistent ontology or impossible local classes, and classified 350 foods as characterized. HermiT preserves direct types and the hierarchy; an ancestor query should follow rdf:type/rdfs:subClassOf*, rather than assuming every ancestor type is explicitly materialized.

The FoodOn fetcher verifies the recorded SHA-256 before replacing the module. The recorded version URL returned 404; the recorded original source URL produced the expected bytes. The module and source/license records are committed for offline normal runs.

## 4. Constraint validation with SHACL

`shapes/shapes.ttl` and `shapes/triage.md` connect the rules to their severity and rationale. These are closed-world source checks; OWL's open-world semantics do not make absent names, observations or references erroneous by themselves.

The current snapshot passes with 0 violations and 353 completeness warnings. The pipeline includes the vocabulary while validating and runs validation before reasoning. The course target-count routine follows subclasses; an empty target is rejected. Tests demonstrate that a negative amount fails, warnings pass, and an empty target fails. Reports are saved before a violation stops execution.

The workflow follows the template and runs the pipeline with --no-load before regression checks. Local negative tests are not a substitute for hosted CI evidence: no GitHub Actions red/green run is claimed until the workflow is pushed and executed.

## 5. Operational data integration

The template source() function loads the real SQL sample into SQLite, or accepts DB_URL. Morph-KGC executes the R2RML mapping. The current source produces 9,359 mapped triples. IRIs encode kind, USDA source and source key. The mapping's food view converts publication-date representation; raw source strings are preserved. Four named source-table graphs support the Session 4 PROV-O explanation of where a food-name fact originated.

Materialization is the deployed choice for this small release snapshot: it permits a gate over the complete graph, repeatable outputs and local use. Its tradeoff is staleness until a rebuild. The course PostgreSQL/Ontop CLI comparison is adapted under `mapping/ontop/`, with a shared count query and an equality/timing recorder. The shared count-query comparison passed: both views return 358 foods (`mapping/virtualization-comparison.json`). The generated PostgreSQL SQL is preserved in the run log. This is a single-query check, not full graph/query equivalence. Ontop warns that CharacterizedFood equivalence is outside OWL 2 QL; the deployed materialized view retains HermiT classification. The timing file includes JVM startup for Ontop and excludes load time for the already loaded Oxigraph query, so it is not an engine-only latency comparison.

The course Fellegi-Sunter/Jaro-Winkler matcher compares 40 real SR records with 358 Foundation candidates, blocked by category (1,540 candidate pairs). Threshold 4 yields precision 0.684 and recall 0.406; threshold 8 yields precision 0.706 and recall 0.375 (`mapping/er/results.json`). The inherited stated weights are not calibrated for food descriptions. Gold identity is a corresponding NDB concept, not equal nutrient composition; mismatches are recorded, not silently turned into owl:sameAs facts. These results expose limits of transferring customer-matching weights to foods.

## 6. Prediction and evaluation honesty

The Session 6 data conversion, logistic regression, GraphSAGE, TransE and split/ranking code is reused with domain adaptations recorded in `COURSE_CODE_SOURCES.json`. All reviewed outputs and package versions are saved in `model/results/`.

Classification predicts fat >20 g per 100 g. There are 348 labelled foods, including 55 positives; 10 missing-fat foods are excluded. Predictors are non-fat nutrient log1p amounts and availability flags. Category membership supplies the graph structure/group split. Fat is stored separately only for the intentional leak demonstration. No target amount, food name or source identifier becomes a predictor.

The leaky logistic-regression demonstration reaches PR-AUC 1.000, illustrating why that feature must be removed. Random-split scores are shown but are not the generalization claim. Across the four scoreable category-held-out seeds, mean PR-AUC is 0.392 (population SD 0.260) for logistic regression and 0.440 (SD 0.325) for GraphSAGE. The fifth seed has no positive test foods and is explicitly unscoreable. These high variances and the small sample do not establish reliable superiority. Publication dates describe releases, so category grouping is used to test new food groups; this is not a forecasting claim.

Link prediction hides category-contains-food links, retaining observed nutrient links and withholding inverse membership. Three seeds use the course TransE and filtered ranking protocol. Mean MRR is 0.339 for TransE versus 0.448 for popularity. Cold held-out entities are excluded and counted. The graph model loses to the baseline, which is reported rather than concealed. Classification and link prediction are transductive experiments, not validated inductive production models.

## 7. Access layer

The active implementation comes directly from the team template, configured through NS/PFX, prompt_rules.txt, six examples and 11 held-out questions. The graph description is VoID. The course lexical retrieval picks three examples; property/class checks and up to two repairs precede query execution, or the model refuses.

The configured model was gemini-3.5-flash-lite. Live replies were recorded on 2026-10-18 and replayed under the template implementation. The test set contains eight answerable questions and three questions requiring refusal. Mean course set-of-values F1 is 0.856 with schema only, 0.954 with examples and 0.954 with checking/repair. All three required refusals were correct, with no wrong refusal of an answerable question. No successful answer in this recorded run required repair; a regression test separately verifies the repair branch.

The remaining score error includes projecting identifiers as well as requested names. This illustrates a metric/semantic issue rather than a parser failure. A real live smoke test returned 358 foods and refused a price question with reason `price`. `report/access-layer-score.txt`, its JSON metadata and the genuine prompt-keyed cache preserve evidence. Replay is exact for this prompt/model/schema setup; it is not evidence of another fresh live run or arbitrary question coverage.

## 8. Deployment and reproducibility

The root Compose file is adapted from the actual team template: Fuseki, a one-shot pipeline, then an access service dependent on pipeline success. Host ports bind to 127.0.0.1. Root .env stores secrets and is excluded from Git/images. Static UI serving denies hidden paths. No key is present in the reviewed tracked/shareable files.

`python pipeline/run.py --no-load` has been run locally with profiling, mapping, gate, HermiT, all learning experiments, predefined queries, VoID and provenance. `python run.py` adds a local UI shortcut; the legacy launcher remains available. The saved query display and natural-language API share the same validated snapshot. Source, package and input hashes are recorded; the reviewed run outputs are committed separately from ignored build artifacts.

A clean Compose build and full container pipeline passed on 18 October 2026. Fuseki returned 358 foods and 350 inferred characterized foods. The served UI/assets, predefined answers, live natural-language count, unsupported-price refusal and hidden-file rejection passed; all 18 regression tests passed in the Linux image. Evidence is in deployment-smoke.json. The Ontop/PostgreSQL count comparison also passed with the limits described above. Hosted red/green CI runs and actual teammate reviews still need evidence; a local gate failure does not establish a hosted red CI run.

## 9. Open problem: does a valid query answer the intended question?

Our position is that schema grounding and query repair are necessary but insufficient for faithful natural-language answers. The recorded run contains executable queries using real vocabulary that still return the wrong projection for the requested question.

SPARQL defines how graph patterns and projections produce answers; it does not establish that a generated query expresses a user's intent. This explains why two syntactically valid queries can differ in the values they return. [W3C SPARQL 1.1 Query Language](https://www.w3.org/TR/sparql11-query/)

SHACL checks graph constraints against shapes. A dataset passing those checks can still be queried incorrectly, so a validation gate cannot certify language-to-query correctness. [W3C SHACL Recommendation](https://www.w3.org/TR/shacl/)

OWL defines the structural semantics used for ontology reasoning. Consistency and inferred types likewise do not settle whether the model chose the right nutrient, threshold, projection or missing-data interpretation. [W3C OWL 2 Structural Specification](https://www.w3.org/TR/owl2-syntax/)

For this system we therefore retain explicit questions, gold queries, refusals, generated SPARQL and measured answer scores. Future work should test paraphrases, variable projection, zero versus missing values and distribution changes, while distinguishing data validation, inference and question fidelity. We have not implemented or measured that future work.

## Licences

| Ontology, vocabulary or dataset | Licence/source record | Where used |
| --- | --- | --- |
| USDA Foundation Foods April 2024 | Public domain/CC0; data/manifest.json | Primary source tables, graph and learning inputs |
| USDA SR Legacy April 2018 | Public domain/CC0; mapping/er/sources.json | Real cross-release matching sample |
| FoodOn/BFO asserted ancestor extract | CC BY 4.0; data/FOODON-LICENSE.txt and foodon-source.json | Imported module and local subclass alignment |
| Course template/demo code and UI assets | Original authors credited; source hashes and template commit recorded | Layer implementations; UI reuse permission retained from the original course README |

The [team template](https://github.com/ahmabboud/kr-team-template) and [course demos](https://github.com/ahmabboud/course_knowledge_representation) are implementation sources. Third-party library code remains subject to its own licences; this report does not relicense it.
