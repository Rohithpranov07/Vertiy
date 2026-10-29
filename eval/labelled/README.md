# Labelled dataset

Target: 300 messages, split 200 dev / 100 test (stratified by label and language),
including a Tamil and Hindi subset. **The messages and labels are written by a human.**
No tool in this repository generates them.

## Columns (exactly, in this order)

`id,text,language,label,evidence_url,gold_factcheck_url,notes`

| Column | Rule |
|---|---|
| `id` | Unique, stable identifier. |
| `text` | The message as a user would receive it. Do **not** copy the fact-check headline. Do not include real personal identifiers. |
| `language` | `en`, `ta` or `hi`. |
| `label` | `false`, `true` or `unverifiable`. |
| `evidence_url` | Required for every `false` and `true` row: the source that establishes the label. |
| `gold_factcheck_url` | The fact-check the message was derived from; blank if none exists. Used for retrieval precision@3. |
| `notes` | Free text, optional. |

`unverifiable` rows have no ground truth: they are used to judge abstention, and are
excluded from parameter learning.

## Workflow

```
python -m scripts.validate_labelled eval/labelled/all.csv
python -m scripts.split_labelled eval/labelled/all.csv --out eval/labelled
```

The split is deterministic (seeded from `RANDOM_SEED`). Use `dev.csv` for every tuning
and training step. `test.csv` is touched once, by the final evaluation run (`--final`).
