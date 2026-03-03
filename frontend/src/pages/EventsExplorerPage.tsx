import { ApiStateCard } from "../components/ApiStateCard";
import { useApiQuery } from "../hooks/useApiQuery";
import { useGlobalFilters } from "../hooks/useGlobalFilters";
import { toApiQuery } from "../lib/queryString";

type EventRow = {
  event_id: string;
  session_id: string;
  agent_id: string;
  timestamp: string;
  event_type: string;
  role: string | null;
  has_usage: boolean;
};

type EventsPayload = {
  page: number;
  page_size: number;
  total_items: number;
  items: EventRow[];
};

export function EventsExplorerPage() {
  const { filters } = useGlobalFilters();

  const query = useApiQuery<EventsPayload>(
    `/api/events?${toApiQuery({
      page: 1,
      page_size: 50,
      from: filters.from,
      to: filters.to,
      agent: filters.agent,
      role: filters.search,
      usage_bearing_only: filters.minCost ? true : false
    })}`
  );

  return (
    <ApiStateCard title="Events Explorer" query={query}>
      {(payload) => (
        <div className="tableWrap">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Type</th>
                <th>Role</th>
                <th>Agent</th>
                <th>Session</th>
                <th>Usage</th>
              </tr>
            </thead>
            <tbody>
              {payload.items.map((item) => (
                <tr key={item.event_id}>
                  <td>{item.timestamp}</td>
                  <td>{item.event_type}</td>
                  <td>{item.role ?? "-"}</td>
                  <td>{item.agent_id}</td>
                  <td>{item.session_id}</td>
                  <td>{item.has_usage ? "yes" : "no"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted">Showing {payload.items.length} of {payload.total_items} events.</p>
        </div>
      )}
    </ApiStateCard>
  );
}
