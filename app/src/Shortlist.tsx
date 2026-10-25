import { useMemo, useState } from "react";
import { Summary } from "./api";
import { floorText, money } from "./labels";

type SortKey = "price_eur" | "price_per_m2" | "first_seen";

// The liked homes as a table, newest first (spec section 4, step 6; design system, ShortlistRow): the price,
// the €/m², the facts, the area, when it was first seen and the portal link. The CSV has the same columns and
// opens in Sheets. Headers in the label style, hairlines, no stripes; on a phone the facts wrap.
export function Shortlist({ homes }: { homes: Summary[] }) {
  const [sort, setSort] = useState<{ key: SortKey; up: boolean } | null>(null);
  const rows = useMemo(() => {
    if (!sort) return homes;
    const value = (h: Summary) => h[sort.key] ?? (sort.up ? Infinity : -Infinity);
    return [...homes].sort((a, b) => (value(a) > value(b) ? 1 : value(a) < value(b) ? -1 : 0) * (sort.up ? 1 : -1));
  }, [homes, sort]);
  const header = (key: SortKey, label: string, num = false) => (
    <th className={num ? "num" : ""} aria-sort={sort?.key === key ? (sort.up ? "ascending" : "descending") : "none"}>
      <button type="button" onClick={() => setSort((s) => ({ key, up: s?.key === key ? !s.up : true }))}>
        {label}{sort?.key === key ? (sort.up ? " ▲" : " ▼") : ""}
      </button>
    </th>
  );
  const facts = (h: Summary) => [
    h.size_m2 != null ? `${h.size_m2} m²` : null,
    h.bedrooms != null ? `${h.bedrooms} bed` : null,
    floorText(h.floor),
    h.year_built ? `built ${h.year_built}` : null,
    h.renovated_year ? `renovated ${h.renovated_year}` : null,
    h.energy_class ? `energy ${h.energy_class}` : null,
  ].filter(Boolean).join(" · ");

  if (homes.length === 0) {
    return (
      <section className="panel results">
        <h2>Shortlist</h2>
        <p className="muted">Nothing liked yet. Like a home and it lands here.</p>
      </section>
    );
  }
  return (
    <section className="panel results" aria-labelledby="short-h">
      <div className="card-head">
        <h2 id="short-h">{homes.length} liked</h2>
        <a className="button-link" href="/api/export.csv" download="shortlist.csv">Download CSV</a>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {header("price_eur", "Price", true)}
              {header("price_per_m2", "€/m²", true)}
              <th>Facts</th>
              <th>Area</th>
              {header("first_seen", "First seen")}
              <th>Listing</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((h) => (
              <tr key={h.listing_id}>
                <td className="num">
                  {money(h.price_eur)}
                  {h.previous_price_eur != null && h.price_eur != null && (
                    <span className={`change ${h.previous_price_eur > h.price_eur ? "down" : "up"}`}> was {money(h.previous_price_eur)}</span>
                  )}
                </td>
                <td className="num">{h.price_per_m2?.toLocaleString("en-GB") ?? "–"}</td>
                <td className="facts-cell">{facts(h)}</td>
                <td>{[h.area, h.sub_area].filter(Boolean).join(" · ")}</td>
                <td>{h.first_seen}</td>
                <td>{h.synthetic ? <span className="muted">synthetic</span> : <a href={h.url} target="_blank" rel="noreferrer noopener">{h.source} ↗</a>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
