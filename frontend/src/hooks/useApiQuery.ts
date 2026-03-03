import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch } from "../lib/api";

export type ApiQueryState<T> = {
  loading: boolean;
  error: ApiError | Error | null;
  data: T | null;
  reload: () => void;
};

export function useApiQuery<T>(path: string): ApiQueryState<T> {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | Error | null>(null);
  const [data, setData] = useState<T | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  const reload = useCallback(() => {
    setReloadTick((tick) => tick + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function run() {
      setLoading(true);
      setError(null);

      try {
        const payload = await apiFetch<T>(path);
        if (!cancelled) {
          setData(payload);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err as ApiError | Error);
          setData(null);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    void run();

    return () => {
      cancelled = true;
    };
  }, [path, reloadTick]);

  return useMemo(
    () => ({
      loading,
      error,
      data,
      reload
    }),
    [loading, error, data, reload]
  );
}
