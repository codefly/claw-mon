import { ApiStateCard } from "../components/ApiStateCard";
import { useApiQuery } from "../hooks/useApiQuery";
import { useGlobalFilters } from "../hooks/useGlobalFilters";
import { toApiQuery } from "../lib/queryString";

type BreakdownRow = {
  key: string;
  total_tokens: number;
  total_cost_usd: number;
};

type BreakdownPayload = {
  items: BreakdownRow[];
};

export function TaskInsightsPage() {
  const { filters } = useGlobalFilters();

  const query = useApiQuery<BreakdownPayload>(
    `/api/breakdown?${toApiQuery({
      by: "provider",
      page: 1,
      page_size: 20,
      from: filters.from,
      to: filters.to,
      agent: filters.agent,
      model: filters.model,
      provider: filters.provider
    })}`
  );

  return (
    <ApiStateCard title="Task Insights (Shell)" query={query}>
      {(payload) => (
        <ul className="simpleList">
          {payload.items.map((item) => (
            <li key={item.key}>
              <strong>{item.key}</strong>
              <span>{item.total_tokens} tokens</span>
              <span>${item.total_cost_usd.toFixed(4)}</span>
            </li>
          ))}
        </ul>
      )}
    </ApiStateCard>
  );
}
