// Words for the codes the search uses, so the bar, the cards and the table read like a person wrote them.

import { Card, HardLimits, Preference, SearchSummary } from "./api";

// The shell's own words (D90, D91), in one place so the language switch (step 4) has one thing to swap.
export const UI = {
  app: "Tispi",
  newSearch: "New search",
  searches: "Searches",
  yourSearches: "Your searches",
  hideSearches: "Hide the searches",
  options: "Options",
  chat: "Chat",
  homes: "Homes",
  shortlist: "Shortlist",
  views: "Views",
  allAreas: "All areas",
  limits: "Limits",
  details: "details",
  send: "Send",
  today: "Today",
  close: "Close",
  wish: (n: number) => `${n} wish${n === 1 ? "" : "es"}`,
  homesCount: (n: number) => `${n} ${n === 1 ? "home" : "homes"}`,
  verdictsCount: (n: number) => `${n} ${n === 1 ? "verdict" : "verdicts"}`,
  shortlistedCount: (n: number) => `${n} shortlisted`,
  swipedLine: (swiped: number, liked: number) => `${swiped} swiped · ${liked} liked`,
  likeRate: (pct: number) => `${pct}% like rate`,
  checkinIn: (n: number) => `check-in in ${n}`,
  limitsHint: "Hard limits are checked in code and never broken. Wishes only rank. To change anything, tell Tispi in the chat.",
  rentNotYet: "Rentals aren't supported yet; the deck is for buying.",
  covers: (areas: string[], data: string) => `Covers ${areas.join(", ")} · ${data}`,
  dataLabel: "Data",
  about: "About Tispi",
  aboutText: "Tispi turns a chat into search limits, searches the portals' listings, shows one card per home and learns your taste from your likes and rejects. Photos are linked, never stored; nothing is kept about agents or owners.",
};

export const AREAS: [string, string][] = [
  ["Egaleo", "Egaleo · Αιγάλεω"],
  ["Peristeri", "Peristeri · Περιστέρι"],
  ["Chaidari", "Chaidari · Χαϊδάρι"],
];

export const TYPES: Record<string, string> = {
  apartment: "apartment",
  maisonette: "maisonette",
  studio: "studio",
  detached_house: "house",
  loft: "loft",
  building: "whole building",
  apartment_complex: "apartment complex",
};

export const REJECT_REASONS: [string, string][] = [
  ["too_dark", "Too dark"],
  ["too_small", "Too small"],
  ["bad_floor", "Bad floor"],
  ["needs_work", "Needs work"],
  ["too_expensive", "Too expensive"],
  ["bad_value", "Bad value for money"],
  ["wrong_area", "Wrong area"],
];

// "Can't judge": a skip that says why the listing didn't let the user decide (D71).
export const CANT_JUDGE_REASONS: [string, string][] = [
  ["photos_unclear", "Photos don't show it"],
  ["too_little_info", "Too little information"],
];

const FEATURES: Record<string, string> = {
  price_eur: "Price",
  size_m2: "Size",
  bedrooms: "Bedrooms",
  bathrooms: "Bathrooms",
  floor_level: "Floor",
  year_built: "Built",
  renovated_year: "Renovated",
  energy_class: "Energy class",
  metro_walk_min: "Metro on foot",
  balcony: "Balcony",
  lift: "Lift",
  parking: "Parking",
  storage: "Storage room",
  dual_aspect: "Dual aspect",
  corner: "Corner",
  whole_floor: "Whole floor",
  move_in_ready: "Ready to move in",
  price_per_m2: "€/m²",
};

const UNITS: Record<string, string> = { size_m2: " m²", metro_walk_min: " min", price_eur: " €" };

export function weightWord(weight: number): string {
  if (weight >= 0.9) return "a must";
  if (weight >= 0.7) return "strong wish";
  if (weight >= 0.4) return "would like";
  return "a bonus";
}

