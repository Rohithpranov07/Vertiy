# Evaluation

`python -m eval.run_eval --split dev` writes `eval/report.md` and `eval/report.json`.
The test split runs only with `--final` (see `eval/final_run.py`).

Starter files `eval/variants/starter.csv`, `eval/domains_test.csv`, `eval/domains_trusted.csv`
and `eval/redaction_test.csv` are **SYNTHETIC** (made up for the harness). Replace them with
real, human-labelled files before reporting results.
