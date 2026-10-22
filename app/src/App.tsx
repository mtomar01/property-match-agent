import { useState } from "react";
import { Card, ChatReply, HardLimits, SearchResult, runSearch, sendChat } from "./api";
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

  const search = async () => {
    if (!card) return;
    setBusy("search");
    setError(null);
    try {
      const found = await runSearch(card);
      setResult(found);
      setSearchedAs(found.searched_as);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
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
          onSearch={search}
        />
        {result && <ResultsTable result={result} />}
      </main>
    </>
  );
}
