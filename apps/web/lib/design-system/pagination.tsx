"use client";

export function Pagination({ currentPage, totalPages, onPageChange }: {
  currentPage: number; totalPages: number; onPageChange: (page: number) => void;
}) {
  return (
    <nav className="ds-pagination" aria-label="ترقيم الصفحات">
      <button className="ds-pagination-btn" onClick={() => onPageChange(currentPage - 1)} disabled={currentPage <= 1} aria-label="السابق">‹</button>
      {Array.from({ length: Math.min(totalPages, 7) }).map((_, i) => {
        const page = i + 1;
        return <button key={page} className={`ds-pagination-btn ${page === currentPage ? 'active' : ''}`} onClick={() => onPageChange(page)}>{page}</button>;
      })}
      <button className="ds-pagination-btn" onClick={() => onPageChange(currentPage + 1)} disabled={currentPage >= totalPages} aria-label="التالي">›</button>
    </nav>
  );
}
