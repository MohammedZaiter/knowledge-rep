# Data layer

The four prepared USDA Foundation CSVs and `example.sql` are committed so a clean checkout can run without downloading data. `example.sql` is generated from those CSVs by `python data/build_sample.py` and loaded by the template pipeline's source() function. `DB_URL`, if configured, follows the template's external-database route and must expose the same table/column schema.

`python data/prepare.py --source <extracted-USDA-folder>` regenerates the CSVs, source manifest and SQL sample. `raw/` is ignored. Dataset source/license/hash information is in `manifest.json`; FoodOn source/license information is in `foodon-source.json` and `FOODON-LICENSE.txt`.

`profiling/source_profile.py` is the Session 1 ydata-profiling adaptation. `profiling/data_profile.py` records the food-specific constraint evidence. The separate cross-release entity-resolution sample is documented in `mapping/er/sources.json` and is not merged into the nutrient fact graph.

After manually editing prepared CSVs, run `python data/build_sample.py` to synchronize the SQL input. Do not regenerate it while testing an intentionally broken SQL sample: the gate should see that broken source.
