import { Card, HardLimits } from "./api";
import { AREAS, FLOORS, TYPES, money, preferenceText, weightWord } from "./labels";

interface Props {
  card: Card | null;
  searchedAs: Partial<HardLimits> | null;
  ready: boolean;
  unsupported: boolean;
  busy: boolean;
  onChange: (card: Card) => void;
  onSearch: () => void;
}

type NumberField = keyof Pick<HardLimits, "max_price_eur" | "min_price_eur" | "min_size_m2" | "max_size_m2" | "min_bedrooms" | "max_bedrooms" | "min_year_built">;

export function CriteriaCard({ card, searchedAs, ready, unsupported, busy, onChange, onSearch }: Props) {
  if (!card) {
    return (
      <section className="panel card" aria-labelledby="card-h">
        <h2 id="card-h">Your search</h2>
        <p className="muted">The card fills in as you chat: hard limits the search never breaks, and nice-to-haves that only rank the results. Nothing is searched until you confirm it.</p>
      </section>
    );
  }

  const limits = card.hard_limits;
  const set = (patch: Partial<Card>) => onChange({ ...card, ...patch });
  const setLimit = (patch: Partial<HardLimits>) => set({ hard_limits: { ...limits, ...patch } });
  const toggle = (list: string[], value: string) => (list.includes(value) ? list.filter((v) => v !== value) : [...list, value]);
  const number = (field: NumberField, label: string, suffix = "") => (
    <label className="field" htmlFor={field}>
      <span>{label}</span>
      <span className="input-wrap">
        <input
          id={field}
          inputMode="numeric"
          value={limits[field] == null ? "" : limits[field]!.toLocaleString("en-GB")}
          onChange={(e) => {
            const digits = e.target.value.replace(/[^\d]/g, "");
            setLimit({ [field]: digits ? Number(digits) : null } as Partial<HardLimits>);
          }}
        />
        {suffix && <span className="suffix">{suffix}</span>}
      </span>
    </label>
  );
  const range = searchedAs && searchedAs.max_price_eur != null
    ? `${money(searchedAs.min_price_eur)} to ${money(searchedAs.max_price_eur)}`
    : null;

  return (
    <section className="panel card" aria-labelledby="card-h">
      <div className="card-head">
        <h2 id="card-h">Your search</h2>
        <span className={`pill ${unsupported ? "warn" : ready ? "ok" : ""}`}>
          {unsupported ? "Rentals aren't supported yet" : ready ? "Ready to confirm" : "Still asking"}
        </span>
      </div>

      <div className="row">
        <span className="eyebrow">Buying</span>
        <div className="chips" role="group" aria-label="Buying to">
          {(["buy", "invest"] as const).map((intent) => (
            <button key={intent} type="button" className={`chip ${card.intent === intent ? "on" : ""}`} aria-pressed={card.intent === intent}
              onClick={() => set({ intent })}>
              {intent === "buy" ? "To live in" : "Investor mode"}
            </button>
          ))}
        </div>
      </div>

      <div className="block">
        <h3 className="eyebrow">Never broken</h3>
        <div className="grid">
          {number("max_price_eur", "Top price", "€")}
          {number("min_price_eur", "Lowest price", "€")}
        </div>
        <label className="check">
          <input type="checkbox" checked={card.budget_around} onChange={(e) => set({ budget_around: e.target.checked })} />
          "Around": search 10% either side
        </label>
        <p className="hint">
          {range ? <>Searched as <strong>{range}</strong>. </> : null}
          With no lowest price, code sets half the top price, to keep out wrecks and ads with no real price.
        </p>
        <div className="grid">
          {number("min_size_m2", "Size from", "m²")}
          {number("max_size_m2", "Size up to", "m²")}
          {number("min_bedrooms", "Bedrooms from")}
          {number("max_bedrooms", "Bedrooms up to")}
          {number("min_year_built", "Built from")}
        </div>
        <div className="checks">
          <label className="check">
            <input type="checkbox" checked={card.ideally.includes("size")} onChange={() => set({ ideally: toggle(card.ideally, "size") })} />
            Size "ideally": ±10%
          </label>
          <label className="check">
            <input type="checkbox" checked={card.ideally.includes("bedrooms")} onChange={() => set({ ideally: toggle(card.ideally, "bedrooms") })} />
            Bedrooms "ideally": ±1
          </label>
        </div>
        <ChipRow label="Areas (none means all three)" options={AREAS} chosen={card.areas} onToggle={(v) => set({ areas: toggle(card.areas, v) })} />
        <ChipRow label="Types (only if you named them)" options={TYPES} chosen={limits.property_types}
          onToggle={(v) => setLimit({ property_types: toggle(limits.property_types, v) })} />
        <ChipRow label="Floors ruled out" options={FLOORS} chosen={limits.exclude_floors}
          onToggle={(v) => setLimit({ exclude_floors: toggle(limits.exclude_floors, v) })} />
      </div>

      <div className="block">
        <h3 className="eyebrow">Nice to have: ranking only</h3>
        {card.preferences.length === 0 ? (
          <p className="muted">None yet.</p>
        ) : (
          <ul className="prefs">
            {card.preferences.map((p, i) => (
              <li key={`${p.feature}-${i}`}>
                <span>{preferenceText(p)}</span>
                <span className="weight">{weightWord(p.weight)}</span>
                <button type="button" className="remove" aria-label={`Remove ${preferenceText(p)}`}
                  onClick={() => set({ preferences: card.preferences.filter((_, j) => j !== i) })}>
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {card.open_questions.length > 0 && (
        <div className="block">
          <h3 className="eyebrow">Worth checking on each result</h3>
          <ul className="notes">
            {card.open_questions.map((q) => <li key={q}>{q}</li>)}
          </ul>
        </div>
      )}

      <button type="button" className="primary wide" disabled={busy || unsupported || !limits.max_price_eur} onClick={onSearch}>
        {busy ? "Searching…" : "Confirm and search"}
      </button>
      {!limits.max_price_eur && !unsupported && <p className="hint">The search needs a top price.</p>}
    </section>
  );
}

function ChipRow({ label, options, chosen, onToggle }: { label: string; options: [string, string][]; chosen: string[]; onToggle: (value: string) => void }) {
  return (
    <div className="row">
      <span className="eyebrow">{label}</span>
      <div className="chips" role="group" aria-label={label}>
        {options.map(([value, text]) => (
          <button key={value} type="button" className={`chip ${chosen.includes(value) ? "on" : ""}`} aria-pressed={chosen.includes(value)}
            onClick={() => onToggle(value)}>
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
