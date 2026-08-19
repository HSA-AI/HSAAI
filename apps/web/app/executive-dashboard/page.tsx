const kpis = [{label:'طلبات AI',value:'68K',desc:'إجمالي الاستخدام'},{label:'مستخدمون نشطون',value:'3,240',desc:'داخل المؤسسة'},{label:'وثائق مفهرسة',value:'18,720',desc:'معرفة معتمدة'},{label:'ساعات موفرة',value:'4,280',desc:'تقدير تشغيلي'}]
const headers = ['المؤشر','القيمة','الدلالة']
const rows = [['نسبة إجابات من المعرفة','91%','اعتماد أعلى على مصادر المؤسسة'],['حوكمة الوثائق','98%','وثائق مصنفة ومراجعة'],['الصحة التشغيلية','97%','استقرار عام'],['إجراءات مؤتمتة','1,366','تحسن الكفاءة'],['تبني تقنية المعلومات','84%','أعلى الإدارات استخدامًا']]

export default function Page() {
  return (
    <main dir="rtl" className="min-h-screen bg-slate-950 text-white p-6">
      <section className="mx-auto max-w-7xl space-y-7">
        <div className="rounded-3xl border border-amber-400/20 bg-gradient-to-l from-slate-900 via-slate-950 to-black p-8 shadow-2xl">
          <span className="inline-flex rounded-full border border-amber-400/30 bg-amber-400/10 px-4 py-2 text-sm font-bold text-amber-300">HSAAI Enterprise Operations</span>
          <h1 className="mt-5 text-3xl font-black md:text-5xl">Executive Dashboard</h1>
          <p className="mt-4 max-w-4xl text-slate-300 leading-8">لوحة تنفيذية للإدارة العليا تعرض أثر HSAAI على الاستخدام، المعرفة، الأتمتة، الكفاءة، وتبني الإدارات للذكاء الاصطناعي.</p>
        </div>
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {kpis.map((item) => (
            <div key={item.label} className="rounded-2xl border border-slate-800 bg-slate-900/80 p-5">
              <p className="text-sm text-slate-400">{item.label}</p>
              <strong className="mt-2 block text-3xl text-amber-300">{item.value}</strong>
              <span className="mt-2 block text-sm text-slate-400">{item.desc}</span>
            </div>
          ))}
        </div>
        <section className="rounded-3xl border border-slate-800 bg-white p-6 text-slate-950">
          <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-2xl font-black">تفاصيل التشغيل</h2>
            <span className="rounded-full bg-emerald-100 px-4 py-2 text-sm font-bold text-emerald-700">Operational Ready</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full border-separate border-spacing-y-3 text-sm">
              <thead>
                <tr>{headers.map((h) => <th key={h} className="bg-slate-100 p-3 text-right">{h}</th>)}</tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>{r.map((c, j) => <td key={j} className="border-y border-slate-200 bg-slate-50 p-3">{c}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

      </section>
    </main>
  )
}
