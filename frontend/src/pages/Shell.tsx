import { Link, Outlet } from "react-router-dom";
import type { User } from "../api";

export function Shell({ user, onLeave }: { user: User; onLeave: () => void }) {
  const home = user.role === "UNDERWRITER" ? "/desk" : "/app";
  return (
    <div className="app-shell">
      <header className="topbar">
        <Link className="brand" to={home}>
          <strong>Кредитный кабинет</strong>
          <span>{user.role === "UNDERWRITER" ? "Сотрудник банка" : "Кабинет предпринимателя"}</span>
        </Link>
        <div className="top-actions">
          <span>{user.full_name}</span>
          {user.role === "CLIENT" && <Link to="/app/new">Новая заявка</Link>}
          <button className="ghost" type="button" onClick={onLeave}>Выйти</button>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
