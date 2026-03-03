import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { useApiQuery } from "../hooks/useApiQuery";

type Payload = { ok: boolean };

function Harness({ path }: { path: string }) {
  const query = useApiQuery<Payload>(path);

  if (query.loading) {
    return <p>loading</p>;
  }

  if (query.error) {
    return <p>error:{query.error.message}</p>;
  }

  return <p>ok:{query.data?.ok ? "true" : "false"}</p>;
}

describe("useApiQuery", () => {
  it("handles success", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      statusText: "OK",
      headers: {
        get: () => "application/json"
      },
      text: async () => JSON.stringify({ ok: true })
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <Harness path="/api/health" />
      </MemoryRouter>
    );

    expect(screen.getByText("loading")).toBeInTheDocument();
    await screen.findByText("ok:true");
  });

  it("handles error", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      statusText: "Server Error",
      headers: {
        get: () => "application/json"
      },
      text: async () => JSON.stringify({ detail: "boom" })
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <Harness path="/api/health" />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/error:Server Error/)).toBeInTheDocument();
    });
  });

  it("handles non-json success payloads as errors", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      statusText: "OK",
      headers: {
        get: () => "text/html"
      },
      text: async () => "<html>not-json</html>"
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <MemoryRouter>
        <Harness path="/api/overview" />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/error:Expected JSON response/)).toBeInTheDocument();
    });
  });
});
