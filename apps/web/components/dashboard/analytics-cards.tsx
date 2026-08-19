import { Card } from "@/components/ui/card";
const cards=[['Tokens Today','125K'],['Active Agents','5'],['Workspaces','3'],['Avg Latency','840ms']];
export function AnalyticsCards(){ return <div className="grid gap-4 md:grid-cols-4">{cards.map(([k,v])=><Card key={k}><p className="text-sm text-slate-500">{k}</p><p className="mt-2 text-3xl font-bold">{v}</p></Card>)}</div> }
