import React, { useEffect, useRef, useState } from "react";
import { niceName } from "../format.js";
import { sendChat } from "../api.js";
import Markdown from "./Markdown.jsx";

const SUGGESTIONS = [
  "Quel est le résultat net part du groupe ?",
  "Quel est le total du bilan ?",
  "Quels sont les principaux actionnaires ?",
  "Quel est le coefficient d'exploitation ?"
];

function useAutoGrow() {
  const ref = useRef(null);
  const auto = () => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 140) + "px";
  };
  return [ref, auto];
}

export default function ChatPanel({ rapport = null }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [textRef, autoGrow] = useAutoGrow();
  const bottomRef = useRef(null);

  const scope = rapport ? niceName(rapport) : "Tous les rapports";
  const scopeHint = rapport
    ? "Le rapport est déposé. Les questions portent sur l'index de cette base."
    : "Les questions portent sur l'ensemble des rapports en base.";

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

  const newSession = () => {
    setMessages([]);
    setError(null);
    setInput("");
  };

  const submit = async (text) => {
    const question = (text ?? input).trim();
    if (!question || busy) return;
    setInput("");
    setError(null);
    const history = messages
      .filter((m) => m.role !== "system")
      .slice(-8)
      .map(({ role, content }) => ({ role, content }));
    setMessages((m) => [...m, { role: "user", content: question }]);
    setBusy(true);
    try {
      const reply = await sendChat(question, history, rapport);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: reply.content, sources: reply.sources }
      ]);
    } catch (e) {
      setError("Le modèle n'a pas répondu. Réessayez dans un instant.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="chat">
      <div className="chat-head">
        <div>
          <p className="chat-title">Analyste — {scope}</p>
          <p className="chat-sub">{scopeHint}</p>
        </div>
        <div className="chat-head-actions">
          <span className="chat-status">En ligne</span>
          <button className="chat-new" onClick={newSession}>
            Nouvelle session
          </button>
        </div>
      </div>

      <div className="chat-body">
        {messages.length === 0 && !busy && (
          <div className="chat-empty">
            <p className="chat-empty-h">Session sur {scope}</p>
            <p className="chat-empty-s">
              Les réponses viennent du(des) rapport(s) sélectionné(s), accompagnées du
              rapport et des pages. Chaque réponse est sourcée.
            </p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} className="chip" onClick={() => submit(s)}>
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div key={i} className={`msg ${m.role}`}>
            <div className="bubble">
              {m.role === "assistant" ? (
                <Markdown>{m.content}</Markdown>
              ) : (
                m.content
              )}
            </div>
            {m.role === "assistant" && m.sources && m.sources.length > 0 && (
              <div className="msg-sources">{m.sources.join(", ")}</div>
            )}
          </div>
        ))}

        {busy && (
          <div className="msg assistant">
            <div className="bubble typing">
              <span />
              <span />
              <span />
            </div>
            <div className="msg-sources">Consultation de l’index…</div>
          </div>
        )}

        {error && <p className="chat-error">{error}</p>}
        <div ref={bottomRef} />
      </div>

      <div className="chat-composer">
        <textarea
          ref={textRef}
          rows={1}
          value={input}
          placeholder="Écrivez votre question…"
          onInput={autoGrow}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              submit();
            }
          }}
        />
        <button
          className="btn btn-primary send"
          disabled={busy || !input.trim()}
          onClick={() => submit()}
          aria-label="Envoyer"
        >
          ⏎
        </button>
      </div>
      <p className="chat-hint">Entrée pour envoyer · Maj+Entrée pour passer à la ligne</p>
    </div>
  );
}