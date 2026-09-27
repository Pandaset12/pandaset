import { useEffect, useRef, useState } from "react";
import { pct, money } from "../../../quant/analytics";
export function LineChart({
  dates,
  series,
  secondary,
  label = "Portfolio",
  secondaryLabel = "U.S. market proxy (VTI)",
  currency = false,
  endValue = 1,
  compact = false,
}: {
  dates: string[];
  series: number[];
  secondary?: number[];
  label?: string;
  secondaryLabel?: string;
  currency?: boolean;
  endValue?: number;
  compact?: boolean;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const container = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(760);
  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => {
      setWidth(Math.max(240, Math.round(entry.contentRect.width)));
    });
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  const height = compact ? 205 : 256,
    pad = { top: 20, bottom: 30, left: 8, right: 61 };
  const all = [...series, ...(secondary || [])];
  let min = Math.min(...all),
    max = Math.max(...all);
  const gap = max - min || 0.1;
  min -= gap * 0.13;
  max += gap * 0.15;
  const x = (i: number) =>
    pad.left +
    (i / Math.max(1, series.length - 1)) * (width - pad.left - pad.right);
  const y = (n: number) =>
    pad.top + ((max - n) / (max - min)) * (height - pad.top - pad.bottom);
  const path = (values: number[]) =>
    values
      .map(
        (v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(2)},${y(v).toFixed(2)}`,
      )
      .join(" ");
  const format = (v: number) =>
    currency ? money((v / series.at(-1)!) * endValue) : pct(v - 1, 0);
  const dateTicks = width < 420 ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1];
  const index = Math.min(hover ?? series.length - 1, series.length - 1);
  const date = new Date(
    (dates[index] || dates.at(-1) || "") + "T12:00:00Z",
  ).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
  return (
    <div className="chart-wrap" ref={container}>
      <div className="chart-legend">
        <span>
          <i className="legend-line" />
          {label}
        </span>
        {secondary && (
          <span>
            <i className="legend-line secondary" />
            {secondaryLabel}
          </span>
        )}
        <span className="chart-readout" aria-live="off">
          {hover !== null ? `${date} · ${format(series[index])}` : ""}
        </span>
      </div>
      <svg
        className="line-chart"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label={`${label}: ${pct(series.at(-1)! / series[0] - 1)} over the selected period${secondary ? `; ${secondaryLabel}: ${pct(secondary.at(-1)! / secondary[0] - 1)}` : ""}.${currency ? " Both lines model growth from a shared starting value; dollar axis labels show modeled value." : ""} Hover or use the timeline slider for individual values.`}
      >
        <defs>
          <linearGradient
            id={`fill-${label.replace(/\W/g, "")}`}
            x1="0"
            y1="0"
            x2="0"
            y2="1"
          >
            <stop offset="0%" stopColor="var(--bamboo)" stopOpacity=".13" />
            <stop offset="100%" stopColor="var(--bamboo)" stopOpacity=".015" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3].map((i) => {
          const value = min + ((max - min) * i) / 3;
          return (
            <g key={i}>
              <line
                x1={pad.left}
                x2={width - pad.right + 3}
                y1={y(value)}
                y2={y(value)}
                stroke="var(--border)"
                strokeDasharray="3 5"
              />
              <text
                x={width - pad.right + 14}
                y={y(value) + 4}
                className="chart-label"
              >
                {currency
                  ? `${money(((value / series.at(-1)!) * endValue) / 1000)}k`
                  : pct(value - 1, 0)}
              </text>
            </g>
          );
        })}
        <path
          d={`${path(series)} L${x(series.length - 1)},${height - pad.bottom} L${x(0)},${height - pad.bottom} Z`}
          fill={`url(#fill-${label.replace(/\W/g, "")})`}
        />
        {secondary && (
          <path
            d={path(secondary)}
            fill="none"
            stroke="var(--comparison)"
            strokeWidth="1.7"
            strokeDasharray="5 5"
          />
        )}
        <path
          d={path(series)}
          fill="none"
          stroke="var(--bamboo)"
          strokeWidth="2.6"
          strokeLinejoin="round"
        />
        {dateTicks.map((f, i) => {
          const idx = Math.round((series.length - 1) * f);
          return (
            <text
              key={i}
              x={x(idx)}
              y={height - 5}
              textAnchor={
                i === 0
                  ? "start"
                  : i === dateTicks.length - 1
                    ? "end"
                    : "middle"
              }
              className="chart-label"
            >
              {new Date((dates[idx] || "") + "T12:00:00Z").toLocaleDateString(
                "en-US",
                {
                  month: "short",
                  timeZone: "UTC",
                  ...(series.length < 70 ? { day: "numeric" as const } : {}),
                },
              )}
            </text>
          );
        })}
        {hover !== null && (
          <g>
            <line
              x1={x(index)}
              x2={x(index)}
              y1={pad.top}
              y2={height - pad.bottom}
              stroke="var(--comparison)"
              strokeDasharray="4 4"
            />
            <circle
              cx={x(index)}
              cy={y(series[index])}
              r="5"
              fill="var(--bamboo)"
              stroke="var(--ink)"
              strokeWidth="2"
            />
          </g>
        )}
        <rect
          x={pad.left}
          y={0}
          width={width - pad.right - pad.left}
          height={height - pad.bottom}
          fill="transparent"
          onPointerMove={(e) => {
            const bounds = e.currentTarget.getBoundingClientRect();
            setHover(
              Math.max(
                0,
                Math.min(
                  series.length - 1,
                  Math.round(
                    ((e.clientX - bounds.left) / bounds.width) *
                      (series.length - 1),
                  ),
                ),
              ),
            );
          }}
          onPointerLeave={() => setHover(null)}
        />
      </svg>
      <input
        className="chart-slider"
        aria-label={`${label} chart timeline`}
        type="range"
        min="0"
        max={series.length - 1}
        value={index}
        onChange={(e) => setHover(Number(e.target.value))}
        aria-valuetext={`${date}: ${format(series[index])}`}
      />
    </div>
  );
}
