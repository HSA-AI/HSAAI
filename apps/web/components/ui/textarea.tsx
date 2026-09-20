import * as React from "react";
import { cn } from "@/lib/utils";

export function Textarea({ className, ...props }: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "w-full rounded-xl border border-hsa-border bg-white px-3.5 py-2.5 text-sm text-hsa-black",
        "placeholder:text-hsa-secondary/70 transition focus:border-hsa-gold focus:outline-none focus:ring-2 focus:ring-hsa-yellow/30",
        className,
      )}
      {...props}
    />
  );
}
