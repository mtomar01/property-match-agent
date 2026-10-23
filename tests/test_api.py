"""The app's web API, served for real on a free local port, with a fake model (no paid calls)."""

import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from agent import interview
from api.server import App, serve
from learning import patterns


def card(**limits):
    hard = {n: None for n in interview.HARD_FIELDS}
    hard.update(property_types=[], exclude_floors=[])
    hard.update(limits)
    return {"intent": "buy", "areas": ["Egaleo"], "hard_limits": hard, "budget_around": False, "ideally": [],
            "preferences": [], "open_questions": []}


class FakeModel:
    """Answers like the interview: ready to search on the first message, then a check-in or a change by chat."""

    def __init__(self):
        self.messages, self.seen, self.card = self, [], card(max_price_eur=250000)

    def create(self, **body):
        self.seen.append(body["messages"])
        last = body["messages"][-1]["content"]
        text = last if isinstance(last, str) else ""
        if text.startswith("<swipe_stats>"):
            note = json.loads(text.split("\n")[2])
            reply, action, asking = f"Noticed: {note['evidence']}. Shall I?", "ask", ["suggest_change"]
            self.pending = note["patch"]
        elif text.lower() in ("yes", "ναι") and getattr(self, "pending", None):
            self.card = patterns.apply(self.card, self.pending)
            reply, action, asking = "Done. Searching again.", "confirm", []
        elif text.lower() == "no":
            reply, action, asking = "Kept as it was.", "confirm", []
        else:
            reply, action, asking = "Buying in Egaleo up to €250,000: here come the homes.", "confirm", []
        out = {"reasoning": "", "reply": reply, "action": action, "asking_about": asking, "not_covered_areas": [],
               "declined_advice": [], "unsupported": [], "criteria": self.card}
        usage = SimpleNamespace(input_tokens=1, output_tokens=1, cache_creation_input_tokens=0, cache_read_input_tokens=0)
        return SimpleNamespace(stop_reason="end_turn", usage=usage, content=[SimpleNamespace(type="text", text=json.dumps(out))])


