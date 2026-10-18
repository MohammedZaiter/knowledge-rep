# Access layer

This is the actual `kr-team-template/access-layer/access_layer.py`, configured with FoodScope `NS`/`PFX`, its dataset identifier and reasoned graph path. `prompt_rules.txt`, six SHACL-vocabulary examples and 11 non-overlapping test questions replace the supply-chain content. Source hashes are in `COURSE_CODE_SOURCES.json`.

The model, HTTP interface, lexical example selection, VoID schema, property/class checks, two-repair limit, refusal and record/replay approach remain the course implementations. `serve.py` adds static UI/result serving around the course TEXT2SPARQL contract. The root .env holds GOOGLE_API_KEY. Nothing substitutes fake model replies when the key or cache is unavailable.

From the repository root, with the environment active:

```powershell
python access-layer/ask.py "How many foods are there?"
$env:LLM_MODE="replay"
$env:VOID_FILE=(Join-Path (Get-Location) "report/access-layer-void.ttl")
python access-layer/evaluate.py
Remove-Item Env:LLM_MODE
Remove-Item Env:VOID_FILE
```

For a new live evaluation, use `LLM_MODE="record"`. For the deployed Fuseki graph, also set `SPARQL_ENDPOINT=http://127.0.0.1:3030/kr/sparql`. The genuine cache is intentionally shareable and contains only the controlled public-data evaluation replies, never API keys.

The course scorer compares sets of returned values, not ordered rows or query semantics. A correct query that projects extra identifiers can lose F1; successful parsing and known vocabulary do not prove the intended question was answered. The measured run is preserved in `report/access-layer-score.txt` with the date/model and before/after settings. The live HTTP demo returned 358 foods and refused a question asking food prices.

For score replay, the archived VoID context is pinned in `report/access-layer-void.ttl`, with context hashes in `report/access-layer-context.json`. The original template SAMPLE-based generator is retained; regenerating VoID can change the exact prompt.
