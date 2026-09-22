import React from "react";

export default function Metrics({ items }) {
  return (
    <div className="metrics-grid">
      {items.map((m) => (
        <article className="metric" key={m.label}>
          <p className="metric-label">{m.label}</p>
          <p className="metric-value">{m.value}</p>
          <p className="metric-delta">{m.delta}</p>
          <p className="metric-detail">{m.detail}</p>
          <span className="page-pill">p. {m.page}</span>
        </article>
      ))}
    </div>
  );
}