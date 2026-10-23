// Words for the codes the search uses, so the card and the table read like a person wrote them.

export const AREAS: [string, string][] = [
  ["Egaleo", "Egaleo · Αιγάλεω"],
  ["Peristeri", "Peristeri · Περιστέρι"],
  ["Chaidari", "Chaidari · Χαϊδάρι"],
];

export const TYPES: [string, string][] = [
  ["apartment", "Apartment"],
  ["maisonette", "Maisonette"],
  ["studio", "Studio"],
  ["detached_house", "House"],
  ["loft", "Loft"],
  ["building", "Whole building"],
];

export const FLOORS: [string, string][] = [
  ["basement", "Basement"],
  ["semi_basement", "Semi-basement"],
  ["ground", "Ground"],
  ["raised_ground", "Raised ground"],
  ["mezzanine", "Mezzanine"],
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

export function preferenceText(p: { feature: string; min: unknown; max: unknown; equals: unknown }): string {
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
  if (floor == null) return "–";
  const named = FLOORS.find(([code]) => code === floor);
  if (named) return named[1];
  if (floor === "top") return "Top (ρετιρέ)";
  return `${floor}${floor === "1" ? "st" : floor === "2" ? "nd" : floor === "3" ? "rd" : "th"}`;
}

const euro = new Intl.NumberFormat("en-GB", { style: "currency", currency: "EUR", maximumFractionDigits: 0 });
export const money = (value: number | null | undefined) => (value == null ? "–" : euro.format(value));

// "Price €155,000 to €230,000 and size 65 to 97 m²": what a widening would search, in words.
export function wideningText(patch: Record<string, number | string[]>, searched: Record<string, number | null | undefined>): string {
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
    const added = (patch.property_types as string[]).filter((t) => !((searched.property_types as unknown as string[]) ?? []).includes(t));
    parts.push(`add ${added.map((t) => TYPES.find(([code]) => code === t)?.[1].toLowerCase() ?? t).join(", ")}`);
  }
  if ("areas" in patch) {
    const all = patch.areas as string[];
    parts.push(`add ${all[all.length - 1]}`);
  }
  const text = parts.join(" and ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}
