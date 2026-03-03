import { NavLink, Outlet, useLocation } from "react-router-dom";

import { GlobalFilterBar } from "./GlobalFilterBar";

const navItems = [
  { to: "/overview", label: "Overview" },
  { to: "/sessions", label: "Sessions" },
  { to: "/events", label: "Events Explorer" },
  { to: "/insights", label: "Task Insights" },
  { to: "/settings", label: "Settings" }
];

export function AppShell() {
  const location = useLocation();
  const search = location.search;

  return (
    <div className="appRoot">
      <header className="topBar">
        <div className="titleWrap">
          <h1>OpenClaw Monitor</h1>
          <p>Usage analytics and exploration console</p>
        </div>

        <nav className="mainNav" aria-label="Main navigation">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={`${item.to}${search}`}
              className={({ isActive }) => (isActive ? "navItem active" : "navItem")}
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </header>

      <main className="mainContent">
        <GlobalFilterBar />
        <Outlet />
      </main>
    </div>
  );
}