export function preferenceText(p: Preference): string {
  const name = FEATURES[p.feature] ?? p.feature;
  const unit = UNITS[p.feature] ?? "";
  if (p.equals === true) return name;
  if (p.feature === "move_in_ready" && p.equals === false) return "A renovation project";
  if (p.equals === false) return `No ${name.toLowerCase()}`;
  if (p.feature === "energy_class" && p.min != null) return `${name} ${p.min} or better`;
  if (p.feature === "floor_level" && p.min != null) return `Floor ${p.min} or higher`;
  if (p.min != null && p.max != null) return `${name} ${p.min} to ${p.max}${unit}`;
  if (p.min != null) return `${name} ${p.feature.endsWith("year") || p.feature === "year_built" ? "from" : "at least"} ${p.min}${unit}`;
  if (p.max != null) return `${name} up to ${p.max}${unit}`;
  return name;
}

export function floorText(floor: string | null): string {
  if (floor == null) return "floor unknown";
  if (floor === "top") return "top floor (ρετιρέ)";
  if (/^\d+$/.test(floor)) return `${floor}${floor === "1" ? "st" : floor === "2" ? "nd" : floor === "3" ? "rd" : "th"} floor`;
  return floor.replace("_", " ");
}

const euro = new Intl.NumberFormat("en-GB", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
export const money = (value: number | null | undefined) => (value == null ? "–" : euro.format(value));

const MUST_WORDS: Record<string, string> = { parking: "parking", lift: "a lift", balcony: "a balcony", storage: "a storage room" };
const floorWord = (level: number) => (level <= 0 ? "ground" : level < 1 ? "mezzanine" : `${level}`);

// "€90,000 to €220,000", "up to €250,000", "from €90,000": the price as a phrase, or nothing when none is set.
export function priceText(min: number | null | undefined, max: number | null | undefined, intent?: string | null): string {
  const rent = intent === "rent" ? "rent " : "";
  if (min != null && max != null) return `${rent}${money(min)} to ${money(max)}`;
  if (max != null) return `${rent}up to ${money(max)}`;
  if (min != null) return `${rent}from ${money(min)}`;
  return "";
}

// The search is the title (D90, D91): the areas on one line, the price under them, in place of a logo.
export function titleText(card: Card | null, searched: Partial<HardLimits> | null): { areas: string; price: string } {
  if (!card) return { areas: UI.newSearch, price: "" };
  const limits = searched ?? card.hard_limits;
  return { areas: card.areas.length ? card.areas.join(" · ") : UI.allAreas, price: priceText(limits.min_price_eur, limits.max_price_eur, card.intent) };
}

// "€90–220k", "up to €250k": the price in the searches list, short enough for a row.
function shortMoney(value: number): string {
  return value >= 1000 && value % 1000 === 0 ? `${value / 1000}k` : euro.format(value).replace("€", "");
}
export function searchTitle(s: SearchSummary): string {
  if (!s.has_card) return UI.newSearch;
  const areas = s.areas.length ? s.areas.join(" · ") : UI.allAreas;
  const rent = s.intent === "rent" ? "rent " : "";
  let price = "";
  if (s.min_price_eur != null && s.max_price_eur != null) price = `€${shortMoney(s.min_price_eur).replace("k", "")}–${shortMoney(s.max_price_eur)}`;
  else if (s.max_price_eur != null) price = `up to €${shortMoney(s.max_price_eur)}`;
  else if (s.min_price_eur != null) price = `from €${shortMoney(s.min_price_eur)}`;
  return price ? `${areas} · ${rent}${price}` : areas;
}

// "Today · 41 homes · 8 verdicts · 4 shortlisted": the counts that tell two searches apart.
export function searchSub(s: SearchSummary, today = new Date()): string {
  const created = new Date(s.created);
  const sameDay = created.toDateString() === today.toDateString();
  const when = sameDay ? UI.today : created.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
  const parts = [when];
  if (s.homes != null) parts.push(UI.homesCount(s.homes));
  if (s.verdicts) parts.push(UI.verdictsCount(s.verdicts));
  if (s.shortlisted) parts.push(UI.shortlistedCount(s.shortlisted));
  return parts.join(" · ");
}

// The bar above the deck: every hard limit other than the areas and the price, which are the title (D90, D91).
export function barText(card: Card, searched: Partial<HardLimits>): string[] {
  const parts: string[] = [];
  const lo = searched.min_size_m2, hi = searched.max_size_m2;
  if (lo != null && hi != null) parts.push(`${lo} to ${hi} m²`);
  else if (lo != null) parts.push(`from ${lo} m²`);
  else if (hi != null) parts.push(`up to ${hi} m²`);
  const bl = searched.min_bedrooms, bh = searched.max_bedrooms;
  if (bl != null && bh != null) parts.push(`${bl} to ${bh} bedrooms`);
  else if (bl != null) parts.push(`${bl}+ bedrooms`);
  else if (bh != null) parts.push(`up to ${bh} bedrooms`);
  if (searched.min_year_built != null) parts.push(`built from ${searched.min_year_built}`);
  if (searched.property_types?.length) parts.push(searched.property_types.map((t) => TYPES[t] ?? t).join(" or "));
  if (searched.exclude_floors?.length) parts.push(`no ${searched.exclude_floors.map((f) => f.replace("_", " ")).join(", ")}`);
  if (searched.max_price_per_m2 != null) parts.push(`up to ${money(searched.max_price_per_m2)}/m²`);
  if (searched.max_floor_without_lift != null) {
    parts.push(searched.max_floor_without_lift === 0 ? "ground floor or a lift" : `lift above floor ${searched.max_floor_without_lift}`);
  }
  if (searched.exclude_conditions?.length) parts.push(`no ${searched.exclude_conditions.map((c) => c.replace("_", " ")).join(" or ")}`);
  for (const f of searched.must_have ?? []) parts.push(`with ${MUST_WORDS[f] ?? f}`);
  if (searched.min_bathrooms != null) parts.push(`${searched.min_bathrooms}+ bathrooms`);
  if (searched.min_renovated_year != null) parts.push(`renovated or built from ${searched.min_renovated_year}`);
  const fl = searched.min_floor_level, fh = searched.max_floor_level;
  if (fl != null && fh != null) parts.push(`floor ${floorWord(fl)} to ${floorWord(fh)}`);
  else if (fl != null) parts.push(`floor ${floorWord(fl)} or higher`);
  else if (fh != null) parts.push(`floor ${floorWord(fh)} or lower`);
  if (searched.max_metro_walk_min != null) parts.push(`metro within ${searched.max_metro_walk_min} min on foot`);
  for (const [kind, features] of Object.entries(searched.must_have_if_type ?? {})) {
    parts.push(`${features.map((f) => MUST_WORDS[f] ?? f).join(", ")} for a ${TYPES[kind] ?? kind}`);
  }
  if (card.intent === "invest") parts.push("investor mode");
  return parts;
}

// "Price €155,000 to €230,000 and size 65 to 97 m²": what a widening would search, in words.
export function wideningText(patch: Record<string, number | string[]>, searched: Record<string, unknown>): string {
  const parts: string[] = [];
  const merged = { ...searched, ...patch } as Record<string, unknown>;
  if ("max_price_eur" in patch || "min_price_eur" in patch) {
    parts.push(`price ${money(merged.min_price_eur as number)} to ${money(merged.max_price_eur as number)}`);
  }
  if ("min_size_m2" in patch || "max_size_m2" in patch) {
    const lo = merged.min_size_m2 as number | undefined, hi = merged.max_size_m2 as number | undefined;
    parts.push(lo != null && hi != null ? `size ${lo} to ${hi} m²` : lo != null ? `size from ${lo} m²` : `size up to ${hi} m²`);
  }
  if ("min_bedrooms" in patch) parts.push(`${patch.min_bedrooms}+ bedrooms`);
  if ("max_bedrooms" in patch) parts.push(`up to ${patch.max_bedrooms} bedrooms`);
  if ("min_year_built" in patch) parts.push(`built from ${patch.min_year_built}`);
  if ("max_price_per_m2" in patch) parts.push(`up to ${money(patch.max_price_per_m2 as number)}/m²`);
  if ("max_floor_without_lift" in patch) parts.push(`stairs up to floor ${patch.max_floor_without_lift}`);
  if ("exclude_conditions" in patch) parts.push("any condition");
  if ("must_have" in patch) {
    const had = (searched.must_have as string[] | undefined) ?? [];
    const dropped = had.filter((f) => !(patch.must_have as string[]).includes(f));
    parts.push(`${dropped.map((f) => MUST_WORDS[f] ?? f).join(", ")} as a wish, not a must`);
  }
  if ("min_bathrooms" in patch) parts.push(`${patch.min_bathrooms}+ bathrooms`);
  if ("min_renovated_year" in patch) parts.push(`renovated or built from ${patch.min_renovated_year}`);
  if ("min_floor_level" in patch) parts.push(`floor ${floorWord(patch.min_floor_level as number)} or higher`);
  if ("max_floor_level" in patch) parts.push(`floor ${floorWord(patch.max_floor_level as number)} or lower`);
  if ("max_metro_walk_min" in patch) parts.push(`metro within ${patch.max_metro_walk_min} min`);
  if ("must_have_if_type" in patch) {
    const kept = Object.keys(patch.must_have_if_type as unknown as Record<string, string[]>);
    const dropped = Object.keys((searched.must_have_if_type as Record<string, string[]> | undefined) ?? {}).filter((k) => !kept.includes(k));
    parts.push(`no must for a ${dropped.map((k) => TYPES[k] ?? k).join(" or ")}`);
  }
  if ("property_types" in patch) {
    const had = (searched.property_types as string[] | undefined) ?? [];
    const added = (patch.property_types as string[]).filter((t) => !had.includes(t));
    parts.push(`add ${added.map((t) => TYPES[t] ?? t).join(", ")}`);
  }
  if ("areas" in patch) {
    const all = patch.areas as string[];
    parts.push(`add ${all[all.length - 1]}`);
  }
  const text = parts.join(" and ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

// The same widening as a message to the assistant, so it hears the change and the card follows (D61, D66).
export function wideningMessage(patch: Record<string, number | string[]>): string {
  const words: Record<string, string> = {
    max_price_eur: "top price", min_price_eur: "lowest price", min_size_m2: "minimum size", max_size_m2: "maximum size",
    min_bedrooms: "minimum bedrooms", max_bedrooms: "maximum bedrooms", min_year_built: "earliest year built",
    max_price_per_m2: "top price per m²", max_floor_without_lift: "floors of stairs without a lift",
    min_bathrooms: "minimum bathrooms", min_renovated_year: "renovated or built from", min_floor_level: "lowest floor",
    max_floor_level: "highest floor", max_metro_walk_min: "minutes to the metro",
  };
  const parts = Object.entries(patch).map(([name, value]) =>
    name === "property_types" ? `types ${(value as string[]).map((t) => TYPES[t] ?? t).join(", ")}`
      : name === "areas" ? `areas ${(value as string[]).join(", ")}`
      : name === "exclude_conditions" ? "drop the condition limit"
      : name === "must_have" ? `keep ${(value as string[]).length ? (value as string[]).join(", ") : "nothing"} as a must and make the rest wishes`
      : name === "must_have_if_type" ? "drop the must for that property type"
      : `${words[name] ?? name} ${value}`);
  return `Yes, widen it: ${parts.join(", ")}.`;
}
