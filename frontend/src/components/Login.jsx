import React, { useState } from "react";
import { trackEvent } from "../api.js";

// ── Credentials — change these as needed ──────────────────────
const DEMO_EMAIL    = "demo@annualedge.com";
const DEMO_PASSWORD = "Demo@2025";

const ADMIN_EMAIL    = "admin@annualedge.com";
const ADMIN_PASSWORD = "Edge@Admin25";
// ─────────────────────────────────────────────────────────────

const DEMO_MSG_KEY   = "ae-demo-msgs";
const DEMO_MSG_LIMIT = 5;

function getDemoMsgsUsed() {
  return parseInt(localStorage.getItem(DEMO_MSG_KEY) || "0", 10);
}

export default function Login({ onLogin }) {
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd]   = useState(false);
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  const demoMsgsUsed = getDemoMsgsUsed();
  const demoBlocked  = demoMsgsUsed >= DEMO_MSG_LIMIT;

  const handleDemoLogin = () => {
    if (loading) return;
    setError("");
    setLoading(true);
    trackEvent("demo_login");
    setTimeout(() => {
      onLogin({ role: "demo", email: DEMO_EMAIL });
    }, 400);
  };

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

      // Demo
      if (em === DEMO_EMAIL.toLowerCase() && password === DEMO_PASSWORD) {
        onLogin({ role: "demo", email: em });
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

        {/* Divider */}
        <div className="login-divider">
          <span>or</span>
        </div>

        {/* Demo quick access */}
        <button
          type="button"
          className="login-demo-btn"
          onClick={handleDemoLogin}
          disabled={loading}
          title={demoBlocked ? "Demo messages exhausted" : `${DEMO_MSG_LIMIT - demoMsgsUsed} free message${DEMO_MSG_LIMIT - demoMsgsUsed > 1 ? "s" : ""} remaining`}
        >
          {loading ? (
            <span className="login-spinner login-spinner-dark" />
          ) : demoBlocked ? (
            <>
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M2 4h12M2 8h8M2 12h6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              Continue — Browse &amp; PDF only
            </>
          ) : (
            <>
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <circle cx="8" cy="5" r="3" stroke="currentColor" strokeWidth="1.4"/>
                <path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              Demo Account
              <span className="login-demo-badge">
                {DEMO_MSG_LIMIT - demoMsgsUsed} chat free
              </span>
            </>
          )}
        </button>

        {/* Demo info */}
        <div className="login-footer">
          {demoBlocked ? (
            <span className="login-uses exhausted">
              <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
                <rect x="3" y="7.5" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
                <path d="M5.5 7.5V5a2.5 2.5 0 0 1 5 0v2.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
              </svg>
              Demo messages exhausted — contact admin
            </span>
          ) : (
            <span className="login-uses">
              <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
                <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/>
                <path d="M8 5v3l2 2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              {DEMO_MSG_LIMIT - demoMsgsUsed} free message{DEMO_MSG_LIMIT - demoMsgsUsed > 1 ? "s" : ""} remaining
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
