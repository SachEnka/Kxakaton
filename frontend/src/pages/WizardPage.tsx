import { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, loadUser, type Application, type ProductCard } from "../api";
import {
  annuityPayment,
  burdenFit,
  day,
  money,
  PRESETS,
  PURPOSE_RATES,
  PURPOSES,
  rate,
  type RegistryCard,
} from "../format";

export function WizardPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const preset = PRESETS[loadUser()?.email || ""];
  const [step, setStep] = useState(1);
  const [purpose, setPurpose] = useState(preset?.purpose || "TURNOVER");
  const [amount, setAmount] = useState(preset?.amount || 1500000);
  const [term, setTerm] = useState(preset?.term || 18);
  const [cards, setCards] = useState<{ primary: ProductCard; alternative: ProductCard | null } | null>(null);
  const [draftId, setDraftId] = useState(params.get("draft") || "");
  const [inn, setInn] = useState(preset?.inn || "");
  const [legalForm, setLegalForm] = useState<"OOO" | "IP">(preset?.legalForm || "OOO");
  const [revenue, setRevenue] = useState(preset?.revenue || 0);
  const [expenses, setExpenses] = useState(preset?.expenses || 0);
  const [comment, setComment] = useState("");
  const [productCode, setProductCode] = useState(preset?.purpose || "TURNOVER");
  const [registry, setRegistry] = useState<RegistryCard | null>(null);
  const [registryError, setRegistryError] = useState("");
  const [registryLoading, setRegistryLoading] = useState(false);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [draftState, setDraftState] = useState<"idle" | "saving" | "saved">("idle");
  const skipDraftLoad = useRef(false);

  useEffect(() => {
    const id = params.get("draft");
    if (!id) return;
    if (skipDraftLoad.current) {
      skipDraftLoad.current = false;
      return;
    }
    let active = true;
    api<Application>(`/api/applications/${id}`)
      .then((application) => {
        if (!active) return;
        if (application.status !== "DRAFT") {
          navigate(`/app/applications/${id}`);
          return;
        }
        setDraftId(id);
        setStep(3);
        setAmount(application.amount);
        setTerm(application.term_months);
        setProductCode(application.product_code);
        setInn(application.company.inn || "");
        setLegalForm(application.company.legal_form === "IP" ? "IP" : "OOO");
        setRevenue(application.monthly_revenue || 0);
        setExpenses(application.monthly_expenses || 0);
        setComment(application.comment || "");
      })
      .catch((reason) => {
        if (active) setError(reason instanceof Error ? reason.message : "Черновик не открылся");
      });
    return () => {
      active = false;
    };
  }, [navigate, params]);

  useEffect(() => {
    if (step !== 3 || (inn.length !== 10 && inn.length !== 12)) {
      setRegistry(null);
      setRegistryError("");
      setRegistryLoading(false);
      return;
    }
    let active = true;
    setRegistryLoading(true);
    setRegistryError("");
    const timer = window.setTimeout(() => {
      api<RegistryCard>(`/api/registry/${inn}`)
        .then((card) => {
          if (!active) return;
          setRegistry(card);
          setLegalForm(card.legal_form);
        })
        .catch((reason) => {
          if (!active) return;
          setRegistry(null);
          setRegistryError(reason instanceof Error ? reason.message : "Не удалось получить сведения из ЕГРЮЛ");
        })
        .finally(() => {
          if (active) setRegistryLoading(false);
        });
    }, 400);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [inn, step]);

  useEffect(() => {
    if (step !== 3 || !draftId || pending) return;
    let active = true;
    setDraftState("saving");
    const timer = window.setTimeout(() => {
      api(`/api/applications/${draftId}`, {
        method: "PATCH",
        body: JSON.stringify({
          inn,
          legal_form: legalForm,
          amount,
          term_months: term,
          monthly_revenue: revenue,
          monthly_expenses: expenses,
          comment,
        }),
      })
        .then(() => {
          if (active) setDraftState("saved");
        })
        .catch(() => {
          if (active) setDraftState("idle");
        });
    }, 700);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [step, draftId, inn, legalForm, amount, term, revenue, expenses, comment, pending]);

  const simRate = useMemo(() => {
    if (cards) {
      const chosen = [cards.primary, cards.alternative].find((item) => item?.code === productCode);
      if (chosen) return chosen.base_rate;
    }
    const byProduct: Record<string, number> = { TURNOVER: 20, DEVELOPMENT: 18, OVERDRAFT: 22, LINE: 19 };
    return byProduct[productCode] ?? PURPOSE_RATES[purpose]?.rate ?? 20;
  }, [cards, productCode, purpose]);

  const payment = useMemo(() => annuityPayment(amount, simRate, term), [amount, simRate, term]);
  const fit = useMemo(() => burdenFit(payment, revenue || preset?.revenue), [payment, revenue, preset]);

  async function recommend(event: FormEvent) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const result = await api<{ primary: ProductCard; alternative: ProductCard | null }>("/api/applications/recommend", {
        method: "POST",
        body: JSON.stringify({ purpose, amount, term_months: term }),
      });
      setCards(result);
      setStep(2);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось подобрать продукт");
    } finally {
      setPending(false);
    }
  }

  async function choose(card: ProductCard) {
    setPending(true);
    setError("");
    try {
      const draft = await api<Application>("/api/applications", {
        method: "POST",
        body: JSON.stringify({
          purpose,
          product_code: card.code,
          amount: card.fits ? amount : card.suggested_amount,
          term_months: card.fits ? term : card.suggested_term,
        }),
      });
      setDraftId(draft.id);
      setProductCode(card.code);
      setAmount(card.fits ? amount : card.suggested_amount);
      setTerm(card.fits ? term : card.suggested_term);
      skipDraftLoad.current = true;
      setParams({ draft: draft.id });
      setStep(3);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось создать заявку");
    } finally {
      setPending(false);
    }
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!draftId) return;
    setPending(true);
    setError("");
    try {
      await api(`/api/applications/${draftId}`, {
        method: "PATCH",
        body: JSON.stringify({
          inn,
          legal_form: legalForm,
          amount,
          term_months: term,
          monthly_revenue: revenue,
          monthly_expenses: expenses,
          comment,
        }),
      });
      await api(`/api/applications/${draftId}/submit`, { method: "POST" });
      navigate(`/app/applications/${draftId}`);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось отправить заявку");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="page stack">
      <div>
        <p className="muted">Шаг {step} из 3</p>
        <h1>{step === 1 ? "Зачем нужны деньги" : step === 2 ? "Подходящий продукт" : "Данные для заявки"}</h1>
      </div>
      {preset && step === 1 && <p className="note">Для этой учётки подготовлен сценарий: {preset.title}. Поля уже заполнены.</p>}
      {error && <p className="alert" role="alert">{error}</p>}

      {step === 1 && (
        <form className="panel stack" onSubmit={recommend}>
          <div className="choices">
            {PURPOSES.map((item) => (
              <button key={item.code} type="button" className={purpose === item.code ? "choice active" : "choice"} onClick={() => setPurpose(item.code)}>
                <strong>{item.title}</strong>
                <small>{item.text}</small>
              </button>
            ))}
          </div>
          <div className="grid-2">
            <label>Сумма, ₽<input type="number" min={1} value={amount} onChange={(event) => setAmount(Number(event.target.value))} required /></label>
            <label>Срок, месяцев<input type="number" min={1} max={120} value={term} onChange={(event) => setTerm(Number(event.target.value))} required /></label>
          </div>
          <ConditionsSimulator
            payment={payment}
            rateValue={simRate}
            fitClass={`fit-${fit.level}`}
            fitLabel={fit.label}
            hint={`Ориентир по ставке ${rate(simRate)} для ${PURPOSE_RATES[purpose]?.label || "продукта"}. Точные условия появятся после проверок.`}
          />
          <button className="primary" type="submit" disabled={pending}>Подобрать продукт</button>
        </form>
      )}

      {step === 2 && cards && (
        <div className="stack">
          {[cards.primary, cards.alternative].filter((item): item is ProductCard => item !== null).map((card) => (
            <article key={card.code} className={card.recommended ? "card recommended stack" : "card stack"}>
              <div className="row" style={{ justifyContent: "space-between" }}>
                <h2>{card.title}</h2>
                {card.recommended && <span className="badge wait">Рекомендуем</span>}
              </div>
              <p>{card.reason}</p>
              <p className="muted">
                {money(card.min_amount)} – {money(card.max_amount)}, {card.min_term}–{card.max_term} мес., ставка от {rate(card.base_rate)}
                {" · "}
                платёж ≈ {money(annuityPayment(card.fits ? amount : card.suggested_amount, card.base_rate, card.fits ? term : card.suggested_term))}
              </p>
              {!card.fits && (
                <p className="note">
                  Сумма или срок вне коридора. Ближайшие допустимые значения: {money(card.suggested_amount)} на {card.suggested_term} мес.
                </p>
              )}
              <div className="row">
                <button className="primary" type="button" disabled={!card.fits || pending} onClick={() => choose(card)}>Оформить заявку</button>
                {!card.fits && (
                  <button
                    className="secondary"
                    type="button"
                    onClick={() => {
                      setAmount(card.suggested_amount);
                      setTerm(card.suggested_term);
                      setCards(null);
                      setStep(1);
                    }}
                  >
                    Подставить допустимые параметры
                  </button>
                )}
              </div>
            </article>
          ))}
          <button className="text-button" type="button" onClick={() => setStep(1)}>Изменить цель</button>
        </div>
      )}

      {step === 3 && (
        <form className="panel stack" onSubmit={submit}>
          <p className="muted">Контактное лицо — {loadUser()?.full_name}. Повторно его вводить не нужно. Продукт: {productCode}.</p>
          <div className="grid-2">
            <label>Сумма, ₽<input type="number" min={1} value={amount} onChange={(event) => setAmount(Number(event.target.value))} required /></label>
            <label>Срок, месяцев<input type="number" min={1} max={120} value={term} onChange={(event) => setTerm(Number(event.target.value))} required /></label>
            <label>
              ИНН
              <input
                value={inn}
                onChange={(event) => setInn(event.target.value.replace(/\D/g, "").slice(0, 12))}
                inputMode="numeric"
                required
              />
            </label>
            <label>
              Форма
              <select value={legalForm} onChange={(event) => setLegalForm(event.target.value as "OOO" | "IP")}>
                <option value="OOO">ООО</option>
                <option value="IP">ИП</option>
              </select>
            </label>
            <label>Выручка в месяц, ₽<input type="number" min={0} value={revenue} onChange={(event) => setRevenue(Number(event.target.value))} required /></label>
            <label>Расходы в месяц, ₽<input type="number" min={0} value={expenses} onChange={(event) => setExpenses(Number(event.target.value))} required /></label>
          </div>
          <ConditionsSimulator
            payment={payment}
            rateValue={simRate}
            fitClass={`fit-${fit.level}`}
            fitLabel={fit.label}
            hint="Меняйте сумму и срок — платёж и оценка нагрузки обновляются сразу. После отправки банк проверит данные и может предложить другие условия."
          />
          {registryLoading && <p className="muted">Ищем организацию в ЕГРЮЛ и «Прозрачном бизнесе»…</p>}
          {registryError && <p className="alert" role="alert">{registryError}</p>}
          {registry && (
            <section className="note stack">
              <strong>{registry.short_name || registry.full_name}</strong>
              <p>{registry.full_name}</p>
              <p>ОГРН {registry.ogrn || "—"}{registry.kpp ? ` · КПП ${registry.kpp}` : ""}</p>
              <p>Руководитель: {registry.director_post || registry.director_name || "—"}</p>
              <p>{registry.address || registry.region || "Адрес не опубликован"} · зарегистрирована {day(registry.registration_date)} · {registry.status_label}</p>
              <p className="muted">{registry.source_label}</p>
              {registry.transparent && (
                <>
                  <p>ОКВЭД: {registry.transparent.okved || "не опубликован"}</p>
                  <p>
                    Уставный капитал: {registry.transparent.charter_capital ? money(registry.transparent.charter_capital) : "не опубликован"}
                    {" · "}
                    сотрудники: {registry.transparent.employees_published ? registry.transparent.employees_count : "ФНС не публикует"}
                  </p>
                  <p>
                    Налоговый режим: {registry.transparent.tax_regime || "не опубликован"}
                    {" · "}
                    недоимка: {registry.transparent.tax_debt ? money(registry.transparent.tax_debt_amount) : "на карточке не опубликована"}
                  </p>
                  {!!registry.transparent.mass_address_count && (
                    <p>По адресу сервис показывает связанных организаций: {registry.transparent.mass_address_count}.</p>
                  )}
                  <p className="muted">{registry.transparent.note}</p>
                </>
              )}
              {registry.transparent_error && <p>{registry.transparent_error}</p>}
              {registry.credit_history && <p className="muted">{registry.credit_history.note}</p>}
            </section>
          )}
          <label>Комментарий<textarea value={comment} onChange={(event) => setComment(event.target.value)} /></label>
          <p className="muted">Демо-ИНН остаются учебными: 7700000001–7700000005. Любой другой ИНН запрашивается в ЕГРЮЛ и «Прозрачном бизнесе». Кредитное бюро по ИНН не открыто.</p>
          <p className="muted">
            {draftState === "saving" ? "Сохраняем черновик…" : draftState === "saved" ? "Черновик сохранён. Можно закрыть страницу и вернуться." : "Черновик сохранится сам, когда поля заполнены."}
          </p>
          <button className="primary" type="submit" disabled={pending || registryLoading || !registry}>
            {pending ? "Отправляем…" : "Отправить заявку"}
          </button>
        </form>
      )}
    </main>
  );
}

function ConditionsSimulator({
  payment,
  rateValue,
  fitClass,
  fitLabel,
  hint,
}: {
  payment: number;
  rateValue: number;
  fitClass: string;
  fitLabel: string;
  hint: string;
}) {
  return (
    <section className="simulator" aria-live="polite">
      <div className="simulator-head">
        <div>
          <p className="muted">Ориентировочный платёж</p>
          <strong>{money(payment)}</strong>
          <span className="muted"> / мес. · ставка {rate(rateValue)}</span>
        </div>
        <p className={fitClass}>{fitLabel}</p>
      </div>
      <p className="muted">{hint}</p>
    </section>
  );
}
