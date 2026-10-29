# Demo messages

Five messages that exercise the main paths. Steps 1 and 3 are an original forward and an edited
copy of it; step 4 has a link that imitates a trusted outlet from `data/domains.csv`; step 5 is a
Tamil message. Each claim is taken from a published fact-check in the local index, so
`make setup` (which ingests them) must have run first. `expected.json` records the expected
verdict per step; `make demo` prints MATCH or DIFFERENT against it.

Also try the headline-backed true claims: any recent headline from `data/feeds.txt` (for example
copied from The Hindu) should come back Likely true, because a trusted outlet reports it.
Refresh the headlines with `python -m scripts.ingest_headlines`.
