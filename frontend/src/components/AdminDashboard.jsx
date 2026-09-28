import React, { useEffect, useState, useCallback, useMemo } from "react";
import {
  fetchAnalyticsDeep,
  fetchAdminUsers,
  fetchAdminUserHistory,
  fetchAdminAnon,
  fetchAdminResetPassword,
  trackError,
} from "../api.js";

const REFRESH_MS = 30_000;

function flagOf(code) {
  if (!code || code.length !== 2) return "";
  return String.fromCodePoint(
    ...[...code.toUpperCase()].map((c) => 0x1f1e6 + c.charCodeAt(0) - 65)
  );
}

function formatWhen(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString("fr");
}

function timeOnly(ts) {
  if (!ts) return "—";
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleTimeString("fr");
}

function formatMs(ms) {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  return `${(ms / 1000).toFixed(1)} s`;
}

function duration(firstSeen, lastSeen) {
  if (!firstSeen || !lastSeen) return "—";
  const ms = new Date(lastSeen) - new Date(firstSeen);
  if (Number.isNaN(ms) || ms < 0) return "—";
  if (ms < 60_000) return `${Math.round(ms / 1000)}s`;
  if (ms < 3_600_000) return `${Math.round(ms / 60_000)}m`;
  if (ms < 86_400_000) return `${(ms / 3_600_000).toFixed(1)}h`;
  return `${Math.round(ms / 86_400_000)}j`;
}

function toPairs(rows) {
  return (Array.isArray(rows) ? rows : []).map((r) =>
    Array.isArray(r) ? r : [r?.name ?? "—", r?.count ?? 0]
  );
}

function num(n) {
  return (n ?? 0).toLocaleString("fr");
}

const PAGES = [
  { key: "overview", label: "Vue d'ensemble", icon: <GaugeIcon /> },
  { key: "traffic",  label: "Trafic & Visiteurs", icon: <GlobeIcon /> },
  { key: "chat",     label: "Chat & Questions", icon: <ChatIcon /> },
  { key: "accounts", label: "Comptes", icon: <UsersIcon /> },
  { key: "security", label: "Connexions & Sécurité", icon: <LockIcon /> },
  { key: "usage",    label: "Contenu & Usage", icon: <DocIcon /> },
];

const PAGE_HINTS = {
  overview: "Activité globale du site, des connexions et du chatbot.",
  traffic:  "Visiteurs par IP, appareils, navigateurs et géographie.",
  chat:     "Questions posées, latences et couverture thématique.",
  accounts: "Comptes enregistrés, quota quotidien et historique.",
  security: "Tentatives de connexion, force brute et journal détaillé.",
  usage:    "Rapports et PDF consultés, sociétés explorées, erreurs.",
};

