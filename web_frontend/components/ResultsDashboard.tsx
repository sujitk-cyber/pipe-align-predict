"use client"

import { useQuery } from "@tanstack/react-query"
import api, { API_URL } from "@/lib/api"
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell,
} from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2, Download, FileText, Activity, TrendingDown, AlertTriangle, Ruler } from "lucide-react"

interface ResultsDashboardProps {
  jobId: string
}

const CONFIDENCE_COLORS: Record<string, string> = {
  High: "#22c55e",
  Medium: "#eab308",
  Low: "#ef4444",
}

function GlassChartTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null
  return (
    <div className="glass rounded-xl px-4 py-3 text-xs shadow-glass">
      <p className="font-medium text-foreground/80 mb-1">{label}</p>
      {payload.map((entry: any, i: number) => (
        <div key={i} className="flex items-center gap-2 py-0.5">
          <span className="h-2 w-2 rounded-full shrink-0" style={{ backgroundColor: entry.fill || entry.color }} />
          <span className="text-muted-foreground">{entry.name || entry.dataKey}</span>
          <span className="ml-auto font-mono font-medium tabular-nums">{entry.value}</span>
        </div>
      ))}
    </div>
  )
}

const KPI_ICONS = [
  { icon: Activity, gradient: "from-blue-500 to-indigo-600", shadow: "shadow-blue-500/20" },
  { icon: TrendingDown, gradient: "from-amber-500 to-orange-500", shadow: "shadow-amber-500/20" },
  { icon: AlertTriangle, gradient: "from-rose-500 to-red-500", shadow: "shadow-rose-500/20" },
  { icon: Ruler, gradient: "from-emerald-500 to-teal-500", shadow: "shadow-emerald-500/20" },
]

