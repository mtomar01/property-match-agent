"""The beta at one address (D100): a session per visitor from the invite link, the purge after idle minutes, the caps.

Served for real on a free local port with the fake model from test_api, so no paid calls.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from api.server import SESSION_COOKIE, App, Beta, serve
from test_api import FakeModel


@pytest.fixture()
def beta_server(tmp_path):
    clock = {"now": 1_800_000_000.0}
    metrics = tmp_path / "metrics.jsonl"

    def make_app(user_id):
        return App(client=FakeModel(), cache_dir=None, user_id=user_id, state_dir=tmp_path / "state", swipes_dir=tmp_path / "swipes")

    beta = Beta(make_app, invite="friends-2026", idle_minutes=15, per_visitor=2, per_day=3, metrics_path=metrics,
                clock=lambda: clock["now"])
    server = serve(port=0, beta=beta)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(NoRedirect)

    def ask(path, body=None, cookie=None):
        data = json.dumps(body).encode() if body is not None else None
        headers = {"Content-Type": "application/json"}
        if cookie:
            headers["Cookie"] = f"{SESSION_COOKIE}={cookie}"
        request = urllib.request.Request(base + path, data=data, headers=headers)
        try:
            with opener.open(request) as response:
                raw = response.read()
                kind = response.headers.get("Content-Type", "")
                return response.status, (json.loads(raw) if "json" in kind else raw.decode("utf-8")), response.headers
        except urllib.error.HTTPError as err:
            raw = err.read()
            return err.code, (json.loads(raw) if "json" in (err.headers.get("Content-Type") or "") else raw.decode("utf-8")), err.headers

    yield ask, beta, clock, metrics, tmp_path
    server.shutdown()


def invite(ask, token="friends-2026"):
    status, _, headers = ask(f"/?invite={token}")
    assert status == 302 and headers["Location"] == "/"
    cookie = headers["Set-Cookie"]
    assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=Lax" in cookie
    return cookie.split(";")[0].split("=", 1)[1]


def test_the_door_is_the_invite_link_and_the_cookie_is_signed(beta_server):
    ask, beta, _, _, _ = beta_server
    status, page, _ = ask("/")
    assert status == 200 and "private beta" in page  # the gate page, not the app
    status, out, _ = ask("/api/state")
    assert status == 401 and "invite" in out["error"]
    status, page, _ = ask("/?invite=wrong")
    assert status == 200 and "private beta" in page  # a wrong token sees the gate too
    status, _, _ = ask("/robots.txt")
    assert status == 200
    cookie = invite(ask)
    status, state, _ = ask("/api/state", cookie=cookie)
    assert status == 200 and state["messages"] == []
    user_id, signature = cookie.split(".")
    forged = f"{user_id}.{'0' * len(signature)}"
    status, _, _ = ask("/api/state", cookie=forged)
    assert status == 401  # a cookie without the right signature is nobody's
    assert beta.session_from(f"{SESSION_COOKIE}={cookie}") == user_id


def test_every_visitor_has_a_search_of_their_own(beta_server):
    ask, _, _, _, _ = beta_server
    a, b = invite(ask), invite(ask)
    assert a != b
    ask("/api/chat", {"text": "Egaleo up to 250k"}, cookie=a)
    _, state_a, _ = ask("/api/state", cookie=a)
    _, state_b, _ = ask("/api/state", cookie=b)
    assert len(state_a["messages"]) == 2 and state_b["messages"] == [] and state_b["searches"] == []
    _, deck, _ = ask("/api/deck", {"limit": 2}, cookie=a)
    ask("/api/swipe", {"listing_id": deck["cards"][0]["listing_id"], "decision": "like"}, cookie=a)
    _, short_b, _ = ask("/api/shortlist", cookie=b)
    assert short_b["homes"] == []  # a's like is not b's


def test_the_caps_stop_the_paid_route_with_a_sentence(beta_server):
    ask, _, _, _, _ = beta_server
    a = invite(ask)
    assert ask("/api/chat", {"text": "Egaleo up to 250k"}, cookie=a)[0] == 200
    assert ask("/api/chat", {"text": "make it 220k"}, cookie=a)[0] == 200
    status, out, _ = ask("/api/chat", {"text": "and 2 bedrooms"}, cookie=a)
    assert status == 429 and "limit for one visitor" in out["error"]  # the second cap: 2 turns a visitor
    assert ask("/api/deck", {"limit": 2}, cookie=a)[0] == 200  # the deck and the swipes still work
    b = invite(ask)
    assert ask("/api/chat", {"text": "Peristeri up to 200k"}, cookie=b)[0] == 200
    status, out, _ = ask("/api/chat", {"text": "make it 180k"}, cookie=b)
    assert status == 429 and "budget for today" in out["error"]  # the day's cap: 3 in all


def test_an_idle_session_is_wiped_and_leaves_one_anonymous_line(beta_server):
    ask, beta, clock, metrics, tmp_path = beta_server
    a = invite(ask)
    ask("/api/chat", {"text": "Egaleo up to 250k"}, cookie=a)
    _, deck, _ = ask("/api/deck", {"limit": 1}, cookie=a)
    ask("/api/swipe", {"listing_id": deck["cards"][0]["listing_id"], "decision": "like"}, cookie=a)
    user_id = a.split(".")[0]
    assert list((tmp_path / "state").glob(f"{user_id}.*")) and list((tmp_path / "swipes").glob(f"{user_id}.*"))
    clock["now"] += 14 * 60
    assert beta.purge() == []  # 14 minutes: still there
    clock["now"] += 2 * 60
    assert beta.purge() == [user_id]  # 16 minutes idle: gone
    assert not list((tmp_path / "state").glob(f"{user_id}.*")) and not list((tmp_path / "swipes").glob(f"{user_id}.*"))
    line = json.loads(metrics.read_text().splitlines()[-1])
    assert line["turns"] == 1 and line["swipes"] == 1 and line["likes"] == 1 and len(line["session"]) == 12
    assert user_id not in line["session"] and "Egaleo" not in metrics.read_text()  # counts only, nothing said
    _, state, _ = ask("/api/state", cookie=a)  # the same cookie starts clean
    assert state["messages"] == [] and state["searches"] == []
