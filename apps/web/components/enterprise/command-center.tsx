export function CommandCenter() {
  const cards = [
    ["Internal AI", "Local LLM active, external providers blocked"],
    ["Knowledge Brain", "Qdrant RAG with workspace isolation"],
    ["Governance", "RBAC, audit logs, retention policies"],
    ["Operations", "Monitoring, alerts, load tests, backups"],
  ];
  return (
    <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {cards.map(([title, body]) => (
        <div key={title} className="rounded-2xl border bg-surface/70 p-5 shadow-sm backdrop-blur">
          <div className="text-sm text-text-muted">HSAAI Enterprise</div>
          <h3 className="mt-2 text-xl font-semibold tracking-tight">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-text-muted">{body}</p>
        </div>
      ))}
    </section>
  );
}
