import { type FormEvent, useState } from "react";
import { ApiError, ask } from "./api";
import { AnswerView } from "./AnswerView";
import type { Answer } from "./types";

const TOKEN_KEY = "offline.token";

function readToken(): string {
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? "";
  } catch {
    return "";
  }
}

function saveToken(token: string): void {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, token);
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    // Storage can be disabled. The token then lives only in memory for this tab.
  }
}

function SignIn({ onToken }: { onToken: (token: string) => void }) {
  const [value, setValue] = useState("");
  function submit(event: FormEvent) {
    event.preventDefault();
    if (value.trim()) onToken(value.trim());
  }
  return (
    <form className="card" onSubmit={submit}>
      <label htmlFor="token">Access token</label>
      <input
        id="token"
        type="password"
        autoComplete="off"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <button type="submit">Sign in</button>
      <p className="hint">Ask your admin for a token. It is kept only for this browser tab.</p>
    </form>
  );
}

export function App() {
  const [token, setToken] = useState(readToken);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  function updateToken(next: string) {
    saveToken(next);
    setToken(next);
    setAnswer(null);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (question.trim().length < 3) return;
    setBusy(true);
    setError("");
    setAnswer(null);
    try {
      setAnswer(await ask(question.trim(), token));
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) updateToken("");
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <header>
        <h1>Offline</h1>
        <p>Answers from public federal regulations, with a citation for every claim.</p>
      </header>
      {!token ? (
        <SignIn onToken={updateToken} />
      ) : (
        <>
          <form className="card" onSubmit={submit}>
            <label htmlFor="question">Question</label>
            <textarea
              id="question"
              rows={3}
              maxLength={1000}
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What is the simplified acquisition threshold?"
            />
            <div className="row">
              <button type="submit" disabled={busy}>
                {busy ? "Searching" : "Ask"}
              </button>
              <button type="button" className="quiet" onClick={() => updateToken("")}>
                Sign out
              </button>
            </div>
          </form>
          <section aria-live="polite">
            {error && <p className="notice warn">{error}</p>}
            {answer && <AnswerView answer={answer} />}
          </section>
        </>
      )}
    </main>
  );
}
