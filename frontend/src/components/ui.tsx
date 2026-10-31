import type { ButtonHTMLAttributes, HTMLAttributes, ReactNode } from "react";
import { Link } from "react-router-dom";
import { cn } from "../lib/utils";

export function Card({
  className,
  ...props
}: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cn(
        "rounded-xl border border-[#e5d8c8] bg-paper shadow-panel",
        className,
      )}
      {...props}
    />
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-3xl">
        <p className="mb-2 text-[11px] font-bold uppercase tracking-[0.16em] text-brass">
          {eyebrow}
        </p>
        <h1 className="font-editorial text-[clamp(2rem,4vw,2.75rem)] font-medium leading-[1.05] tracking-[-0.02em] text-espresso">
          {title}
        </h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-ink">
          {description}
        </p>
      </div>
      {actions ? <div className="flex flex-wrap items-center gap-2">{actions}</div> : null}
    </div>
  );
}

export function Button({
  className,
  variant = "primary",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  const variants = {
    primary:
      "border-espresso bg-espresso text-white hover:bg-[#44342c] hover:border-[#44342c]",
    secondary:
      "border-[#d7c8b7] bg-paper text-espresso hover:border-brass hover:bg-[#fffaf3]",
    ghost:
      "border-transparent bg-transparent text-muted-ink hover:bg-[#f5ecdf] hover:text-espresso",
    danger:
      "border-[#d4aaa2] bg-[#fff7f4] text-oxblood hover:bg-[#f8e9e4]",
  };

  return (
    <button
      className={cn(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border px-3.5 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50",
        variants[variant],
        className,
      )}
      {...props}
    />
  );
}

export function LinkButton({
  to,
  children,
  className,
  variant = "secondary",
}: {
  to: string;
  children: ReactNode;
  className?: string;
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  const variants = {
    primary: "border-espresso bg-espresso text-white hover:bg-[#44342c]",
    secondary:
      "border-[#d7c8b7] bg-paper text-espresso hover:border-brass hover:bg-[#fffaf3]",
    ghost: "border-transparent bg-transparent text-muted-ink hover:bg-[#f5ecdf]",
    danger: "border-[#d4aaa2] bg-[#fff7f4] text-oxblood hover:bg-[#f8e9e4]",
  };

  return (
    <Link
      className={cn(
        "inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border px-3.5 py-2 text-sm font-semibold transition-colors",
        variants[variant],
        className,
      )}
      to={to}
    >
      {children}
    </Link>
  );
}

export function Badge({
  children,
  tone = "neutral",
  className,
}: {
  children: ReactNode;
  tone?: "neutral" | "danger" | "success" | "brass" | "blue";
  className?: string;
}) {
  const tones = {
    neutral: "border-[#e2d9cf] bg-[#f7f2eb] text-[#62574f]",
    danger: "border-[#e3c2bc] bg-[#fbefec] text-oxblood",
    success: "border-[#c9d8cb] bg-[#edf4ed] text-forest",
    brass: "border-[#e2cfad] bg-[#fbf2e2] text-[#76592a]",
    blue: "border-[#c8d6dd] bg-[#eef4f7] text-[#446575]",
  };

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-[0.08em]",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function ApiState({
  loading,
  error,
  empty,
  onRetry,
}: {
  loading: boolean;
  error: string | null;
  empty?: boolean;
  onRetry?: () => void;
}) {
  if (loading) {
    return (
      <p className="rounded-lg border border-[#e5d8c8] bg-paper p-4 text-xs text-muted-ink" role="status">
        Loading data from the backend…
      </p>
    );
  }
  if (error) {
    return (
      <div className="rounded-lg border border-[#e3c2bc] bg-[#fff7f4] p-4 text-xs text-oxblood" role="alert">
        <p>Backend request failed: {error}</p>
        {onRetry ? (
          <Button className="mt-3" variant="secondary" onClick={onRetry}>
            Retry request
          </Button>
        ) : null}
      </div>
    );
  }
  if (empty) {
    return (
      <p className="rounded-lg border border-[#e5d8c8] bg-paper p-4 text-xs text-muted-ink" role="status">
        The backend returned no records for this view.
      </p>
    );
  }
  return null;
}

export function SectionTitle({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
      <div>
        <h2 className="font-editorial text-xl font-semibold text-espresso">{title}</h2>
        {description ? (
          <p className="mt-1 text-xs leading-5 text-muted-ink">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}

export function MetricCard({
  label,
  value,
  note,
  icon,
  tone = "brass",
}: {
  label: string;
  value: string;
  note: string;
  icon: string;
  tone?: "brass" | "red" | "green" | "neutral";
}) {
  const tones = {
    brass: "bg-[#f8f0e2] text-[#856236]",
    red: "bg-[#f8ece8] text-oxblood",
    green: "bg-[#edf3ec] text-forest",
    neutral: "bg-[#f2eee8] text-[#645b54]",
  };

  return (
    <Card className="p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-medium text-muted-ink">{label}</p>
          <p className="mt-2 font-editorial text-3xl font-semibold leading-none text-espresso">
            {value}
          </p>
        </div>
        <span
          className={cn(
            "material-symbols-outlined grid h-10 w-10 place-items-center rounded-lg text-[20px]",
            tones[tone],
          )}
          aria-hidden="true"
        >
          {icon}
        </span>
      </div>
      <p className="mt-3 text-[11px] leading-4 text-muted-ink">{note}</p>
    </Card>
  );
}

export function EmptyState({
  title,
  description,
  icon = "inventory_2",
}: {
  title: string;
  description: string;
  icon?: string;
}) {
  return (
    <div className="flex flex-col items-center px-5 py-12 text-center">
      <span className="material-symbols-outlined mb-3 text-3xl text-[#9b8a78]" aria-hidden="true">
        {icon}
      </span>
      <h3 className="font-editorial text-lg font-semibold text-espresso">{title}</h3>
      <p className="mt-1 max-w-md text-sm leading-6 text-muted-ink">{description}</p>
    </div>
  );
}
