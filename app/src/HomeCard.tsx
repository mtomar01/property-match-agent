import { useEffect, useState } from "react";
import { DeckCard, Listed } from "./api";
import { Labels, floorText, money, useLabels } from "./labels";

// One home, in reading order (design system, HomeCard): the photo, the price with €/m² beside it, the facts line,
// up to two reasons, the market list with its marks, then the portal link. Every line is computed by code
// (learning/deck.py); the component never reorders or invents one. No badges, no rating.
export function HomeCard({ card }: { card: DeckCard }) {
  const L = useLabels();
  return (
    <article className="home">
      <Photo url={card.photo_url} card={card} />
      <div className="home-body">
        {card.skipped_before && <p className="hint">{L.skippedBefore}</p>}
        <div className="home-head">
          <strong className="price">{money(card.price_eur, L)}</strong>
          <span className="per-m2">{card.price_per_m2 ? `${card.price_per_m2.toLocaleString(L.locale)} €${L.perM2}` : ""}</span>
        </div>
        <p className="facts">
          {[
            card.size_m2 != null ? `${card.size_m2} ${L.m2}` : null,
            card.bedrooms != null ? L.bed(card.bedrooms) : null,
            floorText(card.floor, L),
            [card.area, card.sub_area].filter(Boolean).join(" · "),
            card.year_built ? L.built(card.year_built) : null,
            card.renovated_year ? L.renovated(card.renovated_year) : null,
            card.energy_class ? L.energy(card.energy_class) : null,
          ].filter(Boolean).join(" · ")}
        </p>
        <ul className="reasons">
          {card.reasons.map((r) => <li key={r.feature}>{r.text}</li>)}
        </ul>
        {(card.market.length > 0 || card.listed) && (
          <ul className="market" aria-label={L.theMarket}>
            {card.market.map((m) => <li key={m.feature} className={m.feature}>{m.text}</li>)}
            {card.listed && (
              <li className="listed">
                {listedText(card.listed, card.price_eur, L)}:{" "}
                {card.listed.others.map((o, i) => (
                  <span key={o.listing_id}>
                    {i > 0 && ", "}
                    <a href={o.url} target="_blank" rel="noreferrer noopener">{o.source}{o.price_eur ? ` ${money(o.price_eur, L)}` : ""} ↗</a>
                  </span>
                ))}
              </li>
            )}
          </ul>
        )}
        <a className="small card-link" href={card.url} target="_blank" rel="noreferrer noopener">
          {card.synthetic ? L.syntheticListing : L.openOn(card.source)}
        </a>
      </div>
    </article>
  );
}

// "Listed 3 times, €185,000 to €199,000" (spec section 11): this card is the cheapest version.
function listedText(listed: Listed, price: number | null, L: Labels): string {
  const times = L.listedTimes(listed.times);
  if (listed.price_min && listed.price_max && listed.price_min !== listed.price_max) {
    return L.listedRange(times, money(listed.price_min, L), money(listed.price_max, L), price === listed.price_min);
  }
  return L.listedSame(times);
}

// The photo loads from the portal only while this card is on screen; nothing is downloaded or kept (D64).
function Photo({ url, card }: { url: string | null; card: DeckCard }) {
  const L = useLabels();
  const [failed, setFailed] = useState(false);
  useEffect(() => setFailed(false), [url]);
  if (url && !failed) {
    return <img className="photo" src={url} alt="" referrerPolicy="no-referrer" onError={() => setFailed(true)} />;
  }
  return (
    <div className="photo placeholder" aria-hidden="true">
      <span>{(card.property_type && L.types[card.property_type]) ?? card.property_type?.replace("_", " ") ?? L.home}</span>
      <span className="small">{card.synthetic ? L.synthetic : L.noPhoto}</span>
    </div>
  );
}
