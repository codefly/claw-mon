import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { App } from "../App";

describe("app routing", () => {
  it("renders each primary route", async () => {
    const cases = [
      { path: "/overview", heading: "Overview" },
      { path: "/sessions", heading: "Sessions" },
      { path: "/events", heading: "Events Explorer" },
      { path: "/insights", heading: "Task Insights (Shell)" },
      { path: "/settings", heading: "Settings" }
    ];

    for (const item of cases) {
      const { unmount } = render(
        <MemoryRouter initialEntries={[item.path]}>
          <App />
        </MemoryRouter>
      );

      expect(await screen.findByRole("heading", { name: item.heading })).toBeInTheDocument();
      unmount();
    }
  });
});
