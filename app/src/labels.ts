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