export function ResultsDashboard({ jobId }: ResultsDashboardProps) {
  const { data: metrics, isLoading, error } = useQuery({
    queryKey: ["metrics", jobId],
    queryFn: async () => (await api.get(`/jobs/${jobId}/metrics`)).data,
  })

  const { data: downloads } = useQuery({
    queryKey: ["downloads", jobId],
    queryFn: async () => (await api.get(`/jobs/${jobId}/downloads`)).data,
  })

  if (isLoading) {
    return (
      <div className="flex h-[400px] w-full items-center justify-center" role="status" aria-label="Loading results">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-hidden="true" />
        <span className="ml-2 text-muted-foreground">Loading results...</span>
      </div>
    )
  }

  if (error || !metrics) {
    return (
      <div className="glass-card rounded-2xl p-8 text-center text-red-600" role="alert">
        Failed to load results. They might not be ready yet.
      </div>
    )
  }

  const matchingStats = [
    { name: "Confident", value: metrics.confident_matches || 0, fill: "#22c55e" },
    { name: "Uncertain", value: metrics.uncertain_matches || 0, fill: "#eab308" },
    { name: "Missing (A)", value: metrics.missing_anomalies || 0, fill: "#ef4444" },
    { name: "New (B)", value: metrics.new_anomalies || 0, fill: "#3b82f6" },
  ]

  const confDist = metrics.confidence_distribution || {}
  const confidenceData = Object.entries(confDist).map(([label, count]) => ({
    name: label,
    value: count as number,
  }))

  const growthSummary = metrics.growth_summary || {}

  function formatBytes(bytes: number) {
    if (bytes < 1024) return `${bytes} B`
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
  }

  const kpiData = [
    {
      title: "Total Matches",
      value: metrics.total_matches || 0,
      sub: `${metrics.confident_matches} confident, ${metrics.uncertain_matches} uncertain`,
    },
    {
      title: "Mean Growth Rate",
      value: growthSummary.mean_growth_pct_per_yr != null ? `${growthSummary.mean_growth_pct_per_yr}%` : "N/A",
      sub: "per year (depth)",
    },
    {
      title: "Max Growth",
      value: growthSummary.max_growth_pct_per_yr != null ? `${growthSummary.max_growth_pct_per_yr}%` : "N/A",
      sub: "per year",
      alert: true,
    },
    {
      title: "Alignment Residual",
      value: metrics.avg_dist_error != null ? `${metrics.avg_dist_error} ft` : "0 ft",
      sub: "Mean error",
    },
  ]

  return (
    <div className="space-y-6 animate-in fade-in duration-500">
      {/* KPI Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {kpiData.map((kpi, i) => {
          const { icon: Icon, gradient, shadow } = KPI_ICONS[i]
          return (
            <Card key={kpi.title} className="glass-shine">
              <CardContent className="pt-6">
                <div className="flex items-start justify-between mb-3">
                  <p className="text-sm font-medium text-muted-foreground">{kpi.title}</p>
                  <div className={`h-9 w-9 rounded-xl bg-gradient-to-br ${gradient} flex items-center justify-center shadow-md ${shadow}`}>
                    <Icon className="h-4 w-4 text-white" aria-hidden="true" />
                  </div>
                </div>
                <div className={`text-2xl font-bold tracking-tight ${kpi.alert ? 'text-rose-600' : ''}`}>
                  {kpi.value}
                </div>
                <p className="text-xs text-muted-foreground mt-1">{kpi.sub}</p>
              </CardContent>
            </Card>
          )
        })}
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
        {/* Matching Overview */}
        <Card className="col-span-4">
          <CardHeader>
            <CardTitle>Matching Overview</CardTitle>
          </CardHeader>
          <CardContent className="pl-2">
            <div className="h-[300px] w-full" role="img" aria-label="Bar chart showing matching overview statistics">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={matchingStats}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" strokeOpacity={0.5} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                  <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                  <Tooltip content={<GlassChartTooltip />} cursor={{ fill: "transparent" }} />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                    {matchingStats.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Top Severity */}
        <Card className="col-span-3">
          <CardHeader>
            <CardTitle>Top Critical Anomalies</CardTitle>
            <CardDescription>Highest severity score based on depth and growth.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {(metrics.top_10_severity || []).slice(0, 5).map((item: any, i: number) => (
                <div key={i} className="flex items-center rounded-xl p-2.5 hover:bg-white/30 transition-colors">
                  <div className="h-7 w-7 rounded-lg bg-rose-500/10 flex items-center justify-center text-xs font-bold text-rose-600 shrink-0">
                    {i + 1}
                  </div>
                  <div className="ml-3 space-y-0.5 min-w-0">
                    <p className="text-sm font-medium leading-none truncate">ID: {item.feature_id_a || "N/A"}</p>
                    <p className="text-xs text-muted-foreground">
                      Depth: {item.depth_pct_b}% (+{item.depth_growth_pct_per_yr}%/yr)
                    </p>
                  </div>
                  <div className="ml-auto font-mono font-semibold text-sm text-rose-600 tabular-nums">
                    {item.severity_score}
                  </div>
                </div>
              ))}
              {(!metrics.top_10_severity || metrics.top_10_severity.length === 0) && (
                <p className="text-sm text-muted-foreground text-center py-4">No critical anomalies found.</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Confidence Distribution */}
      {confidenceData.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Confidence Distribution</CardTitle>
            <CardDescription>Match confidence levels across all matched anomalies.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="h-[250px] w-full" role="img" aria-label="Bar chart showing confidence distribution">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={confidenceData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" strokeOpacity={0.5} />
                  <XAxis dataKey="name" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "hsl(var(--muted-foreground))" }} />
                  <YAxis allowDecimals={false} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }} />
                  <Tooltip content={<GlassChartTooltip />} cursor={{ fill: "transparent" }} />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                    {confidenceData.map((entry, i) => (
                      <Cell key={i} fill={CONFIDENCE_COLORS[entry.name] || "#94a3b8"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Downloads / Exports */}
      {downloads && downloads.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Exports & Downloads</CardTitle>
            <CardDescription>Download pipeline output files.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {downloads.map((file: any) => (
                <a
                  key={file.filename}
                  href={`${API_URL}/jobs/${jobId}/files/${file.filename}`}
                  download
                  className="flex items-center gap-3 glass-card rounded-xl p-3.5 hover:scale-[1.01] transition-all"
                  aria-label={`Download ${file.filename}`}
                >
                  <div className="h-9 w-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                    <FileText className="h-4 w-4 text-primary" aria-hidden="true" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{file.filename}</p>
                    <p className="text-xs text-muted-foreground">{formatBytes(file.size_bytes)}</p>
                  </div>
                  <Download className="h-4 w-4 text-muted-foreground shrink-0" aria-hidden="true" />
                </a>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
