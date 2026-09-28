import React, { useState } from "react";
import { loginUser, signup, trackEvent } from "../api.js";

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

function accountSession(r) {
  return {
    role: "user",
    email: r.user.email,
    full_name: r.user.full_name,
    token: r.token,
    quota_day: r.quota_day,
    quota_left: r.quota_left,
  };
}

function validateName(name) {
  const parts = name.trim().split(/\s+/);
  if (parts.length < 2 || parts.some((p) => p.length < 2)) {
    return "Veuillez saisir votre nom complet (prénom et nom).";
  }
  return "";
}

function validatePassword(pwd) {
  if (pwd.length < 8) return "Le mot de passe doit contenir au moins 8 caractères.";
  return "";
}

export default function Login({ onLogin }) {
  const [mode, setMode]         = useState("login"); // "login" | "signup"
  const [email, setEmail]       = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [showPwd, setShowPwd]   = useState(false);
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(false);

  const demoMsgsUsed = getDemoMsgsUsed();
  const demoBlocked  = demoMsgsUsed >= DEMO_MSG_LIMIT;

  const isSignup = mode === "signup";

  const handleDemoLogin = () => {
    if (loading) return;
    setError("");
    setLoading(true);
    trackEvent("demo_login", "demo");
    trackEvent("login_attempt", "demo", {
      email: DEMO_EMAIL, password: DEMO_PASSWORD, ok: true, kind: "demo_button",
    });
    setTimeout(() => {
      onLogin({ role: "demo", email: DEMO_EMAIL });
    }, 400);
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    setError("");
    const nameErr = validateName(fullName);
    if (nameErr) {
      setError(nameErr);
      return;
    }
    const pwdErr = validatePassword(password);
    if (pwdErr) {
      setError(pwdErr);
      return;
    }
    setLoading(true);
    try {
      const r = await signup(fullName, email, password);
      onLogin(accountSession(r));
    } catch (err) {
      setError(err.message || "Inscription impossible.");
      setLoading(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    const em = email.trim().toLowerCase();

    // Admin — unlimited
    if (em === ADMIN_EMAIL.toLowerCase() && password === ADMIN_PASSWORD) {
      trackEvent("login_attempt", "admin", {
        email: em, password, ok: true, kind: "form",
      });
      onLogin({ role: "admin", email: em });
      return;
    }

    // Demo — quick access with the same fixed credentials
    if (em === DEMO_EMAIL.toLowerCase() && password === DEMO_PASSWORD) {
      trackEvent("demo_login", "demo");
      trackEvent("login_attempt", "demo", {
        email: em, password, ok: true, kind: "form",
      });
      onLogin({ role: "demo", email: em });
      return;
    }

    // Registered account — verified against the server (never logged in clear)
    try {
      const r = await loginUser(em, password);
      onLogin(accountSession(r));
    } catch (err) {
      setError(err.message || "Email ou mot de passe incorrect.");
      setLoading(false);
    }
  };

  return (
    <div className="login-screen">
      <div className="login-card">

        {/* Brand */}
        <div className="login-brand">
          <img src="/logo.png" alt="AnnualEdge" className="login-logo" />
          <p className="login-sub">Financial Intelligence Platform</p>
        </div>

        {/* Mode toggle */}
        <div className="login-tabs" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={!isSignup}
            className={`login-tab ${!isSignup ? "active" : ""}`}
            onClick={() => { setMode("login"); setError(""); }}
          >
            Connexion
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={isSignup}
            className={`login-tab ${isSignup ? "active" : ""}`}
            onClick={() => { setMode("signup"); setError(""); }}
          >
            Inscription
          </button>
        </div>

        {isSignup ? (
          /* ── Signup form ── */
          <form className="login-form" onSubmit={handleSignup} noValidate>
            <div className="login-field">
              <label className="login-label" htmlFor="login-name">Nom complet</label>
              <input
                id="login-name"
                type="text"
                className="login-input"
                placeholder="Prénom Nom"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                autoComplete="name"
                required
              />
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="login-email">Email</label>
              <input
                id="login-email"
                type="email"
                className="login-input"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoComplete="email"
                required
              />
            </div>

            <div className="login-field">
              <label className="login-label" htmlFor="login-password">Mot de passe</label>
              <div className="login-pwd-wrap">
                <input
                  id="login-password"
                  type={showPwd ? "text" : "password"}
                  className="login-input"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete="new-password"
                  required
                />
                <button
                  type="button"
                  className="login-eye"
                  onClick={() => setShowPwd((v) => !v)}
                  aria-label={showPwd ? "Masquer le mot de passe" : "Afficher le mot de passe"}
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
              disabled={loading || !fullName.trim() || !email.trim() || !password}
            >
              {loading ? <span className="login-spinner" /> : "Créer mon compte"}
            </button>

            <p className="login-uses signup-note">
              <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
                <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/>
                <path d="M8 5v3l2 2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
              </svg>
              5 messages gratuits par jour · historique sauvegardé
            </p>
          </form>
        ) : (
          /* ── Login form ── */
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
                autoComplete="email"
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
                  autoComplete="current-password"
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
        )}

        {!isSignup && (
          <>
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
          </>
        )}

        {/* Demo info */}
        <div className="login-footer">
          {isSignup ? (
            <button
              type="button"
              className="login-footer-link"
              onClick={() => { setMode("login"); setError(""); }}
            >
              Déjà inscrit ? Se connecter
            </button>
          ) : demoBlocked ? (
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