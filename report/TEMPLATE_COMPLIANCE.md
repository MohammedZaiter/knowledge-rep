# Team-template alignment and verification

Template: https://github.com/ahmabboud/kr-team-template, commit `0b1804188bf8c84b41debb523d140abb9aa47bc5`.

| Template requirement | Implementation/evidence | Status |
| --- | --- | --- |
| Root layer folders | data, ontology, shapes, mapping, pipeline, model, access-layer, report, fuseki | Implemented |
| Real committed SQL sample or DB_URL | data/example.sql; template source() function | Local run passed |
| Reused vocabulary, profile, version, CQs, reasoner | Explicit FoodOn module import/catalog; OWL 2 DL version 1.1.0; competency_questions.md; reasoner-run.json | Implemented; local HermiT run verified |
| SHACL inventory/triage/gate | shapes/triage.md, data/constraint_inventory.csv, reports, regression cases | Local pass and rejection cases verified |
| CI gate and hosted blocked commit | Template workflow + regression checks | Workflow added; hosted red/green run not yet collected |
| R2RML materialization | Course Morph-KGC over template SQL source | Local run verified |
| Materialized/virtualized comparison | Course PostgreSQL/Ontop setup and mapping/compare_virtualized.py | Verified for the shared count query: 358 foods in each view; OWL 2 QL warning retained |
| Two-source entity resolution | Real Foundation/SR sample, NDB-labelled truth, course matcher and er/results.json | Measured; imperfect results retained |
| Classification/link prediction and baselines | Course logistic regression, GraphSAGE, TransE and popularity; model/results | Multi-seed runs verified; limitations documented |
| Grounded NL access, refusal and before/after score | Template code, six examples, 11 test questions, real cache and report/access-layer-score.txt | Live smoke tests passed; full recorded evaluation replay verified |
| One-command Compose stack | Template service ordering, root .env, localhost ports | Clean build and full pipeline passed; UI/API and Fuseki verified in deployment-smoke.json |
| Report and open problem | REPORT.md sections 1–9 and three primary standards references | Draft completed from measured evidence |
| Individual branches/teammate reviews | Team workflow | Requires actual teammate contributions/reviews; not fabricated by this change |

The local `python run.py` shortcut and browser table UI are additional adapters around the template pipeline/access contracts. They do not replace the course algorithms. Source lineage is in COURSE_CODE_SOURCES.json.

The clean Docker run and 18 Linux regression tests passed on 18 October 2026; deployment-smoke.json records the endpoint counts and live API checks. The virtualized count comparison is also recorded, with its profile limit. Hosted CI evidence and actual teammate reviews remain handoff checks, not claims of full grading compliance.
