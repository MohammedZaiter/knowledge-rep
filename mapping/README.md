# Mapping and integration

`mapping.ttl` uses the template's R2RML/Morph-KGC materialization approach over four USDA tables. Stable IRIs include kind, source and source key. The food SQL view converts publication dates to midnight `xsd:dateTime` for HermiT compatibility. Source CSV/SQL dates remain unchanged.

The deployed configuration materializes a release snapshot: validation, reproducible queries and a small fixed graph matter more here than minute-by-minute source freshness. `DB_URL` follows the template contract and can point at the same four-table schema in PostgreSQL. Keep credentials in root `.env`.

## Two-source matching

Run `python mapping/er/match_foods.py` from the repository root. It adapts the course Fellegi-Sunter/Jaro-Winkler code to genuine USDA Foundation/SR Legacy names and category blocks. The 40 SR sample records are compared with 358 Foundation candidates. `er/truth.csv` labels 32 shared-NDB records and 8 without a corresponding NDB record; NDB identifiers are not matching features. `er/sources.json` records exact source hashes and the gold-label scope.

The target is a corresponding USDA NDB concept across releases, not identical nutrient composition. The course's stated weights are retained and are not calibrated to food names. `er/results.json` records false positives/negatives and precision/recall at thresholds 4 and 8. These imperfect links are evaluation evidence and are not automatically asserted as `owl:sameAs` in the food graph.

## Materialized versus Ontop

This uses the course PostgreSQL 16, Ontop 5.5.0 and PostgreSQL JDBC code. It requires Java 21 and a running Docker engine. Add `POSTGRES_USER=kr` and a local `POSTGRES_PASSWORD` to root `.env`; do not commit the password. Leave `DB_URL` unset to use these values, or set it to the same PostgreSQL database.

From the repository root, with the environment active:

```powershell
docker compose -f mapping/docker-compose.yml up -d
python mapping/load_database.py
python mapping/ontop/setup_ontop.py
python mapping/compare_virtualized.py
```

The loader uses the same four committed CSVs as the SQL sample. The comparison runs one shared count query against `build/graph.nt` and virtualized PostgreSQL data, checks equal rows and writes `mapping/virtualization-comparison.json`. Ontop/JDBC binaries are ignored. JDBC properties are generated under the ignored `build/ontop/.food.properties`, which the UI cannot serve.

The timing report explicitly distinguishes JVM startup from the materialized engine's already-loaded query time; it is not an engine-only latency benchmark. The comparison completed on 2026-10-18: both views returned 358 foods. This verifies that shared count query, not every possible query. Ontop logged that the CharacterizedFood equivalence is outside OWL 2 QL; the materialized HermiT view is therefore retained for the application. The profile warning is preserved in the result JSON.