@pytest.fixture()
def api(tmp_path):
    model = FakeModel()
    app = App(client=model, cache_dir=None, user_id="test", state_dir=tmp_path / "state", swipes_dir=tmp_path / "swipes")
    server = serve(app, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"

    def ask(path, body=None, raw=False):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(base + path, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, (response.read().decode("utf-8-sig") if raw else json.loads(response.read()))
        except urllib.error.HTTPError as err:
            return err.code, json.loads(err.read())

    yield ask, model, app
    server.shutdown()


def test_chat_keeps_the_conversation_and_says_when_the_deck_is_ready(api):
    ask, model, _ = api
    status, first = ask("/api/chat", {"text": "Αιγάλεω μέχρι 250 χιλιάδες"})
    assert status == 200 and first["action"] == "confirm" and first["deck_ready"]
    assert first["searched_as"]["min_price_eur"] == 125000  # code's lowest price, shown on the bar
    status, second = ask("/api/chat", {"text": "και μπαλκόνι"})
    assert status == 200 and len(model.seen[-1]) == 3  # user, assistant, user: one history per user
    status, state = ask("/api/state")
    assert [m["role"] for m in state["messages"]] == ["user", "assistant", "user", "assistant"]


def test_the_deck_needs_a_card_then_shows_reasons_and_explore_cards(api):
    ask, _, _ = api
    status, out = ask("/api/deck", {})
    assert status == 400 and "first" in out["error"]
    ask("/api/chat", {"text": "Egaleo up to 250k"})
    status, out = ask("/api/deck", {"limit": 10})
    assert status == 200 and out["total_matches"] == 11 and len(out["cards"]) == 10
    assert all(125000 <= c["price_eur"] <= 250000 and c["area"] == "Egaleo" for c in out["cards"])
    assert all(1 <= len(c["reasons"]) <= 2 for c in out["cards"])
    assert [c["explore_card"] for c in out["cards"]] == [False] * 4 + [True] + [False] * 5  # one in five while the top lasts
    assert [c["deck_position"] for c in out["cards"]] == list(range(10))


def test_swipes_are_kept_and_never_shown_again_and_the_shortlist_exports(api):
    ask, _, app = api
    ask("/api/chat", {"text": "Egaleo up to 250k"})
    _, before = ask("/api/deck", {"limit": 3})
    first = before["cards"][0]
    status, out = ask("/api/swipe", {"listing_id": first["listing_id"], "decision": "like", "deck_position": 0})
    assert status == 200 and out["swipes"] == {**out["swipes"], "swipes": 1, "likes": 1, "like_rate": 1.0} and out["checkin"] is None
    status, out = ask("/api/swipe", {"listing_id": before["cards"][1]["listing_id"], "decision": "reject", "reasons": ["too_dark"],
                                     "deck_position": 1})
    assert out["swipes"]["reject_reasons"] == {"too_dark": 1}
    _, after = ask("/api/deck", {"limit": 3})
    assert first["listing_id"] not in {c["listing_id"] for c in after["cards"]} and after["cards"][0]["deck_position"] == 2
    assert ask("/api/swipe", {"listing_id": "nope", "decision": "like"})[0] == 404
    status, short = ask("/api/shortlist")
    assert status == 200 and [h["listing_id"] for h in short["homes"]] == [first["listing_id"]]
    status, csv_text = ask("/api/export.csv", raw=True)
    lines = csv_text.splitlines()
    assert status == 200 and lines[0].startswith("listing_id,price_eur,size_m2") and len(lines) == 2 and first["listing_id"] in lines[1]
    assert app.swipes.path.exists() and "private" in str(app.swipes.path) or "swipes" in str(app.swipes.path)


def test_a_checkin_comes_after_ten_swipes_with_a_pattern_and_a_no_is_not_repeated(api):
    ask, model, app = api
    ask("/api/chat", {"text": "Egaleo up to 250k"})
    _, out = ask("/api/deck", {"limit": 20})
    checkins = []
    for i, c in enumerate(out["cards"][:12]):  # a taste: only recent builds
        decision = "like" if (c["year_built"] or 0) >= 2005 else "reject"
        _, res = ask("/api/swipe", {"listing_id": c["listing_id"], "decision": decision, "deck_position": c["deck_position"],
                                    "explore_card": c["explore_card"]})
        if res["checkin"]:
            checkins.append((i, res["checkin"]))
    assert len(checkins) == 1 and checkins[0][0] >= 9
    checkin = checkins[0][1]
    assert checkin["asking_about"] == ["suggest_change"] and "of" in checkin["reply"] and checkin["suggestion"]["feature"]
    stats_message = model.seen[-1][-1]["content"]
    assert stats_message.startswith("<swipe_stats>") and "patch" in stats_message
    assert app.state["pending"]["key"] == checkin["suggestion"]["key"]
    # the user says no: the card stays, and that suggestion is marked declined
    _, answer = ask("/api/chat", {"text": "no"})
    assert answer["action"] == "confirm" and app.state["pending"] is None
    assert app.state["declined"] == [checkin["suggestion"]["key"]]
    _, state = ask("/api/state")
    assert not any(m["text"].startswith("<swipe_stats>") for m in state["messages"])  # code's note isn't shown as the user's words


def test_a_yes_to_a_checkin_changes_the_card_and_the_deck_follows(api):
    ask, model, app = api
    ask("/api/chat", {"text": "Egaleo up to 250k"})
    _, out = ask("/api/deck", {"limit": 20})
    checkin = None
    for c in out["cards"]:
        if checkin:
            break
        _, res = ask("/api/swipe", {"listing_id": c["listing_id"], "decision": "like" if (c["year_built"] or 0) >= 2005 else "reject",
                                    "deck_position": c["deck_position"]})
        checkin = res["checkin"]
    assert checkin
    _, answer = ask("/api/chat", {"text": "yes"})
    assert answer["action"] == "confirm" and patterns.taken(answer["card"], checkin["suggestion"]["patch"])
    assert app.state["declined"] == []
    _, after = ask("/api/deck", {"limit": 5})
    assert after["total_matches"] <= out["total_matches"]


def test_reset_starts_a_new_search_but_keeps_the_swipes(api):
    ask, _, app = api
    ask("/api/chat", {"text": "Egaleo up to 250k"})
    _, out = ask("/api/deck", {"limit": 1})
    ask("/api/swipe", {"listing_id": out["cards"][0]["listing_id"], "decision": "like"})
    _, state = ask("/api/reset", {})
    assert state["messages"] == [] and state["card"] is None and state["swipes"]["swipes"] == 1


def test_search_never_breaks_a_limit_and_refuses_rentals(api):
    ask, _, _ = api
    status, out = ask("/api/search", {"card": card(max_price_eur=200000)})
    assert status == 200 and out["searched_as"]["max_price_eur"] == 200000
    assert all(100000 <= r["price_eur"] <= 200000 and r["area"] == "Egaleo" for r in out["results"])
    status, out = ask("/api/search", {"card": dict(card(max_price_eur=900), intent="rent")})
    assert status == 400 and "rentals" in out["error"]


def test_a_thin_search_comes_back_with_ways_to_widen_it(api):
    ask, _, _ = api
    thin = dict(card(max_price_eur=190000, min_size_m2=80, max_size_m2=80, property_types=["apartment"]),
                budget_around=True, ideally=["size"])
    status, out = ask("/api/search", {"card": thin})
    assert status == 200 and out["total_matches"] < 5
    together = out["if_eased"]["together"]
    assert together["limits"] == {"max_price_eur": 230000, "min_price_eur": 155000, "min_size_m2": 65, "max_size_m2": 97}
    assert together["matches"] >= 5


def test_a_listing_marks_its_description_untrusted(api):
    ask, _, _ = api
    status, out = ask("/api/listing?id=spitogatos:SYN0001")
    assert status == 200 and "description_untrusted" in out
    assert ask("/api/listing?id=nope")[0] == 404


def test_an_empty_message_is_refused(api):
    ask, _, _ = api
    status, out = ask("/api/chat", {"text": "  "})
    assert status == 400 and "message" in out["error"]
