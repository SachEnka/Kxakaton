import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, type Brief } from "../api";
import { money, when } from "../format";

export function ClientHome() {
  const [items, setItems] = useState<Brief[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api<{ items: Brief[] }>("/api/applications")
      .then((payload) => {
        if (active) setItems(payload.items);
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "Не удалось загрузить заявки");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="page stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <h1>Ваши заявки</h1>
          <p className="muted">Статус сохраняется. Можно закрыть страницу и вернуться.</p>
        </div>
        <Link className="primary" to="/app/new" style={{ textDecoration: "none" }}>Подобрать финансирование</Link>
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      {!error && items.length === 0 && (
        <section className="panel">
          <h2>Пока пусто</h2>
          <p className="muted">Начните с цели: зачем нужны деньги, какая сумма и на какой срок.</p>
        </section>
      )}
      <div className="stack">
        {items.map((item) => (
          <Link key={item.id} to={`/app/applications/${item.id}`} className="card" style={{ textDecoration: "none" }}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <strong>{item.public_number}</strong>
              <span className={badgeClass(item.status)}>{item.status_label}</span>
            </div>
            <p>{item.product_name} · {money(item.amount)}</p>
            <p className="muted">{item.company_name || "Компания ещё не указана"} · {when(item.created_at)}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}

function badgeClass(status: string) {
  if (["APPROVED", "ISSUED", "CONTRACTING"].includes(status)) return "badge ok";
  if (["REJECTED", "CANCELLED"].includes(status)) return "badge bad";
  if (["NEED_INFO", "DECISION_READY", "APPROVED_WITH_CHANGES"].includes(status)) return "badge wait";
  return "badge";
}
