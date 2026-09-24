import React, { useState } from "react";

// ── Credentials — change these as needed ──────────────────────
const DEMO_EMAIL    = "demo@annualedge.com";
const DEMO_PASSWORD = "Demo@2025";
const DEMO_MAX_USES = 2;

const ADMIN_EMAIL    = "admin@annualedge.com";
const ADMIN_PASSWORD = "Edge@Admin25";
// ─────────────────────────────────────────────────────────────

const LS_USES_KEY = "ae-demo-uses";

function getDemoUses() {
  return parseInt(localStorage.getItem(LS_USES_KEY) || "0", 10);
}

export default function Login({ onLogin }) {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd]   = useState(false);
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  const demoUses    = getDemoUses();
  const demoBlocked = demoUses >= DEMO_MAX_USES;

  const handleSubmit = (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    // Small delay for UX feel
    setTimeout(() => {
      const em = email.trim().toLowerCase();

      // Admin — unlimited
      if (em === ADMIN_EMAIL.toLowerCase() && password === ADMIN_PASSWORD) {
        onLogin({ role: "admin", email: em });
        return;
      }

      // Demo — limited uses
      if (em === DEMO_EMAIL.toLowerCase() && password === DEMO_PASSWORD) {
        const uses = getDemoUses();
        if (uses >= DEMO_MAX_USES) {
          setError("Demo access exhausted. Contact the administrator for full access.");
          setLoading(false);
          return;
        }
        localStorage.setItem(LS_USES_KEY, String(uses + 1));
        onLogin({ role: "demo", usesLeft: DEMO_MAX_USES - uses - 1, email: em });
        return;
      }

      setError("Incorrect email or password.");
      setLoading(false);
    }, 500);
  };

  return (
    <div className="login-screen">
      <div className="login-card">

        {/* Brand */}
        <div className="login-brand">
          <span className="login-mark">AE</span>
          <h1 className="login-title">AnnualEdge</h1>
          <p className="login-sub">Financial Intelligence Platform</p>
        </div>

        {/* Form */}
        <form className="login-form" onSubmit={handleSubmit} noValidate>
          <div className="login-field">
            <label className="login-label" htmlFor="login-email">Email</label>
            <input
              id="login-email"
              type="email"
              className="login-input"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoFocus
              required
            />
          </div>

          <div className="login-field">
            <label className="login-label" htmlFor="login-password">Password</label>
            <div className="login-pwd-wrap">
              <input
                id="login-password"
                type={showPwd ? "text" : "password"}
                className="login-input"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="login-eye"
                onClick={() => setShowPwd((v) => !v)}
                aria-label={showPwd ? "Hide password" : "Show password"}
              >
                {showPwd ? (
                  <svg viewBox="0 0 20 20" fill="none" width="16" height="16">
                    <path d="M3 3l14 14M8.5 8.6A3 3 0 0 0 10 13a3 3 0 0 0 2.9-2.3M6.5 6.6C4.8 7.7 3.5 9 3 10c1.3 3 4 5 7 5a8 8 0 0 0 3.5-.8M10 5c3 0 5.7 2 7 5a9 9 0 0 1-1.5 2.3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                  </svg>
                ) : (
                  <svg viewBox="0 0 20 20" fill="none" width="16" height="16">
                    <ellipse cx="10" cy="10" rx="7" ry="4.5" stroke="currentColor" strokeWidth="1.5"/>
                    <circle cx="10" cy="10" r="2" fill="currentColor"/>
                  </svg>
                )}
              </button>
            </div>
          </div>

          {error && (
            <div className="login-error">
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14" style={{ flexShrink: 0 }}>
                <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/>
                <path d="M8 5v3.5M8 11h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              {error}
            </div>
          )}

          <button
            type="submit"
            className="login-btn"
            disabled={loading || !email.trim() || !password}
          >
            {loading ? (
              <span className="login-spinner" />
            ) : (
              "Sign in"
            )}
          </button>
        </form>

        {/* Demo access info */}
        <div className="login-footer">
          {demoBlocked ? (
            <span className="login-uses exhausted">
              <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
                <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/>
                <path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              Demo access exhausted
            </span>
          ) : (
            <span className="login-uses">
              <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
                <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/>
                <path d="M8 5v3l2 2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              Demo access · {DEMO_MAX_USES - demoUses} use{DEMO_MAX_USES - demoUses > 1 ? "s" : ""} remaining
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
