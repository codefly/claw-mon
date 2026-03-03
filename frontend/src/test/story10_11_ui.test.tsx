import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { App } from "../App";

function jsonResponse(payload: unknown, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: status >= 200 && status < 300 ? "OK" : "Error",
    headers: {
      get: () => "application/json"
    },
    text: async () => JSON.stringify(payload)
  };
}

function installOverviewFetchMock() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);

    if (url.startsWith("/api/overview")) {
      return jsonResponse({
        summary: {
          events: 3,
          input_tokens: 40,
          output_tokens: 20,
          cache_read_tokens: 5,
          cache_write_tokens: 2,
          total_tokens: 67,
          total_cost_usd: 1.2345
        },
        top_model_by_spend: {
          model: "model-x",
          total_cost_usd: 0.9
        }
      });
    }

    if (url.includes("/api/trends") && url.includes("metric=cost")) {
      return jsonResponse({
        bucket: "day",
        metric: "cost",
        points: [
          { bucket: "2026-03-01", value: 0.5 },
          { bucket: "2026-03-02", value: 0.7345 }
        ]
      });
    }

    if (url.includes("/api/trends") && url.includes("metric=tokens")) {
      return jsonResponse({
        bucket: "day",
        metric: "tokens",
        points: [
          { bucket: "2026-03-01", value: 32 },
          { bucket: "2026-03-02", value: 35 }
        ]
      });
    }

    if (url.includes("/api/breakdown") && url.includes("by=agent")) {
      return jsonResponse({
        by: "agent",
        page: 1,
        page_size: 12,
        total_items: 1,
        items: [{ key: "agent-a", events: 2, total_tokens: 40, total_cost_usd: 1.0 }]
      });
    }

    if (url.includes("/api/breakdown") && url.includes("by=model")) {
      return jsonResponse({
        by: "model",
        page: 1,
        page_size: 12,
        total_items: 1,
        items: [{ key: "model-x", events: 2, total_tokens: 40, total_cost_usd: 1.0 }]
      });
    }

    if (url.startsWith("/api/sessions?")) {
      return jsonResponse({
        page: 1,
        page_size: 100,
        total_items: 2,
        items: [
          {
            session_id: "s2",
            agent_id: "agent-a",
            total_cost_usd: 1.1,
            total_tokens: 55,
            ended_at: "2026-03-02T10:00:00Z"
          },
          {
            session_id: "s1",
            agent_id: "agent-b",
            total_cost_usd: 0.2,
            total_tokens: 12,
            ended_at: "2026-03-01T10:00:00Z"
          }
        ]
      });
    }

    return jsonResponse({ detail: "not found" }, 404);
  });

  vi.stubGlobal("fetch", fetchMock);
}

describe("Story 10/11 UI", () => {
  it("applies overview breakdown clicks to global filters", async () => {
    installOverviewFetchMock();

    const user = userEvent.setup();
    render(
      <MemoryRouter initialEntries={["/overview"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Top Burn Sessions" })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /agent-a/i }));

    expect((screen.getByLabelText("Agent") as HTMLInputElement).value).toBe("agent-a");
    expect(screen.getByRole("link", { name: "s2" })).toBeInTheDocument();
  });

  it("renders sessions detail pane with high burn moments", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);

      if (url.startsWith("/api/sessions?") && !url.includes("/api/sessions/session-1")) {
        return jsonResponse({
          page: 1,
          page_size: 20,
          total_items: 1,
          items: [
            {
              session_id: "session-1",
              agent_id: "agent-a",
              file_path: "/tmp/session-1.jsonl",
              started_at: "2026-03-01T09:00:00Z",
              ended_at: "2026-03-01T09:02:00Z",
              total_events: 3,
              usage_events: 2,
              total_tokens: 80,
              total_cost_usd: 1.2
            }
          ]
        });
      }

      if (url.startsWith("/api/sessions/session-1")) {
        return jsonResponse({
          session: {
            session_id: "session-1",
            agent_id: "agent-a",
            file_path: "/tmp/session-1.jsonl",
            started_at: "2026-03-01T09:00:00Z",
            ended_at: "2026-03-01T09:02:00Z",
            total_events: 3
          },
          usage_summary: {
            usage_events: 2,
            total_tokens: 80,
            total_cost_usd: 1.2,
            models: ["model-a"],
            providers: ["anthropic"]
          },
          events: {
            page: 1,
            page_size: 200,
            total_items: 3,
            items: [
              {
                event_id: "e1",
                session_id: "session-1",
                timestamp: "2026-03-01T09:00:00Z",
                event_type: "message",
                role: "assistant",
                has_usage: true,
                usage: { total_tokens: 50, usd_cost: 0.8, model: "model-a", provider: "anthropic" }
              },
              {
                event_id: "e2",
                session_id: "session-1",
                timestamp: "2026-03-01T09:01:00Z",
                event_type: "tool",
                role: null,
                has_usage: false,
                usage: null
              }
            ]
          }
        });
      }

      return jsonResponse({ detail: "not found" }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/sessions/session-1"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "High Burn Moments" })).toBeInTheDocument();
    expect(screen.getByText(/^50 tokens$/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Mixed Event Timeline" })).toBeInTheDocument();
  });

  it("shows selected event raw json in events explorer", async () => {
    const user = userEvent.setup();

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.startsWith("/api/events")) {
        return jsonResponse({
          page: 1,
          page_size: 50,
          total_items: 2,
          items: [
            {
              event_id: "a",
              session_id: "session-1",
              agent_id: "agent-a",
              timestamp: "2026-03-01T10:00:00Z",
              event_type: "message",
              role: "assistant",
              has_usage: true,
              raw_json: JSON.stringify({ id: "a", text: "first" })
            },
            {
              event_id: "b",
              session_id: "session-2",
              agent_id: "agent-b",
              timestamp: "2026-03-01T09:59:00Z",
              event_type: "tool",
              role: null,
              has_usage: false,
              raw_json: JSON.stringify({ id: "b", text: "second" })
            }
          ]
        });
      }
      return jsonResponse({ detail: "not found" }, 404);
    });

    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter initialEntries={["/events"]}>
        <App />
      </MemoryRouter>
    );

    expect(await screen.findByRole("heading", { name: "Selected Event JSON" })).toBeInTheDocument();
    expect(screen.getByText(/"first"/)).toBeInTheDocument();

    await user.click(screen.getByText("2026-03-01T09:59:00Z"));

    await waitFor(() => {
      expect(screen.getByText(/"second"/)).toBeInTheDocument();
    });
  });
});
