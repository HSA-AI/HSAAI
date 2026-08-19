import * as React from "react";
import { cn } from "@/lib/utils";
export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) { return <input className={cn("w-full rounded-xl border bg-white px-3 py-2 outline-none focus:ring-2 focus:ring-slate-400 dark:border-slate-800 dark:bg-slate-900", className)} {...props} />; }
