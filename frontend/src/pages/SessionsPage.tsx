import { useMemo, useState } from "react";
import { Link, useLocation, useParams } from "react-router-dom";

import { ApiStateCard } from "../components/ApiStateCard";
import { PaginationControls } from "../components/PaginationControls";
import { useApiQuery } from "../hooks/useApiQuery";
import { useGlobalFilters } from "../hooks/useGlobalFilters";
import { toApiQuery } from "../lib/queryString";

type SessionRow = {
  session_id: string;
  agent_id: string;
  file_path: string;
  started_at: string | null;
  ended_at: string | null;
  total_events: number;
  usage_events: number;
  total_tokens: number;
  total_cost_usd: number;
};

type SessionsPayload = {
  page: number;
  page_size: number;
  total_items: number;
  items: SessionRow[];
};

type SessionEvent = {
  event_id: string;
  session_id: string;
  timestamp: string;
  event_type: string;
  role: string | null;
  has_usage: boolean;
  usage: {
    total_tokens: number;
    usd_cost: number;
    model: string;
    provider: string;
  } | null;
};

type SessionDetailPayload = {
  session: {
    session_id: string;
    agent_id: string;
    file_path: string;
    started_at: string | null;
    ended_at: string | null;
    total_events: number;
  };
  usage_summary: {
    usage_events: number;
    total_tokens: number;
    total_cost_usd: number;
    models: string[];
    providers: string[];
  };
  events: {
    page: number;
    page_size: number;
    total_items: number;
    items: SessionEvent[];
  };
};

const CURRENCY = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 4,
  maximumFractionDigits: 4
});

export function SessionsPage() {
  const { filters } = useGlobalFilters();
  const { sessionId } = useParams();
  const location = useLocation();
  const [page, setPage] = useState(1);

  const sessionsQuery = useApiQuery<SessionsPayload>(
    `/api/sessions?${toApiQuery({
      page,
      page_size: 20,
      from: filters.from,
      to: filters.to,
      agent: filters.agent,
      model: filters.model,
      provider: filters.provider
    })}`
  );

  const selectedSessionId = useMemo(() => {
    if (sessionId) {
      return sessionId;
    }

    return sessionsQuery.data?.items[0]?.session_id ?? null;
  }, [sessionId, sessionsQuery.data]);

  const detailQuery = useApiQuery<SessionDetailPayload>(
    selectedSessionId
      ? `/api/sessions/${selectedSessionId}?${toApiQuery({ page: 1, page_size: 200 })}`
      : "/api/sessions/missing?page=1&page_size=1"
  );

  const highBurn = useMemo(() => {
    const items = detailQuery.data?.events.items ?? [];
    return [...items]
      .filter((event) => event.usage)
      .sort((a, b) => (b.usage?.total_tokens ?? 0) - (a.usage?.total_tokens ?? 0))
      .slice(0, 5);
  }, [detailQuery.data]);

  return (
    <div className="splitLayout">
      <ApiStateCard title="Sessions" query={sessionsQuery}>
        {(payload) => (
          <>
            <div className="tableWrap">
              <table>
                <thead>
                  <tr>
                    <th>Session</th>
                    <th>Agent</th>
                    <th>Events</th>
                    <th>Usage Events</th>
                    <th>Tokens</th>
                    <th>Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {payload.items.map((item) => {
                    const selected = item.session_id === selectedSessionId;
                    return (
                      <tr key={item.session_id} className={selected ? "selectedRow" : undefined}>
                        <td>
                          <Link to={`/sessions/${item.session_id}${location.search}`}>{item.session_id}</Link>
                        </td>
                        <td>{item.agent_id}</td>
                        <td>{item.total_events}</td>
                        <td>{item.usage_events}</td>
                        <td>{item.total_tokens}</td>
                        <td>{CURRENCY.format(item.total_cost_usd)}</td>
                      </tr>
                    );
                  })}
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
        <div className="panelHeader">
          <h2>Session Detail</h2>
          <button
            type="button"
            className="ghostButton"
            onClick={() => {
              if (!selectedSessionId) {
                return;
              }
              detailQuery.reload();
            }}
          >
            Reload Detail
          </button>
        </div>

        {!selectedSessionId && <p className="muted">Select a session from the list.</p>}
        {selectedSessionId && detailQuery.loading && <p className="muted">Loading session detail...</p>}
        {selectedSessionId && detailQuery.error && <p className="muted">Failed to load session detail.</p>}

        {selectedSessionId && detailQuery.data && (
          <div className="pageStack">
            <div className="detailMetaGrid">
              <article className="statCard">
                <h3>Session</h3>
                <p>{detailQuery.data.session.session_id}</p>
              </article>
              <article className="statCard">
                <h3>Total Tokens</h3>
                <p>{detailQuery.data.usage_summary.total_tokens}</p>
              </article>
              <article className="statCard">
                <h3>Total Cost</h3>
                <p>{CURRENCY.format(detailQuery.data.usage_summary.total_cost_usd)}</p>
              </article>
              <article className="statCard">
                <h3>Models</h3>
                <p>{detailQuery.data.usage_summary.models.join(", ") || "-"}</p>
              </article>
            </div>

            <section className="panel nestedPanel">
              <h3>High Burn Moments</h3>
              {highBurn.length === 0 && <p className="muted">No usage events in this session.</p>}
              {highBurn.length > 0 && (
                <ul className="simpleList">
                  {highBurn.map((event) => (
                    <li key={event.event_id}>
                      <span>{event.timestamp}</span>
                      <span>{event.usage?.model}</span>
                      <span>{event.usage?.total_tokens ?? 0} tokens</span>
                      <span>{CURRENCY.format(event.usage?.usd_cost ?? 0)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="panel nestedPanel">
              <h3>Mixed Event Timeline</h3>
              <div className="tableWrap">
                <table>
                  <thead>
                    <tr>
                      <th>Timestamp</th>
                      <th>Type</th>
                      <th>Role</th>
                      <th>Usage Overlay</th>
                    </tr>
                  </thead>
                  <tbody>
                    {detailQuery.data.events.items.map((event) => (
                      <tr key={event.event_id}>
                        <td>{event.timestamp}</td>
                        <td>{event.event_type}</td>
                        <td>{event.role ?? "-"}</td>
                        <td>
                          {event.usage
                            ? `${event.usage.total_tokens} tokens | ${CURRENCY.format(event.usage.usd_cost)} | ${event.usage.model}`
                            : "-"}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </div>
        )}
      </section>
    </div>
  );
}
