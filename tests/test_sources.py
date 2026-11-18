import unittest
from datetime import datetime, timezone

from helpers import raw

from alertpages.sources import afad, cap, emsc, gdacs, kandilli, rss, usgs

UTC = timezone.utc


class AfadTest(unittest.TestCase):
    def test_parse(self):
        a = afad.parse(raw("afad.json"))
        self.assertEqual(len(a), 10)
        first = a[0]
        self.assertEqual(first.id, "afad:734497")
        self.assertEqual(first.time, datetime(2026, 11, 18, 4, 28, 56, tzinfo=UTC))
        self.assertAlmostEqual(first.lat, 37.62033)
        self.assertAlmostEqual(first.lon, 37.36083)
        self.assertEqual(first.magnitude, 2.2)
        self.assertEqual(first.depth_km, 7.0)
        self.assertEqual(first.area, "Pazarcık (Kahramanmaraş)")

    def test_url_window(self):
        u = afad.url({"lookback_hours": 6, "min_magnitude": 3}, datetime(2026, 11, 18, 12, tzinfo=UTC))
        self.assertIn("start=2026-11-18T06%3A00%3A00", u)
        self.assertIn("minmag=3", u)


class KandilliTest(unittest.TestCase):
    def setUp(self):
        self.a = kandilli.parse(raw("kandilli_lst0.html"))

    def test_count_and_local_time(self):
        self.assertEqual(len(self.a), 8)
        # 2026.11.10 12:31:20 Turkish time == 09:31:20 UTC
        self.assertEqual(self.a[0].time, datetime(2026, 11, 10, 9, 31, 20, tzinfo=UTC))

    def test_quality_suffix_removed(self):
        self.assertEqual(self.a[0].area, "SARITOSUN-(ELAZIG)")
        self.assertEqual(self.a[2].area, "SAROS KORFEZI (EGE DENIZI)")
        self.assertTrue(self.a[2].title.endswith("(revised)"))

    def test_prefers_mw_over_ml(self):
        aegean = self.a[4]  # ML 3.4, Mw 3.3
        self.assertEqual(aegean.magnitude, 3.3)
        self.assertEqual(self.a[0].magnitude, 1.9)  # only ML present

    def test_windows_1254(self):
        body = raw("kandilli_lst0.html").decode("utf-8").encode("windows-1254")
        again = kandilli.parse(body)
        self.assertEqual([x.id for x in again], [x.id for x in self.a])


class EmscTest(unittest.TestCase):
    def test_parse(self):
        a = emsc.parse(raw("emsc.json"))
        self.assertEqual(len(a), 10)
        self.assertEqual(a[0].id, "emsc:20261118_0000063")
        self.assertEqual(a[0].time.replace(microsecond=0), datetime(2026, 11, 18, 4, 28, 56, tzinfo=UTC))
        self.assertEqual(a[0].area, "Central Turkey")

    def test_bbox_query(self):
        u = emsc.url({"bbox": [25.5, 35.5, 45, 42.5]}, datetime(2026, 11, 18, tzinfo=UTC))
        for part in ("minlon=25.5", "minlat=35.5", "maxlon=45", "maxlat=42.5"):
            self.assertIn(part, u)


class UsgsTest(unittest.TestCase):
    def test_parse(self):
        a = usgs.parse(raw("usgs.json"))
        self.assertEqual(len(a), 8)
        self.assertEqual(a[0].id, "usgs:us7000tyxc")
        self.assertEqual(a[0].magnitude, 5.2)
        self.assertIsNotNone(a[0].lat)
        self.assertTrue(a[0].url.startswith("https://earthquake.usgs.gov/"))


class GdacsTest(unittest.TestCase):
    def setUp(self):
        self.a = gdacs.parse(raw("gdacs.xml"))

    def test_parse(self):
        self.assertEqual(len(self.a), 6)
        eq = self.a[0]
        self.assertEqual(eq.kind, "earthquake")
        self.assertEqual(eq.magnitude, 5.8)
        self.assertEqual(eq.severity, "minor")
        self.assertEqual(eq.id, "gdacs:EQ1577911:green")
        self.assertEqual(eq.time, datetime(2026, 11, 18, 3, 42, 34, tzinfo=UTC))
        self.assertAlmostEqual(eq.lat, -5.7009)

    def test_cyclone_orange_is_severe(self):
        tc = [x for x in self.a if x.kind == "cyclone"]
        self.assertEqual(len(tc), 1)
        self.assertEqual(tc[0].severity, "severe")
        self.assertIsNone(tc[0].magnitude)


class CapTest(unittest.TestCase):
    def test_atom_feed(self):
        now = datetime(2026, 11, 15, 12, tzinfo=UTC)
        a = cap.parse(raw("meteoalarm_greece.atom"), {"name": "meteoalarm", "kind": "weather"}, now=now)
        self.assertEqual(len(a), 4)
        self.assertEqual({x.severity for x in a}, {"moderate"})
        self.assertIn("Epirus", [x.area for x in a])
        self.assertEqual(len({x.id for x in a}), 4)

    def test_expired_dropped(self):
        now = datetime(2026, 11, 18, tzinfo=UTC)
        self.assertEqual(cap.parse(raw("meteoalarm_greece.atom"), {}, now=now), [])

    def test_single_alert_document(self):
        doc = b"""<?xml version="1.0"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>TEST-1</identifier><sender>test</sender>
  <sent>2026-11-18T05:00:00+03:00</sent><status>Actual</status><msgType>Alert</msgType>
  <info><language>en</language><event>Flood</event><severity>Severe</severity>
    <headline>Test flood warning</headline><expires>2026-11-19T00:00:00+00:00</expires>
    <area><areaDesc>Test valley</areaDesc><circle>41.0,29.0 10</circle></area></info>
  <info><language>tr</language><event>Sel</event><severity>Severe</severity>
    <headline>Test sel uyarisi</headline><area><areaDesc>Test vadisi</areaDesc></area></info>
</alert>"""
        now = datetime(2026, 11, 18, 3, tzinfo=UTC)
        a = cap.parse(doc, {"kind": "flood", "language": "en"}, now=now)
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0].severity, "severe")
        self.assertEqual((a[0].lat, a[0].lon), (41.0, 29.0))
        self.assertEqual(a[0].time, datetime(2026, 11, 18, 2, tzinfo=UTC))

    def test_test_status_ignored(self):
        doc = b"""<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2"><identifier>x</identifier>
<sent>2026-11-18T00:00:00Z</sent><status>Exercise</status><info><event>x</event></info></alert>"""
        self.assertEqual(cap.parse(doc, {}), [])


class RssTest(unittest.TestCase):
    def test_items(self):
        doc = b"""<rss version="2.0"><channel><title>t</title>
<item><title>Bulletin 1</title><link>https://example.org/1</link><guid>b1</guid>
<pubDate>Wed, 18 Nov 2026 03:56:50 GMT</pubDate></item></channel></rss>"""
        a = rss.parse(doc, {"name": "bulletin"})
        self.assertEqual(a[0].id, "bulletin:b1")
        self.assertEqual(a[0].time, datetime(2026, 11, 18, 3, 56, 50, tzinfo=UTC))


if __name__ == "__main__":
    unittest.main()
