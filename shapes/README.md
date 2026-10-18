# shapes/

Our SHACL shapes are in [shapes.ttl](shapes.ttl): one constraint per rule of
the inventory (`data/constraint_inventory.csv`, C1 to C10). Each check has an
`sh:message` with its rule id and a severity that says what the pipeline
does: a **Violation stops the load**, a Warning is reported and the data is
kept.

- [triage.md](triage.md): every result on our data, triaged as a data defect
  or a wrong constraint, and for each rule why we made it SHACL and not OWL.
  On the sample: 0 Violation, 353 Warning (all C7, a constraint we found false
  in the data and kept as a Warning).
- [red-run.txt](red-run.txt): the gate blocking one deliberately broken row,
  with the link to the red CI run.

To run it locally (the gate also runs in CI, `.github/workflows/shacl-gate.yml`):

```sh
python pipeline/run.py --no-load        # stops at step 3 on any Violation; report in build/shacl-report.txt
python pipeline/validate.py             # the report grouped by shape and message, with focus-node counts
```

The pipeline also fails when a shape has no focus nodes, because a wrong
target class validates nothing and would pass silently
(`build/shape_coverage.json`).
