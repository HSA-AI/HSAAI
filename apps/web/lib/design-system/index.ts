/**
 * HSAAI Design System — Barrel Export
 * ═══════════════════════════════════════════════════════════════════════
 *
 * Import any design system component from one place:
 *   import { Button, Card, Badge, Input } from "@/lib/design-system";
 *
 * ═══════════════════════════════════════════════════════════════════════
 */

// Tokens (for programmatic access)
export { tokens } from "./tokens";

// Components
export { Button, type ButtonProps, buttonVariants } from "./button";
export {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardBody,
  CardFooter,
  type CardProps,
  cardVariants,
} from "./card";
export { Badge, type BadgeProps, badgeVariants } from "./badge";
export { Input, Textarea, Select, type InputProps, type TextareaProps, type SelectProps, inputVariants } from "./input";

// Typography
export {
  Display,
  DisplaySm,
  H1,
  H2,
  H3,
  H4,
  Body,
  BodyLarge,
  BodySmall,
  Caption,
  Label,
  Code,
  Eyebrow,
  PageTitle,
  SectionTitle,
  CardTitle as TypographyCardTitle,
} from "./typography";

// Layout
export { PageHero, type PageHeroProps } from "./page-hero";

// ─── Enhancement Components (v6.1 Polish) ─────────────────────
export { Skeleton } from "./skeleton";
export { Toast, ToastContainer, useToast } from "./toast";
export { Breadcrumb, BreadcrumbItem } from "./breadcrumb";
export { Pagination } from "./pagination";
export { EmptyState } from "./empty-state";
