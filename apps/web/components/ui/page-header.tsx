import * as React from "react";

/**
 * HSAAI Page Header — unified page intro: eyebrow + title + description + actions
 */
export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0 max-w-3xl">
        {eyebrow ? (
          <p className="text-xs font-semibold uppercase tracking-widest text-hsa-gold">{eyebrow}</p>
        ) : null}
        <h1 className="mt-1 text-h1 font-bold text-hsa-black">{title}</h1>
        {description ? (
          <p className="mt-2 text-sm leading-7 text-hsa-secondary">{description}</p>
        ) : null}
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div> : null}
    </header>
  );
}
