import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import {
  applyGlobalFilterUpdate,
  type GlobalFilterKey,
  type GlobalFilters,
  parseGlobalFilters
} from "../lib/queryString";

export function useGlobalFilters() {
  const [searchParams, setSearchParams] = useSearchParams();

  const filters = useMemo(() => parseGlobalFilters(searchParams), [searchParams]);

  function setFilter(key: GlobalFilterKey, value: string) {
    setSearchParams((prev) => applyGlobalFilterUpdate(prev, { [key]: value }));
  }

  function setFilters(updates: GlobalFilters) {
    setSearchParams((prev) => applyGlobalFilterUpdate(prev, updates));
  }

  function clearFilters() {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      for (const key of [
        "from",
        "to",
        "agent",
        "model",
        "provider",
        "search",
        "minCost",
        "minTokens"
      ] as const) {
        next.delete(key);
      }
      return next;
    });
  }

  return {
    filters,
    setFilter,
    setFilters,
    clearFilters
  };
}
