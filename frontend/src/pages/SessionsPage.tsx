import { ApiStateCard } from "../components/ApiStateCard";
import { useApiQuery } from "../hooks/useApiQuery";
import { useGlobalFilters } from "../hooks/useGlobalFilters";
import { toApiQuery } from "../lib/queryString";

type SessionRow = {
  session_id: string;
  agent_id: string;
  total_events: number;
  total_tokens: number;
  total_cost_usd: number;
  ended_at: string | null;
};

type SessionsPayload = {
  page: number;
  page_size: number;
  total_items: number;
  items: SessionRow[];
};

export function SessionsPage() {
  const { filters } = useGlobalFilters();

  const query = useApiQuery<SessionsPayload>(
    `/api/sessions?${toApiQuery({
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
    <ApiStateCard title="Sessions" query={query}>
      {(payload) => (
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Session</th>
                <th>Agent</th>
                <th>Events</th>
                <th>Tokens</th>
                <th>Cost</th>
                <th>Last Activity</th>
              </tr>
            </thead>
            <tbody>
              {payload.items.map((item) => (
                <tr key={item.session_id}>
                  <td>{item.session_id}</td>
                  <td>{item.agent_id}</td>
                  <td>{item.total_events}</td>
                  <td>{item.total_tokens}</td>
                  <td>${item.total_cost_usd.toFixed(4)}</td>
                  <td>{item.ended_at ?? "-"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">Showing {payload.items.length} of {payload.total_items} sessions.</p>
        </div>
      )}
    </ApiStateCard>
  );
}