export default function AdminDashboard({ onClose }) {
  const [data, setData]           = useState(null);
  const [loading, setLoading]     = useState(true);
  const [error, setError]         = useState(null);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [page, setPage]           = useState("overview");

  const load = useCallback(() => {
    fetchAnalyticsDeep(300)
      .then((d) => {
        setData(d);
        setError(null);
        setLastUpdated(new Date());
      })
      .catch((e) => {
        setError("Impossible de charger les données d'analyse.");
        trackError("analytics_dashboard_failed", e?.message || "");
      })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, REFRESH_MS);
    return () => clearInterval(interval);
  }, [load]);

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const current = PAGES.find((p) => p.key === page);

  return (
    <div className="adash-overlay">
      <div className="adash-layout">
        <aside className="adash-side">
          <div className="adash-side-brand">
            <img src="/logo.png" alt="AnnualEdge" className="adash-side-logo" />
            <div>
              <div className="adash-side-title">Pilotage</div>
              <div className="adash-side-badge">Admin</div>
            </div>
          </div>
          <nav className="adash-nav">
            {PAGES.map((p) => (
              <button
                key={p.key}
                className={`adash-nav-btn ${page === p.key ? "active" : ""}`}
                onClick={() => setPage(p.key)}
              >
                <span className="adash-nav-icon">{p.icon}</span>
                <span className="adash-nav-label">{p.label}</span>
              </button>
            ))}
          </nav>
          <div className="adash-side-foot">
            <span className="adash-updated">
              Actualisé {lastUpdated ? lastUpdated.toLocaleTimeString("fr") : "…"}
            </span>
            <button className="adash-refresh" onClick={() => window.location.reload()} title="Actualiser (recharge la page)">
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M13.5 2.5A6.5 6.5 0 0 0 2 8M2.5 13.5A6.5 6.5 0 0 0 14 8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
                <path d="M13.5 2.5v3h-3M2.5 13.5v-3h3" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <button className="adash-close" onClick={onClose} title="Fermer (Échap)">
              <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
                <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </aside>

        <div className="adash-main">
          <header className="adash-top">
            <div className="adash-top-left">
              <span className="adash-header-icon">{current?.icon}</span>
              <div>
                <h2 className="adash-title">{current?.label}</h2>
                <p className="adash-subtitle">{PAGE_HINTS[current?.key]}</p>
              </div>
            </div>
          </header>

          <div className="adash-scroll">
            {loading && <LoadingSkeleton />}
            {error && !loading && <ErrorState message={error} onRetry={load} />}
            {data && !loading && (
              <>
                {page === "overview" && <OverviewPage data={data} />}
                {page === "traffic"  && <TrafficPage data={data} />}
                {page === "chat"     && <ChatPage data={data} />}
                {page === "accounts" && <AccountsPage />}
                {page === "security" && <SecurityPage data={data} />}
                {page === "usage"    && <UsagePage data={data} />}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Vue d'ensemble ───────────────────────────────────────────────────────── */

function OverviewPage({ data }) {
  const { summary, logins, chat, usage } = data;
  const totalDevices = Object.values(summary.device_breakdown || {}).reduce((s, v) => s + v, 0);

  return (
    <>
      <div className="adash-kpi-grid">
        <KpiCard icon={<EyeIcon />}   label="Visites"           value={num(summary.total_visits)}  sub="chargements de page" color="blue" />
        <KpiCard icon={<UsersIcon />} label="Visiteurs uniques" value={num(summary.unique_visitors_all ?? 0)} sub={`${num(summary.unique_visitors_30d ?? 0)} sur 30 jours`} color="purple" />
        <KpiCard icon={<ChatIcon />}  label="Questions"         value={num(chat.total_questions)} sub={`${num(chat.unique_askers ?? 0)} demandeurs`} color="amber" />
        <KpiCard icon={<UserIcon />}  label="Inscriptions"      value={num(logins.signups ?? 0)}  sub="comptes créés" color="teal" />
        <KpiCard icon={<LockIcon />}  label="Connexions"        value={num(logins.total_attempts)} sub={`${num(logins.total_failed)} échouées`} color="blue" />
        <KpiCard icon={<DocIcon />}   label="PDF ouverts"       value={num(usage.pdf_opens)}      sub="citations suivies" color="purple" />
        <KpiCard icon={<BuildingIcon />} label="Sociétés vues"  value={num(usage.company_selects)} sub="sélections latérale" color="teal" />
        <KpiCard icon={<ErrorIcon />} label="Erreurs"           value={num(usage.errors)} sub={`${num(summary.total_demo_exhausted ?? 0)} fins de démo`} color="rose" />
      </div>

      <div className="adash-charts-row">
        <div className="adash-card adash-card-wide">
          <div className="adash-card-header">
            <span className="adash-card-title">Visites — 7 derniers jours</span>
          </div>
          <BarChart data={summary.visits_per_day} color="var(--adash-blue)" />
        </div>
        <div className="adash-card adash-card-wide">
          <div className="adash-card-header">
            <span className="adash-card-title">Questions — 7 derniers jours</span>
            <span className="adash-card-sub">p95 {formatMs(chat.p95_latency_ms)}</span>
          </div>
          <BarChart data={chat.questions_per_day} color="var(--adash-amber)" />
        </div>
      </div>

      <TimelineCard timeline={data.timeline || []} />

      <div className="adash-charts-row">
        <div className="adash-card">
          <div className="adash-card-header">
            <span className="adash-card-title">Appareils</span>
            <span className="adash-card-sub">{totalDevices} visites</span>
          </div>
          <div className="adash-devices">
            {[
              { key: "desktop", label: "Ordinateur", icon: <DesktopIcon />, color: "var(--adash-blue)" },
              { key: "mobile",  label: "Mobile",  icon: <MobileIcon />,  color: "var(--adash-teal)" },
              { key: "tablet",  label: "Tablette",  icon: <TabletIcon />,  color: "var(--adash-purple)" },
            ].map(({ key, label, icon, color }) => {
              const count = summary.device_breakdown?.[key] ?? 0;
              const pct = totalDevices > 0 ? Math.round((count / totalDevices) * 100) : 0;
              return (
                <div key={key} className="adash-device-row">
                  <div className="adash-device-label">
                    <span className="adash-device-icon">{icon}</span>
                    <span>{label}</span>
                  </div>
                  <div className="adash-device-bar-wrap">
                    <div className="adash-device-bar-fill" style={{ width: `${pct}%`, background: color }} />
                  </div>
                  <div className="adash-device-stats">
                    <span className="adash-device-count">{num(count)}</span>
                    <span className="adash-device-pct">{pct}%</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <DistributionCard title="Navigateurs" rows={data.clients.browsers} />
        <DistributionCard title="Systèmes d'exploitation" rows={data.clients.systems} />
      </div>

      {(data.clients.devices?.length ?? 0) > 1 && <DistributionCard title="Appareils (détail)" rows={data.clients.devices} />}

      <LocationsCard countries={summary.top_countries} cities={summary.top_cities} />

      <HourHeatmap hours={data.hours} />

      {(summary.total_demo_exhausted ?? 0) > 0 && (
        <AbuseInsight
          exhausted={summary.total_demo_exhausted ?? 0}
          logins={summary.total_demo_logins}
        />
      )}

      <TopListsCard usage={usage} />
    </>
  );
}

/* ── Trafic & Visiteurs ───────────────────────────────────────────────────── */

function TrafficPage({ data }) {
  const { summary, clients } = data;
  return (
    <>
      <div className="adash-kpi-grid">
        <KpiCard icon={<EyeIcon />}   label="Visites"             value={num(summary.total_visits)}  sub="toutes périodes" color="blue" />
        <KpiCard icon={<UsersIcon />} label="Visiteurs uniques"   value={num(summary.unique_visitors_all ?? 0)} sub="par IP" color="purple" />
        <KpiCard icon={<GlobeIcon />} label="Localisés"           value={num(summary.located_visitors ?? 0)} sub={`${num(summary.unique_visitors_30d ?? 0)} sur 30 jours`} color="teal" />
        <KpiCard icon={<AlertIcon />} label="Échecs de connexion" value={num(data.logins.total_failed)} sub="sur toutes tentatives" color="rose" />
      </div>

      <div className="adash-charts-row">
        <div className="adash-card adash-card-wide">
          <div className="adash-card-header">
            <span className="adash-card-title">Visites — 7 derniers jours</span>
          </div>
          <BarChart data={summary.visits_per_day} color="var(--adash-blue)" />
        </div>
      </div>

      <LocationsCard countries={summary.top_countries} cities={summary.top_cities} />

      <TimeChart title="Croissance des visites" series={[
        { key: "visits",    label: "Visites",    color: "var(--adash-blue)" },
        { key: "signups",   label: "Inscriptions", color: "var(--adash-teal)" },
        { key: "questions", label: "Questions",  color: "var(--adash-amber)" },
      ]} timeline={data.timeline} />

      <div className="adash-charts-row">
        <DistributionCard title="Navigateurs" rows={clients.browsers} />
        <DistributionCard title="Systèmes" rows={clients.systems} />
      </div>

      <HourHeatmap hours={data.hours} />

      <VisitorsTable visitors={data.visitors || []} />
    </>
  );
}

/* ── Chat & Questions ─────────────────────────────────────────────────────── */

function ChatPage({ data }) {
  const { chat } = data;
  const [query, setQuery] = useState("");
  const [roleFilter, setRoleFilter] = useState("");

  const questions = data.questions || [];

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return questions.filter((r) => {
      if (roleFilter && r.role !== roleFilter) return false;
      if (!q) return true;
      return [r.question, r.company, r.year, r.sector, r.location].some((v) =>
        String(v || "").toLowerCase().includes(q)
      );
    });
  }, [questions, query, roleFilter]);

  const roles = useMemo(
    () => Array.from(new Set(questions.map((r) => r.role).filter(Boolean))),
    [questions]
  );

  return (
    <>
      <div className="adash-kpi-grid">
        <KpiCard icon={<ChatIcon />}   label="Questions"   value={num(chat.total_questions)} sub={`${num(chat.unique_askers ?? 0)} demandeurs`} color="amber" />
        <KpiCard icon={<UsersIcon />}  label="Par visiteur" value={chat.questions_per_asker}  sub="question moyenne" color="blue" />
        <KpiCard icon={<ClockIcon />}  label="Réponse moyenne" value={formatMs(chat.avg_latency_ms)} sub={`p95 ${formatMs(chat.p95_latency_ms)}`} color="teal" />
        <KpiCard icon={<CheckIcon />}  label="Avec sources" value={`${chat.source_rate ?? 0}%`} sub="citation incluse" color="purple" />
      </div>

      <div className="adash-charts-row">
        <BarListCard title="Sociétés les plus demandées" rows={chat.top_companies} />
        <BarListCard title="Années demandées" rows={chat.top_years} />
        <BarListCard title="Secteurs" rows={chat.top_sectors} />
      </div>

      {chat.top_reports?.length > 0 && (
        <BarListCard title="Rapports les plus utilisés" rows={chat.top_reports} wide />
      )}

      <div className="adash-card">
        <div className="adash-card-header">
          <span className="adash-card-title">Journal des questions</span>
          <div className="adash-search">
            <select className="adash-select" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value)}>
              <option value="">Tous les rôles</option>
              {roles.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <input
              className="adash-search-input"
              placeholder="Filtrer question, société, année, lieu…"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            {query && (
              <button className="adash-search-clear" onClick={() => setQuery("")} title="Effacer">×</button>
            )}
          </div>
        </div>
        <div className="adash-card-sub adash-count-note">
          {filtered.length} sur {questions.length} affichées
        </div>
        <QuestionTable rows={filtered} />
      </div>

      <div className="adash-card">
        <div className="adash-card-header">
          <span className="adash-card-title">Latence &amp; qualité</span>
        </div>
        <div className="adash-metric-grid">
          <Metric label="Temps moyen"      value={formatMs(chat.avg_latency_ms)} />
          <Metric label="Médiane (p50)"    value={formatMs(chat.p50_latency_ms)} />
          <Metric label="Percentile 95"    value={formatMs(chat.p95_latency_ms)} />
          <Metric label="Maximum"          value={formatMs(chat.max_latency_ms)} />
          <Metric label="Taux d'erreur"    value={`${chat.error_rate ?? 0}%`} />
          <Metric label="Avec sources"     value={`${chat.source_rate ?? 0}%`} />
          <Metric label="Demandeurs"       value={num(chat.unique_askers)} />
          <Metric label="Questions / demandeur" value={chat.questions_per_asker} />
        </div>
      </div>
    </>
  );
}

function Metric({ label, value }) {
  return (
    <div className="adash-metric">
      <span className="adash-metric-val">{value ?? "—"}</span>
      <span className="adash-metric-lbl">{label}</span>
    </div>
  );
}

/* ── Comptes ───────────────────────────────────────────────────────────────── */

function AccountsPage() {
  const [tab, setTab]                 = useState("reg");
  const [state, setState]             = useState({ data: null, error: null });
  const [loading, setLoading]         = useState(true);
  const [anonState, setAnonState]     = useState({ data: null, error: null });
  const [anonLoading, setAnonLoading] = useState(true);
  const [query, setQuery]             = useState("");
  const [modal, setModal]             = useState(null);
  const [history, setHistory]         = useState(null);
  const [histLoading, setHistLoading] = useState(false);
  const [resetFor, setResetFor]       = useState(null);
  const [resetInput, setResetInput]   = useState("");
  const [resetResult, setResetResult] = useState(null);
  const [resetError, setResetError]   = useState(null);
  const [resetBusy, setResetBusy]     = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setAnonLoading(true);
    fetchAdminUsers()
      .then((d) => setState({ data: d, error: null }))
      .catch((e) => { setState({ data: null, error: "Impossible de charger les comptes." }); trackError("admin_users_failed", e?.message || ""); })
      .finally(() => setLoading(false));
    fetchAdminAnon()
      .then((d) => setAnonState({ data: d, error: null }))
      .catch(() => setAnonState({ data: null, error: "Impossible de charger les visiteurs anonymes." }))
      .finally(() => setAnonLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const regRows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const users = state.data?.users || [];
    if (!q) return users;
    return users.filter((u) =>
      [u.email, u.full_name].some((v) => String(v || "").toLowerCase().includes(q))
    );
  }, [state.data, query]);

  const openUser = (row) => {
    setModal({ kind: "reg", row });
    setHistory(null);
    setHistLoading(true);
    fetchAdminUserHistory(row.id)
      .then((h) => setHistory(h))
      .catch(() => setHistory({ messages: [], user: { full_name: "?", email: "erro" } }))
      .finally(() => setHistLoading(false));
  };

  const openAnon = (conv) => {
    setModal({ kind: "anon", row: conv });
    setHistory({ messages: conv.messages || [], user: null });
    setHistLoading(false);
  };

  const openReset = (userId) => {
    setResetFor(resetFor === userId ? null : userId);
    setResetInput("");
    setResetResult(null);
    setResetError(null);
  };

  const closeModal = () => {
    setModal(null);
    setHistory(null);
    setResetFor(null);
    setResetInput("");
    setResetResult(null);
    setResetError(null);
  };

  const doReset = (userId) => {
    if (resetBusy) return;
    setResetBusy(true);
    setResetError(null);
    setResetResult(null);
    fetchAdminResetPassword(userId, resetInput.trim())
      .then((r) => {
        setResetResult(r);
        setResetInput("");
        setModal((prev) => prev && { ...prev, row: { ...prev.row, password: r.new_password, password_recoverable: true } });
        load();
      })
      .catch((e) => setResetError(e?.message || "Réinitialisation impossible."))
      .finally(() => setResetBusy(false));
  };

  if (loading && anonLoading) {
    return (
      <div className="adash-card">
        <div className="adash-empty">Chargement des comptes…</div>
      </div>
    );
  }

  const u = state.data;
  if (state.error && !u) return <ErrorState message={state.error} onRetry={load} />;
  const a = anonState.data;

  const withMessages = (u?.users || []).filter((x) => x.messages_total > 0);
  const msgsTotal = (u?.users || []).reduce((s, x) => s + x.messages_total, 0);
  const convos = a?.convos || [];
  const anonQuestions = convos.reduce((s, c) => s + (c.questions || c.messages?.length || 0), 0);

  return (
    <>
      <div className="adash-kpi-grid">
        <KpiCard icon={<UserIcon />}  label="Comptes enregistrés" value={num(u?.total ?? 0)} sub="inscrits au total" color="teal" />
        <KpiCard icon={<ChatIcon />}  label="Avec messages" value={num(withMessages.length)} sub="réponses sauvegardées" color="amber" />
        <KpiCard icon={<GlobeIcon />} label="Non enregistrés" value={num(convos.length)} sub="visiteurs anonymes" color="blue" />
        <KpiCard icon={<DocIcon />}   label="Questions anonymes" value={num(anonQuestions)} sub="posées sans compte" color="purple" />
      </div>

      <div className="adash-tabs">
        <button className={`adash-tab ${tab === "reg" ? "active" : ""}`} onClick={() => setTab("reg")}>
          Comptes enregistrés ({u?.users?.length ?? 0})
        </button>
        <button className={`adash-tab ${tab === "anon" ? "active" : ""}`} onClick={() => setTab("anon")}>
          Comptes non enregistrés ({convos.length})
        </button>
      </div>

      {tab === "reg" && (
        <div className="adash-card">
          <div className="adash-card-header">
            <span className="adash-card-title">Comptes enregistrés</span>
            <div className="adash-search">
              <input
                className="adash-search-input"
                placeholder="Filtrer par nom ou email…"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
              {query && <button className="adash-search-clear" onClick={() => setQuery("")} title="Effacer">×</button>}
            </div>
          </div>
          <div className="adash-card-sub adash-count-note">
            {regRows.length} sur {u?.users?.length ?? 0} comptes
          </div>
          {regRows.length === 0 ? (
            <div className="adash-empty">Aucun compte enregistré pour le moment.</div>
          ) : (
            <div className="adash-table-wrap">
              <table className="adash-table">
                <thead>
                  <tr>
                    <th>Compte</th>
                    <th>Inscrit le</th>
                    <th className="adash-num">Messages</th>
                    <th>Quota aujourd'hui</th>
                    <th>Dernier message</th>
                    <th>Mot de passe</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {regRows.map((urow) => (
                    <tr
                      key={urow.id}
                      className="adash-clickable"
                      onClick={() => openUser(urow)}
                      title="Voir les questions et réponses"
                    >
                      <td>
                        <div className="adash-account-name">{urow.full_name}</div>
                        <div className="adash-account-email">{urow.email}</div>
                      </td>
                      <td className="adash-cell-muted">{formatWhen(urow.created_at)}</td>
                      <td className="adash-num">{num(urow.messages_total)}</td>
                      <td>
                        <QuotaBar used={urow.quota_used_today} total={u?.quota_day} left={urow.quota_left_today} />
                      </td>
                      <td className="adash-cell-muted">{formatWhen(urow.last_message_at)}</td>
                      <td>
                        {urow.password_recoverable && urow.password ? (
                          <div className="adash-pwd-current">
                            <code>{urow.password}</code>
                            <button
                              className="adash-pwd-copy"
                              onClick={(e) => { e.stopPropagation(); navigator.clipboard?.writeText(urow.password); }}
                            >Copier</button>
                          </div>
                        ) : (
                          <span className="adash-pwd-current adash-pwd-current-na">—</span>
                        )}
                        <button
                          className="adash-pwd-btn"
                          title="Réinitialiser le mot de passe"
                          onClick={(e) => { e.stopPropagation(); openUser(urow); openReset(urow.id); }}
                        >
                          Réinitialiser
                        </button>
                      </td>
                      <td className="adash-cell-muted">
                        <span className="adash-expand-caret">▸</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {tab === "anon" && (
        <div className="adash-card">
          <div className="adash-card-header">
            <span className="adash-card-title">Comptes non enregistrés</span>
          </div>
          <div className="adash-card-sub adash-count-note">
            {convos.length} visiteur(s) anonyme(s) · {anonQuestions} question(s)
          </div>
          {anonState.error && !a ? <div className="adash-empty">{anonState.error}</div> : null}
          {convos.length === 0 ? (
            <div className="adash-empty">Aucune conversation anonyme pour le moment.</div>
          ) : (
            <div className="adash-table-wrap">
              <table className="adash-table">
                <thead>
                  <tr>
                    <th>Visiteur</th>
                    <th>Nom</th>
                    <th>Email</th>
                    <th className="adash-num">Questions</th>
                    <th>Dernier message</th>
                    <th>Appareil</th>
                    <th>Navigateur / OS</th>
                  </tr>
                </thead>
                <tbody>
                  {convos.map((conv) => (
                    <tr
                      key={conv.key}
                      className="adash-clickable"
                      onClick={() => openAnon(conv)}
                      title="Voir la conversation"
                    >
                      <td>
                        <div className="adash-account-name">{conv.ip || "–"}</div>
                        <div className="adash-account-email">{conv.location || ""}</div>
                      </td>
                      <td className="adash-cell-muted">—</td>
                      <td className="adash-cell-muted">—</td>
                      <td className="adash-num">{conv.questions ?? conv.messages?.length ?? 0}</td>
                      <td className="adash-cell-muted">{formatWhen(conv.last_seen)}</td>
                      <td className="adash-cell-muted">{conv.device || "–"}</td>
                      <td className="adash-cell-muted">{[conv.browser, conv.os].filter(Boolean).join(" / ") || "–"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {modal != null && (
        <UserMessagesModal
          row={modal.row}
          isAnon={modal.kind === "anon"}
          history={history}
          loading={histLoading}
          onClose={closeModal}
          resetVisible={modal.kind === "reg" && resetFor === modal.row.id}
          resetInput={resetInput}
          resetResult={resetResult}
          resetError={resetError}
          resetBusy={resetBusy}
          onResetInput={setResetInput}
          onResetSubmit={() => doReset(modal.row.id)}
        />
      )}
    </>
  );
}

function QuotaBar({ used, total, left }) {
  const pct = total > 0 ? Math.round((used / total) * 100) : 0;
  const done = used >= total;
  return (
    <div className="adash-quota">
      <div className="adash-quota-bar">
        <div
          className={`adash-quota-fill ${done ? "full" : ""}`}
          style={{ width: `${Math.min(100, Math.max(3, pct))}%` }}
        />
      </div>
      <span className={`adash-quota-txt ${done ? "exhausted" : ""}`}>
        {done ? "quota atteint" : `${left} restants`}
      </span>
    </div>
  );
}

function UserMessagesModal({
  row, isAnon, history, loading, onClose,
  resetVisible, resetInput, resetResult, resetError, resetBusy,
  onResetInput, onResetSubmit,
}) {
  const meta = history?.user || {};
  const fullName = meta.full_name || row?.full_name || (isAnon ? "—" : "Compte");
  const email = meta.email || row?.email || "—";
  const sub = isAnon
    ? `— · ${row?.ip || ""}${row?.location ? " · " + row.location : ""}`
    : `${email}${row?.created_at ? " · inscrit le " + formatWhen(row.created_at) : ""}`;

  useEffect(() => {
    const onKey = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="adash-umodal" onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="adash-umodal-box">
        <div className="adash-umodal-head">
          <img className="adash-umodal-brand" src="/logo.png" alt="AE" />
          <div className="adash-umodal-meta">
            <div className="adash-umodal-name">{fullName}</div>
            <div className="adash-umodal-sub">{sub}</div>
          </div>
          <button className="adash-umodal-close" onClick={onClose} title="Fermer">✕</button>
        </div>

        {resetVisible && (
          <div className="adash-umodal-reset">
            <PasswordResetForm
              user={{ full_name: fullName, email }}
              current={row?.password}
              value={resetInput}
              onChange={onResetInput}
              result={resetResult}
              error={resetError}
              busy={resetBusy}
              onSubmit={onResetSubmit}
            />
          </div>
        )}

        <div className="adash-umodal-body">
          {loading ? (
            <div className="adash-empty">Chargement de la conversation…</div>
          ) : !history || !history.messages || history.messages.length === 0 ? (
            <div className="adash-empty">Aucun message enregistré pour ce compte.</div>
          ) : (
            history.messages.map((m, i) => (
              <UserMessage key={i} m={m} anon={isAnon} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}

function UserMessage({ m, anon }) {
  return (
    <div className="adash-conv">
      <div className="adash-conv-time">{formatWhen(m.timestamp)}</div>
      <div className="adash-conv-row user">
        <div className="adash-conv-bubble user">{m.question || "—"}</div>
      </div>
      <div className="adash-conv-row assistant">
        <img className="adash-conv-avatar" src="/logo.png" alt="AE" />
        <div className="adash-conv-assistant">
          <div className="adash-conv-bubble assistant">
            {m.answer || (anon ? "Réponse non enregistrée (visiteur anonyme)" : "—")}
          </div>
          <div className="adash-conv-sources">
            {typeof m.sources === "number" && m.sources > 0 && (
              <span className="adash-conv-source">{m.sources} source(s)</span>
            )}
            {Array.isArray(m.sources) && m.sources.map((s, j) => (
              <span key={j} className="adash-conv-source">
                {s.label || s.url || "source"}
              </span>
            ))}
            {anon && m.latency_ms != null && (
              <span className="adash-conv-source">{m.latency_ms} ms</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function PasswordResetForm({ user, value, onChange, result, error, busy, onSubmit, current }) {
  return (
    <div className="adash-pwd">
      <div className="adash-pwd-head">Mot de passe</div>
      {user?.full_name && current != null && (
        <div className="adash-pwd-show">
          <span className="adash-pwd-done-title">Mot de passe actuel :</span>
          <code>{current}</code>
          <button className="adash-pwd-copy" onClick={() => navigator.clipboard?.writeText(current)}>Copier</button>
        </div>
      )}
      {user?.full_name && current == null && (
        <div className="adash-pwd-note">
          Mot de passe actuel : — (compte créé avant la récupération, non récupérable → réinitialisez-le).
        </div>
      )}
      {result ? (
        <div className="adash-pwd-done">
          <div className="adash-pwd-done-title">Nouveau mot de passe de {result.full_name} :</div>
          <div className="adash-pwd-show">
            <code>{result.new_password}</code>
            <button className="adash-pwd-copy" onClick={() => navigator.clipboard?.writeText(result.new_password)}>Copier</button>
          </div>
          <div className="adash-pwd-note">Transmettez-le à {result.email}. Le mot de passe précédent ne fonctionne plus.</div>
        </div>
      ) : (
        <div className="adash-pwd-form">
          <input
            className="adash-search-input adash-pwd-input"
            type="text"
            placeholder="Nouveau mot de passe (laisser vide = auto-généré, 8 caractères min.)"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") onSubmit(); }}
          />
          <button className="adash-pwd-submit" disabled={busy} onClick={onSubmit}>
            {busy ? "Réinitialisation…" : "Réinitialiser"}
          </button>
          {error && <div className="adash-pwd-error">{error}</div>}
        </div>
      )}
    </div>
  );
}

/* ── Connexions & Sécurité ────────────────────────────────────────────────── */

function SecurityPage({ data }) {
  const { logins, login_log: log } = data;
  const attackers = (logins.top_bruteforce || []).filter((r) => r.failed > 0);

  return (
    <>
      <div className="adash-kpi-grid">
        <KpiCard icon={<UserIcon />}  label="Tentatives"   value={num(logins.total_attempts)} sub="toutes tentatives" color="blue" />
        <KpiCard icon={<CheckIcon />} label="Réussies"     value={num(logins.total_success)}  sub={`${logins.success_rate}% de succès`} color="teal" />
        <KpiCard icon={<LockIcon />}  label="Échouées"     value={num(logins.total_failed)}   sub="mauvais identifiants" color="rose" />
        <KpiCard icon={<AlertIcon />} label="Inscriptions" value={num(logins.signups || 0)}   sub="comptes créés" color="amber" />
      </div>

      <div className="adash-card">
        <div className="adash-card-header">
          <span className="adash-card-title">Identifiants utilisés</span>
          <span className="adash-card-sub">réussite / échec par compte</span>
        </div>
        {(logins.by_email || []).length === 0 ? (
          <div className="adash-empty">Aucune tentative de connexion enregistrée.</div>
        ) : (
          <div className="adash-table-wrap">
            <table className="adash-table">
              <thead>
                <tr>
                  <th>Email</th>
                  <th className="adash-num">Tentatives</th>
                  <th className="adash-num">Succès</th>
                  <th className="adash-num">Échecs</th>
                  <th className="adash-num">IP uniques</th>
                  <th>Première fois</th>
                  <th>Dernière fois</th>
                </tr>
              </thead>
              <tbody>
                {logins.by_email.map((r) => (
                  <tr key={r.email}>
                    <td className="adash-loc">{r.email}</td>
                    <td className="adash-num">{num(r.attempts)}</td>
                    <td className="adash-num">{num(r.success)}</td>
                    <td className={`adash-num ${r.failed ? "adash-num-hot" : ""}`}>{num(r.failed)}</td>
                    <td className="adash-num">{num(r.unique_ips)}</td>
                    <td className="adash-cell-muted">{formatWhen(r.first_seen)}</td>
                    <td className="adash-cell-muted">{formatWhen(r.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {attackers.length > 0 && (
        <div className="adash-card adash-abuse-card">
          <div className="adash-card-header">
            <span className="adash-card-title">
              <span className="adash-abuse-dot" />
              Échecs de connexion par IP
            </span>
            <span className="adash-card-sub">devination possible d'identifiants</span>
          </div>
          <div className="adash-table-wrap">
            <table className="adash-table">
              <thead>
                <tr>
                  <th>Adresse IP</th>
                  <th>Localisation</th>
                  <th className="adash-num">Échecs</th>
                  <th>Dernière tentative</th>
                </tr>
              </thead>
              <tbody>
                {attackers.map((r) => (
                  <tr key={r.ip_hash}>
                    <td><code className="adash-ip">{r.ip || "—"}</code></td>
                    <td><span className="adash-loc">{r.location}</span></td>
                    <td className="adash-num adash-num-hot">{num(r.failed)}</td>
                    <td className="adash-cell-muted">{formatWhen(r.last_seen)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <div className="adash-card">
        <div className="adash-card-header">
          <span className="adash-card-title">Journal des connexions</span>
          <span className="adash-card-sub">plus récentes d'abord</span>
        </div>
        <LogTable rows={log} />
      </div>

      <AbuseInsight
        exhausted={data.summary.total_demo_exhausted ?? 0}
        logins={data.summary.total_demo_logins}
      />
    </>
  );
}

function LogTable({ rows }) {
  if (!rows || rows.length === 0) return <div className="adash-empty">Rien enregistré pour le moment.</div>;
  return (
    <div className="adash-table-wrap">
      <table className="adash-table">
        <thead>
          <tr>
            <th>Quand</th>
            <th>Résultat</th>
            <th>Email</th>
            <th>Mot de passe</th>
            <th>Adresse IP</th>
            <th>Localisation</th>
            <th>Via</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.ip_hash}-${r.ts}-${i}`}>
              <td className="adash-cell-muted">{formatWhen(r.ts)}</td>
              <td>
                <span className={`adash-chip ${r.ok ? "adash-chip-demo" : "adash-chip-fail"}`}>
                  {r.ok ? "succès" : "échec"}
                </span>
              </td>
              <td className="adash-loc">{r.email || "—"}</td>
              <td><code className="adash-pwd">{r.password || "—"}</code></td>
              <td><code className="adash-ip">{r.ip || "—"}</code></td>
              <td>{r.location}</td>
              <td className="adash-cell-muted">{r.kind || "—"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ── Contenu & Usage ──────────────────────────────────────────────────────── */

function UsagePage({ data }) {
  const { usage, summary } = data;
  return (
    <>
      <div className="adash-kpi-grid">
        <KpiCard icon={<DocIcon />}      label="PDF ouverts"    value={num(usage.pdf_opens)}      sub="citations suivies" color="purple" />
        <KpiCard icon={<BuildingIcon />} label="Sociétés vues"  value={num(usage.company_selects)} sub="sélections latérale" color="teal" />
        <KpiCard icon={<LogoutIcon />}   label="Déconnexions"   value={num(usage.logouts)}         sub="fin de session" color="blue" />
        <KpiCard icon={<ErrorIcon />}    label="Erreurs"        value={num(usage.errors)}         sub="événements signalés" color="rose" />
      </div>

      <div className="adash-charts-row">
        <BarListCard title="Sociétés les plus consultées" rows={usage.top_companies_viewed} />
        <BarListCard title="PDF les plus ouverts" rows={usage.top_pdfs_opened} />
      </div>

      <div className="adash-charts-row">
        <ErrorKindsCard rows={usage.error_kinds || []} total={usage.errors || 0} />
      </div>
    </>
  );
}

function ErrorKindsCard({ rows, total }) {
  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">Types d'erreurs</span>
        <span className="adash-card-sub">{total} au total</span>
      </div>
      <div className="adash-devices">
        {rows.length === 0 && <div className="adash-empty">Aucune erreur enregistrée.</div>}
        {rows.map(([kind, count]) => (
          <div key={kind} className="adash-device-row adash-geo-row">
            <div className="adash-device-label">
              <span className="adash-list-name" title={kind}>{kind}</span>
            </div>
            <div className="adash-device-stats">
              <span className="adash-device-count">{num(count)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── Composants partagés ──────────────────────────────────────────────────── */

function DistributionCard({ title, rows = [] }) {
  const total = rows.reduce((s, r) => s + r.count, 0);
  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">{title}</span>
        <span className="adash-card-sub">{num(total)} événements</span>
      </div>
      <div className="adash-devices">
        {rows.length === 0 && <div className="adash-empty">Aucune donnée</div>}
        {rows.map((r) => {
          const pct = total > 0 ? Math.round((r.count / total) * 100) : 0;
          return (
            <div key={r.name} className="adash-device-row adash-geo-row">
              <div className="adash-device-label">
                <span>{r.name}</span>
              </div>
              <div className="adash-device-stats">
                <span className="adash-device-count">{num(r.count)}</span>
                <span className="adash-device-pct">{pct}%</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

const TL_SERIES = [
  { key: "visits",    label: "Visites",       color: "var(--adash-blue)" },
  { key: "questions", label: "Questions",     color: "var(--adash-amber)" },
  { key: "logins",    label: "Connexions",    color: "var(--adash-teal)" },
  { key: "signups",   label: "Inscriptions",  color: "var(--adash-purple)" },
  { key: "pdf_opens", label: "PDF ouverts",   color: "var(--adash-rose)" },
];

function TimelineCard({ timeline }) {
  const [metric, setMetric] = useState("visits");
  const active = TL_SERIES.find((s) => s.key === metric);
  const max = Math.max(...timeline.map((d) => d[metric] || 0), 1);

  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">Activité — 30 derniers jours</span>
        <div className="adash-seg">
          {TL_SERIES.map((s) => (
            <button
              key={s.key}
              className={`adash-seg-btn ${metric === s.key ? "active" : ""}`}
              onClick={() => setMetric(s.key)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
      <div className="adash-spark">
        {timeline.map((d) => {
          const v = d[metric] || 0;
          return (
            <div key={d.date} className="adash-spark-col" title={`${d.date} — ${v} ${active.label.toLowerCase()}`}>
              <div className="adash-spark-track">
                <div
                  className="adash-spark-fill"
                  style={{ height: `${(v / max) * 100}%`, background: active.color }}
                />
              </div>
            </div>
          );
        })}
      </div>
      <div className="adash-spark-axis">
        <span>{timeline[0]?.date}</span>
        <span>{timeline[timeline.length - 1]?.date}</span>
      </div>
    </div>
  );
}

function TimeChart({ title, series, timeline }) {
  const [metric, setMetric] = useState(series[0]?.key);
  const active = series.find((s) => s.key === metric) || series[0];
  const max = Math.max(...timeline.map((d) => d[metric] || 0), 1);
  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">{title}</span>
        <div className="adash-seg">
          {series.map((s) => (
            <button
              key={s.key}
              className={`adash-seg-btn ${metric === s.key ? "active" : ""}`}
              onClick={() => setMetric(s.key)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
      <div className="adash-spark">
        {timeline.map((d) => {
          const v = d[metric] || 0;
          return (
            <div key={d.date} className="adash-spark-col" title={`${d.date} — ${v} ${active?.label?.toLowerCase()}`}>
              <div className="adash-spark-track">
                <div className="adash-spark-fill" style={{ height: `${(v / max) * 100}%`, background: active?.color }} />
              </div>
            </div>
          );
        })}
      </div>
      <div className="adash-spark-axis">
        <span>{timeline[0]?.date}</span>
        <span>{timeline[timeline.length - 1]?.date}</span>
      </div>
    </div>
  );
}

const HOUR_SERIES = [
  { key: "visits",        label: "Visites",        color: "var(--adash-blue)" },
  { key: "questions",     label: "Questions",      color: "var(--adash-amber)" },
  { key: "failed_logins", label: "Échecs connexion", color: "var(--adash-rose)" },
];

function HourHeatmap({ hours }) {
  if (!hours) return null;
  const [metric, setMetric] = useState("visits");
  const values = hours[metric] || [];
  const max = Math.max(...values, 1);

  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">Activité par heure (UTC)</span>
        <div className="adash-seg">
          {HOUR_SERIES.map((s) => (
            <button
              key={s.key}
              className={`adash-seg-btn ${metric === s.key ? "active" : ""}`}
              onClick={() => setMetric(s.key)}
            >
              {s.label}
            </button>
          ))}
        </div>
      </div>
      <div className="adash-heat">
        {values.map((v, h) => (
          <div
            key={h}
            className="adash-heat-cell"
            title={`${String(h).padStart(2, "0")}:00 UTC — ${v}`}
            style={{
              background: v === 0 ? "rgba(255,255,255,.03)" : undefined,
              opacity: v === 0 ? 1 : 0.18 + (v / max) * 0.82,
            }}
          >
            <span className="adash-heat-h">{h}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function LocationsCard({ countries = [], cities = [] }) {
  const total = countries.reduce((s, c) => s + c.visitors, 0);

  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">Localisations</span>
        <span className="adash-card-sub">
          {total} {total === 1 ? "visiteur" : "visiteurs"} localisés
        </span>
      </div>
      {total === 0 && cities.length === 0 ? (
        <div className="adash-empty">Aucune donnée de localisation pour le moment.</div>
      ) : (
        <div className="adash-geo-grid">
          <div>
            <div className="adash-geo-heading">Par pays</div>
            <div className="adash-devices">
              {countries.length === 0 && <div className="adash-empty">Inconnu</div>}
              {countries.map((c) => {
                const pct = total > 0 ? Math.round((c.visitors / total) * 100) : 0;
                return (
                  <div key={c.country_code || c.country} className="adash-device-row">
                    <div className="adash-device-label">
                      <span className="adash-flag">{flagOf(c.country_code)}</span>
                      <span>{c.country}</span>
                    </div>
                    <div className="adash-device-bar-wrap">
                      <div
                        className="adash-device-bar-fill"
                        style={{ width: `${pct}%`, background: "var(--adash-blue)" }}
                      />
                    </div>
                    <div className="adash-device-stats">
                      {c.demo_visitors > 0 && (
                        <span className="adash-device-count">{c.demo_visitors} démo</span>
                      )}
                      <span className="adash-device-count">{num(c.visitors)}</span>
                      <span className="adash-device-pct">{pct}%</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          <div>
            <div className="adash-geo-heading">Villes principales</div>
            <div className="adash-devices">
              {cities.length === 0 && <div className="adash-empty">Inconnu</div>}
              {cities.map((c) => (
                <div key={`${c.city}-${c.country_code}`} className="adash-device-row adash-geo-row">
                  <div className="adash-device-label">
                    <span className="adash-flag">{flagOf(c.country_code)}</span>
                    <span>{c.city}</span>
                    <span className="adash-geo-sub">{c.country}</span>
                  </div>
                  <div className="adash-device-stats">
                    <span className="adash-device-count">{num(c.visitors)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function TopListsCard({ usage }) {
  const columns = [
    { title: "Sociétés consultées", rows: toPairs(usage.top_companies_viewed) },
    { title: "PDF ouverts",         rows: toPairs(usage.top_pdfs_opened) },
    { title: "Types d'erreurs",     rows: toPairs(usage.error_kinds) },
  ];
  if (!columns.some((c) => c.rows.length)) return null;

  return (
    <div className="adash-charts-row">
      {columns.map((col) => (
        <div key={col.title} className="adash-card">
          <div className="adash-card-header">
            <span className="adash-card-title">{col.title}</span>
          </div>
          <div className="adash-devices">
            {col.rows.length === 0 && <div className="adash-empty">Aucune donnée</div>}
            {col.rows.map(([name, count]) => (
              <div key={name} className="adash-device-row adash-geo-row">
                <div className="adash-device-label">
                  <span className="adash-list-name" title={name}>{name}</span>
                </div>
                <div className="adash-device-stats">
                  <span className="adash-device-count">{num(count)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function BarListCard({ title, rows = [], wide = false }) {
  const pairs = toPairs(rows);
  const max = Math.max(...pairs.map((r) => r[1]), 1);
  return (
    <div className={`adash-card ${wide ? "adash-card-wide" : ""}`}>
      <div className="adash-card-header">
        <span className="adash-card-title">{title}</span>
      </div>
      <div className="adash-devices">
        {pairs.length === 0 && <div className="adash-empty">Aucune donnée</div>}
        {pairs.map(([name, count]) => (
          <div key={name} className="adash-device-row">
            <div className="adash-device-label">
              <span className="adash-list-name" title={name}>{name}</span>
            </div>
            <div className="adash-device-bar-wrap">
              <div
                className="adash-device-bar-fill"
                style={{ width: `${(count / max) * 100}%`, background: "var(--adash-amber)" }}
              />
            </div>
            <div className="adash-device-stats">
              <span className="adash-device-count">{num(count)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function QuestionTable({ rows }) {
  if (!rows || rows.length === 0) return <div className="adash-empty">Aucune question enregistrée pour le moment.</div>;
  return (
    <div className="adash-table-wrap">
      <table className="adash-table">
        <thead>
          <tr>
            <th>Quand</th>
            <th>Question</th>
            <th>Périmètre</th>
            <th>Rôle</th>
            <th>Localisation</th>
            <th>IP</th>
            <th className="adash-num">Temps</th>
            <th className="adash-num">Src</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={`${r.ip_hash}-${r.ts}-${i}`}>
              <td className="adash-cell-muted">{timeOnly(r.ts)}</td>
              <td className="adash-question">{r.question || "—"}</td>
              <td className="adash-cell-muted">
                {r.company || "tous les rapports"}
                {r.year ? ` · ${r.year}` : ""}
              </td>
              <td>
                {r.role ? (
                  <span className={`adash-chip ${r.role === "admin" ? "adash-chip-demo" : "adash-chip-desktop"}`}>
                    {r.role}
                  </span>
                ) : (
                  <span className="adash-cell-muted">—</span>
                )}
              </td>
              <td>{r.location}</td>
              <td><code className="adash-ip">{r.ip || "—"}</code></td>
              <td className="adash-num">{formatMs(r.latency_ms)}</td>
              <td className="adash-num">{r.sources ?? 0}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function VisitorsTable({ visitors }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("last_seen");
  const [expanded, setExpanded] = useState(null);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = visitors;
    if (q) {
      list = list.filter((v) =>
        [v.ip, v.location, v.isp, v.browser, v.os, v.role].some((val) =>
          String(val || "").toLowerCase().includes(q)
        )
      );
    }
    const sorted = [...list].sort((a, b) => {
      if (sort === "questions") return (b.questions || 0) - (a.questions || 0);
      if (sort === "failures") return (b.logins_fail || 0) - (a.logins_fail || 0);
      if (sort === "events")   return (b.total_events || 0) - (a.total_events || 0);
      return String(b.last_seen || "").localeCompare(String(a.last_seen || ""));
    });
    return sorted;
  }, [visitors, query, sort]);

  if (!visitors || visitors.length === 0) {
    return <div className="adash-card"><div className="adash-empty">Aucune donnée visiteur pour le moment.</div></div>;
  }

  return (
    <div className="adash-card">
      <div className="adash-card-header">
        <span className="adash-card-title">Visiteurs — IP &amp; activité</span>
        <div className="adash-search">
          <input
            className="adash-search-input"
            placeholder="Filtrer IP, ville, FAI, navigateur…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <select
            className="adash-select"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="last_seen">Plus récents</option>
            <option value="questions">Plus de questions</option>
            <option value="failures">Plus d'échecs</option>
            <option value="events">Plus d'événements</option>
          </select>
        </div>
      </div>
      <div className="adash-card-sub adash-count-note">
        {rows.length} sur {visitors.length} IP uniques
      </div>
      <div className="adash-table-wrap">
        <table className="adash-table">
          <thead>
            <tr>
              <th>Localisation</th>
              <th>Adresse IP</th>
              <th>FAI</th>
              <th>Client</th>
              <th>Appareil</th>
              <th>Compte</th>
              <th className="adash-num">Visites</th>
              <th className="adash-num">Conn.</th>
              <th className="adash-num">Échecs</th>
              <th className="adash-num">Qs</th>
              <th className="adash-num">PDF</th>
              <th className="adash-num">Cos</th>
              <th>Période</th>
              <th>Vu le</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((v) => (
              <React.Fragment key={v.ip_hash}>
                <tr
                  className="adash-clickable"
                  onClick={() => setExpanded(expanded === v.ip_hash ? null : v.ip_hash)}
                >
                  <td>
                    <span className="adash-flag">{flagOf(v.country_code)}</span>
                    <span className="adash-loc">{v.location}</span>
                  </td>
                  <td><code className="adash-ip">{v.ip || "—"}</code></td>
                  <td className="adash-cell-muted adash-clip">{v.isp || "—"}</td>
                  <td className="adash-cell-muted adash-clip" title={`${v.browser || "?"} / ${v.os || "?"}`}>
                    {v.browser || "?"}{v.os ? ` · ${v.os}` : ""}
                  </td>
                  <td>
                    <span className={`adash-chip adash-chip-${v.device}`}>{v.device}</span>
                  </td>
                  <td>
                    {v.role ? (
                      <span className={`adash-chip ${v.role === "admin" ? "adash-chip-demo" : "adash-chip-desktop"}`}>
                        {v.role}
                      </span>
                    ) : (
                      <span className="adash-cell-muted">—</span>
                    )}
                  </td>
                  <td className="adash-num">{num(v.visits)}</td>
                  <td className="adash-num">{num(v.logins_ok ?? 0)}</td>
                  <td className={`adash-num ${v.logins_fail ? "adash-num-hot" : ""}`}>{num(v.logins_fail ?? 0)}</td>
                  <td className="adash-num">{num(v.questions)}</td>
                  <td className="adash-num">{num(v.pdf_opens)}</td>
                  <td className="adash-num">{num(v.companies_explored)}</td>
                  <td className="adash-cell-muted">{duration(v.first_seen, v.last_seen)}</td>
                  <td className="adash-cell-muted">{formatWhen(v.last_seen)}</td>
                </tr>
                {expanded === v.ip_hash && (
                  <tr className="adash-detail-row">
                    <td colSpan={14}>
                      <div className="adash-detail">
                        <div>
                          <span className="adash-detail-lbl">Première visite</span>
                          <span className="adash-detail-val">{formatWhen(v.first_seen)}</span>
                        </div>
                        <div>
                          <span className="adash-detail-lbl">Sessions</span>
                          <span className="adash-detail-val">{num(v.sessions)}</span>
                        </div>
                        <div>
                          <span className="adash-detail-lbl">Événements</span>
                          <span className="adash-detail-val">{num(v.total_events)}</span>
                        </div>
                        <div>
                          <span className="adash-detail-lbl">Latence moyenne</span>
                          <span className="adash-detail-val">{formatMs(v.avg_latency_ms)}</span>
                        </div>
                        <div>
                          <span className="adash-detail-lbl">Messages démo</span>
                          <span className="adash-detail-val">{num(v.demo_messages)}</span>
                        </div>
                        <div>
                          <span className="adash-detail-lbl">Fins de démo</span>
                          <span className="adash-detail-val">{num(v.demo_exhausted)}</span>
                        </div>
                      </div>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function KpiCard({ icon, label, value, sub, color }) {
  return (
    <div className={`adash-kpi-card adash-kpi-${color}`}>
      <div className="adash-kpi-icon">{icon}</div>
      <div className="adash-kpi-body">
        <div className="adash-kpi-value">{value ?? 0}</div>
        <div className="adash-kpi-label">{label}</div>
        <div className="adash-kpi-sub">{sub}</div>
      </div>
    </div>
  );
}

function BarChart({ data, color }) {
  if (!data || data.length === 0) return <div className="adash-empty">Aucune donnée</div>;
  const max = Math.max(...data.map((d) => d.count), 1);
  return (
    <div className="adash-barchart">
      {data.map((d) => (
        <div key={d.date} className="adash-bar-col">
          <div className="adash-bar-tooltip">{num(d.count)}</div>
          <div className="adash-bar-track">
            <div
              className="adash-bar-fill"
              style={{ height: `${(d.count / max) * 100}%`, background: color }}
            />
          </div>
          <div className="adash-bar-label">{d.day}</div>
        </div>
      ))}
    </div>
  );
}

function AbuseInsight({ exhausted, logins }) {
  const bypassRate = logins > 0 ? Math.round((exhausted / logins) * 100) : 0;
  const suspected = Math.max(0, exhausted - logins);
  return (
    <div className="adash-card adash-abuse-card">
      <div className="adash-card-header">
        <span className="adash-card-title">
          <span className="adash-abuse-dot" />
          Détection de contournement navigateur
        </span>
        <span className="adash-card-sub">analyse de la limite démo</span>
      </div>
      <div className="adash-abuse-grid">
        <div className="adash-abuse-stat">
          <span className="adash-abuse-val">{num(exhausted)}</span>
          <span className="adash-abuse-lbl">Fois limite atteinte</span>
        </div>
        <div className="adash-abuse-stat">
          <span className="adash-abuse-val">{num(logins)}</span>
          <span className="adash-abuse-lbl">Connexions démo</span>
        </div>
        <div className="adash-abuse-stat">
          <span className="adash-abuse-val adash-abuse-highlight">{bypassRate}%</span>
          <span className="adash-abuse-lbl">Taux d'épuisement</span>
        </div>
        <div className="adash-abuse-stat">
          <span className="adash-abuse-val adash-abuse-highlight">{num(suspected)}</span>
          <span className="adash-abuse-lbl">Contournements probables</span>
        </div>
      </div>
      <p className="adash-abuse-note">
        « Contournements probables » = fois où la limite a été atteinte au-delà du nombre de
        connexions démo distinctes — chaque écart laisse penser qu'un nouveau navigateur /
        fenêtre privée a été utilisé pour réinitialiser le compteur local.
      </p>
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div className="adash-skeleton">
      <div className="adash-kpi-grid">
        {[0,1,2,3,4,5,6,7].map((i) => (
          <div key={i} className="adash-kpi-card adash-skeleton-card">
            <div className="sk-line sk-line-sm" />
            <div className="sk-line sk-line-lg" />
            <div className="sk-line sk-line-xs" />
          </div>
        ))}
      </div>
      <div className="adash-charts-row">
        <div className="adash-card adash-card-wide adash-skeleton-card" style={{height: 180}} />
        <div className="adash-card adash-card-wide adash-skeleton-card" style={{height: 180}} />
      </div>
      <div className="adash-card adash-skeleton-card" style={{height: 140}} />
    </div>
  );
}

function ErrorState({ message, onRetry }) {
  return (
    <div className="adash-error">
      <svg viewBox="0 0 20 20" fill="none" width="32" height="32">
        <circle cx="10" cy="10" r="8.5" stroke="currentColor" strokeWidth="1.3"/>
        <path d="M10 6v5M10 13.5h.01" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
      </svg>
      <p>{message}</p>
      <button className="adash-retry-btn" onClick={onRetry}>Réessayer</button>
    </div>
  );
}

/* ── Icônes ────────────────────────────────────────────────────────────────── */

function GaugeIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" width="18" height="18">
      <path d="M3 12a7 7 0 0 1 14 0" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      <path d="M10 12l3-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      <circle cx="10" cy="13" r="1.4" fill="currentColor"/>
    </svg>
  );
}

function EyeIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <ellipse cx="8" cy="8" rx="6" ry="3.8" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="8" cy="8" r="1.8" fill="currentColor"/>
    </svg>
  );
}

function UsersIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="6" cy="5" r="2.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M1 14c0-2.8 2.2-5 5-5s5 2.2 5 5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <circle cx="11.5" cy="4.5" r="2" stroke="currentColor" strokeWidth="1.2"/>
      <path d="M13.5 13c0-1.9-1-3.5-2.5-4.3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function GlobeIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="8" cy="8" r="6.2" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M1.8 8h12.4M8 1.8c1.6 1.7 2.4 3.9 2.4 6.2S9.6 12.5 8 14.2C6.4 12.5 5.6 10.3 5.6 8s.8-4.5 2.4-6.2z" stroke="currentColor" strokeWidth="1.1"/>
    </svg>
  );
}

function UserIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="8" cy="5" r="2.8" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M2 14c0-3.3 2.7-6 6-6s6 2.7 6 6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function ChatIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <path d="M2 3a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1H5l-3 2V3z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M5 6h6M5 9h4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function DocIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <path d="M9 1.5H4.5A1.5 1.5 0 0 0 3 3v10a1.5 1.5 0 0 0 1.5 1.5h7A1.5 1.5 0 0 0 13 13V5.5L9 1.5z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M9 1.5V5a.5.5 0 0 0 .5.5H13M5.5 9h5M5.5 11.5h3" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function BuildingIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <path d="M2 14V3.5A1 1 0 0 1 3 2.5h5a1 1 0 0 1 1 1V14M9 7h3a1 1 0 0 1 1 1v6M1.5 14h13" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M4.5 5.5h1.5M4.5 8.5h1.5M4.5 11.5h1.5" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function ErrorIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <path d="M8 2.2 14.3 13H1.7L8 2.2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round"/>
      <path d="M8 6.5v3M8 11.5h.01" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );
}

function CheckIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="8" cy="8" r="6.4" stroke="currentColor" strokeWidth="1.3"/>
      <path d="m5.2 8.2 2 2 3.6-4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function LockIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <rect x="3" y="7" width="10" height="7" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M5.5 7V5a2.5 2.5 0 0 1 5 0v2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function AlertIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="8" cy="8" r="6.4" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 5v3.5M8 11h.01" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <circle cx="8" cy="8" r="6.4" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 4.5V8l2.4 1.6" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function LogoutIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="16" height="16">
      <path d="M6 2H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3M10 11l3-3-3-3M13 8H6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function DesktopIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
      <rect x="1" y="2" width="14" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M5.5 14h5M8 11v3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function MobileIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
      <rect x="4" y="1" width="8" height="14" rx="2" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="8" cy="12.5" r=".8" fill="currentColor"/>
    </svg>
  );
}

function TabletIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" width="14" height="14">
      <rect x="2" y="1" width="12" height="14" rx="2" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="8" cy="12.5" r=".8" fill="currentColor"/>
    </svg>
  );
}