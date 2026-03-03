import type { ReactNode } from "react";

import type { ApiQueryState } from "../hooks/useApiQuery";

type ApiStateCardProps<T> = {
  title: string;
  query: ApiQueryState<T>;
  children: (data: T) => ReactNode;
};

export function ApiStateCard<T>({ title, query, children }: ApiStateCardProps<T>) {
  return (
    <section className="panel" aria-live="polite">
      <div className="panelHeader">
        <h2>{title}</h2>
        <button type="button" className="ghostButton" onClick={query.reload}>
          Reload
        </button>
      </div>

      {query.loading && <p className="muted">Loading...</p>}

      {!query.loading && query.error && (
        <div className="errorBlock">
          <p>Request failed.</p>
          <pre>{query.error.message}</pre>
        </div>
      )}

      {!query.loading && !query.error && query.data && children(query.data)}

      {!query.loading && !query.error && !query.data && (
        <p className="muted">No data returned.</p>
      )}
    </section>
  );
}
