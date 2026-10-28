import { useMemo, useState } from "react";
import { Summary } from "./api";
import { floorText, homePrice, money, useLabels } from "./labels";

type SortKey = "price_eur" | "price_per_m2" | "first_seen";

// The liked homes as a table, newest first (spec section 4, step 6; design system, ShortlistRow): the price,
// the €/m², the facts, the area, when it was first seen and the portal link. The CSV has the same columns and
// opens in Sheets. Headers in the label style, hairlines, no stripes; on a phone the facts wrap.
export function Shortlist({ homes }: { homes: Summary[] }) {
  const L = useLabels();
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
    h.size_m2 != null ? `${h.size_m2} ${L.m2}` : null,
    h.bedrooms != null ? L.bed(h.bedrooms) : null,
    floorText(h.floor, L),
    h.year_built ? L.built(h.year_built) : null,
    h.renovated_year ? L.renovated(h.renovated_year) : null,
    h.energy_class ? L.energy(h.energy_class) : null,
  ].filter(Boolean).join(" · ");

  if (homes.length === 0) {
    return (
      <section className="panel results">
        <h2>{L.shortlist}</h2>
        <p className="muted">{L.nothingLiked}</p>
      </section>
    );
  }
  return (
    <section className="panel results" aria-labelledby="short-h">
      <div className="card-head">
        <h2 id="short-h">{L.liked(homes.length)}</h2>
        <a className="button-link" href="/api/export.csv" download="shortlist.csv">{L.downloadCsv}</a>
      </div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              {header("price_eur", L.colPrice, true)}
              {header("price_per_m2", L.colPerM2, true)}
              <th>{L.colFacts}</th>
              <th>{L.colArea}</th>
              {header("first_seen", L.colFirstSeen)}
              <th>{L.colListing}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((h) => (
              <tr key={h.listing_id}>
                <td className="num">
                  {homePrice(h.price_eur, h.listing_type, L)}
                  {h.previous_price_eur != null && h.price_eur != null && (
                    <span className={`change ${h.previous_price_eur > h.price_eur ? "down" : "up"}`}>{L.was(money(h.previous_price_eur, L))}</span>
                  )}
                </td>
                <td className="num" data-unit={` €${L.perM2}`}>{h.price_per_m2?.toLocaleString(L.locale) ?? "–"}</td>
                <td className="facts-cell">{facts(h)}</td>
                <td>{[h.area, h.sub_area].filter(Boolean).join(" · ")}</td>
                <td data-label={`${L.firstSeen} `}>{h.first_seen}</td>
                <td>{h.synthetic ? <span className="muted">{L.synthetic}</span> : <a href={h.url} target="_blank" rel="noreferrer noopener">{h.source} ↗</a>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
