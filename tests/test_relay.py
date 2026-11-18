import io
import json
import tempfile
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from helpers import FIX

from alertpages import cli, http, state, telegram
from alertpages.i18n import strings
from alertpages.model import Alert

UTC = timezone.utc
NOW = datetime(2026, 11, 18, 5, tzinfo=UTC)
FAKE_TOKEN = "123456:TEST-not-a-real-token"


def alert(**kw):
    base = dict(id="afad:1", source="afad", kind="earthquake", title="Pazarcık (Kahramanmaraş)",
                area="Pazarcık (Kahramanmaraş)", time=NOW, lat=37.6, lon=37.4, magnitude=4.4,
                depth_km=7.0, severity="moderate", url="https://example.org/?a=1&b=<2>")
    base.update(kw)
    return Alert(**base)


class StateTest(unittest.TestCase):
    def test_404_means_first_deploy(self):
        with mock.patch.object(state, "fetch", side_effect=http.FetchError("nope", status=404)):
            self.assertEqual(state.load(url="https://x/state.json").status, "missing")

    def test_other_errors_mean_unavailable(self):
        with mock.patch.object(state, "fetch", side_effect=http.FetchError("timeout")):
            self.assertEqual(state.load(url="https://x/state.json").status, "unavailable")
        with mock.patch.object(state, "fetch", return_value=b"<html>not json"):
            self.assertEqual(state.load(url="https://x/state.json").status, "unavailable")

    def test_prune(self):
        s = state.State()
        s.add(["old"], NOW - timedelta(days=30))
        s.add(["new"], NOW)
        s.prune(NOW)
        self.assertEqual(list(s.seen), ["new"])


class TelegramTest(unittest.TestCase):
    def test_format_escapes_and_localizes(self):
        text = telegram.format_alert(alert(), "tr", "Europe/Istanbul")
        self.assertIn("<b>M4.4 Deprem</b>", text)
        self.assertIn("2026-11-18 08:00", text)  # UTC+3
        self.assertIn("&amp;b=&lt;2&gt;", text)
        self.assertIn("Kaynaklar: AFAD 4.4", text)

    def test_token_never_in_errors(self):
        err = urllib.error.URLError(f"failed https://api.telegram.org/bot{FAKE_TOKEN}/sendMessage")
        with mock.patch("urllib.request.urlopen", side_effect=err):
            with self.assertRaises(http.FetchError) as ctx:
                telegram.send(FAKE_TOKEN, "@chan", "hi", retries=0)
        self.assertNotIn(FAKE_TOKEN, str(ctx.exception))
        self.assertIn("***", str(ctx.exception))

    def test_cap_and_failures(self):
        alerts = [alert(id=f"afad:{i}", magnitude=4 + i / 10, time=NOW + timedelta(minutes=i)) for i in range(5)]
        sent = []

        def fake_send(token, chat, text, retries=2):
            if "M4.4" in text:
                raise http.FetchError("HTTP 500")
            sent.append(text)

        with mock.patch.object(telegram, "send", fake_send), mock.patch.object(telegram.time, "sleep"):
            failed = telegram.relay(alerts, FAKE_TOKEN, "@chan", max_messages=3, log=lambda *_: None)
        self.assertEqual([a.id for a in failed], ["afad:4"])
        self.assertEqual(len(sent), 2)  # the 3 strongest, one of which failed
        self.assertIn("M4.2", sent[0])  # still oldest-first


class EndToEndTest(unittest.TestCase):
    def run_cli(self, out, state_file, extra=()):
        argv = ["run", "-c", str(FIX / "offline.toml"), "--fixtures", str(FIX), "-o", out,
                "--state-file", state_file, "--now", "2026-11-18T05:00:00+00:00", *extra]
        buf = io.StringIO()
        with redirect_stdout(buf), mock.patch.object(telegram, "send") as send, \
                mock.patch.object(telegram.time, "sleep"), \
                mock.patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": FAKE_TOKEN, "TELEGRAM_CHAT_ID": "@c"}):
            code = cli.main(argv)
        self.assertEqual(code, 0)
        return send, buf.getvalue()

    def test_prime_then_dedupe(self):
        with tempfile.TemporaryDirectory() as d:
            out, st = str(Path(d) / "site"), str(Path(d) / "state.json")
            send, log = self.run_cli(out, st)
            self.assertEqual(send.call_count, 0)
            self.assertIn("priming", log)
            self.assertIn("42 reports -> 30 events", log)
            Path(st).write_text(Path(out, "state.json").read_text())
            send, _ = self.run_cli(out, st)
            self.assertEqual(send.call_count, 0)

            # forget one AFAD event: only that one is relayed, once
            data = json.loads(Path(st).read_text())
            del data["seen"]["afad:734497"], data["seen"]["emsc:20261118_0000063"]
            Path(st).write_text(json.dumps(data))
            send, _ = self.run_cli(out, st)
            self.assertEqual(send.call_count, 1)
            self.assertIn("Pazarcık", send.call_args.args[2])
            self.assertNotIn(FAKE_TOKEN, send.call_args.args[2])

    def test_backlog_and_site(self):
        with tempfile.TemporaryDirectory() as d:
            out = str(Path(d) / "site")
            send, _ = self.run_cli(out, str(Path(d) / "none.json"), ["--send-backlog"])
            self.assertEqual(send.call_count, 6)  # M2+ inside Türkiye, AFAD/EMSC pairs merged
            files = {p.name for p in Path(out).iterdir()}
            for f in ("index.html", "app.js", "sw.js", "style.css", "manifest.webmanifest",
                      "alerts.json", "feed.xml", "state.json", "i18n.json", "icon.svg", ".nojekyll"):
                self.assertIn(f, files)
            data = json.loads(Path(out, "alerts.json").read_text())
            self.assertEqual(len(data["alerts"]), 30)
            self.assertEqual(sum(s["ok"] for s in data["sources"]), 6)
            ET.fromstring(Path(out, "feed.xml").read_bytes())
            index = Path(out, "index.html").read_text()
            self.assertNotIn("{{", index)
            self.assertNotIn("{{", Path(out, "sw.js").read_text())

    def test_failed_source_is_reported_not_fatal(self):
        cfg = (FIX / "offline.toml").read_text().replace('fixture = "afad.json"', 'fixture = "missing.json"')
        with tempfile.TemporaryDirectory() as d:
            c = Path(d) / "c.toml"
            c.write_text(cfg)
            with redirect_stdout(io.StringIO()):
                code = cli.main(["run", "-c", str(c), "--fixtures", str(FIX), "-o", d + "/s", "--dry-run",
                                 "--now", "2026-11-18T05:00:00+00:00"])
            self.assertEqual(code, 0)
            src = json.loads(Path(d, "s", "alerts.json").read_text())["sources"]
            self.assertFalse(next(s for s in src if s["name"] == "afad")["ok"])


class I18nTest(unittest.TestCase):
    def test_all_languages_have_all_keys(self):
        s = strings()
        def keys(d, p=""):
            return {p + k for k, v in d.items() for k in ([k] if not isinstance(v, dict) else [k + "." + x for x in v])}
        ref = keys(s["en"])
        for lang, d in s.items():
            self.assertEqual(keys(d), ref, lang)


if __name__ == "__main__":
    unittest.main()
