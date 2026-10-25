import { useCallback, useEffect, useMemo, useState } from "react";
import { Card, Checkin, Deck as DeckData, DeckCard, Decision, HardLimits, Message, Preference, SearchSummary, State, Summary, SwipeStats, getDeck, getSearches, getShortlist, getState, newSearch, selectSearch, sendChat, sendSwipe, undoSwipe, answerCheckin } from "./api";
import { Chat } from "./Chat";
import { Deck } from "./Deck";
import { SearchesIcon } from "./Icons";
import { LimitsBar } from "./LimitsBar";
import { LABELS, LabelsContext, Lang, LangPref, Theme, detectLanguage, titleText } from "./labels";
import { Options } from "./Options";
import { Searches } from "./Searches";
import { Shortlist } from "./Shortlist";

type View = "chat" | "deck" | "shortlist";
const DESKTOP = "(min-width: 900px)";
const isDesktop = () => window.matchMedia(DESKTOP).matches;
const VERSION = "Version 0.4";

// The two choices in Options live in the browser (D96); a read can fail in a private window, so each is guarded.
function stored<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const value = localStorage.getItem(key);
    return allowed.includes(value as T) ? (value as T) : fallback;
  } catch {
    return fallback;
  }
}
function store(key: string, value: string) {
  try { localStorage.setItem(key, value); } catch { /* a private window: the choice lasts the session */ }
}

