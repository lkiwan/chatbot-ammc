import React, { useEffect, useRef, useState } from "react";
import { sendChat } from "../api.js";

const SUGGESTIONS = [
  "Quel est le résultat net part du groupe ?",
  "Quel est le total du bilan au 30 juin 2026 ?",
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

export default function ChatPanel() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [textRef, autoGrow] = useAutoGrow();
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, busy]);

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
      const reply = await sendChat(question, history);
      setMessages((m) => [...m, { role: "assistant", content: reply.content, sources: reply.sources }]);
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
          <p className="chat-title">Analyste — édition H1 2026</p>
          <p className="chat-sub">Rapport Attijariwafa bank · lecteur sourcé</p>
        </div>
        <span className="chat-status">En ligne</span>
      </div>

      <div className="chat-body">
        {messages.length === 0 && !busy && (
          <div className="chat-empty">
            <p className="chat-empty-h">Que voulez-vous savoir ?</p>
            <p className="chat-empty-s">
              La réponse viendra du rapport, accompagnée des pages où se trouvent les
              chiffres. Les questions posées ici nourrissent le fil de la discussion.
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
            <div className="bubble">{m.content}</div>
            {m.role === "assistant" && m.sources && m.sources.length > 0 && (
              <div className="msg-sources">
                Pages : {m.sources.join(", ")}
              </div>
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
            <div className="msg-sources">Consultation de l'index…</div>
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