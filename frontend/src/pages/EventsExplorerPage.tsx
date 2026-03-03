import { useMemo, useState } from "react";

import { ApiStateCard } from "../components/ApiStateCard";
import { PaginationControls } from "../components/PaginationControls";
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
  raw_json: string;
};

type EventsPayload = {
  page: number;
  page_size: number;
  total_items: number;
  items: EventRow[];
};

export function EventsExplorerPage() {
  const { filters } = useGlobalFilters();
  const [page, setPage] = useState(1);
  const [eventType, setEventType] = useState("");
  const [role, setRole] = useState("");
  const [agent, setAgent] = useState("");
  const [session, setSession] = useState("");
  const [usageOnly, setUsageOnly] = useState(false);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);

  const query = useApiQuery<EventsPayload>(
    `/api/events?${toApiQuery({
      page,
      page_size: 50,
      from: filters.from,
      to: filters.to,
      type: eventType || undefined,
      role: role || undefined,
      agent: agent || filters.agent,
      session: session || undefined,
      usage_bearing_only: usageOnly
    })}`
  );

  const selectedEvent = useMemo(
    () => query.data?.items.find((item) => item.event_id === selectedEventId) ?? query.data?.items[0] ?? null,
    [query.data, selectedEventId]
  );

  return (
    <div className="splitLayout">
      <ApiStateCard title="Events Explorer" query={query}>
        {(payload) => (
          <>
            <section className="eventsFacetGrid">
              <label>
                Event Type
                <input
                  type="text"
                  placeholder="message"
                  value={eventType}
                  onChange={(event) => {
                    setEventType(event.target.value);
                    setPage(1);
                  }}
                />
              </label>
              <label>
                Role
                <input
                  type="text"
                  placeholder="assistant"
                  value={role}
                  onChange={(event) => {
                    setRole(event.target.value);
                    setPage(1);
                  }}
                />
              </label>
              <label>
                Agent
                <input
                  type="text"
                  placeholder="agent-a"
                  value={agent}
                  onChange={(event) => {
                    setAgent(event.target.value);
                    setPage(1);
                  }}
                />
              </label>
              <label>
                Session
                <input
                  type="text"
                  placeholder="session-id"
                  value={session}
                  onChange={(event) => {
                    setSession(event.target.value);
                    setPage(1);
                  }}
                />
              </label>
            </section>

            <label className="inlineCheck">
              <input
                type="checkbox"
                checked={usageOnly}
                onChange={(event) => {
                  setUsageOnly(event.target.checked);
                  setPage(1);
                }}
              />
              Usage-bearing only
            </label>

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
                    <tr
                      key={item.event_id}
                      className={item.event_id === selectedEvent?.event_id ? "selectedRow" : undefined}
                      onClick={() => setSelectedEventId(item.event_id)}
                    >
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
            </div>

            <PaginationControls
              page={payload.page}
              pageSize={payload.page_size}
              totalItems={payload.total_items}
              onPageChange={setPage}
            />
          </>
        )}
      </ApiStateCard>

      <section className="panel">
        <h2>Selected Event JSON</h2>
        {!selectedEvent && <p className="muted">Select an event row to inspect raw payload.</p>}
        {selectedEvent && <pre className="jsonPane">{prettyJson(selectedEvent.raw_json)}</pre>}
      </section>
    </div>
  );
}

function prettyJson(rawJson: string): string {
  try {
    return JSON.stringify(JSON.parse(rawJson), null, 2);
  } catch {
    return rawJson;
  }
}
