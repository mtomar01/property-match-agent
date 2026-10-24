import { useCallback, useEffect, useState } from "react";
import { Card, Checkin, Deck as DeckData, DeckCard, Decision, HardLimits, Message, Summary, SwipeStats, getDeck, getShortlist, getState, resetSearch, sendChat, sendSwipe, undoSwipe, answerCheckin } from "./api";
import { Bar } from "./Bar";
import { Chat } from "./Chat";
import { Deck } from "./Deck";
import { Shortlist } from "./Shortlist";

// The flow from D61: the chat takes the width until the assistant is ready, then the deck comes up with
// the card as a bar above it. Every change, including a yes to a check-in, goes through the chat.
export function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [card, setCard] = useState<Card | null>(null);
  const [searchedAs, setSearchedAs] = useState<Partial<HardLimits> | null>(null);
  const [ready, setReady] = useState(false);
  const [unsupported, setUnsupported] = useState(false);
  const [deck, setDeck] = useState<DeckData | null>(null);
  const [queue, setQueue] = useState<DeckCard[]>([]);
  const [checkin, setCheckin] = useState<Checkin | null>(null);
  const [stats, setStats] = useState<SwipeStats | null>(null);
  const [canUndo, setCanUndo] = useState(false);
  const [shortlist, setShortlist] = useState<Summary[]>([]);
  const [view, setView] = useState<"deck" | "shortlist">("deck");
  const [busy, setBusy] = useState<"chat" | "swipe" | "deck" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState("");
  const [areas, setAreas] = useState<string[]>([]);

  const fail = (err: unknown) => setError(err instanceof Error ? err.message : String(err));

  const loadDeck = useCallback(async () => {
    setBusy("deck");
    try {
      const next = await getDeck(10);
      setDeck(next);
      setQueue(next.cards);
      setStats(next.swipes);
      setCanUndo(next.can_undo);
      setData(next.data);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(null);
    }
  }, []);

  useEffect(() => {
    getState().then((state) => {
      setMessages(state.messages);
      setCard(state.card);
      setSearchedAs(state.searched_as);
      setStats(state.swipes);
      setData(state.data);
      setAreas(state.areas);
      setUnsupported(state.unsupported.includes("rent") || state.card?.intent === "rent");
      if (state.checkin && state.card) {  // a check-in left waiting: show it again (D72)
        setReady(true);
        setCheckin(state.checkin);
        void loadDeck();
      } else if (state.action === "confirm" && state.card && state.card.intent !== "rent") {
        setReady(true);
        void loadDeck();
      }
    }).catch(fail);
    getShortlist().then((s) => setShortlist(s.homes)).catch(() => undefined);
  }, [loadDeck]);

  const send = async (text: string) => {
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy("chat");
    setError(null);
    try {
      const reply = await sendChat(text);
      setMessages((m) => [...m, { role: "assistant", text: reply.reply }]);
      setCard(reply.card);
      setSearchedAs(reply.searched_as);
      setStats(reply.swipes);
      setUnsupported(reply.unsupported.includes("rent") || reply.card.intent === "rent");
      setCheckin(null);
      if (reply.deck_ready) {
        setReady(true);
        setView("deck");
        await loadDeck();
      }
    } catch (err) {
      fail(err);
    } finally {
      setBusy(null);
    }
  };

  const swipe = useCallback(async (home: DeckCard, decision: Decision, reasons: string[], note?: string) => {
    setBusy("swipe");
    setError(null);
    try {
      const result = await sendSwipe({ listing_id: home.listing_id, decision, reasons, note, deck_position: home.deck_position, explore_card: home.explore_card });
      setStats(result.swipes);
      setCanUndo(result.can_undo);
      setQueue((q) => q.filter((c) => c.listing_id !== home.listing_id));
      // a skipped home still waits at the end of the deck, so it stays in the count (D71)
      setDeck((d) => d ? { ...d, remaining: d.remaining - (decision === "skip" ? 0 : 1), swipes: result.swipes, since_checkin: result.since_checkin } : d);
      if (decision === "like") setShortlist((s) => [home, ...s]);
      if (result.checkin) {
        setCheckin(result.checkin);
        setMessages((m) => [...m, { role: "assistant", text: result.checkin!.reply }]);
      }
      // a new search starts the like rate from zero, so the header follows the server's counts
    } catch (err) {
      fail(err);
    } finally {
      setBusy(null);
    }
  }, []);

  // A tap on a ladder question (D75): "no" to a tapped reason, or a pulse answer. A follow-up shows in the chat.
  const tap = useCallback(async (answer: string) => {
    setBusy("swipe");
    setError(null);
    try {
      const result = await answerCheckin(answer);
      setStats(result.swipes);
      setCheckin(null);
      if (result.follow_up) setMessages((m) => [...m, { role: "assistant", text: result.follow_up! }]);
      if (result.focus_chat) setTimeout(() => document.getElementById("message")?.focus(), 50);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(null);
    }
  }, []);

  // The back button: the last decision is taken back and its home returns to the front (D71).
  const undo = useCallback(async () => {
    setBusy("swipe");
    setError(null);
    try {
      const result = await undoSwipe();
      setStats(result.swipes);
      setCanUndo(result.can_undo);
      if (result.card) {
        const back = result.card;
        setQueue((q) => [back, ...q.filter((c) => c.listing_id !== back.listing_id)]);
        if (result.undone === "like") setShortlist((s) => s.filter((h) => h.listing_id !== back.listing_id));
        setDeck((d) => d ? { ...d, remaining: d.remaining + (result.undone === "skip" ? 0 : 1), swipes: result.swipes, since_checkin: result.since_checkin } : d);
      }
    } catch (err) {
      fail(err);
    } finally {
      setBusy(null);
    }
  }, []);

  useEffect(() => {
    if (ready && deck && queue.length <= 2 && deck.remaining > queue.length && busy === null && !checkin) void loadDeck();
  }, [ready, deck, queue.length, busy, checkin, loadDeck]);

  const startOver = async () => {
    if (!window.confirm("Start a new search? Your swipes and shortlist stay.")) return;
    try {
      const state = await resetSearch();
      setMessages(state.messages);
      setCard(null);
      setSearchedAs(null);
      setReady(false);
      setDeck(null);
      setQueue([]);
      setCheckin(null);
      setStats(state.swipes);
      setView("deck");
    } catch (err) {
      fail(err);
    }
  };

  const current = queue[0] ?? null;
  const nextCheckin = deck ? Math.max(0, deck.checkin_every - deck.since_checkin) : null;

  return (
    <>
      <header className="top">
        <div className="brand">
          <h1>Property Match</h1>
          <span className="muted small">{areas.join(" · ")}{data ? ` · ${data}` : ""}</span>
        </div>
        <div className="top-right">
          {stats && stats.swipes > 0 && (
            <span className="muted small">
              {stats.swipes} swiped · {stats.likes} liked
              {stats.like_rate != null ? ` · ${Math.round(stats.like_rate * 100)}% like rate` : ""}
              {ready && nextCheckin != null ? ` · check-in in ${nextCheckin}` : ""}
            </span>
          )}
          {(messages.length > 0 || ready) && <button type="button" className="link" onClick={startOver}>New search</button>}
        </div>
      </header>

      {!ready ? (
        <main className="layout single">
          <Chat messages={messages} busy={busy === "chat"} error={error} onSend={send} />
          {unsupported && <p className="hint center">Rentals aren't supported yet; the deck is for buying.</p>}
        </main>
      ) : (
        <main className="layout deck-layout">
          {card && searchedAs && <Bar card={card} searched={searchedAs} />}
          <nav className="tabs" aria-label="Views">
            <button type="button" className={`tab ${view === "deck" ? "on" : ""}`} onClick={() => setView("deck")}>Homes</button>
            <button type="button" className={`tab ${view === "shortlist" ? "on" : ""}`} onClick={() => setView("shortlist")}>
              Shortlist{shortlist.length ? ` (${shortlist.length})` : ""}
            </button>
          </nav>
          <div className="deck-and-chat">
            {view === "deck" ? (
              <Deck deck={deck} card={current} checkin={checkin} busy={busy !== null} canUndo={canUndo} onSwipe={swipe} onUndo={undo} onAnswer={send} onTap={tap} />
            ) : (
              <Shortlist homes={shortlist} />
            )}
            <Chat messages={messages} busy={busy === "chat"} error={error} compact onSend={send} />
          </div>
        </main>
      )}
    </>
  );
}
