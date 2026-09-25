import React, { useEffect, useRef, useState } from "react";
import { sendChatStream } from "../api.js";
import Markdown from "./Markdown.jsx";

const LS_KEY       = "ammc-qa-history";
const MAX_HISTORY  = 20;
const DEMO_MSG_KEY   = "ae-demo-msgs";
const DEMO_MSG_LIMIT = 2;

function getDemoMsgsUsed() {
  return parseInt(localStorage.getItem(DEMO_MSG_KEY) || "0", 10);
}

const SUGGESTIONS_DEFAULT = [
  "Quel est le résultat net de l'exercice ?",
  "Quels sont les principaux actionnaires ?",
  "Quel est le total du bilan ?",
  "Quelle est la stratégie de développement ?",
];

const SUGGESTIONS_BANK = [
  "Quel est le produit net bancaire ?",
  "Quels sont les principaux actionnaires ?",
  "Quel est le coefficient d'exploitation ?",
  "Quelles sont les perspectives de croissance ?",
];

function useAutoGrow() {
  const ref = useRef(null);
  const grow = () => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  };
  return [ref, grow];
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export default function ChatPanel({ company, companyName, year, sector, onOpenSource, isDemo }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [textRef, grow] = useAutoGrow();
  const bottomRef = useRef(null);
  const streamIdxRef = useRef(null);
  const [demoMsgsUsed, setDemoMsgsUsed] = useState(getDemoMsgsUsed);

  // Persistent Q&A history — survives new sessions and company/year changes
  const [qaHistory, setQaHistory] = useState(loadHistory);
  const [showHistory, setShowHistory] = useState(false);
  const [expandedIdx, setExpandedIdx] = useState(null);

  const isBank = sector?.toLowerCase().includes("banque") || sector?.toLowerCase().includes("assur");
  const suggestions = isBank ? SUGGESTIONS_BANK : SUGGESTIONS_DEFAULT;

  // Persist history to localStorage whenever it changes
  useEffect(() => {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify(qaHistory));
    } catch {
      // localStorage full or unavailable — fail silently
    }
  }, [qaHistory]);

  useEffect(() => {
    setMessages([]);
    setError(null);
    setInput("");
    // History intentionally NOT cleared here — persists across context switches
  }, [company, year]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const newSession = () => {
    setMessages([]);
    setError(null);
    setInput("");
    // History intentionally NOT cleared — persists across sessions
  };

  const clearHistory = () => {
    setQaHistory([]);
    setShowHistory(false);
    setExpandedIdx(null);
  };

  const submit = async (text) => {
    const question = (text ?? input).trim();
    if (!question || busy) return;
    setInput("");
    if (textRef.current) textRef.current.style.height = "auto";
    setError(null);

    const history = messages
      .filter((m) => m.role !== "system")
      .slice(-8)
      .map(({ role, content }) => ({ role, content }));

    // Demo guard — block if limit reached
    if (isDemo) {
      const used = getDemoMsgsUsed();
      if (used >= DEMO_MSG_LIMIT) return;
      const next = used + 1;
      localStorage.setItem(DEMO_MSG_KEY, String(next));
      setDemoMsgsUsed(next);
    }

    setBusy(true);
    setMessages((m) => {
      const next = [...m, { role: "user", content: question }, { role: "assistant", content: "", sources: [] }];
      streamIdxRef.current = next.length - 1;
      return next;
    });

    let answerText = "";

    try {
      await sendChatStream(
        question,
        history,
        { company: company || null, year: year ? String(year) : null, sector: sector || null },
        {
          onToken: (token) => {
            answerText += token;
            const idx = streamIdxRef.current;
            setMessages((m) => {
              const next = [...m];
              next[idx] = { ...next[idx], content: next[idx].content + token };
              return next;
            });
          },
          onDone: ({ sources }) => {
            const idx = streamIdxRef.current;
            setMessages((m) => {
              const next = [...m];
              next[idx] = { ...next[idx], sources };
              return next;
            });
            // Save Q&A pair to persistent history
            setQaHistory((h) => [
              {
                question,
                answer: answerText,
                companyName: companyName || null,
                year: year ? String(year) : null,
                timestamp: Date.now(),
              },
              ...h,
            ].slice(0, MAX_HISTORY));
          },
        }
      );
    } catch {
      setError("Le modèle n'a pas répondu. Réessayez dans un instant.");
      setMessages((m) => m.filter((_, i) => i !== streamIdxRef.current));
    } finally {
      setBusy(false);
    }
  };

  const scopeLabel = companyName
    ? [companyName, year].filter(Boolean).join(" · ")
    : "Tous les rapports";

  return (
    <div className="chat">
      <div className="chat-head">
        <div className="chat-head-left">
          <div className="chat-scope-badge">
            <svg viewBox="0 0 16 16" fill="none" width="13" height="13">
              <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.4"/>
              <path d="M5.5 8l2 2 3-3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
            {scopeLabel}
          </div>
          {sector && <span className="chat-sector">{sector}</span>}
        </div>
        <div className="chat-head-right">
          <span className="chat-online">
            <span className="online-dot" />
            En ligne
          </span>
          <button className="btn-new-session" onClick={newSession}>
            Nouvelle session
          </button>
        </div>
      </div>

      <div className="chat-body">
        {messages.length === 0 && !busy && (
          <div className="chat-welcome">
            <div className="chat-welcome-icon">
              <svg viewBox="0 0 56 56" fill="none">
                <defs>
                  <linearGradient id="wg" x1="0" y1="0" x2="1" y2="1">
                    <stop offset="0%" stopColor="#2563eb"/>
                    <stop offset="100%" stopColor="#1d4ed8"/>
                  </linearGradient>
                </defs>
                <rect width="56" height="56" rx="16" fill="url(#wg)"/>
                <rect x="10" y="34" width="8" height="14" rx="2" fill="white" opacity=".4"/>
                <rect x="24" y="22" width="8" height="26" rx="2" fill="white" opacity=".7"/>
                <rect x="38" y="12" width="8" height="36" rx="2" fill="white"/>
              </svg>
            </div>
            <h3 className="chat-welcome-title">
              {companyName ? `Analyse — ${companyName}` : "Analyse multi-rapports"}
            </h3>
            <p className="chat-welcome-sub">
              {companyName
                ? `Posez une question sur les rapports de ${companyName}${year ? ` (${year})` : ""}.`
                : "Posez une question sur l'ensemble des 70 entreprises indexées."}
            </p>
            <div className="suggestions">
              {suggestions.map((s) => (
                <button key={s} className="chip" onClick={() => submit(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            {m.role === "assistant" && (
              <div className="msg-avatar">
                <svg viewBox="0 0 24 24" fill="none" width="16" height="16">
                  <circle cx="12" cy="12" r="10" fill="var(--accent)"/>
                  <path d="M8 12h8M12 8v8" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
                </svg>
              </div>
            )}
            <div className="msg-content">
              <div className="bubble">
                {m.role === "assistant" ? (
                  <Markdown>{m.content}</Markdown>
                ) : (
                  m.content
                )}
              </div>
              {m.role === "assistant" && m.sources?.length > 0 && (
                <div className="msg-sources">
                  {m.sources.map((s, j) =>
                    s?.url ? (
                      <span key={j} className="source-wrap">
                        <button
                          className="source-tag"
                          onClick={() => onOpenSource(s)}
                          title={`Ouvrir p.${s.page ?? 1} dans la visionneuse`}
                        >
                          {s.label}
                        </button>
                        <a
                          className="source-ext"
                          href={`${s.url}#page=${s.page ?? 1}`}
                          target="_blank"
                          rel="noreferrer"
                          title="Ouvrir dans un nouvel onglet"
                        >
                          ↗
                        </a>
                      </span>
                    ) : (
                      <span key={j} className="source-tag">{s.label || s}</span>
                    )
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {busy && !messages[streamIdxRef.current]?.content && (
          <div className="msg assistant">
            <div className="msg-avatar">
              <svg viewBox="0 0 24 24" fill="none" width="16" height="16">
                <circle cx="12" cy="12" r="10" fill="var(--accent)"/>
                <path d="M8 12h8M12 8v8" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
              </svg>
            </div>
            <div className="msg-content">
              <div className="bubble typing">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}

        {error && <p className="chat-error">{error}</p>}
        <div ref={bottomRef} />
      </div>

      {/* Persistent Q&A history bar — survives new sessions */}
      {qaHistory.length > 0 && (
        <div className="chat-history-bar">
          <div className="chat-history-header">
            <button
              className="chat-history-toggle"
              onClick={() => { setShowHistory((v) => !v); setExpandedIdx(null); }}
            >
              <svg viewBox="0 0 16 16" fill="none" width="13" height="13">
                <path d="M8 3v5l3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3"/>
              </svg>
              Historique
              <span className="chat-history-count">{qaHistory.length}</span>
              <svg
                viewBox="0 0 16 16" fill="none" width="12" height="12"
                style={{ transition: "transform .2s", transform: showHistory ? "rotate(180deg)" : "rotate(0deg)" }}
              >
                <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            {showHistory && (
              <button className="chat-history-clear" onClick={clearHistory} title="Effacer l'historique">
                Effacer
              </button>
            )}
          </div>

          {showHistory && (
            <div className="chat-history-list">
              {qaHistory.map((item, i) => (
                <div key={i} className={`chat-history-item${expandedIdx === i ? " expanded" : ""}`}>
                  <div className="chat-history-item-row">
                    <button
                      className="chat-history-item-head"
                      onClick={() => setExpandedIdx(expandedIdx === i ? null : i)}
                    >
                      <div className="chat-history-item-meta">
                        {item.companyName && (
                          <span className="chat-history-badge">{item.companyName}{item.year ? ` · ${item.year}` : ""}</span>
                        )}
                        <span className="chat-history-time">
                          {new Date(item.timestamp).toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                      <p className="chat-history-question">
                        {item.question.length > 80 ? item.question.slice(0, 80) + "…" : item.question}
                      </p>
                      <svg
                        viewBox="0 0 16 16" fill="none" width="11" height="11"
                        className="chat-history-chevron"
                        style={{ transform: expandedIdx === i ? "rotate(180deg)" : "rotate(0deg)" }}
                      >
                        <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </button>
                    <button
                      className="chat-history-delete"
                      title="Supprimer"
                      onClick={(e) => {
                        e.stopPropagation();
                        setQaHistory((h) => h.filter((_, idx) => idx !== i));
                        if (expandedIdx === i) setExpandedIdx(null);
                        else if (expandedIdx > i) setExpandedIdx(expandedIdx - 1);
                      }}
                    >
                      <svg viewBox="0 0 16 16" fill="none" width="12" height="12">
                        <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                    </button>
                  </div>

                  {expandedIdx === i && (
                    <div className="chat-history-item-body">
                      <div className="chat-history-answer">
                        <Markdown>{item.answer}</Markdown>
                      </div>
                      <button
                        className="chat-history-reask"
                        onClick={() => {
                          setInput(item.question);
                          if (textRef.current) {
                            textRef.current.focus();
                            setTimeout(grow, 0);
                          }
                        }}
                      >
                        Reposer cette question →
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {isDemo && demoMsgsUsed >= DEMO_MSG_LIMIT ? (
        <div className="demo-limit-wall">
          <div className="demo-limit-left">
            <svg viewBox="0 0 24 24" fill="none" width="18" height="18">
              <rect x="3" y="11" width="18" height="11" rx="2" stroke="currentColor" strokeWidth="1.5"/>
              <path d="M7 11V7a5 5 0 0 1 10 0v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
            </svg>
            <div className="demo-limit-text">
              <p className="demo-limit-title">Chat limit reached</p>
              <p className="demo-limit-sub">
                You can still <strong>browse companies and view PDF reports</strong> freely.
                Contact the admin to unlock full chat access.
              </p>
            </div>
          </div>
          <div className="demo-limit-pills">
            <span className="demo-pill allowed">
              <svg viewBox="0 0 12 12" fill="none" width="10" height="10">
                <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Browse reports
            </span>
            <span className="demo-pill allowed">
              <svg viewBox="0 0 12 12" fill="none" width="10" height="10">
                <path d="M2 6l3 3 5-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              View PDFs
            </span>
            <span className="demo-pill blocked">
              <svg viewBox="0 0 12 12" fill="none" width="10" height="10">
                <rect x="2" y="5.5" width="8" height="5" rx="1" stroke="currentColor" strokeWidth="1.2"/>
                <path d="M4 5.5V4a2 2 0 0 1 4 0v1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
              </svg>
              Chat
            </span>
          </div>
        </div>
      ) : (
        <>
          <div className="chat-composer">
            <textarea
              ref={textRef}
              rows={1}
              value={input}
              placeholder={`Question sur ${companyName || "tous les rapports"}…`}
              onInput={grow}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  submit();
                }
              }}
            />
            <button
              className="btn-send"
              disabled={busy || !input.trim()}
              onClick={() => submit()}
              aria-label="Envoyer"
            >
              <svg viewBox="0 0 20 20" fill="none" width="18" height="18">
                <path d="M17 10L3 3l3 7-3 7 14-7z" fill="currentColor"/>
              </svg>
            </button>
          </div>
          {isDemo && (
            <p className="chat-hint demo-hint">
              Demo · {DEMO_MSG_LIMIT - demoMsgsUsed} message{DEMO_MSG_LIMIT - demoMsgsUsed > 1 ? "s" : ""} remaining
            </p>
          )}
          {!isDemo && (
            <p className="chat-hint">Entrée pour envoyer · Maj+Entrée pour nouvelle ligne</p>
          )}
        </>
      )}
    </div>
  );
}
