import { useMemo, useState } from "react";
import { SearchResult, Summary, Widening } from "./api";
import { AREAS, floorText, money, wideningText } from "./labels";

type Column = { key: keyof Summary; label: string; numeric?: boolean; render?: (row: Summary) => React.ReactNode };

const COLUMNS: Column[] = [
  { key: "price_eur", label: "Price", numeric: true, render: (r) => <Price row={r} /> },
  { key: "size_m2", label: "m²", numeric: true },
  { key: "price_per_m2", label: "€/m²", numeric: true, render: (r) => (r.price_per_m2 == null ? "–" : Math.round(r.price_per_m2).toLocaleString("en-GB")) },
  { key: "bedrooms", label: "Bedrooms", numeric: true },
  { key: "floor", label: "Floor", render: (r) => floorText(r.floor) },
  { key: "year_built", label: "Built", numeric: true },
  { key: "renovated_year", label: "Renovated", numeric: true },
  { key: "energy_class", label: "Energy" },
  { key: "area", label: "Area", render: (r) => AREAS.find(([code]) => code === r.area)?.[0] ?? r.area ?? "–" },
  { key: "first_seen", label: "First seen" },
];

const UNKNOWN: Record<string, string> = { price_eur: "price", size_m2: "size", bedrooms: "bedrooms", floor: "floor", area: "area", property_type: "type" };

function Price({ row }: { row: Summary }) {
  if (row.previous_price_eur == null || row.price_eur == null) return <>{money(row.price_eur)}</>;
  const down = row.price_eur < row.previous_price_eur;
  return (
    <>
      {money(row.price_eur)}{" "}
      <span className={`change ${down ? "down" : "up"}`} title={`Was ${money(row.previous_price_eur)}`}>
        {down ? "▼" : "▲"} {money(Math.abs(row.price_eur - row.previous_price_eur))}
      </span>
    </>
  );
}

export function ResultsTable({ result, onWiden, busy }: { result: SearchResult; onWiden: (option: Widening) => void; busy: boolean }) {
  const [sort, setSort] = useState<{ key: keyof Summary; up: boolean } | null>(null);
  const rows = useMemo(() => {
    if (!sort) return result.results;
    return [...result.results].sort((a, b) => {
      const x = a[sort.key], y = b[sort.key];
      if (x == null) return 1;
      if (y == null) return -1;
      return (x < y ? -1 : x > y ? 1 : 0) * (sort.up ? 1 : -1);
    });
  }, [result, sort]);
  const unknown = Object.entries(result.excluded_because_unknown ?? {});

  return (
    <section className="panel results" aria-labelledby="results-h">
      <div className="card-head">
        <h2 id="results-h">
          {result.total_matches} {result.total_matches === 1 ? "home" : "homes"} match
        </h2>
        <span className="muted small">
          Showing {result.returned}, best matches first · {result.data}
        </span>
      </div>
      {result.if_eased && <Widen result={result} onWiden={onWiden} busy={busy} />}
      {unknown.length > 0 && (
        <p className="hint">
          Left out because the listing doesn't say its {unknown.map(([field, n]) => `${UNKNOWN[field] ?? field.replace(/_/g, " ")} (${n})`).join(", ")}.
        </p>
      )}
      {result.total_matches === 0 ? (
        <p className="muted">Nothing passes every limit yet.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                {COLUMNS.map((c) => (
                  <th key={c.key} className={c.numeric ? "num" : undefined}
                    aria-sort={sort?.key === c.key ? (sort.up ? "ascending" : "descending") : "none"}>
                    <button type="button" onClick={() => setSort({ key: c.key, up: sort?.key === c.key ? !sort.up : true })}>
                      {c.label}{sort?.key === c.key ? (sort.up ? " ↑" : " ↓") : ""}
                    </button>
                  </th>
                ))}
                <th>Listing</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.listing_id}>
                  {COLUMNS.map((c) => (
                    <td key={c.key} className={c.numeric ? "num" : undefined}>
                      {c.render ? c.render(r) : (r[c.key] as React.ReactNode) ?? "–"}
                    </td>
                  ))}
                  <td>
                    {r.synthetic ? (
                      <span className="muted small" title="An invented listing for the public repo">Synthetic</span>
                    ) : (
                      <a href={r.url} target="_blank" rel="noreferrer">{r.source}</a>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

// Fewer than 5 homes: code's ways to widen, each with its count. A click is the user's yes (D50, D63).
function Widen({ result, onWiden, busy }: { result: SearchResult; onWiden: (option: Widening) => void; busy: boolean }) {
  const options = Object.values(result.if_eased ?? {})
    .filter((o) => o.matches > result.total_matches)
    .sort((a, b) => (a.matches >= 5) === (b.matches >= 5) ? Object.keys(a.limits).length - Object.keys(b.limits).length || b.matches - a.matches : a.matches >= 5 ? -1 : 1)
    .slice(0, 4);
  if (options.length === 0) {
    return <p className="hint">Only {result.total_matches} found, and widening one step doesn't add any. Tell the assistant what matters least.</p>;
  }
  return (
    <div className="widen">
      <p className="hint">Only {result.total_matches} found. Widen the search?</p>
      <div className="chips">
        {options.map((o) => (
          <button key={JSON.stringify(o.limits)} type="button" className="chip widen-option" disabled={busy} onClick={() => onWiden(o)}>
            {wideningText(o.limits, result.searched_as as Record<string, number | null>)} · <strong>{o.matches} homes</strong>
          </button>
        ))}
      </div>
    </div>
  );
}
