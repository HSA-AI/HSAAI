export function GraphSearchBar({ value, onChange, onSearch }: { value: string; onChange: (value: string) => void; onSearch: () => void }) {
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-hsa-yellow/20 bg-white p-4 shadow-sm dark:bg-slate-950 md:flex-row">
      <input value={value} onChange={(event) => onChange(event.target.value)} placeholder="ابحث داخل الرسم المعرفي: SAP, Policy, Agent..." className="min-h-12 flex-1 rounded-xl border border-slate-200 bg-transparent px-4 outline-none focus:border-hsa-yellow dark:border-slate-700" />
      <button onClick={onSearch} className="rounded-xl bg-hsa-yellow px-5 py-3 font-black text-hsa-black">بحث Graph</button>
    </div>
  );
}
