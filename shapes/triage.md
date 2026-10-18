# Triage of the SHACL report

Shapes: [shapes.ttl](shapes.ttl). Rules and their counts:
[../data/constraint_inventory.csv](../data/constraint_inventory.csv) (written by
`python data/profiling/data_profile.py`). Report: `build/shacl-report.txt`
(written by `python pipeline/run.py --no-load`).

On the committed sample (358 foods, 1,499 observations, 9,359 mapped triples)
the gate reports **0 Violation and 353 Warning**. All 353 warnings come from
one rule, C7.

## Every rule, its result and the decision

For each result we asked one question: is the data wrong (a data defect),
or is the rule wrong (a wrong constraint)?

| Rule | Evidence in the data | Severity | Result | Triage | Decision |
|---|---|---|---|---|---|
| C1 one unique numeric `fdc_id` per food | 0 of 358 foods break it | Violation | holds | — | keep |
| C2 one nonempty description per food | 0 of 358 foods break it | Violation | holds | — | keep |
| C3 the category reference resolves | 0 of 358 foods break it | Violation | holds | — | keep |
| C4 amounts are nonnegative | 0 of 1,499 observations break it | Violation | holds | — | keep |
| C5 one amount per food and nutrient | 0 of 1,499 observations break it | Violation | holds | — | keep |
| C6 a gram amount is at most 100 g per 100 g | 0 of 1,190 gram observations break it | Violation | holds | — | keep |
| C7 every food has all six nutrients | **353 of 358 foods break it** | Warning | 353 warnings | **wrong constraint** | keep as Warning, keep the data, no zero filling |
| C8 an observation references an existing food and nutrient | 0 of 1,499 observations break it | Violation | holds | — | keep |
| C9 one publication date per food | 0 of 358 foods break it | Violation | holds | — | keep |
| C10 nutrients and categories are named; units are G or MG | 0 of 34 reference rows break it | Violation | holds | — | keep |

### C7: a constraint found false in the data

The proposed rule was "every food has a value for each of the six selected
nutrients". The data says otherwise: 353 of the 358 foods lack at least one.
By nutrient (`build/profile.json`, `missing_by_nutrient`):

| Nutrient | Foods with no value |
|---|---|
| sugars (2000) | 353 |
| fiber (1079) | 177 |
| sodium (1093) | 49 |
| carbohydrate (1005) | 48 |
| protein (1003) | 12 |
| fat (1004) | 10 |

8 foods have no observation at all (358 foods, 350 characterized by HermiT).

This is not a data defect. USDA Foundation Foods analyses selected nutrients
per food, so a missing value means "not analysed", not "zero" and not
"error". Making C7 a Violation would block every load; dropping the partial
foods would leave 5. Decision: C7 stays as a **Warning**, the foods stay in
the graph, and no value is filled with 0. The consequence is carried
forward: queries that need a nutrient only see foods that have it (Q5: 353
foods have no sugar value), the access layer prompt says "Missing
observations are unknown, not zero", and the learning layer drops the 10
foods with no fat value from the label rather than guessing it
(`model/results/build_graph.txt`).

As the template asks, this rule is reported, not dropped; the technical
report repeats it.

## Why SHACL and not OWL (or the reverse)

| Rule | Where | Why |
|---|---|---|
| C1 to C10 | SHACL | Each says what the data **must contain**. That is a closed-world question: a missing name or amount must be a failure. OWL is open world: a missing value is unknown, so OWL can never reject it. |
| C3, C8 (references resolve) | SHACL `sh:class` | An OWL `rdfs:range` would *infer* the target is a Category or Food instead of rejecting a reference that does not exist. The ontology keeps the ranges for reasoning; the shapes check them. |
| C1 (unique id) | SHACL-SPARQL | With `owl:hasKey` and no unique name assumption, two foods sharing an id are inferred to be *the same* food, not rejected. Uniqueness across nodes also needs SPARQL in SHACL, because core SHACL checks one node at a time. |
| C5, C6 | SHACL-SPARQL | C5 compares two observations; C6's limit depends on the unit of another node (the nutrient). Neither is expressible in core SHACL. |
| C7 | SHACL Warning | A completeness rule that is false on the data (above). In OWL, a cardinality `min 6` would never fire, because missing observations could exist somewhere. |
| Domains, disjointness, CharacterizedFood | OWL | These must hold for *reasoning*, not for loading: HermiT uses them to classify the 350 characterized foods and to detect contradictions (none: `ontology/reasoner-run.txt`). |

## The gate blocks a bad row

One broken row (observation 2219740, protein amount 7.35 → −7.35) gives
1 Violation of C4; the pipeline stops at step 3 with exit code 1 and the
endpoint is not loaded. The local run is recorded in
[red-run.txt](red-run.txt), together with the link to the red CI run.
