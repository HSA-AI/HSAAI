/**
 * HSAAI Design System — Input Component
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Unified form input system.
 * Replaces all 7+ ad-hoc input styles.
 *
 * Features:
 *   - Consistent border, radius, padding across all inputs
 *   - Gold focus ring (2px solid, 2px offset)
 *   - Error state with danger color
 *   - Disabled state with reduced opacity
 *   - Optional left/right icon slots
 *   - Proper label association for screen readers
 *
 * Sub-components: Input, Textarea, Select, Label, FormField
 *
 * ═══════════════════════════════════════════════════════════════════════
 */
import { forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// ─── Input ──────────────────────────────────────────────────────────────
const inputVariants = cva(
  [
    "w-full",
    "font-sans text-body text-text-primary",
    "bg-surface",
    "border border-border",
    "rounded-lg",
    "px-3 py-2.5",
    "transition-colors duration-fast",
    "placeholder:text-text-muted",
    "focus:outline-none focus:border-primary-gold focus:ring-2 focus:ring-focus",
    "disabled:opacity-50 disabled:cursor-not-allowed",
    "aria-invalid:border-danger aria-invalid:ring-danger/20",
  ],
  {
    variants: {
      size: {
        sm: "h-9 text-body-sm px-2.5 py-1.5 rounded-md",
        md: "h-10 text-body px-3 py-2.5 rounded-lg",
        lg: "h-12 text-body-lg px-4 py-3 rounded-xl",
      },
      error: {
        true: "border-danger focus:border-danger focus:ring-danger/20",
        false: "",
      },
    },
    defaultVariants: {
      size: "md",
      error: false,
    },
  }
);

export interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "size">,
    Omit<VariantProps<typeof inputVariants>, "error"> {
  label?: string;
  error?: string;
  hint?: string;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, size, error, label, hint, leftIcon, rightIcon, id, ...props }, ref) => {
    const inputId = id || props.name;
    const hasError = Boolean(error);

    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={inputId}
            className="text-body-sm font-semibold text-text-secondary"
          >
            {label}
          </label>
        )}
        <div className="relative flex items-center">
          {leftIcon && (
            <span className="absolute left-3 flex items-center text-text-muted pointer-events-none" aria-hidden="true">
              {leftIcon}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            className={cn(
              inputVariants({ size, error: hasError }),
              leftIcon && "pl-10",
              rightIcon && "pr-10",
              className
            )}
            aria-invalid={hasError || undefined}
            aria-describedby={hint ? `${inputId}-hint` : undefined}
            {...props}
          />
          {rightIcon && (
            <span className="absolute right-3 flex items-center text-text-muted" aria-hidden="true">
              {rightIcon}
            </span>
          )}
        </div>
        {hint && !error && (
          <p id={`${inputId}-hint`} className="text-caption text-text-muted">
            {hint}
          </p>
        )}
        {error && (
          <p className="text-caption text-danger" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
);
Input.displayName = "Input";

// ─── Textarea ───────────────────────────────────────────────────────────
export interface TextareaProps
  extends Omit<React.TextareaHTMLAttributes<HTMLTextAreaElement>, "size">,
    Omit<VariantProps<typeof inputVariants>, "error"> {
  label?: string;
  error?: string;
  hint?: string;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ className, size, error, label, hint, id, ...props }, ref) => {
    const textareaId = id || props.name;
    const hasError = Boolean(error);
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={textareaId}
            className="text-body-sm font-semibold text-text-secondary"
          >
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          className={cn(
            inputVariants({ size, error: hasError }),
            "min-h-[5rem] resize-y py-2.5",
            className
          )}
          aria-invalid={hasError || undefined}
          {...props}
        />
        {hint && !error && (
          <p className="text-caption text-text-muted">{hint}</p>
        )}
        {error && (
          <p className="text-caption text-danger" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
);
Textarea.displayName = "Textarea";

// ─── Select ─────────────────────────────────────────────────────────────
export interface SelectProps
  extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, "size">,
    Omit<VariantProps<typeof inputVariants>, "error"> {
  label?: string;
  error?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ className, size, error, label, id, children, ...props }, ref) => {
    const selectId = id || props.name;
    const hasError = Boolean(error);
    return (
      <div className="flex flex-col gap-1.5">
        {label && (
          <label
            htmlFor={selectId}
            className="text-body-sm font-semibold text-text-secondary"
          >
            {label}
          </label>
        )}
        <select
          ref={ref}
          id={selectId}
          className={cn(
            inputVariants({ size, error: hasError }),
            "appearance-none bg-no-repeat pr-10",
            className
          )}
          style={{
            backgroundImage:
              "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' fill='none' viewBox='0 0 24 24' stroke='%2378716C'%3E%3Cpath stroke-linecap='round' stroke-linejoin='round' stroke-width='2' d='M19 9l-7 7-7-7'/%3E%3C/svg%3E\")",
            backgroundPosition: "right 0.75rem center",
            backgroundSize: "1.25rem",
          }}
          aria-invalid={hasError || undefined}
          {...props}
        >
          {children}
        </select>
        {error && (
          <p className="text-caption text-danger" role="alert">
            {error}
          </p>
        )}
      </div>
    );
  }
);
Select.displayName = "Select";

export { inputVariants };
