import { useMemo } from "react";
import { Link, useLocation } from "react-router-dom";

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

type TrendPoint = {
  bucket: string;
  value: number;
};

type TrendPayload = {
  bucket: string;
  metric: "cost" | "tokens";
  points: TrendPoint[];
};

type BreakdownItem = {
  key: string;
  events: number;
  total_tokens: number;
  total_cost_usd: number;
};

type BreakdownPayload = {
  by: "agent" | "model" | "provider";
  page: number;
  page_size: number;
  total_items: number;
  items: BreakdownItem[];
};

type SessionsPayload = {
  items: Array<{
    session_id: string;
    agent_id: string;
    total_cost_usd: number;
    total_tokens: number;
    ended_at: string | null;
  }>;
};

const CURRENCY = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 4,
  maximumFractionDigits: 4
});

const NUMBER = new Intl.NumberFormat("en-US");

function SparkBars({
  title,
  points,
  valueFormatter
}: {
  title: string;
  points: TrendPoint[];
  valueFormatter: (value: number) => string;
}) {
  if (points.length === 0) {
    return (
      <section className="panel">
        <h3>{title}</h3>
        <p className="muted">No trend points for this filter range.</p>
      </section>
    );
  }

  const maxValue = Math.max(...points.map((point) => point.value), 1);

  return (
    <section className="panel">
      <h3>{title}</h3>
      <div className="barChartList">
        {points.map((point) => {
          const width = Math.max((point.value / maxValue) * 100, 2);
          return (
            <div key={point.bucket} className="barChartRow">
              <span className="barChartLabel">{point.bucket}</span>
              <div className="barChartTrack">
                <div className="barChartFill" style={{ width: `${width}%` }} />
              </div>
              <span className="barChartValue">{valueFormatter(point.value)}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function ClickableBreakdown({
  title,
  items,
  onSelect,
  formatter
}: {
  title: string;
  items: BreakdownItem[];
  onSelect: (key: string) => void;
  formatter: (value: number) => string;
}) {
  if (items.length === 0) {
    return (
      <section className="panel">
        <h3>{title}</h3>
        <p className="muted">No breakdown data yet.</p>
      </section>
    );
  }

  const maxValue = Math.max(...items.map((item) => item.total_cost_usd), 1);

  return (
    <section className="panel">
      <h3>{title}</h3>
      <div className="barChartList">
        {items.slice(0, 10).map((item) => {
          const width = Math.max((item.total_cost_usd / maxValue) * 100, 2);
          return (
            <button key={item.key} type="button" className="barAction" onClick={() => onSelect(item.key)}>
              <span className="barChartLabel">{item.key}</span>
              <div className="barChartTrack">
                <div className="barChartFill" style={{ width: `${width}%` }} />
              </div>
              <span className="barChartValue">{formatter(item.total_cost_usd)}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}

export function OverviewPage() {
  const { filters, setFilters } = useGlobalFilters();
  const location = useLocation();
  const sharedQuery = toApiQuery({
    from: filters.from,
    to: filters.to,
    agent: filters.agent,
    model: filters.model,
    provider: filters.provider
  });

  const overviewQuery = useApiQuery<OverviewPayload>(`/api/overview?${sharedQuery}`);
  const costTrendQuery = useApiQuery<TrendPayload>(`/api/trends?${toApiQuery({ ...filters, bucket: "day", metric: "cost" })}`);
  const tokenTrendQuery = useApiQuery<TrendPayload>(`/api/trends?${toApiQuery({ ...filters, bucket: "day", metric: "tokens" })}`);
  const agentBreakdownQuery = useApiQuery<BreakdownPayload>(`/api/breakdown?${toApiQuery({ ...filters, by: "agent", page: 1, page_size: 12 })}`);
  const modelBreakdownQuery = useApiQuery<BreakdownPayload>(`/api/breakdown?${toApiQuery({ ...filters, by: "model", page: 1, page_size: 12 })}`);
  const sessionsQuery = useApiQuery<SessionsPayload>(
    `/api/sessions?${toApiQuery({
      ...filters,
      page: 1,
      page_size: 100
    })}`
  );

  const topBurnSessions = useMemo(() => {
    const items = sessionsQuery.data?.items ?? [];
    return [...items]
      .sort((a, b) => b.total_cost_usd - a.total_cost_usd || b.total_tokens - a.total_tokens)
      .slice(0, 8);
  }, [sessionsQuery.data]);

  const overview = overviewQuery.data;
  const summary = overview?.summary;
  const emptyOverview = !summary || summary.events === 0;

  return (
    <div className="pageStack">
      <section className="panel">
        <div className="panelHeader">
          <h2>Overview</h2>
          <button type="button" className="ghostButton" onClick={overviewQuery.reload}>
            Reload Overview
          </button>
        </div>

        {overviewQuery.loading && <p className="muted">Loading overview...</p>}
        {overviewQuery.error && <p className="muted">Unable to load overview metrics.</p>}

        {!overviewQuery.loading && !overviewQuery.error && summary && (
          <>
            <div className="cardGrid">
              <article className="statCard">
                <h3>Total Cost</h3>
                <p>{CURRENCY.format(summary.total_cost_usd)}</p>
              </article>
              <article className="statCard">
                <h3>Total Tokens</h3>
                <p>{NUMBER.format(summary.total_tokens)}</p>
              </article>
              <article className="statCard">
                <h3>Usage Events</h3>
                <p>{NUMBER.format(summary.events)}</p>
              </article>
              <article className="statCard">
                <h3>Top Model</h3>
                <p>{overview?.top_model_by_spend?.model ?? "-"}</p>
              </article>
            </div>
            <p className="muted tokenMixLine">
              Token mix: input {NUMBER.format(summary.input_tokens)} | output {NUMBER.format(summary.output_tokens)} |
              cache read {NUMBER.format(summary.cache_read_tokens)} | cache write {NUMBER.format(summary.cache_write_tokens)}
            </p>
          </>
        )}

        {emptyOverview && !overviewQuery.loading && !overviewQuery.error && (
          <p className="muted">No usage data in the selected filters/date range.</p>
        )}
      </section>

      <div className="twoColGrid">
        <SparkBars
          title="Daily Cost Trend"
          points={costTrendQuery.data?.points ?? []}
          valueFormatter={(value) => CURRENCY.format(value)}
        />
        <SparkBars
          title="Daily Token Trend"
          points={tokenTrendQuery.data?.points ?? []}
          valueFormatter={(value) => NUMBER.format(Math.round(value))}
        />
      </div>

      <div className="twoColGrid">
        <ClickableBreakdown
          title="Cost by Agent (click to filter)"
          items={agentBreakdownQuery.data?.items ?? []}
          onSelect={(key) => setFilters({ agent: key })}
          formatter={(value) => CURRENCY.format(value)}
        />
        <ClickableBreakdown
          title="Cost by Model (click to filter)"
          items={modelBreakdownQuery.data?.items ?? []}
          onSelect={(key) => setFilters({ model: key })}
          formatter={(value) => CURRENCY.format(value)}
        />
      </div>

      <section className="panel">
        <div className="panelHeader">
          <h3>Top Burn Sessions</h3>
          <button type="button" className="ghostButton" onClick={sessionsQuery.reload}>
            Reload Sessions
          </button>
        </div>

        {sessionsQuery.loading && <p className="muted">Loading sessions...</p>}
        {sessionsQuery.error && <p className="muted">Failed to load sessions.</p>}

        {!sessionsQuery.loading && !sessionsQuery.error && topBurnSessions.length === 0 && (
          <p className="muted">No sessions available for selected filters.</p>
        )}

        {topBurnSessions.length > 0 && (
          <div className="tableWrap">
            <table>
              <thead>
                <tr>
                  <th>Session</th>
                  <th>Agent</th>
                  <th>Tokens</th>
                  <th>Cost</th>
                  <th>Last Activity</th>
                </tr>
              </thead>
              <tbody>
                {topBurnSessions.map((session) => (
                  <tr key={session.session_id}>
                    <td>
                      <Link to={`/sessions/${session.session_id}${location.search}`}>{session.session_id}</Link>
                    </td>
                    <td>{session.agent_id}</td>
                    <td>{NUMBER.format(session.total_tokens)}</td>
                    <td>{CURRENCY.format(session.total_cost_usd)}</td>
                    <td>{session.ended_at ?? "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
