import { KpiCard } from "@/components/ui/kpi-card";
import { Bot, Clock3, Database, UsersRound } from "lucide-react";

const cards = [
  { key: "Tokens Today", value: "125K", icon: <Database size={20} />, hint: "استهلاك التوكنات اليوم" },
  { key: "Active Agents", value: "5", icon: <Bot size={20} />, hint: "وكلاء نشطون الآن" },
  { key: "Workspaces", value: "3", icon: <UsersRound size={20} />, hint: "مساحات عمل مفعّلة" },
  { key: "Avg Latency", value: "840ms", icon: <Clock3 size={20} />, hint: "متوسط زمن الاستجابة" },
];

export function AnalyticsCards() {
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {cards.map((c) => (
        <KpiCard key={c.key} label={c.key} value={c.value} icon={c.icon} hint={c.hint} />
      ))}
    </div>
  );
}
