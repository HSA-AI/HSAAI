import Link from "next/link";

export function Breadcrumb({ items }: { items: { label: string; href?: string }[] }) {
  return (
    <nav className="ds-breadcrumb" aria-label="مسار التنقل">
      {items.map((item, i) => (
        <span key={i} className="flex items-center gap-2">
          {item.href ? <Link href={item.href}>{item.label}</Link> : <span aria-current="page">{item.label}</span>}
          {i < items.length - 1 && <span className="ds-breadcrumb-separator">/</span>}
        </span>
      ))}
    </nav>
  );
}

export function BreadcrumbItem({ label, href }: { label: string; href?: string }) {
  return href ? <Link href={href}>{label}</Link> : <span aria-current="page">{label}</span>;
}
