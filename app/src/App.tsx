import { useState } from "react";
import { Card, ChatReply, HardLimits, SearchResult, Widening, runSearch, sendChat } from "./api";
import { Chat, Message } from "./Chat";
import { CriteriaCard } from "./CriteriaCard";
import { ResultsTable } from "./ResultsTable";

export function App() {
  const [session, setSession] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [card, setCard] = useState<Card | null>(null);
  const [last, setLast] = useState<ChatReply | null>(null);
  const [searchedAs, setSearchedAs] = useState<Partial<HardLimits> | null>(null);
  const [result, setResult] = useState<SearchResult | null>(null);
  const [busy, setBusy] = useState<"chat" | "search" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const send = async (text: string) => {
    setMessages((m) => [...m, { role: "user", text }]);
    setBusy("chat");
    setError(null);
    try {
      const reply = await sendChat(session, text);
      setSession(reply.session);
      setMessages((m) => [...m, { role: "assistant", text: reply.reply }]);
      setCard(reply.card);
      setSearchedAs(reply.searched_as);
      setLast(reply);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  const search = async (which: Card | null = card) => {
    if (!which) return;
    setBusy("search");
    setError(null);
    try {
      const found = await runSearch(which);
      setResult(found);
      setSearchedAs(found.searched_as);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  };

  // The user picked one of code's widenings: set exactly the limits that were counted, then search again.
  const widen = (option: Widening) => {
    if (!card || !result) return;
    const done = result.searched_as;
    const patch = option.limits as Partial<HardLimits> & { areas?: string[] };
    const hard = { ...card.hard_limits };
    let { budget_around, ideally, areas } = card;
    if ("max_price_eur" in patch || "min_price_eur" in patch) {
      hard.max_price_eur = done.max_price_eur ?? hard.max_price_eur;
      hard.min_price_eur = done.min_price_eur ?? hard.min_price_eur;
      budget_around = false;
    }
    if ("min_size_m2" in patch || "max_size_m2" in patch) {
      hard.min_size_m2 = done.min_size_m2 ?? hard.min_size_m2;
      hard.max_size_m2 = done.max_size_m2 ?? hard.max_size_m2;
      ideally = ideally.filter((x) => x !== "size");
    }
    if ("min_bedrooms" in patch || "max_bedrooms" in patch) {
      hard.min_bedrooms = done.min_bedrooms ?? hard.min_bedrooms;
      hard.max_bedrooms = done.max_bedrooms ?? hard.max_bedrooms;
      ideally = ideally.filter((x) => x !== "bedrooms");
    }
    const { areas: newAreas, ...limits } = patch;
    const next: Card = { ...card, hard_limits: { ...hard, ...limits }, budget_around, ideally, areas: newAreas ?? areas };
    setCard(next);
    void search(next);
  };

  const unsupported = Boolean(last?.unsupported.includes("rent") || card?.intent === "rent");

  return (
    <>
      <header className="top">
        <div className="brand">
          <h1>Property Match</h1>
          <span className="muted small">Egaleo · Peristeri · Chaidari</span>
        </div>
        <span className="muted small">Hard limits are checked in code, never by the model.</span>
      </header>
      <main className="layout">
        <Chat messages={messages} busy={busy === "chat"} error={error} onSend={send} />
        <CriteriaCard
          card={card}
          searchedAs={searchedAs}
          ready={last?.action === "confirm"}
          unsupported={unsupported}
          busy={busy === "search"}
          onChange={setCard}
          onSearch={() => void search()}
        />
        {result && <ResultsTable result={result} onWiden={widen} busy={busy === "search"} />}
      </main>
    </>
  );
}
