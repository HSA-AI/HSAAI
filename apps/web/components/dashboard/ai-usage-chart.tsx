"use client";
import { Card } from "@/components/ui/card"; import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
const data=[{d:'Sat',v:20},{d:'Sun',v:35},{d:'Mon',v:44},{d:'Tue',v:60},{d:'Wed',v:72},{d:'Thu',v:90}];
export function AiUsageChart(){ return <Card><h2 className="mb-4 text-lg font-semibold">AI Usage</h2><div className="h-72"><ResponsiveContainer width="100%" height="100%"><LineChart data={data}><XAxis dataKey="d"/><YAxis/><Tooltip/><Line type="monotone" dataKey="v" stroke="currentColor"/></LineChart></ResponsiveContainer></div></Card> }
