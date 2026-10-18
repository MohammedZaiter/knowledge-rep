# mapping/

## The mapping

[mapping.ttl](mapping.ttl) is our R2RML mapping from the four tables to the
ontology: one triples map per table and one IRI template per kind of thing.
Our IRIs follow one pattern, kind / source system / source key, for example
`https://ul.edu.lb/kr/id/food/usda/321358`, so the same key from a second
source can never collide. The pipeline materializes the mapping with
Morph-KGC (`pipeline/run.py`, step 2): 9,359 triples, which the shapes then
validate together with the ontology.

## Materialized and virtualized

We put the same four tables in PostgreSQL and virtualized them with Ontop,
to compare against the materialized graph:

```sh
docker compose -f mapping/docker-compose.yml up -d   # PostgreSQL on 127.0.0.1:5432; POSTGRES_PASSWORD in .env
python mapping/load_database.py
python mapping/ontop/setup_ontop.py                   # downloads Ontop 5.5.0 and the JDBC driver
python mapping/compare_virtualized.py                 # -> virtualization-comparison.json
```

Result ([virtualization-comparison.json](virtualization-comparison.json)):
both answer the food count with 358. Ontop reports our CharacterizedFood
definition as outside OWL 2 QL, so the virtual graph cannot answer CQ6. Our
deployed system is materialized; we argue the choice in the report, section 5.

## Entity resolution across two sources

In [er/](er/) we match 40 SR Legacy (April 2018) records against the 358
Foundation Foods (April 2024) records, using Jaro-Winkler similarity and
Fellegi-Sunter weights ([er/match_foods.py](er/match_foods.py)). The gold
labels ([er/truth.csv](er/truth.csv)) come from the USDA NDB number the two
releases share: 32 true pairs and 8 records with no counterpart. We use the
NDB number only for the labels, never as a matching feature.

```sh
python mapping/er/match_foods.py      # -> er/results.json
```

| Threshold | True positives | False positives | False negatives | Precision | Recall |
|---|---|---|---|---|---|
| 4 | 13 | 6 | 19 | 0.684 | 0.406 |
| 8 | 12 | 5 | 20 | 0.706 | 0.375 |

The matches stay an evaluation result; we do not write them into the graph
as `owl:sameAs`.
