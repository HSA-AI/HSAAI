"use client";
import { Card } from "@/components/ui/card";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

const data = [
  { d: "السبت", v: 20 },
  { d: "الأحد", v: 35 },
  { d: "الاثنين", v: 44 },
  { d: "الثلاثاء", v: 60 },
  { d: "الأربعاء", v: 72 },
  { d: "الخميس", v: 90 },
];

/** HSAAI chart theme: gold line + soft gold fill, unified borders */
export function AiUsageChart() {
  return (
    <Card>
      <h2 className="mb-4 text-lg font-bold text-hsa-black">AI Usage — استخدام الذكاء الاصطناعي</h2>
      <div className="h-72" dir="ltr">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="hsaGoldFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#F4C430" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#F4C430" stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#E7E5E4" />
            <XAxis dataKey="d" tick={{ fill: "#64748B", fontSize: 12 }} axisLine={{ stroke: "#E7E5E4" }} tickLine={false} />
            <YAxis tick={{ fill: "#64748B", fontSize: 12 }} axisLine={false} tickLine={false} width={36} />
            <Tooltip
              contentStyle={{ borderRadius: 12, border: "1px solid #E7E5E4", boxShadow: "0 8px 25px rgba(17,17,17,.10)", fontFamily: "inherit" }}
              labelStyle={{ fontWeight: 700, color: "#111111" }}
            />
            <Area type="monotone" dataKey="v" name="Usage" stroke="#A67C00" strokeWidth={2.5} fill="url(#hsaGoldFill)" activeDot={{ r: 5, fill: "#F4C430", stroke: "#A67C00" }} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
