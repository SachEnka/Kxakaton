import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Application } from "../api";
import { day, money, rate, when } from "../format";

export function ApplicationPage() {
  const { id } = useParams();
  const [application, setApplication] = useState<Application | null>(null);
  const [answer, setAnswer] = useState("");
  const [revenue, setRevenue] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (!id) return;
    let active = true;
    api<Application>(`/api/applications/${id}`)
      .then((payload) => {
        if (active) setApplication(payload);
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "Заявка не открылась");
      });
    return () => {
      active = false;
    };
  }, [id]);

  async function act(path: string, body?: unknown) {
    if (!id) return;
    setPending(true);
    setError("");
    try {
      const next = await api<Application>(`/api/applications/${id}${path}`, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      });
      setApplication(next);
      setAnswer("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Действие не выполнено");
    } finally {
      setPending(false);
    }
  }

  function sendAnswer(event: FormEvent) {
    event.preventDefault();
    const monthly = revenue.trim() ? Number(revenue) : undefined;
    act("/answers", { answer, monthly_revenue: monthly });
  }

  if (error && !application) return <main className="page"><p className="alert" role="alert">{error}</p></main>;
  if (!application) return <main className="page"><p>Загружаем заявку…</p></main>;
  const decision = application.decision;

  return (
    <main className="page stack">
      <div className="row" style={{ justifyContent: "space-between" }}>
        <div>
          <p className="muted">{application.public_number}</p>
          <h1>{application.status_label}</h1>
        </div>
        <span className={badge(application.status)}>{application.product_name}</span>
      </div>
      <ol className="timeline">
        {application.timeline.map((item) => (
          <li key={item.key} className={item.state}>{item.title}</li>
        ))}
      </ol>
      <section className="split">
        <article className="panel stack">
          <h2>Где заявка сейчас</h2>
          <p><strong>Уже сделано.</strong> {application.stage.done}</p>
          <p><strong>Сейчас.</strong> {application.stage.now}</p>
          <p><strong>Дальше.</strong> {application.stage.next_actor}</p>
          {error && <p className="alert" role="alert">{error}</p>}
          {application.status === "DRAFT" && <Link to={`/app/new?draft=${application.id}`}>Продолжить заполнение</Link>}
          {application.pending_question && (
            <form className="stack" onSubmit={sendAnswer}>
              <p className="note">{application.pending_question}</p>
              <label>Ответ<textarea value={answer} onChange={(event) => setAnswer(event.target.value)} required /></label>
              <label>Уточнённая выручка в месяц, если хотите её поправить<input value={revenue} onChange={(event) => setRevenue(event.target.value)} inputMode="decimal" /></label>
              <button className="primary" disabled={pending} type="submit">Отправить ответ</button>
            </form>
          )}
          {decision && application.status !== "DECISION_READY" && (
            <DecisionCard application={application} />
          )}
          {application.status === "DECISION_READY" && (
            <p className="note">{decision?.explanation || "Сотрудник банка проверяет оценку."}</p>
          )}
          <div className="row">
            {application.status === "APPROVED" && (
              <button className="primary" type="button" disabled={pending} onClick={() => act("/accept-offer")}>Перейти к оформлению</button>
            )}
            {application.status === "APPROVED_WITH_CHANGES" && (
              <>
                <button className="primary" type="button" disabled={pending} onClick={() => act("/accept-offer")}>Принять условия</button>
                <button className="secondary" type="button" disabled={pending} onClick={() => act("/decline-offer")}>Отказаться</button>
              </>
            )}
            {application.status === "CONTRACTING" && (
              <button className="primary" type="button" disabled={pending} onClick={() => act("/sign")}>Подписать</button>
            )}
          </div>
          {application.status === "CONTRACTING" && (
            <p className="muted">Подписание смоделировано: электронной подписи и перевода денег нет.</p>
          )}
          {application.status === "ISSUED" && (
            <p className="note">Финансирование в прототипе отмечено как оформленное. Платёж клиенту не отправляется.</p>
          )}
        </article>
        <aside className="panel stack">
          <h2>Компания</h2>
          <p>{application.company.name || "Компания"}</p>
          {application.company.full_name && application.company.full_name !== application.company.name && (
            <p className="muted">{application.company.full_name}</p>
          )}
          <p className="muted">ИНН {application.company.inn || "—"}{application.company.kpp ? ` · КПП ${application.company.kpp}` : ""}</p>
          <p className="muted">ОГРН {application.company.ogrn || "—"}</p>
          <p className="muted">Руководитель: {application.company.director_name || "—"}</p>
          <p className="muted">{application.company.region || application.company.address || "Регион не указан"} · с {day(application.company.registration_date)}</p>
          {application.company.registry_status_label && <p>{application.company.registry_status_label}</p>}
          {application.company.source_label && <p className="muted">{application.company.source_label}</p>}
          <p>{money(application.amount)} на {application.term_months} мес.</p>
          <p className="muted">Выручка {money(application.monthly_revenue)} · расходы {money(application.monthly_expenses)}</p>
        </aside>
      </section>
      <section className="panel">
        <h2>Журнал</h2>
        <ul className="journal">
          {application.events.map((event) => (
            <li key={event.id}>
              <time dateTime={event.created_at}>{when(event.created_at)}</time>
              <span>{event.message}</span>
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

function DecisionCard({ application }: { application: Application }) {
  const decision = application.decision;
  if (!decision) return null;
  return (
    <div className="stack">
      <p>{decision.explanation}</p>
      {decision.changes.length > 0 && (
        <ul>
          {decision.changes.map((change) => (
            <li key={change.field}>
              {change.field}: было {change.field === "Ставка" ? rate(change.requested) : change.field === "Срок" ? `${change.requested} мес.` : money(change.requested)}, стало {change.field === "Ставка" ? rate(change.offered) : change.field === "Срок" ? `${change.offered} мес.` : money(change.offered)}
            </li>
          ))}
        </ul>
      )}
      {decision.offered_amount != null && (
        <div className="kpis">
          <div className="kpi"><span>Сумма</span><strong>{money(decision.offered_amount)}</strong></div>
          <div className="kpi"><span>Срок</span><strong>{decision.offered_term_months} мес.</strong></div>
          <div className="kpi"><span>Ставка</span><strong>{rate(decision.offered_rate)}</strong></div>
          <div className="kpi"><span>Платёж</span><strong>{money(decision.monthly_payment)}</strong></div>
        </div>
      )}
    </div>
  );
}

function badge(status: string) {
  if (["APPROVED", "ISSUED", "CONTRACTING"].includes(status)) return "badge ok";
  if (["REJECTED", "CANCELLED"].includes(status)) return "badge bad";
  return "badge wait";
}
