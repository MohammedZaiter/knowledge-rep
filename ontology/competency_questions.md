# Competency questions and ontology traceability

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
