import { type FormEvent, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "./auth";
import { Brand, Field } from "./components";

type Mode = "sign-in" | "create";

export function AuthPage() {
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mode, setMode] = useState<Mode>("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const returnTo = typeof location.state === "object" && location.state
    && "returnTo" in location.state && typeof location.state.returnTo === "string"
    ? location.state.returnTo : "/overview";

  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError(null); setNotice(null);
    try {
      if (mode === "sign-in") {
        await auth.signIn(email.trim(), password);
        navigate(returnTo, { replace: true });
      } else {
        const confirmationRequired = await auth.signUp(email.trim(), password);
        if (confirmationRequired) setNotice("Check your email to confirm the account, then sign in.");
        else navigate(returnTo, { replace: true });
      }
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Authentication failed.");
    } finally { setBusy(false); }
  }

  async function guest() {
    setBusy(true); setError(null);
    try { await auth.continueAsGuest(); navigate(returnTo, { replace: true }); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "Guest sign-in failed."); }
    finally { setBusy(false); }
  }

  return (
    <main className="auth-page">
      <section className="auth-card" aria-labelledby="auth-title">
        <Brand />
        <p className="page-eyebrow">SECURE WORKSPACE ACCESS</p>
        <h1 id="auth-title">{mode === "sign-in" ? "Sign in to WindSight" : "Create your account"}</h1>
        <p>Analytics remain public. An account is only required to save and manage analysis configurations.</p>
        {!auth.configured && <div className="inline-alert" role="alert">Supabase authentication is not configured for this environment.</div>}
        <form onSubmit={submit} className="auth-form">
          <Field id="auth-email" label="Email">
            <input id="auth-email" type="email" autoComplete="email" required value={email} onChange={(event) => setEmail(event.target.value)} />
          </Field>
          <Field id="auth-password" label="Password">
            <input id="auth-password" type="password" autoComplete={mode === "sign-in" ? "current-password" : "new-password"} minLength={6} required value={password} onChange={(event) => setPassword(event.target.value)} />
          </Field>
          {error && <div className="inline-alert" role="alert">{error}</div>}
          {notice && <div className="inline-notice" role="status">{notice}</div>}
          <button className="primary-button" disabled={busy || !auth.configured} type="submit">{busy ? "Please wait…" : mode === "sign-in" ? "Sign in" : "Create account"}</button>
        </form>
        <button className="secondary-button auth-guest" disabled={busy || !auth.configured} onClick={() => void guest()}>Continue as Guest</button>
        <button className="text-button" disabled={busy} onClick={() => { setMode(mode === "sign-in" ? "create" : "sign-in"); setError(null); setNotice(null); }}>
          {mode === "sign-in" ? "Need an account? Create one" : "Already have an account? Sign in"}
        </button>
        <Link to={returnTo}>Return to public analytics</Link>
      </section>
    </main>
  );
}
