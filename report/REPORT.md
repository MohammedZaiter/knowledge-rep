# Technical report: FoodScope

**Team:** Mohammed Zaiter, Ali Tarhini
**System:** a knowledge graph of USDA food composition data, reusing FoodOn,
validated with SHACL, reasoned with HermiT, and queried in SPARQL or in English.

This report documents what is deployed in this repository. Every number is
quoted from a file in the repository, named next to it.

## 1. Problem framing and scope

A nutritionist or a food scientist wants to ask questions such as "which
foods have more than 20 g of fat per 100 g?" or "which foods have no sodium
measurement?". USDA FoodData Central publishes the answers, but as CSV files
in which one food's composition is spread over many rows, nutrients are
identified by numbers, and a missing value looks the same as a value that was
never measured. FoodScope turns those tables into a graph that answers these
questions directly, says which facts it holds and which it does not, and
refuses questions it cannot answer.

The questions the system must answer are six competency questions
([ontology/competency_questions.md](../ontology/competency_questions.md)):
identify a food (CQ1), its category (CQ2), how much of a nutrient it contains
and in which unit (CQ3), which foods pass a nutrient threshold (CQ4), which
foods were published from a date (CQ5), and which foods have any recorded
composition (CQ6). Each is tested by a query in
[sparql/queries.sparql](../sparql/queries.sparql); the 13 queries return
answers on the deployed graph (`build/answers.json`) and take between 0.07 and
2.15 ms each in Oxigraph ([sparql/query-timings.txt](../sparql/query-timings.txt)).

**Scope.** Six nutrients (protein 1003, fat 1004, carbohydrate 1005, fiber
1079, sodium 1093, sugars 2000), amounts per 100 g edible portion, from the
April 2024 Foundation Foods release: 358 foods, 1,499 observations, 28
category definitions ([data/README.md](../data/README.md)).

**Left out, and why.** Price, allergens, health claims and recipes: no
competency question needs them and the source does not hold them, so the
access layer refuses them (section 7). The other nutrients of FoodData
Central: six cover the questions above and keep the sample small enough to
validate in CI on every push. Branded foods and the full SR Legacy release:
we use SR Legacy only as the second source for entity resolution (section 5).

**Why a graph, and why RDF.** The questions cross three kinds of thing
(foods, nutrients, categories) through measurements, and the graph keeps a
measurement as its own node with its food, nutrient and amount. We chose RDF
over a property graph because the system relies on three things a property
graph does not give us as standards: reuse of a published ontology (FoodOn),
a reasoner that classifies foods from a definition, and SHACL validation
before loading. The cost is a more verbose query language; the access layer
(section 7) is our answer to that cost.

## 2. Data understanding and constraint discovery

**Source.** USDA FoodData Central, Foundation Foods, April 2024 release,
public domain (CC0) ([data/manifest.json](../data/manifest.json), with the
download URL and the hashes of the original files). One row of `foods.csv` is
one food (`fdc_id`, description, category, publication date); one row of
`measurements.csv` is one amount of one nutrient for one food, per 100 g
edible portion. `data/prepare.py` selects the records from the original CSVs;
`data/example.sql` holds the same tables for the pipeline and CI.

**Profiling.** `data/profiling/source_profile.py` produces ydata-profiling
reports per table (regenerated, not committed). The finding that shaped the
rest of the system is missingness by nutrient (`build/profile.json`): of the
358 foods, 353 have no sugars value, 177 no fiber, 49 no sodium, 48 no
carbohydrate, 12 no protein and 10 no fat; 8 foods have no observation at all.

**Constraint inventory** ([data/constraint_inventory.csv](../data/constraint_inventory.csv),
counted by `data/profiling/data_profile.py`):

