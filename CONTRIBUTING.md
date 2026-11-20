# Contributing

```
git clone https://github.com/TahaKocpinar/alertpages
cd alertpages
python -m unittest discover -s tests -v
```

Standard library only. Tests run offline against the files in `tests/fixtures/`.

## Adding a feed

1. Add a module in `alertpages/sources/` with `url(opts, now)` and `parse(raw, opts)`, and register it in `alertpages/sources/__init__.py`.
2. Save one real response from the feed in `tests/fixtures/` (trim it if it is large) and note the date and URL in `tests/fixtures/README.md`.
3. Add a test that parses the fixture and checks one event field by field.
4. Say in the PR how often the feed updates and whether it allows automated polling.

Official agency feeds first. Aggregators and scraped pages only when there is no official feed, and they must fail quietly when the page changes.

## Not wanted

Anything that presents this as an official or early-warning service. The README disclaimer stays.
