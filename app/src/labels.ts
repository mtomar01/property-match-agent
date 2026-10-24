// Words for the codes the search uses, so the bar, the cards and the table read like a person wrote them.

import { Card, HardLimits, Preference } from "./api";

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

// The one-line bar above the deck: every hard limit, always visible (D61).
export function barText(card: Card, searched: Partial<HardLimits>): string[] {
  const parts: string[] = [];
  parts.push(card.areas.length ? card.areas.join(" · ") : "All areas");
  if (searched.max_price_eur != null) parts.push(`${money(searched.min_price_eur)} to ${money(searched.max_price_eur)}`);
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
  };
  const parts = Object.entries(patch).map(([name, value]) =>
    name === "property_types" ? `types ${(value as string[]).map((t) => TYPES[t] ?? t).join(", ")}`
      : name === "areas" ? `areas ${(value as string[]).join(", ")}`
      : `${words[name] ?? name} ${value}`);
  return `Yes, widen it: ${parts.join(", ")}.`;
}