// The shell follows a chat app (D90, D91): the search is the title, past searches live in a sidebar (desktop) or a
// drawer (phone), the limits bar carries every other limit, and the three things to look at are the chat, the
// homes and the shortlist: a floating pill bar on the phone, the chat always open with two tabs on desktop.
// Every change, including a yes to a check-in, still goes through the chat (D61).
export function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [card, setCard] = useState<Card | null>(null);
  const [searchedAs, setSearchedAs] = useState<Partial<HardLimits> | null>(null);
  const [wishes, setWishes] = useState<Preference[]>([]);
  const [ready, setReady] = useState(false);
  const [unsupported, setUnsupported] = useState(false);
  const [deck, setDeck] = useState<DeckData | null>(null);
  const [queue, setQueue] = useState<DeckCard[]>([]);
  const [checkin, setCheckin] = useState<Checkin | null>(null);
  const [stats, setStats] = useState<SwipeStats | null>(null);
  const [canUndo, setCanUndo] = useState(false);
  const [shortlist, setShortlist] = useState<Summary[]>([]);
  const [searches, setSearches] = useState<SearchSummary[]>([]);
  const [view, setView] = useState<View>("chat");
  const [sideOpen, setSideOpen] = useState(() => isDesktop());
  const [optionsOpen, setOptionsOpen] = useState(false);
  const [busy, setBusy] = useState<"chat" | "swipe" | "deck" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [data, setData] = useState("");
  const [areas, setAreas] = useState<string[]>([]);
  const [phone, setPhone] = useState(() => !isDesktop());
  const [theme, setTheme] = useState<Theme>(() => stored("tispi.theme", ["system", "light", "dark"], "system"));
  const [langPref, setLangPref] = useState<LangPref>(() => stored("tispi.lang", ["auto", "en", "el"], "auto"));

  // Appearance: System is color-scheme "light dark" on the root; a pinned theme is one attribute (D94).
  useEffect(() => {
    if (theme === "system") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = theme;
    store("tispi.theme", theme);
  }, [theme]);

  // Language: Automatic follows the user's last message, as the server's check-ins already do (D92); before any
  // message, the browser's language. A fixed choice pins the screen for a household that writes in one language.
  const lang: Lang = useMemo(() => {
    if (langPref !== "auto") return langPref;
    const last = [...messages].reverse().find((m) => m.role === "user")?.text;
    return detectLanguage(last, navigator.language.toLowerCase().startsWith("el") ? "el" : "en");
  }, [langPref, messages]);
  const L = LABELS[lang];
  useEffect(() => {
    document.documentElement.lang = lang;
    store("tispi.lang", langPref);
  }, [lang, langPref]);

  useEffect(() => {
    const media = window.matchMedia(DESKTOP);
    const onChange = () => setPhone(!media.matches);
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, []);

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

  const refreshSearches = useCallback(() => {
    getSearches().then((s) => setSearches(s.searches)).catch(() => undefined);
  }, []);

  // A snapshot of one search, from a reload, a switch or "New search": the chat, the card, the counts, the deck.
  const apply = useCallback((state: State) => {
    setMessages(state.messages);
    setCard(state.card);
    setSearchedAs(state.searched_as);
    setWishes(state.wishes ?? []);
    setStats(state.swipes);
    setData(state.data);
    setAreas(state.areas);
    setSearches(state.searches);
    setUnsupported(state.unsupported.includes("rent") || state.card?.intent === "rent");
    setDeck(null);
    setQueue([]);
    setCheckin(null);
    setError(null);
    const deckReady = !!state.card && state.card.intent !== "rent" && (!!state.checkin || state.action === "confirm");
    setReady(deckReady);
    setView(deckReady ? "deck" : "chat");
    if (deckReady) {
      if (state.checkin) setCheckin(state.checkin);  // a check-in left waiting: show it again (D72)
      void loadDeck();
      getShortlist().then((s) => setShortlist(s.homes)).catch(() => undefined);
    } else {
      setShortlist([]);
    }
  }, [loadDeck]);

  useEffect(() => {
    getState().then(apply).catch(fail);
  }, [apply]);

  const send = async (text: string) => {
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy("chat");
    setError(null);
    try {
      const reply = await sendChat(text);
      setMessages((m) => [...m, { role: "assistant", text: reply.reply }]);
      setCard(reply.card);
      setSearchedAs(reply.searched_as);
      setWishes(reply.wishes ?? []);
      setStats(reply.swipes);
      setUnsupported(reply.unsupported.includes("rent") || reply.card.intent === "rent");
      setCheckin(null);
      if (reply.deck_ready) {
        setReady(true);
        setView("deck");  // the app lands on the homes by itself once the limits are validated (D90)
        await loadDeck();
      }
      refreshSearches();
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
      // the current row in the searches list keeps step with the counts just confirmed by the server
      setSearches((list) => list.map((s) => s.current && decision !== "skip"
        ? { ...s, verdicts: s.verdicts + 1, shortlisted: s.shortlisted + (decision === "like" ? 1 : 0) } : s));
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
      if (result.focus_chat) {
        setView("chat");
        setTimeout(() => document.getElementById("message")?.focus(), 50);
      }
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
        setSearches((list) => list.map((s) => s.current && result.undone !== "skip"
          ? { ...s, verdicts: Math.max(0, s.verdicts - 1), shortlisted: Math.max(0, s.shortlisted - (result.undone === "like" ? 1 : 0)) } : s));
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

  // "New search": a blank chat; the one before stays in the list with its swipes (D94), so nothing to confirm.
  const startNew = async () => {
    if (!isDesktop()) setSideOpen(false);
    try {
      apply(await newSearch());
      setTimeout(() => document.getElementById("message")?.focus(), 50);
    } catch (err) {
      fail(err);
    }
  };

  const pick = async (id: string) => {
    if (!isDesktop()) setSideOpen(false);
    if (searches.find((s) => s.id === id)?.current) return;
    try {
      apply(await selectSearch(id));
    } catch (err) {
      fail(err);
    }
  };

  const closeSide = useCallback(() => setSideOpen(false), []);
  const current = queue[0] ?? null;
  const nextCheckin = deck ? Math.max(0, deck.checkin_every - deck.since_checkin) : null;
  const title = titleText(card, searchedAs, L);
  const rightView: "deck" | "shortlist" = view === "shortlist" ? "shortlist" : "deck";

  return (
    <LabelsContext.Provider value={L}>
    <div className={`shell ${sideOpen ? "side-open" : ""} ${ready ? "ready" : "asking"}`}>
      <Searches searches={searches} open={sideOpen} onClose={closeSide} onSelect={pick} onNew={startNew} onOptions={() => setOptionsOpen(true)} />

      <div className="mainarea">
        <header className="hdr">
          <button type="button" className="icon-btn open-side" aria-label={L.yourSearches} aria-expanded={sideOpen} onClick={() => setSideOpen(true)}>
            <SearchesIcon />
          </button>
          <div className="where">
            <div className="areas">{title.areas}</div>
            {title.price && <div className="price-line">{title.price}</div>}
          </div>
          {stats && stats.swipes > 0 && (
            <span className="status muted small">
              {L.swipedLine(stats.swipes, stats.likes)}
              {stats.like_rate != null ? ` · ${L.likeRate(Math.round(stats.like_rate * 100))}` : ""}
              {ready && nextCheckin != null ? ` · ${L.checkinIn(nextCheckin)}` : ""}
            </span>
          )}
        </header>

        <main className="panes">
          <section className={`pane chat-pane ${view === "chat" ? "on" : ""}`} aria-label={L.chat}>
            <Chat messages={messages} busy={busy === "chat"} error={error} compact={ready} intro={L.covers(areas, data)} onSend={send} />
            {unsupported && <p className="hint center">{L.rentNotYet}</p>}
          </section>

          {ready && (
            <section className={`pane homes-pane ${view !== "chat" ? "on" : ""}`} aria-label={L.homes}>
              <nav className="tabs" aria-label={L.views}>
                <button type="button" className={`tab ${rightView === "deck" ? "on" : ""}`} onClick={() => setView("deck")}>{L.homes}</button>
                <button type="button" className={`tab ${rightView === "shortlist" ? "on" : ""}`} onClick={() => setView("shortlist")}>
                  {L.shortlist}{shortlist.length ? ` (${shortlist.length})` : ""}
                </button>
              </nav>
              {rightView === "deck" && card && searchedAs && <LimitsBar card={card} searched={searchedAs} wishes={wishes} oneRow={phone} />}
              {rightView === "deck" ? (
                <Deck deck={deck} card={current} checkin={checkin} busy={busy !== null} canUndo={canUndo} onSwipe={swipe} onUndo={undo} onAnswer={send} onTap={tap} />
              ) : (
                <Shortlist homes={shortlist} />
              )}
            </section>
          )}
        </main>

        <nav className="views" aria-label={L.views}>
          <button type="button" className={`view ${view === "chat" ? "on" : ""}`} onClick={() => setView("chat")}>{L.chat}</button>
          <button type="button" className={`view ${view === "deck" ? "on" : ""}`} disabled={!ready} onClick={() => setView("deck")}>{L.homes}</button>
          <button type="button" className={`view ${view === "shortlist" ? "on" : ""}`} disabled={!ready} onClick={() => setView("shortlist")}>
            {L.shortlist}{shortlist.length ? ` (${shortlist.length})` : ""}
          </button>
        </nav>
      </div>

      <Options open={optionsOpen} data={data} areas={areas} theme={theme} langPref={langPref} lang={lang} version={VERSION}
        onTheme={setTheme} onLang={setLangPref} onClose={() => setOptionsOpen(false)} />
    </div>
    </LabelsContext.Provider>
  );
}
