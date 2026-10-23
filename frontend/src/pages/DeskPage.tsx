import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Brief } from "../api";
import { money, when } from "../format";

export function DeskPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<Brief[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    api<{ items: Brief[] }>("/api/underwriter/applications")
      .then((payload) => {
        if (active) setItems(payload.items);
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "Очередь не загрузилась");
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <main className="page stack">
      <div>
        <h1>Очередь заявок</h1>
        <p className="muted">Здесь те же заявки, что видит клиент, плюс проверки и факторы решения.</p>
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      <div className="panel">
        <table>
          <thead>
            <tr>
              <th>Номер</th>
              <th>Компания</th>
              <th>Продукт</th>
              <th>Сумма</th>
              <th>Статус</th>
              <th>Дата</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="clickable" onClick={() => navigate(`/desk/${item.id}`)}>
                <td>{item.public_number}</td>
                <td>{item.company_name || "—"}<br /><span className="muted">{item.inn}</span></td>
                <td>{item.product_name}</td>
                <td>{money(item.amount)}</td>
                <td>
                  {item.status_label}
                  {item.awaits_employee && <div className="badge wait">Ждёт сотрудника</div>}
                </td>
                <td>{when(item.created_at)}</td>
              </tr>
            ))}
            {items.length === 0 && (
              <tr><td colSpan={6}>Заявок пока нет. Их создаёт клиент в своём кабинете.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </main>
  );
}