| Rule | Evidence in the data | Source |
|---|---|---|
| C1 one unique numeric `fdc_id` per food | 0 of 358 foods break it | foods.fdc_id |
| C2 one nonempty description per food | 0 of 358 foods break it | foods.description |
| C3 every category reference resolves | 0 of 358 foods break it | foods → categories |
| C4 nutrient amounts are nonnegative | 0 of 1,499 observations break it | measurements.amount |
| C5 one amount per food and nutrient | 0 of 1,499 observations break it | measurements (food, nutrient) |
| C6 a gram amount is at most 100 g per 100 g | 0 of 1,190 gram observations break it | measurements + nutrient unit |
| C7 every food has all six selected nutrients | **353 of 358 foods break it** | foods → measurements |
| C8 an observation references an existing food and nutrient | 0 of 1,499 observations break it | measurements.food_id, nutrient_id |
| C9 one publication date per food | 0 of 358 foods break it | foods.publication_date |
| C10 nutrients and categories are named; units are G or MG | 0 of 34 reference rows break it | nutrients, categories |

**A constraint found false in the data: C7.** We expected every food to
have all six nutrients. 353 of 358 do not. USDA Foundation Foods analyses
selected nutrients per food, so a missing value means "not analysed". We
report the rule rather than drop it, keep it as a Warning (section 4), and
never fill a missing value with 0.

## 3. Ontology

**Reused vocabulary: FoodOn** (CC BY 4.0). Our `food:Food` is a subclass of
FoodOn's *food product* (`obo:FOODON_00001002`). FoodOn fits because it is the
OBO Foundry ontology for food products, and its *food product* means what a
USDA food record describes: "food material for humans and animals which is
processed with the intention that it be consumable" (its definition, in
`ontology/foodon-module.ttl`). We do not import all of FoodOn: we import a
documented extract,
[ontology/foodon-module.ttl](../ontology/foodon-module.ttl), with the three
asserted ancestors (food product, food material, material entity) and their
source release, resolved offline through `ontology/catalog-v001.xml`, as
Protégé does. `ontology/fetch_ontologies.py` rebuilds the extract from the
release recorded in [data/foodon-source.json](../data/foodon-source.json).

**Alignment outward.** `food:Food rdfs:subClassOf obo:FOODON_00001002`; through
the module, our foods are also food materials and BFO material entities.
FoodOn has no classes for a nutrient measurement or a USDA category, so we
added them.

**Our extension** ([ontology/ontology.ttl](../ontology/ontology.ttl)): Food,
Category, Nutrient, Observation, and CharacterizedFood, defined as
`Food and (hasObservation some Observation)`. Observation is its own class
because CQ3 and CQ4 need the food, the nutrient and the amount together; a
property per nutrient could not say which nutrients were never measured.
Every class and property carries `food:answersCQ` with the competency
questions it answers; Category, Nutrient and Observation are pairwise
disjoint with Food.

**OWL profile: OWL 2 DL.** Not EL, because `food:hasObservation` and
`food:ofFood` are inverse properties; not QL, because the CharacterizedFood
definition is an intersection with an existential restriction (Ontop rejects
it as outside QL, `mapping/virtualization-comparison.json`). We therefore use
HermiT, a DL reasoner.

**Reasoner run** ([ontology/reasoner-run.txt](../ontology/reasoner-run.txt),
dated 2026-10-18): HermiT on the mapped graph with the ontology and the
FoodOn module, 9,459 triples in, 10,615 after reasoning; consistent; no
impossible class. HermiT classifies 350 foods as CharacterizedFood. The other
8 foods have no observation and stay unclassified: under the open world
assumption the graph does not claim they have none.

**What the reasoner does not do for us.** HermiT writes back only the most
specific new type (CharacterizedFood), and Fuseki applies no `rdfs:subClassOf`
inference, so a query for `?x a obo:FOODON_00001002` finds no food in the
endpoint. Our FoodOn reuse is at the level of the schema (the axiom and the
import), not materialized on every instance. Adding the superclass types to
the loaded graph, or loading Fuseki with RDFS inference, would close this.

