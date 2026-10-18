# data/

Our source is a sample of the USDA FoodData Central **Foundation Foods**
release of April 2024 (public domain / CC0, see [manifest.json](manifest.json)).
One row of `foods.csv` is one food; one row of `measurements.csv` is one
nutrient amount for one food, per 100 g edible portion.

| File | What it holds |
|---|---|
| `foods.csv`, `measurements.csv`, `nutrients.csv`, `categories.csv` | the prepared tables: 358 foods, 1,499 observations, 6 nutrients, 28 categories |
| `example.sql` | the same tables as SQL; the pipeline loads it into `build/example.sqlite` when `DB_URL` is not set, and CI maps and validates it on every push |
| `constraint_inventory.csv` | our constraint inventory: each rule, the count that supports it, and where the count came from |
| `manifest.json`, `foodon-source.json`, `FOODON-LICENSE.txt` | sources, hashes and licences |
| `prepare.py`, `build_sample.py` | rebuild the tables and `example.sql` from the original USDA download (`data/raw/`, ignored) |
| `profiling/` | the profiling scripts |

## Profiling and the constraint inventory

```sh
python data/profiling/data_profile.py      # counts every rule -> data/constraint_inventory.csv
pip install -r data/profiling/requirements-profiling.txt
python data/profiling/source_profile.py    # ydata-profiling reports -> build/profiling/
```

`data_profile.py` counts each rule on the prepared tables. Nine rules hold
with 0 exceptions. C7 ("every food has all six nutrients") is false for 353
of 358 foods, so we kept it as a Warning (see
[../shapes/triage.md](../shapes/triage.md)). We regenerate the HTML profiling
reports rather than commit them.

To use another database instead of the sample, set `DB_URL` in `.env`
(see `docker-compose.yml`) and keep `example.sql` so CI can still validate.
