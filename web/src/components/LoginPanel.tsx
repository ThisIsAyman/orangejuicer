import { useState } from "react";
import { login } from "../otf/auth";

interface Props {
  onLoggedIn: () => void;
}

/** Email/password sign-in that runs Cognito SRP entirely in the browser. */
export default function LoginPanel({ onLoggedIn }: Props) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      onLoggedIn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form className="login-panel" onSubmit={handleSubmit}>
      <h3>Sign in to OrangeTheory</h3>
      <p className="login-hint">
        Your credentials are sent directly to OrangeTheory and never stored on any server.
        Only your login session is kept in this browser.
      </p>
      <label>
        Email
        <input
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
      </label>
      <label>
        Password
        <input
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </label>
      {error && <p className="login-error">{error}</p>}
      <button type="submit" className="btn-primary" disabled={busy}>
        {busy ? "Signing in…" : "Sign in"}
      </button>
    </form>
  );
}
