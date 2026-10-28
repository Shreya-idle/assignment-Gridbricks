import type { ReactNode } from "react";
import {
  ChartLineUp,
  Database,
  Gauge,
  Info,
  SlidersHorizontal,
  Target,
  TrendUp,
  Wind,
} from "@phosphor-icons/react";

export function Brand() {
  return (
    <div className="brand" aria-label="WindSight — Energy Intelligence">
      <span className="brand-mark" aria-hidden="true"><Wind weight="bold" /></span>
      <span><strong>WindSight</strong><small>ENERGY INTELLIGENCE</small></span>
    </div>
  );
}

export const navigation = [
  { label: "Overview", icon: Gauge, path: "/overview" },
  { label: "Forecast Analysis", icon: ChartLineUp, path: "/forecast-analysis" },
  { label: "Forecast Accuracy", icon: Target, path: "/forecast-accuracy" },
  { label: "Data Sources", icon: Database, path: "/data-sources" },
  { label: "Settings", icon: SlidersHorizontal, path: "/settings" },
];

interface MetricCardProps {
  label: string;
  value: number | null;
  detail: string;
  tone: "teal" | "blue" | "slate";
  icon: "wind" | "trend" | "target" | "chart";
  unit?: string;
}

const metricIcons = { wind: Wind, trend: TrendUp, target: Target, chart: ChartLineUp };

export function MetricCard({ label, value, detail, tone, icon, unit = "MW" }: MetricCardProps) {
  const Icon = metricIcons[icon];
  return (
    <article className="metric-card">
      <div className="metric-card__top">
        <span>{label}</span>
        <span className={`metric-icon metric-icon--${tone}`} aria-hidden="true"><Icon /></span>
      </div>
      <strong className="metric-value">{value === null ? "—" : value.toFixed(2)}</strong>
      <div className="metric-meta"><span>{unit}</span><small>{detail}</small></div>
    </article>
  );
}

export function Field({
  id,
  label,
  error,
  children,
  className = "",
}: {
  id: string;
  label: string;
  error?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`field ${className}`}>
      <label htmlFor={id}>{label}</label>
      {children}
      {error && <span id={`${id}-error`} className="field-error">{error}</span>}
    </div>
  );
}

export function InfoHint({ children }: { children: ReactNode }) {
  return <span className="info-hint"><Info aria-hidden="true" />{children}</span>;
}