**Version IRI.** `https://ul.edu.lb/kr/food/1.1.0`, with
`owl:priorVersion <https://ul.edu.lb/kr/food/1.0.0>`; its `owl:versionInfo`
records that 1.1.0 introduced the imported FoodOn module. Version 1.0.0
predates this repository's history.

## 4. Constraint validation with SHACL

**The shapes** ([shapes/shapes.ttl](../shapes/shapes.ttl)) cover every rule of
the inventory, C1 to C10. Each check has an `sh:message` with its rule id and a
severity that says what the pipeline does: a Violation stops the load; a
Warning is reported and the data is kept. C1 (uniqueness), C5 (one amount per
food and nutrient) and C6 (the gram limit depends on the nutrient's unit) need
SHACL-SPARQL; the rest are core SHACL. The pipeline also fails when a shape
has no focus nodes, because a wrong target class would validate nothing and
pass silently (`build/shape_coverage.json`: 358 foods, 1,499 observations,
6 nutrients, 28 categories).

**Why SHACL and not OWL.** Each rule says what the data must contain, which
is a closed-world question: a missing name or amount must be a failure. OWL is
open world, where a missing value is unknown, so OWL cannot reject it. Two
cases make the difference concrete: for C3 and C8, an OWL `rdfs:range` would
*infer* that a dangling reference is a Category or a Food instead of rejecting
it; for C1, `owl:hasKey` without the unique name assumption would infer that
two foods with one id are the same food, not that the data is wrong. What must
hold for *reasoning* (domains, disjointness, the CharacterizedFood
definition) stays in OWL. The rule-by-rule argument is in
[shapes/triage.md](../shapes/triage.md).

**Triage.** On the real data the gate reports 0 Violation and 353 Warning
(`build/shacl-report.txt`), all from C7. We triaged C7 as a wrong constraint,
not a data defect: the rule is false for 353 of 358 foods because USDA
analyses selected nutrients per food. Making it a Violation would block every
load; dropping the incomplete foods would leave 5. We kept C7 as a Warning,
kept the foods, and carried the decision forward: the access layer's prompt
says that missing observations are unknown, not zero, and the learning layer
leaves the 10 foods without a fat value out of the label instead of guessing
it. The full triage is in [shapes/triage.md](../shapes/triage.md).

**The gate, before the endpoint and in CI.** `pipeline/run.py` validates the
mapped graph together with the ontology (step 3); a Violation exits with
code 1 before the reasoner, the VoID and the load, so the endpoint is only
ever loaded with data that passed. The same pipeline runs in GitHub Actions on
every push and pull request (`.github/workflows/shacl-gate.yml`). **A red run
it blocked:** one broken row, observation 2219740 with its protein amount
changed from 7.35 to −7.35, gives one C4 Violation and stops the run
([shapes/red-run.txt](../shapes/red-run.txt), with the link to the red CI run
on the unmerged branch `ci-red-run`).

## 5. Operational data integration

**The mapping** ([mapping/mapping.ttl](../mapping/mapping.ttl)) is R2RML, one
triples map per table, materialized with Morph-KGC: 9,359 triples. Our IRIs
follow one pattern, kind / source system / source key (for example
`https://ul.edu.lb/kr/id/food/usda/321358`), so a key from a second source can
never collide with a USDA key, and two records become one thing only through
an explicit entity resolution decision. The pipeline also writes one named
graph per source table (`build/food.trig`), which the provenance refers to.

**Materialized and virtualized.** We loaded the same four tables into
PostgreSQL and exposed them through Ontop over the same mapping
([mapping/README.md](../mapping/README.md)). On the shared query (count of
foods) both return 358
([mapping/virtualization-comparison.json](../mapping/virtualization-comparison.json)).
The deployed system is **materialized**, for three reasons:

- *Freshness.* The source changes only when USDA publishes a release, about
  twice a year (our 358 foods carry 11 publication dates from 2019-04-01 to
  2024-04-18, almost all in April or October). A rebuild per release is enough; live
  virtualization would buy freshness we do not need.
- *Latency.* The materialized count took 0.006 s in Oxigraph; Ontop took
  3.13 s. The Ontop time includes the start of the Java process and the
  Oxigraph time excludes loading the graph, so this is not an engine
  benchmark, but it is the latency a user of each setup would see.
- *Workload.* Reads only, a small graph (9,359 mapped triples), and questions
  that need the reasoner: CQ6 depends on the CharacterizedFood definition,
  which Ontop reports as outside OWL 2 QL and cannot answer. Materializing
  lets HermiT run once, before loading.

**Entity resolution across two sources.** We matched 40 records of the April
2018 SR Legacy release against the 358 Foundation Foods records, with
Jaro-Winkler similarity on the description and Fellegi-Sunter weights, using
the category where the original matcher used a plant
([mapping/er/match_foods.py](../mapping/er/match_foods.py)). The weights are
stated, not estimated on food records. The labelled sample
([mapping/er/truth.csv](../mapping/er/truth.csv)) takes its gold from the USDA
NDB number the two releases share: 32 true pairs and 8 records with no
counterpart. The NDB number is used only for the labels, never as a matching
feature ([mapping/er/sources.json](../mapping/er/sources.json)).

| Threshold | TP | FP | FN | Precision | Recall |
|---|---|---|---|---|---|
| 4 | 13 | 6 | 19 | 0.684 | 0.406 |
| 8 | 12 | 5 | 20 | 0.706 | 0.375 |

([mapping/er/results.json](../mapping/er/results.json)). Recall is low because
the two releases word the same food differently, for example "Beverages,
almond milk, unsweetened, shelf stable" (SR Legacy) and "Almond milk,
unsweetened, plain, shelf stable" (Foundation Foods), and the stated weights
were not tuned for food descriptions. With a precision of 0.7 we do not write the
matches into the graph as `owl:sameAs`: one wrong `sameAs` would merge two
foods' nutrients, so the matches stay an evaluation result.

## 6. Prediction and evaluation honesty

**The graph.** `model/build_graph.py` converts `build/graph.nt`, the mapped
graph, into a PyTorch Geometric graph of foods, categories and nutrients
(`model/results/build_graph.txt`: 9,359 triples read).

**Node classification.** Is a food high in fat (above 20 g per 100 g)?
55 high-fat foods of 348; the 10 foods with no fat value are left out, not
guessed. The features are the other five nutrients, as log amounts with a
missing flag. We removed the fat amount from the features because the label
is computed from it; `model/baseline.py` keeps it once on purpose and scores
PR-AUC 1.000 on a random split, which shows the leak
([model/results/baseline.txt](../model/results/baseline.txt)).

**The split, and why it does not leak.** We split by USDA category: about 30%
of the 18 categories go to the test set with all their foods, so a model
cannot pass by remembering a category. Our data does have dates, but a split
by time would leak: `publication_date` is the day USDA published the analysis,
the label does not change with it, and with a cut at 2023-01-01 all 77 foods
published from 2023 fall in one of the 9 categories that also have earlier
foods in training. The argument is in [model/README.md](../model/README.md).

**Baseline, seeds and spread** (PR-AUC, category split; guessing scores 0.158;
[model/results/baseline.txt](../model/results/baseline.txt),
[model/results/gnn.txt](../model/results/gnn.txt)):

| Model | seed 0 | seed 1 | seed 2 | seed 3 | seed 4 | mean of 4 |
|---|---|---|---|---|---|---|
| logistic regression | 0.163 | 0.523 | — | 0.129 | 0.754 | 0.392 |
| GraphSAGE | 0.163 | 0.867 | — | 0.090 | 0.641 | 0.440 |

Seed 2 puts no high-fat food in the test set (only 7 of the 18 categories have
any), so it cannot be scored. The spread between seeds, 0.090 to 0.867 for
GraphSAGE, is larger than the difference between the two models, so we do not
claim that the graph model is better than the table baseline.

**Link prediction.** We hide the links from a category to its foods and rank
the true category among all 18, filtered, three seeds
([model/results/link_prediction.txt](../model/results/link_prediction.txt)):

| Model | seed 0 | seed 1 | seed 2 | mean MRR |
|---|---|---|---|---|
| TransE | 0.382 | 0.345 | 0.289 | 0.339 |
| popularity | 0.395 | 0.423 | 0.527 | 0.448 |

TransE loses to the popularity baseline on every seed. With 18 categories and
few links per food, predicting the most common categories is hard to beat; we
report the loss as the result.

The versions and the date of these runs are in
[model/results/run-metadata.json](../model/results/run-metadata.json). The
predictions are not served by the system and never shown as facts.

## 7. Access layer

**Grounding.** A question in English is sent to Gemini with three things:
the graph's description, a VoID file the pipeline writes from the deployed
graph (95 triples, listing the classes and properties that exist); our
naming rules ([access-layer/prompt_rules.txt](../access-layer/prompt_rules.txt):
the USDA IRIs, the six nutrient ids, units per 100 g, "missing observations
are unknown, not zero"); and the three example queries
([access-layer/examples.ttl](../access-layer/examples.ttl), 6 in all) whose
questions share the most words with it.

**Check and repair.** Before a query runs, it is checked against the VoID: a
property or a class the graph does not have is a problem. The problems go back
to the model, which may repair the query up to twice; a query that is still
wrong after three tries is refused rather than run.

**Refusal on a real unanswerable question.** The rules tell the model to
refuse when a question needs a kind of fact the graph does not hold, and to
say which. Our test set has three such questions; in the recorded run all
three were refused with the missing fact as the reason: "REFUSE: price",
"REFUSE: disease treatment", "REFUSE: allergens"
(`access-layer/llm-cache.json`).

**The score, before and after one improvement**
([report/access-layer-score.txt](access-layer-score.txt), recorded live on
2026-10-18 with `gemini-3.5-flash-lite`). Our test set
([access-layer/questions.yaml](../access-layer/questions.yaml)) has 11
questions with gold queries, none of them an example question: 8 answerable,
3 to refuse. The score is the mean set-of-values F1 on the 8 answerable ones.

| Setting | Mean F1 | Refused correctly | Answered after a repair |
|---|---|---|---|
| schema only | 0.856 | 3 of 3 | 0 |
| plus examples (our improvement) | 0.954 | 3 of 3 | 0 |
| plus check and repair | 0.954 | 3 of 3 | 0 |

The examples improved the score from 0.856 to 0.954. The recorded run needed
no repair, so the repair setting scores the same; this run does not show the
repair loop helping. The run reproduces offline from the recorded answers
([report/access-layer-context.json](access-layer-context.json) holds the hashes
of the exact files used; the command is in
[access-layer/README.md](../access-layer/README.md)).

## 8. Deployment and reproducibility

**The stack** ([docker-compose.yml](../docker-compose.yml)): `fuseki`, the
SPARQL endpoint (dataset `kr`); `pipeline`, which runs once (source, map,
SHACL gate, reasoner, queries, VoID, load, provenance) and stops the stack if
the data fails; and `access-layer`, which starts only after the pipeline
succeeded and serves the questions and our web page. Every port listens on
127.0.0.1 only; the Gemini key and any database password live in `.env`,
which is never committed (`.gitignore`).

**One command from a clean checkout:** `docker compose up --build`, after
copying `.env.example` to `.env` and adding a key. Profiling, entity
resolution and the learning experiments are not on the path to the endpoint:
a failure there cannot keep the endpoint from loading. Each runs as its own
command, and its reviewed output is committed.

**What a clean checkout test surfaced**
([report/clean-checkout.txt](clean-checkout.txt)): our first test, a fresh
clone into an empty folder, failed to build the access layer, because its
Dockerfile still copied a file we had deleted. We fixed the Dockerfile and
repeated the test.

**Provenance.** The pipeline records, in PROV-O, the source files with their
SHA-256 hashes, the run that used them, the program and the named graph
derived from each table (`build/provenance.ttl`: 43 triples about 4 named
graphs). The original USDA and FoodOn downloads are identified by URL and hash
in `data/manifest.json`, `data/foodon-source.json` and
`mapping/er/sources.json`.

**The ontology's version** is in the ontology itself (section 3).

## 9. Open problem: when a graph model loses to a count, what have we learned?

**The question.** When a knowledge graph embedding scores below, or above, a
simple baseline, is that a property of the model, or of how it was trained
and evaluated? Put differently: do reported differences in knowledge graph
completion survive a fair comparison?

**Where it appears in FoodScope.** Our link prediction model, TransE, loses
to a popularity count on every seed: mean MRR 0.339 against 0.448
(`model/results/link_prediction.txt`). In node classification, GraphSAGE has a
higher mean PR-AUC than logistic regression (0.440 against 0.392), but its
scores range from 0.090 to 0.867 across seeds, and one seed of five cannot be
scored at all (`model/results/gnn.txt`). Both results invite a sentence we
could easily have written, "TransE does not work on food data" or
"GraphSAGE beats the table model", and neither is supported by what we ran.

**What the field found.** Kadlec, Bajgar and Kleindienst (2017) re-tuned
DistMult, an older and simpler model, and found that it outperformed most of
the newer models published on the same benchmark: the reported gains partly
reflected better tuning, not better models. Ruffinelli, Broscheit and Gemulla
(2020) made the point systematically: with one large hyperparameter search
over the training choices (loss, negative sampling, regularization), older
models such as RESCAL became competitive with or better than recent ones, and
the training setup often mattered as much as the architecture. Sun et al.
(2020) found a second cause, in the evaluation itself: several recent methods
gave many candidates the same score, and the way the protocol broke those ties
placed the right answer high; under a protocol that breaks ties fairly, their
gains largely disappeared. Ali et al. (2022) reimplemented a large set of
embedding models in one framework, PyKEEN, which is the library we use, and
could not reproduce many published results from the reported settings; they
too found that a model's score depends on the combination of model, loss and
training approach.

**What we checked, and what we could not.** We tested the evaluation cause
on our own run. Our ranking breaks ties in a fixed alphabetical order, and the
popularity baseline scores categories by integer counts, so ties do occur (on
1 to 4 of about 34 test links per seed). Scoring the baseline with optimistic,
pessimistic and mean-rank tie handling changes its MRR by at most 0.001
(`model/results/tie_check.txt`). The protocol does not explain our result. The
training cause we could not rule out: TransE ran once per seed with one
setting (32 dimensions, 150 epochs, PyKEEN's default loss and negative
sampling), and we built a validation split but did not use it to tune
anything. By Ruffinelli et al.'s standard, our comparison gave the baseline,
which has nothing to tune, its best possible form, and gave TransE an
arbitrary one. A third cause is our test size: about 34 hidden links per seed,
so a single link moving from rank 1 to rank 2 changes MRR by 0.015, and three
seeds are too few to estimate the spread well.

**Our position.** A difference between a learned graph model and a baseline
is a finding about the model only when four conditions hold: both sides get
the same tuning budget on a validation split; the protocol is stated in full
(filtered ranking, and how ties are broken); the test is large enough, or
repeated over enough seeds, that the difference exceeds the spread; and the
baseline is the strongest simple one for the task, not a weak one. FoodScope
meets the second and the fourth, partly meets the third, and does not meet
the first. So we claim only what our files support: under one untuned
setting, TransE did not beat a count on this graph, and GraphSAGE was not
distinguishable from logistic regression. We do not claim that graph
embeddings are unsuited to food composition data. On a graph this small (18
categories, a few hundred foods), we expect a well-chosen count to be hard to
beat, and we think the burden should be on the learned model: it should beat
the baseline by more than the seed spread before any system relies on it.

**What this changes in our system.** It is the reason FoodScope does not
serve predictions: the access layer answers only from facts in the graph, and
no prediction is shown as a fact (section 6). It is also the reason our
report quotes every seed and the guessing score next to each model rather than
the best run. The next step we would take is the fair comparison itself: one
hyperparameter search per model with the same budget on the validation split,
ten or more seeds, and the tie check kept as part of the run.

**Sources for this section**

- Kadlec, R., Bajgar, O., Kleindienst, J. (2017). Knowledge Base Completion:
  Baselines Strike Back. *Proceedings of the 2nd Workshop on Representation
  Learning for NLP (RepL4NLP), ACL*, 69–74.
- Ruffinelli, D., Broscheit, S., Gemulla, R. (2020). You CAN Teach an Old Dog
  New Tricks! On Training Knowledge Graph Embeddings. *ICLR 2020*.
- Sun, Z., Vashishth, S., Sanyal, S., Talukdar, P., Yang, Y. (2020). A
  Re-evaluation of Knowledge Graph Completion Methods. *ACL 2020*, 5516–5522.
- Ali, M., Berrendorf, M., Hoyt, C. T., Vermue, L., Galkin, M., Sharifzadeh,
  S., Fischer, A., Tresp, V., Lehmann, J. (2022). Bringing Light Into the
  Dark: A Large-scale Evaluation of Knowledge Graph Embedding Models under a
  Unified Framework. *IEEE Transactions on Pattern Analysis and Machine
  Intelligence* 44(12), 8825–8845.

## References

- USDA Agricultural Research Service. FoodData Central, Foundation Foods,
  April 2024, and SR Legacy, April 2018. https://fdc.nal.usda.gov/
- Dooley, D. M. et al. (2018). FoodOn: a harmonized food ontology to increase
  global food traceability, quality control and data integration. *npj
  Science of Food* 2, 23.
- W3C (2012). R2RML: RDB to RDF Mapping Language. W3C Recommendation.
- W3C (2017). Shapes Constraint Language (SHACL). W3C Recommendation.
- W3C (2012). OWL 2 Web Ontology Language Profiles (Second Edition).
- Glimm, B., Horrocks, I., Motik, B., Stoilos, G., Wang, Z. (2014). HermiT:
  an OWL 2 reasoner. *Journal of Automated Reasoning* 53, 245–269.
- Fellegi, I. P., Sunter, A. B. (1969). A theory for record linkage. *Journal
  of the American Statistical Association* 64, 1183–1210.
- Hamilton, W., Ying, R., Leskovec, J. (2017). Inductive representation
  learning on large graphs (GraphSAGE). *NeurIPS*.
- Bordes, A. et al. (2013). Translating embeddings for modeling
  multi-relational data (TransE). *NeurIPS*.
- W3C (2011). Describing Linked Datasets with the VoID Vocabulary. W3C
  Interest Group Note.

## Licences

| Ontology, vocabulary or dataset | Licence | Where used |
|---|---|---|
| USDA FoodData Central, Foundation Foods (April 2024) | Public domain (CC0) | `data/`, the graph |
| USDA FoodData Central, SR Legacy (April 2018) | Public domain (CC0) | `mapping/er/` (entity resolution sample) |
| FoodOn (release recorded in `data/foodon-source.json`) | CC BY 4.0 (`data/FOODON-LICENSE.txt`) | `ontology/foodon-module.ttl`, `food:Food rdfs:subClassOf` |
| BFO *material entity* (inside the FoodOn extract) | CC BY 4.0 | `ontology/foodon-module.ttl` |
| W3C vocabularies: RDF, RDFS, OWL, XSD, SHACL, PROV-O, VoID, Dublin Core terms | W3C Software and Document licence | ontology, shapes, provenance, VoID |
| FoodScope ontology (ours) | CC BY 4.0 (`dct:license` in `ontology/ontology.ttl`) | `ontology/ontology.ttl` |
