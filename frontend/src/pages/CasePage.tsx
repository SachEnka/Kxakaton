import { FormEvent, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, type Application } from "../api";
import { money, rate, when } from "../format";

export function CasePage() {
  const { id } = useParams();
  const [application, setApplication] = useState<Application | null>(null);
  const [decision, setDecision] = useState("APPROVED");
  const [amount, setAmount] = useState("");
  const [term, setTerm] = useState("");
  const [rateValue, setRateValue] = useState("");
  const [comment, setComment] = useState("");
  const [question, setQuestion] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  function load() {
    if (!id) return;
    api<Application>(`/api/underwriter/applications/${id}`)
      .then((payload) => {
        setApplication(payload);
        setAmount(String(payload.decision?.offered_amount || payload.amount));
        setTerm(String(payload.decision?.offered_term_months || payload.term_months));
        setRateValue(String(payload.decision?.offered_rate || ""));
      })
      .catch((reason) => setError(reason instanceof Error ? reason.message : "Карточка не открылась"));
  }

  useEffect(() => {
    load();
  }, [id]);

  async function send(path: string, body?: unknown) {
    if (!id) return;
    setPending(true);
    setError("");
    try {
      const next = await api<Application>(`/api/underwriter/applications/${id}${path}`, {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      });
      setApplication(next);
      setQuestion("");
      setComment("");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Действие не выполнено");
    } finally {
      setPending(false);
    }
  }

  function override(event: FormEvent) {
    event.preventDefault();
    send("/override", {
      decision,
      comment,
      amount: amount ? Number(amount) : null,
      term_months: term ? Number(term) : null,
      rate: rateValue ? Number(rateValue) : null,
    });
  }

  if (!application && !error) return <main className="page"><p>Загружаем карточку…</p></main>;
  if (!application) return <main className="page"><p className="alert">{error}</p></main>;
  const score = application.decision;

  return (
    <main className="page stack">
      <div>
        <Link to="/desk">К очереди</Link>
        <h1>{application.public_number} · {application.status_label}</h1>
        <p className="muted">{application.company.name} · ИНН {application.company.inn}</p>
      </div>
      {error && <p className="alert" role="alert">{error}</p>}
      <section className="split">
        <article className="panel stack">
          <h2>Заявка</h2>
          <p>{application.product_name}, {application.purpose_label}</p>
          <p>{money(application.amount)} на {application.term_months} мес.</p>
          <p className="muted">Выручка {money(application.monthly_revenue)}, расходы {money(application.monthly_expenses)}</p>
          <p className="muted">{application.company.address}</p>
          <p className="muted">Руководитель: {application.company.director_name || "—"} · статус реестра {application.company.registry_status || "—"}</p>
          {score && (
            <>
              <h2>Оценка</h2>
              <div className="kpis">
                <div className="kpi"><span>Балл</span><strong>{score.score}</strong></div>
                <div className="kpi"><span>Категория</span><strong>{score.quality_category}</strong></div>
                <div className="kpi"><span>Положение</span><strong>{score.financial_position_label}</strong></div>
                <div className="kpi"><span>Обслуживание</span><strong>{score.debt_service_label}</strong></div>
              </div>
              <p>{score.explanation}</p>
              <p className="muted">{score.model_note}</p>
              {score.offered_amount != null && (
                <p>Предложение системы: {money(score.offered_amount)} на {score.offered_term_months} мес. под {rate(score.offered_rate)}, платёж {money(score.monthly_payment)}.</p>
              )}
              {score.stop_factors.length > 0 && (
                <ul>{score.stop_factors.map((item) => <li key={item}>{item}</li>)}</ul>
              )}
              <ul>
                {score.factors?.map((factor) => (
                  <li key={factor.code}><strong>{factor.title}.</strong> {factor.detail}</li>
                ))}
              </ul>
            </>
          )}
        </article>
        <aside className="panel stack">
          <h2>Действия</h2>
          {application.awaits_employee && (
            <button className="primary" type="button" disabled={pending} onClick={() => send("/confirm")}>Подтвердить решение системы</button>
          )}
          <form className="stack" onSubmit={override}>
            <label>
              Новое решение
              <select value={decision} onChange={(event) => setDecision(event.target.value)}>
                <option value="APPROVED">Одобрить</option>
                <option value="APPROVED_WITH_CHANGES">Одобрить с другими условиями</option>
                <option value="REJECTED">Отказать</option>
              </select>
            </label>
            <label>Сумма<input value={amount} onChange={(event) => setAmount(event.target.value)} /></label>
            <label>Срок, мес.<input value={term} onChange={(event) => setTerm(event.target.value)} /></label>
            <label>Ставка, %<input value={rateValue} onChange={(event) => setRateValue(event.target.value)} /></label>
            <label>Комментарий<textarea value={comment} onChange={(event) => setComment(event.target.value)} required /></label>
            <button className="secondary" disabled={pending} type="submit">Изменить решение</button>
          </form>
          <form className="stack" onSubmit={(event) => { event.preventDefault(); send("/request-info", { question }); }}>
            <label>Вопрос клиенту<textarea value={question} onChange={(event) => setQuestion(event.target.value)} required /></label>
            <button className="secondary" disabled={pending} type="submit">Запросить уточнение</button>
          </form>
        </aside>
      </section>
      <section className="stack">
        {application.checks?.map((check) => (
          <article key={check.id} className="panel stack">
            <h2>{sourceTitle(check.source)} · {check.status === "SUCCESS" ? "ответ получен" : "сбой"}</h2>
            <pre>{JSON.stringify(check.response, null, 2)}</pre>
          </article>
        ))}
      </section>
      <section className="panel">
        <h2>Журнал и расчёты</h2>
        <ul className="journal">
          {application.events.map((event) => (
            <li key={event.id}><time dateTime={event.created_at}>{when(event.created_at)}</time><span>{event.message}</span></li>
          ))}
        </ul>
        {application.scores && application.scores.length > 1 && (
          <p className="muted">Расчётов в истории: {application.scores.length}. Старые не удаляются.</p>
        )}
      </section>
    </main>
  );
}

function sourceTitle(source: string) {
  if (source === "EGRUL") return "ЕГРЮЛ / ЕГРИП";
  if (source === "BKI") return "БКИ, синтетическая история";
  if (source === "FNS") return "ФНС «Прозрачный бизнес»";
  return source;
}
