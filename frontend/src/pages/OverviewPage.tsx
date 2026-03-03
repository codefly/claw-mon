import { ApiStateCard } from "../components/ApiStateCard";
import { useApiQuery } from "../hooks/useApiQuery";
import { useGlobalFilters } from "../hooks/useGlobalFilters";
import { toApiQuery } from "../lib/queryString";

type OverviewPayload = {
  summary: {
    events: number;
    input_tokens: number;
    output_tokens: number;
    cache_read_tokens: number;
    cache_write_tokens: number;
    total_tokens: number;
    total_cost_usd: number;
  };
  top_model_by_spend: {
    model: string;
    total_cost_usd: number;
  } | null;
};

export function OverviewPage() {
  const { filters } = useGlobalFilters();

  const query = useApiQuery<OverviewPayload>(
    `/api/overview?${toApiQuery({
      from: filters.from,
      to: filters.to,
      agent: filters.agent,
      model: filters.model,
      provider: filters.provider
    })}`
  );

  return (
    <ApiStateCard title="Overview" query={query}>
      {(payload) => {
        const summary = payload.summary;
        if (!summary) {
          return <p className="muted">Overview payload missing summary data.</p>;
        }

        return (
          <div className="cardGrid">
            <article className="statCard">
              <h3>Total Cost</h3>
              <p>${summary.total_cost_usd.toFixed(4)}</p>
            </article>
            <article className="statCard">
              <h3>Total Tokens</h3>
              <p>{summary.total_tokens.toLocaleString()}</p>
            </article>
            <article className="statCard">
              <h3>Usage Events</h3>
              <p>{summary.events.toLocaleString()}</p>
            </article>
            <article className="statCard">
              <h3>Top Model</h3>
              <p>{payload.top_model_by_spend?.model ?? "-"}</p>
            </article>
          </div>
        );
      }}
    </ApiStateCard>
  );
}
