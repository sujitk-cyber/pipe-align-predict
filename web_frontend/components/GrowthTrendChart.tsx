"use client"

import { useQuery } from "@tanstack/react-query"
import api from "@/lib/api"
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts"
import { Loader2, TrendingUp } from "lucide-react"

interface GrowthTrendChartProps {
  jobId: string
}

function GlassTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="glass rounded-xl shadow-glass px-4 py-3 text-xs">
      <p className="font-medium text-foreground/80 mb-1.5">
        {Math.round(label).toLocaleString()} ft
      </p>
      {payload.map((entry: any, i: number) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          <span
            className="h-2 w-2 rounded-full shrink-0"
            style={{ backgroundColor: entry.color }}
          />
          <span className="text-muted-foreground">{entry.name}</span>
          <span className="ml-auto font-mono font-medium tabular-nums">
            {Number(entry.value)?.toFixed(3)}
          </span>
        </div>
      ))}
    </div>
  )
}

function GlassLegend({ payload }: any) {
  if (!payload?.length) return null
  return (
    <div className="flex items-center justify-center gap-6 pt-2 pb-1">
      {payload.map((entry: any, i: number) => (
        <div key={i} className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <span
            className="h-2.5 w-2.5 rounded-full"
            style={{ backgroundColor: entry.color }}
          />
          {entry.value}
        </div>
      ))}
    </div>
  )
}

export function GrowthTrendChart({ jobId }: GrowthTrendChartProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["growth-trends", jobId],
    queryFn: async () => (await api.get(`/jobs/${jobId}/growth-trends`)).data,
  })

  return (
    <div className="glass-card rounded-2xl p-6 h-full">
      <div className="flex items-start justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold tracking-tight">Growth Trends</h3>
          <p className="text-sm text-muted-foreground mt-0.5">
            Depth growth rate along the pipeline odometer
          </p>
        </div>
        <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center shadow-md shadow-blue-500/20">
          <TrendingUp className="h-4 w-4 text-white" aria-hidden="true" />
        </div>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-20" role="status" aria-label="Loading growth trends">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/50" aria-hidden="true" />
          <span className="sr-only">Loading growth trends...</span>
        </div>
      ) : error || !data || data.length === 0 ? (
        <div className="text-center py-20 text-sm text-muted-foreground">
          No growth trend data available.
        </div>
      ) : (
        <div className="h-[380px] w-full -ml-2" role="img" aria-label="Area chart showing growth trends along pipeline">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id="gradAvg" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.18} />
                  <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="gradMax" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.10} />
                  <stop offset="100%" stopColor="#f43f5e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid
                strokeDasharray="3 3"
                vertical={false}
                stroke="hsl(var(--border))"
                strokeOpacity={0.5}
              />
              <XAxis
                dataKey="odometer"
                tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}k`}
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                dy={8}
              />
              <YAxis
                yAxisId="growth"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                tickFormatter={(v: number) => `${v.toFixed(1)}`}
                width={40}
              />
              <YAxis
                yAxisId="severity"
                orientation="right"
                axisLine={false}
                tickLine={false}
                tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                width={32}
              />
              <Tooltip content={<GlassTooltip />} />
              <Legend content={<GlassLegend />} />
              <Area
                yAxisId="growth"
                type="monotone"
                dataKey="avg_growth"
                name="Avg Growth (%WT/yr)"
                stroke="#3b82f6"
                strokeWidth={2}
                fill="url(#gradAvg)"
                dot={false}
                activeDot={{ r: 4, strokeWidth: 2, fill: "#fff" }}
              />
              <Area
                yAxisId="growth"
                type="monotone"
                dataKey="max_growth"
                name="Max Growth (%WT/yr)"
                stroke="#f43f5e"
                strokeWidth={1.5}
                strokeDasharray="6 3"
                fill="url(#gradMax)"
                dot={false}
                activeDot={{ r: 3, strokeWidth: 2, fill: "#fff" }}
              />
              <Area
                yAxisId="severity"
                type="monotone"
                dataKey="avg_severity"
                name="Avg Severity"
                stroke="#f59e0b"
                strokeWidth={1.5}
                fill="transparent"
                dot={false}
                activeDot={{ r: 3, strokeWidth: 2, fill: "#fff" }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
