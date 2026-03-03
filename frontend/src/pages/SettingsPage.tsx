export function SettingsPage() {
  return (
    <section className="panel">
      <h2>Settings</h2>
      <p className="muted">
        Story 9 provides the shell. Operation wiring for Refresh/Enrich/Reindex controls will be expanded in
        the Settings UI story.
      </p>

      <div className="settingsGrid">
        <label>
          API Base URL
          <input type="text" value={import.meta.env.VITE_API_BASE_URL ?? ""} readOnly />
        </label>

        <label>
          Frontend Mode
          <input type="text" value="Story 9 Shell" readOnly />
        </label>
      </div>
    </section>
  );
}
