import { useGlobalFilters } from "../hooks/useGlobalFilters";

export function GlobalFilterBar() {
  const { filters, setFilter, clearFilters } = useGlobalFilters();

  return (
    <section className="filterBar panel">
      <div className="filterRow">
        <label>
          From
          <input
            type="datetime-local"
            value={filters.from ?? ""}
            onChange={(event) => setFilter("from", event.target.value)}
          />
        </label>

        <label>
          To
          <input
            type="datetime-local"
            value={filters.to ?? ""}
            onChange={(event) => setFilter("to", event.target.value)}
          />
        </label>

        <label>
          Agent
          <input
            type="text"
            value={filters.agent ?? ""}
            placeholder="agent-a"
            onChange={(event) => setFilter("agent", event.target.value)}
          />
        </label>

        <label>
          Model
          <input
            type="text"
            value={filters.model ?? ""}
            placeholder="claude-sonnet-4-6"
            onChange={(event) => setFilter("model", event.target.value)}
          />
        </label>
      </div>

      <div className="filterRow">
        <label>
          Provider
          <input
            type="text"
            value={filters.provider ?? ""}
            placeholder="anthropic"
            onChange={(event) => setFilter("provider", event.target.value)}
          />
        </label>

        <label>
          Search
          <input
            type="text"
            value={filters.search ?? ""}
            placeholder="session/topic"
            onChange={(event) => setFilter("search", event.target.value)}
          />
        </label>

        <label>
          Min Cost
          <input
            type="number"
            value={filters.minCost ?? ""}
            min="0"
            step="0.01"
            onChange={(event) => setFilter("minCost", event.target.value)}
          />
        </label>

        <label>
          Min Tokens
          <input
            type="number"
            value={filters.minTokens ?? ""}
            min="0"
            step="1"
            onChange={(event) => setFilter("minTokens", event.target.value)}
          />
        </label>
      </div>

      <div className="filterActions">
        <button type="button" className="ghostButton" onClick={clearFilters}>
          Clear Filters
        </button>
      </div>
    </section>
  );
}
