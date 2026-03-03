import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";

import { App } from "../App";

describe("global filters", () => {
  it("hydrates from URL and updates query string through inputs", async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={["/overview?agent=agent-a"]}>
        <App />
      </MemoryRouter>
    );

    const agentInput = screen.getByLabelText("Agent") as HTMLInputElement;
    expect(agentInput.value).toBe("agent-a");

    await user.clear(agentInput);
    await user.type(agentInput, "agent-b");

    expect(agentInput.value).toBe("agent-b");
  });
});
