# access-layer/

Questions in English over our graph. A question becomes a SPARQL query,
grounded in the graph's description (`build/void.ttl`) and the closest
example queries. The query is checked against the terms the graph really has,
repaired up to twice, or the question is refused with a reason. Gemini only
(`GOOGLE_API_KEY` in `.env`).

| File | Our version |
|---|---|
| `access_layer.py` | `NS = https://ul.edu.lb/kr/food#`, `PFX = food`; the ask, check, repair, refuse loop |
| `prompt_rules.txt` | how our data is named: USDA IRIs, the six nutrient ids, units per 100 g, "missing is unknown, not zero", and when to refuse |
| `examples.ttl` | 6 example queries in the SHACL vocabulary |
| `questions.yaml` | our test set: 11 questions with gold queries, 3 of which must be refused (price, curing diabetes, allergens); none is an example question |
| `my_access.py` | the class check: catches a class the graph does not have |
| `serve.py` | the TEXT2SPARQL GET contract on http://127.0.0.1:8000, plus our web page and `/api/ask` |

Ask one question (with the pipeline run):

```sh
python access-layer/ask.py "How many foods have more than 30 g protein per 100 g?"
python access-layer/ask.py "What is the price of each food?"      # refused, with the reason
```

## The score

Recorded live on 2026-10-18 with `gemini-3.5-flash-lite`
([../report/access-layer-score.txt](../report/access-layer-score.txt)), mean
set-of-values F1 on the 8 answerable questions:

| Setting | Mean F1 | Refused correctly |
|---|---|---|
| schema only | 0.856 | 3 of 3 |
| plus examples | 0.954 | 3 of 3 |
| plus check and repair | 0.954 | 3 of 3 |

Our improvement was the examples (0.856 to 0.954). The recorded run needed no
repair, so the repair setting scores the same as the examples setting.

Every answer is in `llm-cache.json`, so the score reproduces without the
network:

```sh
cd access-layer
VOID_FILE=../report/access-layer-void.ttl LLM_MODE=replay LLM_DELAY=0 python evaluate.py
```

On Windows PowerShell, set the variables first, for example
`$env:LLM_MODE="replay"`. Record a new score with `LLM_MODE=record` and a key
in `.env`; the free tier limits requests per minute, so the scripts wait 4 s
between calls.
