"""Tests für den Gringo-Notizblock (Speicher, Chat-Anbindung, Webserver)."""

from __future__ import annotations

import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from openjarvis import gringo_notes as gn


@pytest.fixture(autouse=True)
def _home(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENJARVIS_HOME", str(tmp_path))
    return tmp_path


# ── Speicher ─────────────────────────────────────────────────────────


def test_add_list_archive():
    a = gn.add_note("Zahnarzt anrufen")
    b = gn.add_note("Dünger kaufen", datum="2026-11-25T14:00")
    assert [n["text"] for n in gn.list_notes()] == ["Zahnarzt anrufen", "Dünger kaufen"]
    assert gn.archive_notes([a["id"]]) == 1
    assert [n["id"] for n in gn.list_notes()] == [b["id"]]
    archiv = json.loads(gn.notes_path().read_text(encoding="utf-8"))["archiv"]
    assert archiv[0]["text"] == "Zahnarzt anrufen" and archiv[0]["grund"] == "erledigt"


def test_empty_note_rejected():
    with pytest.raises(ValueError):
        gn.add_note("   ")


def test_corrupt_file_is_backed_up_not_lost():
    gn.notes_path().write_text("{kaputt", encoding="utf-8")
    assert gn.list_notes() == []
    assert gn.notes_path().with_suffix(".kaputt.json").exists()


# ── Chat-Anbindung ───────────────────────────────────────────────────


def test_no_notes_no_context():
    assert gn.notes_context("Hallo", 1) is None


def test_first_message_presents_notes_and_marks_them():
    gn.add_note("Dünger kaufen")
    ctx = gn.notes_context("Hallo Gringo", 1)
    assert ctx and "1. Dünger kaufen" in ctx
    assert gn.list_notes()[0]["status"] == "vorgelegt"
    # mitten im Gespräch ohne Stichwort: nichts Neues
    assert gn.notes_context("Wie geht's?", 5) is None


def test_keyword_presents_notes_mid_conversation():
    gn.add_note("Tomaten gießen")
    assert "Tomaten gießen" in (gn.notes_context("Was steht an?", 6) or "")


def test_done_archives_only_presented():
    gn.add_note("A")
    gn.notes_context("Hallo", 1)  # A vorgelegt
    gn.add_note("B")  # neu, noch nicht gesehen
    ctx = gn.notes_context("Alles erledigt, kannst du löschen", 3)
    assert ctx and "1 Notiz" in ctx
    assert [n["text"] for n in gn.list_notes()] == ["B"]


def test_done_by_number():
    gn.add_note("A")
    gn.add_note("B")
    gn.add_note("C")
    gn.notes_context("Notizen", 1)
    gn.notes_context("Notiz 2 und 3 erledigt", 2)
    assert [n["text"] for n in gn.list_notes()] == ["A"]


def test_add_via_chat():
    ctx = gn.notes_context("Notiz: Montag Steuerberater anrufen", 3)
    assert ctx and "Steuerberater" in ctx
    n = gn.list_notes()
    assert n[0]["text"] == "Montag Steuerberater anrufen" and n[0]["quelle"] == "gringo"


def test_notiz_number_done_is_not_mistaken_for_add():
    gn.add_note("A")
    gn.notes_context("Hallo", 1)
    gn.notes_context("Notiz 1 erledigt", 2)
    assert gn.list_notes() == []


def test_weather_prefix_is_ignored():
    text = "## Echte Wetterdaten\nHeubach 5 °C\n\n---\nFrage vom Chef: Notiz: Gießen"
    gn.notes_context(text, 2)
    assert gn.list_notes()[0]["text"] == "Gießen"


# ── Webserver ────────────────────────────────────────────────────────


@pytest.fixture()
def server():
    key = gn.load_or_create_key()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), gn.make_handler(key, 0))
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield httpd.server_address[1], key
    httpd.shutdown()
    httpd.server_close()


def _req(port, method, path, body=None, headers=None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request(method, path, body=body, headers=headers or {})
    r = c.getresponse()
    return r.status, r.read(), dict(r.getheaders())


def test_server_local_roundtrip(server):
    port, _ = server
    st, body, _h = _req(port, "GET", "/")
    assert st == 200 and b"Gringo Notizblock" in body
    st, body, _h = _req(
        port, "POST", "/api/notes", json.dumps({"text": "Test"}), {"X-Gringo": "1"}
    )
    assert st == 201
    nid = json.loads(body)["id"]
    assert json.loads(_req(port, "GET", "/api/notes")[1])["notes"][0]["text"] == "Test"
    st, _b, _h = _req(port, "POST", f"/api/notes/{nid}/done", headers={"X-Gringo": "1"})
    assert st == 200 and gn.list_notes() == []


def test_post_needs_custom_header_and_matching_origin(server):
    port, _ = server
    body = json.dumps({"text": "x"})
    assert _req(port, "POST", "/api/notes", body)[0] == 403
    bad = {"X-Gringo": "1", "Origin": "http://evil.example"}
    assert _req(port, "POST", "/api/notes", body, bad)[0] == 403
    assert gn.list_notes() == []


def test_rebinding_host_needs_key(server):
    port, key = server
    # Fremder Host-Name (DNS-Rebinding) gilt nicht als „lokal“
    assert _req(port, "GET", "/api/notes", headers={"Host": "evil.example"})[0] == 401
    # mit Schlüssel wird ein Cookie gesetzt und weitergeleitet
    st, _b, h = _req(port, "GET", f"/?key={key}", headers={"Host": "evil.example"})
    assert st == 303 and "gringo_key=" in h.get("Set-Cookie", "")
    cookie = {"Host": "evil.example", "Cookie": f"gringo_key={key}"}
    assert _req(port, "GET", "/api/notes", headers=cookie)[0] == 200
    # falscher Schlüssel
    assert _req(port, "GET", "/?key=falsch", headers={"Host": "evil.example"})[0] == 401
