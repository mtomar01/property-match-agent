// The shapes the Python API sends (api/server.py) and the three calls the app makes.

export type Intent = "buy" | "rent" | "invest";

export interface HardLimits {
  max_price_eur: number | null;
  min_price_eur: number | null;
  min_size_m2: number | null;
  max_size_m2: number | null;
  min_bedrooms: number | null;
  max_bedrooms: number | null;
  property_types: string[];
  exclude_floors: string[];
}

export interface Preference {
  feature: string;
  min: number | string | null;
  max: number | string | null;
  equals: boolean | null;
  weight: number;
}

// The card as the user said it. Code adds the margins and the lowest price (core/card_rules.py).
export interface Card {
  intent: Intent | null;
  areas: string[];
  hard_limits: HardLimits;
  budget_around: boolean;
  ideally: string[];
  preferences: Preference[];
  open_questions: string[];
}

export interface Supply {
  matches: number;
  listings_in_areas: number;
  median_price_eur: number | null;
  median_price_per_m2: number | null;
}

export interface ChatReply {
  session: string;
  reply: string;
  action: "ask" | "confirm";
  asking_about: string[];
  unsupported: string[];
  card: Card;
  searched_as: Partial<HardLimits>;
  supply: Supply | null;
}

export interface Summary {
  listing_id: string;
  source: string;
  url: string;
  title: string | null;
  price_eur: number | null;
  size_m2: number | null;
  price_per_m2: number | null;
  bedrooms: number | null;
  floor: string | null;
  area: string | null;
  sub_area: string | null;
  year_built: number | null;
  renovated_year: number | null;
  energy_class: string | null;
  property_type: string | null;
  first_seen: string;
  previous_price_eur: number | null;
  preference_score: number;
  synthetic: boolean;
}

export interface SearchResult {
  total_matches: number;
  returned: number;
  results: Summary[];
  searched_as: Partial<HardLimits>;
  excluded_because_unknown: Record<string, number>;
  searched: number;
  data: string;
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({ error: `The server answered ${response.status}` }));
  if (!response.ok) throw new Error(payload.error ?? `The server answered ${response.status}`);
  return payload as T;
}

export const sendChat = (session: string | null, text: string) => post<ChatReply>("/api/chat", { session, text });
export const runSearch = (card: Card, limit = 50) => post<SearchResult>("/api/search", { card, limit });
