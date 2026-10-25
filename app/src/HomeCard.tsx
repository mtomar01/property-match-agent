import { useEffect, useState } from "react";
import { DeckCard, Listed } from "./api";
import { floorText, money } from "./labels";

// One home, in reading order (design system, HomeCard): the photo, the price with €/m² beside it, the facts line,
// up to two reasons, the market list with its marks, then the portal link. Every line is computed by code
// (learning/deck.py); the component never reorders or invents one. No badges, no rating.
export function HomeCard({ card }: { card: DeckCard }) {
  return (
    <article className="home">
      <Photo url={card.photo_url} card={card} />
      <div className="home-body">
        {card.skipped_before && <p className="hint">You skipped this one earlier.</p>}
        <div className="home-head">
          <strong className="price">{money(card.price_eur)}</strong>
          <span className="per-m2">{card.price_per_m2 ? `€${card.price_per_m2.toLocaleString("en-GB")}/m²` : ""}</span>
        </div>
        <p className="facts">
          {[
            card.size_m2 != null ? `${card.size_m2} m²` : null,
            card.bedrooms != null ? `${card.bedrooms} bed` : null,
            floorText(card.floor),
            [card.area, card.sub_area].filter(Boolean).join(" · "),
            card.year_built ? `built ${card.year_built}` : null,
            card.renovated_year ? `renovated ${card.renovated_year}` : null,
            card.energy_class ? `energy ${card.energy_class}` : null,
          ].filter(Boolean).join(" · ")}
        </p>
        <ul className="reasons">
          {card.reasons.map((r) => <li key={r.feature}>{r.text}</li>)}
        </ul>
        {(card.market.length > 0 || card.listed) && (
          <ul className="market" aria-label="The market">
            {card.market.map((m) => <li key={m.feature} className={m.feature}>{m.text}</li>)}
            {card.listed && (
              <li className="listed">
                {listedText(card.listed, card.price_eur)}:{" "}
                {card.listed.others.map((o, i) => (
                  <span key={o.listing_id}>
                    {i > 0 && ", "}
                    <a href={o.url} target="_blank" rel="noreferrer noopener">{o.source}{o.price_eur ? ` ${money(o.price_eur)}` : ""} ↗</a>
                  </span>
                ))}
              </li>
            )}
          </ul>
        )}
        <a className="small card-link" href={card.url} target="_blank" rel="noreferrer noopener">
          {card.synthetic ? "Synthetic listing (no real page)" : `Open on ${card.source} ↗`}
        </a>
      </div>
    </article>
  );
}

// "Listed 3 times, €185,000 to €199,000" (spec section 11): this card is the cheapest version.
function listedText(listed: Listed, price: number | null): string {
  const times = listed.times === 2 ? "twice" : `${listed.times} times`;
  if (listed.price_min && listed.price_max && listed.price_min !== listed.price_max) {
    return `Listed ${times}, ${money(listed.price_min)} to ${money(listed.price_max)}${price === listed.price_min ? "; this is the cheapest" : ""}`;
  }
  return `Listed ${times} at the same price`;
}

// The photo loads from the portal only while this card is on screen; nothing is downloaded or kept (D64).
function Photo({ url, card }: { url: string | null; card: DeckCard }) {
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [url]);
  if (url && !failed) {
    return <img className="photo" src={url} alt="" referrerPolicy="no-referrer" onError={() => setFailed(true)} />;
  }
  return (
    <div className="photo placeholder" aria-hidden="true">
      <span>{card.property_type?.replace("_", " ") ?? "home"}</span>
      <span className="small">{card.synthetic ? "synthetic listing" : "no photo link saved"}</span>
    </div>
  );
}
