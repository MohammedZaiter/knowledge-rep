# Competency questions

The questions FoodScope must answer, written before the classes and
properties. Every class and property in [ontology.ttl](ontology.ttl) carries
`food:answersCQ` with the questions below that need it; a term no question
needs does not belong in the ontology.

Each question is tested by a query in [../sparql/queries.sparql](../sparql/queries.sparql)
(`Q` numbers are the order in that file). The answers are from
`build/answers.json`, written by `python pipeline/run.py` on the committed
sample (358 foods, 1,499 observations).

| CQ | Question | Terms it needs | Tested by | Answer on the sample |
|---|---|---|---|---|
| CQ1 | Which foods does the snapshot hold, by USDA identifier and name? | `Food`, `sourceId`, `name` | Q1 | 358 foods |
| CQ2 | Which category does each food belong to, and how many foods does each category hold? | `Category`, `category`, `name` | Q6, Q11 | 18 categories used; 49 foods in Dairy and Egg Products |
| CQ3 | How much of a selected nutrient does a food contain per 100 g, and in which unit? | `Observation`, `hasObservation`, `ofFood`, `Nutrient`, `nutrient`, `amount`, `unit` | Q2, Q8, Q10, Q12 | 346 foods with a protein amount; 6 nutrients in G or MG; 1,499 observations |
| CQ4 | Which foods are above or below a threshold for a nutrient? | as CQ3, with `FILTER` on `amount` | Q3, Q4, Q9 | 55 foods above 20 g fat; 217 below 100 mg sodium; 34 with at least 5 g fiber |
| CQ5 | Which foods were published from a given USDA release date? | `publishedOn`, `name` | Q7 | 77 foods published from 2023-01-01 |
| CQ6 | Which foods have at least one recorded composition observation? | `CharacterizedFood`, `hasObservation`, `Observation` | Q13 (and Q5) | 350 characterized foods, inferred by HermiT; 353 foods have no sugar value |

## What the questions decided

- **Observation is a class, not a property of Food.** CQ3 and CQ4 need the
  amount, the nutrient and the food together, so one observation node holds
  all three (`food:ofFood`, `food:nutrient`, `food:amount`). A property
  `food:proteinAmount` per nutrient would need a new property for every
  nutrient and could not say which nutrients were never measured.
- **CharacterizedFood is defined, not asserted** (CQ6):
  `Food and (hasObservation some Observation)`. HermiT classifies the 350
  foods that have an observation; nobody types them by hand.
- **Missing is unknown, not zero** (CQ6, Q5). Under the open world
  assumption, the 8 foods with no observation are simply not classified as
  CharacterizedFood; the graph does not claim they have none. The same holds
  per nutrient: 353 foods have no sugar value, and no query treats that as 0 g.
- **Category is its own class** (CQ2), disjoint from Food, Nutrient and
  Observation, so the USDA category list is data, not a class hierarchy.

## Left out, and why

Price, allergens, health claims and recipes: no CQ asks for them and the
USDA source does not hold them. The access layer refuses these questions
(test questions 9 to 11 in `access-layer/questions.yaml`).

## OWL profile

OWL 2 DL. The ontology is not in OWL 2 EL, because `food:hasObservation` and
`food:ofFood` are declared inverse (`owl:inverseOf`), and not in OWL 2 QL,
because the definition of CharacterizedFood uses an intersection with an
existential restriction (Ontop reports this axiom as outside QL, see
`mapping/virtualization-comparison.json`). HermiT, a DL reasoner, is used for
that reason; the run is in [reasoner-run.txt](reasoner-run.txt).
