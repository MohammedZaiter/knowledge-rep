# ontology/

Our ontology is [ontology.ttl](ontology.ttl): version IRI
`https://ul.edu.lb/kr/food/1.1.0` (prior version 1.0.0), OWL 2 DL.

- **What we reuse:** FoodOn (CC BY 4.0). `food:Food rdfs:subClassOf
  obo:FOODON_00001002` (food product). We import a documented extract,
  [foodon-module.ttl](foodon-module.ttl), with the three asserted ancestors
  (food product, food material, material entity), resolved offline through
  [catalog-v001.xml](catalog-v001.xml) the same way Protégé does.
  [fetch_ontologies.py](fetch_ontologies.py) rebuilds it from the release
  recorded in `data/foodon-source.json`.
- **What we added, only where FoodOn has no term for the USDA data:**
  Food, Category, Nutrient, Observation, and the defined class
  CharacterizedFood (`Food and hasObservation some Observation`).
- **Competency questions:** [competency_questions.md](competency_questions.md).
  Every class and property carries `food:answersCQ`.
- **Reasoner:** HermiT (owlready2) through [local_reasoner.py](local_reasoner.py).
  The pipeline runs it after the SHACL gate. Our dated run is
  [reasoner-run.txt](reasoner-run.txt): consistent, no impossible class,
  350 characterized foods.

To run the reasoner on its own:

```sh
python pipeline/run.py --no-load                     # writes build/validation-input.ttl and build/reasoning.json
python ontology/local_reasoner.py build/validation-input.ttl
```

When we change the ontology, we bump `owl:versionIRI` and `owl:versionInfo`,
set `owl:priorVersion` to the old IRI, run the pipeline, and copy
`build/reasoning.json` to `reasoner-run.json` (and update `reasoner-run.txt`).
Version 1.0.0 predates this repository's history; the `owl:versionInfo` of
1.1.0 records what it introduced: the imported FoodOn ancestor module.
