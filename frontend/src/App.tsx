import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { FormEvent, useState } from "react";
import { api, clearSession, loadUser, saveSession, type User } from "./api";
import { DEMO_ACCOUNTS } from "./format";
import { ApplicationPage } from "./pages/ApplicationPage";
import { CasePage } from "./pages/CasePage";
import { ClientHome } from "./pages/ClientHome";
import { DeskPage } from "./pages/DeskPage";
import { Shell } from "./pages/Shell";
import { WizardPage } from "./pages/WizardPage";

export function App() {
  const [user, setUser] = useState<User | null>(() => loadUser());

  function enter(next: User, token: string) {
    saveSession(token, next);
    setUser(next);
  }

  function leave() {
    clearSession();
    setUser(null);
  }

  return (
    <Routes>
      <Route path="/login" element={<Login onEnter={enter} />} />
      <Route path="/register" element={<Register onEnter={enter} />} />
      <Route
        path="/app"
        element={
          <Guard user={user} role="CLIENT">
            <Shell user={user!} onLeave={leave} />
          </Guard>
        }
      >
        <Route index element={<ClientHome />} />
        <Route path="new" element={<WizardPage />} />
        <Route path="applications/:id" element={<ApplicationPage />} />
      </Route>
      <Route
        path="/desk"
        element={
          <Guard user={user} role="UNDERWRITER">
            <Shell user={user!} onLeave={leave} />
          </Guard>
        }
      >
        <Route index element={<DeskPage />} />
        <Route path=":id" element={<CasePage />} />
      </Route>
      <Route path="*" element={<Navigate to={user?.role === "UNDERWRITER" ? "/desk" : user ? "/app" : "/login"} replace />} />
    </Routes>
  );
}

function Guard({ user, role, children }: { user: User | null; role: User["role"]; children: JSX.Element }) {
  if (!user) return <Navigate to="/login" replace />;
  if (user.role !== role) return <Navigate to={user.role === "UNDERWRITER" ? "/desk" : "/app"} replace />;
  return children;
}

function Login({ onEnter }: { onEnter: (user: User, token: string) => void }) {
  const navigate = useNavigate();
  const [email, setEmail] = useState("client.good@demo.local");
  const [password, setPassword] = useState("Demo-2026");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event?: FormEvent, nextEmail = email) {
    event?.preventDefault();
    setPending(true);
    setError("");
    try {
      const result = await api<{ access_token: string; user: User }>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email: nextEmail, password }),
      });
      onEnter(result.user, result.access_token);
      navigate(result.user.role === "UNDERWRITER" ? "/desk" : "/app");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось войти");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="page login-layout">
      <section className="hero">
        <p className="muted">Кредит для малого и микробизнеса</p>
        <h1>От потребности до решения в одном кабинете</h1>
        <p className="lead">
          Предприниматель выбирает продукт и видит, что происходит с заявкой. Сотрудник банка видит проверки, оценку риска и может изменить решение.
        </p>
      </section>
      <section className="panel stack">
        <h2>Вход</h2>
        <form className="stack" onSubmit={(event) => submit(event)}>
          <label>
            Email
            <input value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="username" />
          </label>
          <label>
            Пароль
            <input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" />
          </label>
          {error && <p className="alert" role="alert">{error}</p>}
          <button className="primary" disabled={pending} type="submit">{pending ? "Входим…" : "Войти"}</button>
        </form>
        <p className="muted">Демо-пароль для всех учёток: Demo-2026</p>
        <div className="stack">
          {DEMO_ACCOUNTS.map((account) => (
            <button
              key={account.email}
              className="account"
              type="button"
              onClick={() => {
                setEmail(account.email);
                submit(undefined, account.email);
              }}
            >
              {account.title}
              <small>{account.email}</small>
            </button>
          ))}
        </div>
        <a href="/register">Создать свой вход клиента</a>
      </section>
    </main>
  );
}

function Register({ onEnter }: { onEnter: (user: User, token: string) => void }) {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "", full_name: "", phone: "" });
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError("");
    try {
      const result = await api<{ access_token: string; user: User }>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify(form),
      });
      onEnter(result.user, result.access_token);
      navigate("/app");
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Не удалось зарегистрироваться");
    }
  }

  return (
    <main className="page narrow">
      <form className="panel stack" onSubmit={submit}>
        <h1>Регистрация</h1>
        <label>ФИО<input value={form.full_name} onChange={(event) => setForm({ ...form, full_name: event.target.value })} required /></label>
        <label>Телефон<input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} /></label>
        <label>Email<input type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} required /></label>
        <label>Пароль<input type="password" minLength={8} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} required /></label>
        {error && <p className="alert" role="alert">{error}</p>}
        <button className="primary" type="submit">Создать кабинет</button>
        <a href="/login">Уже есть вход</a>
      </form>
    </main>
  );
}
