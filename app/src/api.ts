// The shapes the Python API sends (api/server.py) and the calls the app makes.

export type Intent = "buy" | "rent" | "invest";

export interface HardLimits {
  max_price_eur: number | null;
  min_price_eur: number | null;
  min_size_m2: number | null;
  max_size_m2: number | null;
  min_bedrooms: number | null;
  max_bedrooms: number | null;
  min_year_built: number | null;
  property_types: string[];
  exclude_floors: string[];
  max_price_per_m2: number | null;
  max_floor_without_lift: number | null;
  exclude_conditions: string[];
  // D79: firm wishes on fields listings reliably state, made hard limits by code
  must_have?: string[];
  min_bathrooms?: number | null;
  min_renovated_year?: number | null;
  min_floor_level?: number | null;
  max_floor_level?: number | null;
  max_metro_walk_min?: number | null;
  must_have_if_type?: Record<string, string[]>;  // D86: e.g. parking a must for houses only
}

export interface Preference {
  feature: string;
  min: number | string | null;
  max: number | string | null;
  equals: boolean | null;
  firm?: boolean;  // said outright, not "ideally" (D79)
  weight: number;
}

// The card as the user said it. Code adds the margins and the lowest price (core/card_rules.py).
// D98: an order the user asked for outright; code sorts the deck strictly by it, with no explore cards.
export type OrderBy = "price_per_m2_asc" | "price_eur_asc" | "price_eur_desc" | "size_m2_desc" | "year_built_desc" | "days_on_market_desc" | "first_seen_desc";

export interface Card {
  intent: Intent | null;
  areas: string[];
  hard_limits: HardLimits;
  budget_around: boolean;
  ideally: string[];
  preferences: Preference[];
  open_questions: string[];
  order_by?: OrderBy | null;
}

export interface SwipeStats {
  swipes: number;
  likes: number;
  rejects: number;
  like_rate: number | null;
  reject_reasons: Record<string, number>;
  skips: number;
  cant_judge: number;
}

export interface Message {
  role: "user" | "assistant";
  text: string;
}

// One of the user's searches (D94): titled by its limits, told apart by its counts. Never a name to invent.
export interface SearchSummary {
  id: string;
  created: string;
  current: boolean;
  areas: string[];
  intent: Intent | null;
  min_price_eur: number | null;
  max_price_eur: number | null;
  has_card: boolean;
  messages: number;
  homes: number | null;
  verdicts: number;
  shortlisted: number;
}

// What the server keeps for this user: GET /api/state, and the shape /api/chat answers with.
export interface State {
  search: { id: string; created: string } | null;
  searches: SearchSummary[];
  messages: Message[];
  card: Card | null;
  action: "ask" | "confirm" | null;
  asking_about: string[];
  unsupported: string[];
  searched_as: Partial<HardLimits> | null;
  wishes: Preference[];  // the wishes left once firm ones became limits (D79)
  swipes: SwipeStats;
  data: string;
  checkin_every: number;
  areas: string[];
  checkin: Checkin | null;
}

export interface ChatReply {
  reply: string;
  action: "ask" | "confirm";
  asking_about: string[];
  unsupported: string[];
  card: Card;
  searched_as: Partial<HardLimits>;
  wishes: Preference[];
  deck_ready: boolean;
  swipes: SwipeStats;
}

export interface Reason {
  text: string;
  feature: string;
  kind: "preference" | "fact" | "fallback";
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
  synthetic: boolean;
}

export interface MarketLine {
  text: string;
  feature: "price_per_m2" | "days_on_market";
}

export interface DeckCard extends Summary {
  photo_url: string | null;
  reasons: Reason[];
  market: MarketLine[];
  preference_score: number;
  learned_score: number | null;
  listed: Listed | null;
  explore_card: boolean;
  skipped_before: boolean;
  deck_position: number;
}

// One way to widen a thin search, counted by code (agent/interview.py, eased).
export interface Widening {
  limits: Record<string, number | string[]>;
  matches: number;
}

// The same home listed more than once (D78): the card is the cheapest version, the others are links.
export interface Listed {
  times: number;
  price_min: number | null;
  price_max: number | null;
  others: { listing_id: string; source: string; url: string; price_eur: number | null }[];
}

// What the learned ranking has picked up (D76): how much of the order the swipes decide, and its clearest leanings.
export interface Learning {
  verdicts: number;
  share: number;
  leans: { feature: string; words: string; direction: "for" | "against"; weight: number }[];
}

export interface Deck {
  cards: DeckCard[];
  learning: Learning | null;
  total_matches: number;
  remaining: number;
  swiped_of_these: number;
  if_eased?: Record<string, Widening>;
  searched_as: Partial<HardLimits>;
  swipes: SwipeStats;
  data: string;
  checkin_every: number;
  since_checkin: number;
  can_undo: boolean;
  order_by?: OrderBy | null;
}

// The check-in after 10 likes or rejects (D66, D75): a pattern the assistant words, a reason the user tapped,
// or a three-tap pulse. The last two are fixed text and answered with a tap.
export interface Checkin extends ChatReply {
  suggestion: { key: string; feature: string | null; kind: string };
  ladder?: "pattern" | "reason" | "pulse";
  options?: Record<string, string> | null;
  yes_message?: string | null;
}

export interface CheckinAnswer {
  follow_up: string | null;
  focus_chat: boolean;
  swipes: SwipeStats;
}

export interface SwipeResult {
  swipes: SwipeStats;
  checkin: Checkin | null;
  since_checkin: number;
  can_undo: boolean;
}

export type Decision = "like" | "reject" | "skip";

export interface UndoResult {
  card: DeckCard | null;
  undone: Decision;
  swipes: SwipeStats;
  since_checkin: number;
  can_undo: boolean;
}

async function call<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(path, body === undefined ? undefined : {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({ error: `The server answered ${response.status}` }));
  if (!response.ok) throw new Error(payload.error ?? `The server answered ${response.status}`);
  return payload as T;
}

export const getState = () => call<State>("/api/state");
export const sendChat = (text: string) => call<ChatReply>("/api/chat", { text });
export const getDeck = (limit = 10) => call<Deck>("/api/deck", { limit });
export const sendSwipe = (swipe: { listing_id: string; decision: Decision; reasons: string[]; note?: string; deck_position: number; explore_card: boolean }) =>
  call<SwipeResult>("/api/swipe", swipe);
export const undoSwipe = () => call<UndoResult>("/api/undo", {});
export const answerCheckin = (answer: string) => call<CheckinAnswer>("/api/checkin", { answer });
export const getShortlist = () => call<{ homes: Summary[]; swipes: SwipeStats }>("/api/shortlist");
export const newSearch = () => call<State>("/api/searches/new", {});
export const selectSearch = (id: string) => call<State>("/api/searches/select", { id });
export const getSearches = () => call<{ current: string | null; searches: SearchSummary[] }>("/api/searches");
