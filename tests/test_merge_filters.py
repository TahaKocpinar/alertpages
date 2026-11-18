import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from helpers import raw

from alertpages.filters import matches
from alertpages.merge import merge, quake_severity, report_ids
from alertpages.model import Alert
from alertpages.sources import afad, emsc, gdacs, usgs

UTC = timezone.utc
NOW = datetime(2026, 11, 18, 5, tzinfo=UTC)


def quake(src, sec=0, lat=40.0, lon=29.0, mag=4.0, nid="1"):
    return Alert(id=f"{src}:{nid}", source=src, kind="earthquake", title="t",
                 time=NOW + timedelta(seconds=sec), lat=lat, lon=lon, magnitude=mag)


class MergeTest(unittest.TestCase):
    def test_afad_and_emsc_fixtures_pair_up(self):
        reports = afad.parse(raw("afad.json")) + emsc.parse(raw("emsc.json"))
        events = merge(reports)
        self.assertEqual(len(reports), 20)
        self.assertEqual(len(events), 10)
        for e in events:
            self.assertEqual([r["source"] for r in e.reports], ["afad", "emsc"])
            self.assertEqual(e.source, "afad")  # preferred source is primary

    def test_same_source_never_merged(self):
        events = merge([quake("afad", 0, nid="1"), quake("afad", 20, nid="2")])
        self.assertEqual(len(events), 2)

    def test_limits(self):
        self.assertEqual(len(merge([quake("afad"), quake("emsc", sec=200)])), 2)
        self.assertEqual(len(merge([quake("afad"), quake("emsc", lat=41.5)])), 2)  # ~167 km
        self.assertEqual(len(merge([quake("afad"), quake("emsc", mag=5.5)])), 2)
        self.assertEqual(len(merge([quake("afad"), quake("emsc", sec=30, lat=40.3, mag=4.3)])), 1)

    def test_best_match_wins(self):
        # two close quakes; the EMSC report must join the nearer one
        a1 = quake("afad", 0, lat=40.0, nid="a")
        a2 = quake("afad", 40, lat=40.5, nid="b")
        e = quake("emsc", 42, lat=40.49, nid="e")
        events = merge([a1, a2, e])
        joined = next(x for x in events if len(x.reports) == 2)
        self.assertEqual(report_ids(joined), ["afad:b", "emsc:e"])

    def test_preference_and_severity(self):
        g = replace(quake("gdacs", 2, mag=6.0), severity="severe")
        u = quake("usgs", 0, mag=6.1)
        e = merge([g, u])[0]
        self.assertEqual(e.source, "usgs")
        self.assertEqual(e.severity, "severe")
        e2 = merge([g, u], prefer=["gdacs", "usgs"])[0]
        self.assertEqual(e2.source, "gdacs")

    def test_non_quakes_untouched(self):
        a = gdacs.parse(raw("gdacs.xml"))
        events = merge(a + usgs.parse(raw("usgs.json")))
        self.assertEqual(sum(1 for x in events if x.kind != "earthquake"), 3)
        # GDACS PNG M5.8 and USGS M5.8 near Madang are the same quake
        png = [x for x in events if x.kind == "earthquake" and x.magnitude == 5.8 and x.lat < 0]
        self.assertEqual(len(png), 1)
        self.assertEqual({r["source"] for r in png[0].reports}, {"usgs", "gdacs"})

    def test_quake_severity(self):
        self.assertEqual([quake_severity(m) for m in (None, 3.9, 4.0, 5.5, 6.5)],
                         ["unknown", "minor", "moderate", "severe", "extreme"])


class FilterTest(unittest.TestCase):
    def test_magnitude(self):
        e = merge([quake("afad", mag=3.9)])[0]
        self.assertFalse(matches(e, {"min_magnitude": 4}, NOW))
        self.assertTrue(matches(e, {"min_magnitude": 3.5}, NOW))

    def test_gdacs_impact_bypasses_magnitude(self):
        g = replace(quake("gdacs", mag=5.2), severity="severe")
        e = merge([g])[0]
        self.assertTrue(matches(e, {"min_magnitude": 6}, NOW))
        # but a magnitude-derived "severe" does not
        e2 = merge([quake("usgs", mag=5.6)])[0]
        self.assertEqual(e2.severity, "severe")
        self.assertFalse(matches(e2, {"min_magnitude": 6}, NOW))

    def test_severity_for_other_kinds(self):
        w = Alert(id="w", source="cap", kind="weather", title="t", time=NOW, severity="moderate")
        self.assertFalse(matches(w, {"min_severity": "severe"}, NOW))
        self.assertTrue(matches(w, {"min_severity": "Moderate"}, NOW))

    def test_area(self):
        e = merge([quake("afad", lat=41.0, lon=29.0)])[0]
        self.assertTrue(matches(e, {"bbox": [25.5, 35.5, 45, 42.5]}, NOW))
        self.assertFalse(matches(e, {"bbox": [0, 0, 10, 10]}, NOW))
        ist = {"regions": [{"name": "Istanbul", "lat": 41.01, "lon": 28.98, "radius_km": 50}]}
        self.assertTrue(matches(e, ist, NOW))
        far = merge([quake("afad", lat=38.4, lon=27.1)])[0]  # Izmir
        self.assertFalse(matches(far, ist, NOW))

    def test_area_name_for_geometry_less_alerts(self):
        w = Alert(id="w", source="cap", kind="weather", title="t", time=NOW, area="Attica")
        self.assertTrue(matches(w, {"regions": [{"name": "attica", "lat": 0, "lon": 0, "radius_km": 1}]}, NOW))
        self.assertFalse(matches(w, {"bbox": [0, 0, 1, 1]}, NOW))

    def test_age_and_kinds(self):
        old = quake("afad", sec=-7 * 3600)
        self.assertFalse(matches(old, {"max_age_hours": 6}, NOW))
        self.assertFalse(matches(quake("afad"), {"kinds": ["flood"]}, NOW))


if __name__ == "__main__":
    unittest.main()
