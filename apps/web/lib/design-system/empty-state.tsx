export function EmptyState({ title = "لا توجد بيانات", description = "", icon }: {
  title?: string; description?: string; icon?: React.ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center">
      {icon && <div className="mb-4 text-text-muted">{icon}</div>}
      <h3 className="text-lg font-semibold text-text-primary">{title}</h3>
      {description && <p className="mt-2 text-sm text-text-muted max-w-sm">{description}</p>}
    </div>
  );
}
