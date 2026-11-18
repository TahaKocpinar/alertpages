# Fixtures

Real feed responses recorded on 2026-11-18, trimmed to a few items so tests run offline.

| File | Source | Notes |
|---|---|---|
| `afad.json` | AFAD event API | 10 most recent events, Türkiye |
| `emsc.json` | EMSC FDSN (seismicportal.eu) | same 10 events as reported by EMSC |
| `usgs.json` | USGS `2.5_day` GeoJSON feed | first 8 features |
| `gdacs.xml` | GDACS RSS (CC BY 4.0, © European Union) | first 6 items; contact fields removed |
| `meteoalarm_greece.atom` | MeteoAlarm CAP Atom feed for Greece (CC BY 4.0 equivalent) | contact field removed |
| `kandilli_lst0.html` | KOERI `lst0.asp` format | taken from the MIT-licensed test fixture in [cenktekin/sismolog](https://github.com/cenktekin/sismolog); the live endpoint was unreachable from the recording machine |
