export type GlobalFilterKey =
  | "from"
  | "to"
  | "agent"
  | "model"
  | "provider"
  | "search"
  | "minCost"
  | "minTokens";

export type GlobalFilters = Partial<Record<GlobalFilterKey, string>>;

export const FILTER_KEYS: GlobalFilterKey[] = [
  "from",
  "to",
  "agent",
  "model",
  "provider",
  "search",
  "minCost",
  "minTokens"
];

export function parseGlobalFilters(searchParams: URLSearchParams): GlobalFilters {
  const filters: GlobalFilters = {};

  for (const key of FILTER_KEYS) {
    const value = searchParams.get(key);
    if (value && value.trim().length > 0) {
      filters[key] = value;
    }
  }

  return filters;
}

export function applyGlobalFilterUpdate(
  current: URLSearchParams,
  updates: GlobalFilters
): URLSearchParams {
  const next = new URLSearchParams(current);

  for (const [key, value] of Object.entries(updates)) {
    const safeKey = key as GlobalFilterKey;
    if (value && value.trim().length > 0) {
      next.set(safeKey, value.trim());
    } else {
      next.delete(safeKey);
    }
  }

  return next;
}

export function toApiQuery(params: Record<string, string | number | boolean | undefined>): string {
  const qs = new URLSearchParams();

  for (const [key, value] of Object.entries(params)) {
    if (value === undefined) {
      continue;
    }
    qs.set(key, String(value));
  }

  return qs.toString();
}
