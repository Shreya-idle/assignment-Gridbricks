import { ChartLineUp } from "@phosphor-icons/react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { IntervalComparison } from "./types";

const timeFormatter = new Intl.DateTimeFormat("en-GB", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
  timeZone: "UTC",
});

export function ForecastChart({ comparisons }: { comparisons: IntervalComparison[] }) {
  const points = [...comparisons]
    .sort((a, b) => Date.parse(a.start_time) - Date.parse(b.start_time))
    .map((item) => ({
      time: Date.parse(item.start_time),
      actual: item.actual_generation,
      forecast: item.forecast_generation,
    }));

  return (
    <section className="chart-panel" aria-labelledby="chart-title">
      <div className="panel-heading chart-heading">
        <div><h2 id="chart-title">Actual vs forecast</h2><p>Matched delivery intervals · time series</p></div>
        <span className="unit-chip">MW</span>
      </div>
      {points.length ? (
        <div className="chart-wrap" role="img" aria-label="Line chart comparing actual and forecast generation over time">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 16, right: 24, left: 0, bottom: 8 }}>
              <CartesianGrid stroke="#e7edef" vertical={false} />
              <XAxis
                dataKey="time"
                type="number"
                domain={["dataMin", "dataMax"]}
                tickFormatter={(value) => timeFormatter.format(value)}
                tick={{ fill: "#6b7f89", fontSize: 11 }}
                axisLine={{ stroke: "#dce5e7" }}
                tickLine={false}
                minTickGap={42}
              />
              <YAxis
                tick={{ fill: "#6b7f89", fontSize: 11 }}
                axisLine={false}
                tickLine={false}
                width={48}
              />
              <Tooltip
                labelFormatter={(value) => `${timeFormatter.format(Number(value))} UTC`}
                contentStyle={{ border: "1px solid #dce5e7", borderRadius: 8, boxShadow: "0 8px 22px rgba(8,43,58,.08)" }}
              />
              <Legend iconType="circle" iconSize={7} />
              <Line name="Actual generation" dataKey="actual" stroke="#0f8f83" strokeWidth={2.2} dot={false} activeDot={{ r: 4 }} />
              <Line name="Forecast generation" dataKey="forecast" stroke="#5c80ff" strokeWidth={2.2} dot={false} activeDot={{ r: 4 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="chart-empty">
          <span aria-hidden="true"><ChartLineUp /></span>
          <strong>No chart data available</strong>
          <p>Matched interval records will appear here when the backend returns analysis data.</p>
        </div>
      )}
    </section>
  );
}
