/** HSAAI Command Center — light enterprise cards with gold top accent */
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
        <div
          key={title}
          className="rounded-2xl border border-hsa-border border-t-hsa-yellow bg-white p-5 shadow-hsa-card transition-all duration-200 hover:-translate-y-1 hover:shadow-hsa-card-hover"
        >
          <div className="text-xs font-bold uppercase tracking-wide text-hsa-secondary">HSAAI Enterprise</div>
          <h3 className="mt-2 text-lg font-bold tracking-tight text-hsa-black">{title}</h3>
          <p className="mt-2 text-sm leading-6 text-hsa-secondary">{body}</p>
        </div>
      ))}
    </section>
  );
}
