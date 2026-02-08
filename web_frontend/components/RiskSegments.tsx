"use client"

import { useQuery } from "@tanstack/react-query"
import api from "@/lib/api"
import { Loader2, ShieldAlert } from "lucide-react"

interface RiskSegmentsProps {
  jobId: string
}

function riskPill(status: string) {
  const base = "inline-flex items-center rounded-full px-2.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide backdrop-blur-sm"
  if (status === "HIGH RISK")
    return <span className={`${base} bg-red-500/12 text-red-600`} role="status">High</span>
  if (status === "MEDIUM RISK")
    return <span className={`${base} bg-amber-500/12 text-amber-600`} role="status">Medium</span>
  return <span className={`${base} bg-emerald-500/12 text-emerald-600`} role="status">Low</span>
}

export function RiskSegments({ jobId }: RiskSegmentsProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["risk-segments", jobId],
    queryFn: async () => (await api.get(`/jobs/${jobId}/risk-segments`)).data,
  })

  return (
    <div className="glass-card rounded-2xl p-6 h-full flex flex-col">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h3 className="text-lg font-semibold tracking-tight">Risk Segments</h3>
          <p className="text-sm text-muted-foreground mt-0.5">Top anomalies by severity</p>
        </div>
        <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-rose-500 to-red-600 flex items-center justify-center shadow-md shadow-rose-500/20">
          <ShieldAlert className="h-4 w-4 text-white" aria-hidden="true" />
        </div>
      </div>

      {isLoading ? (
        <div className="flex-1 flex justify-center items-center" role="status" aria-label="Loading risk segments">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground/50" aria-hidden="true" />
          <span className="sr-only">Loading risk segments...</span>
        </div>
      ) : error || !data || data.length === 0 ? (
        <p className="text-sm text-muted-foreground flex-1 flex items-center justify-center">
          No risk data available.
        </p>
      ) : (
        <div className="flex-1 space-y-2 overflow-y-auto max-h-[520px] pr-1 -mr-1" role="list" aria-label="Risk segments list">
          {data.map((seg: any) => (
            <div
              key={seg.rank}
              role="listitem"
              className="group relative rounded-xl glass p-3 transition-all duration-200 hover:scale-[1.01]"
            >
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="text-[10px] font-bold text-muted-foreground/60 tabular-nums w-5 shrink-0">
                    {seg.rank}
                  </span>
                  <span className="text-sm font-medium truncate">
                    {seg.feature_id || "Unknown"}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {riskPill(seg.status)}
                  <span className="text-xs font-mono font-semibold tabular-nums text-foreground/70 w-10 text-right">
                    {seg.severity_score ?? "-"}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-3 text-[11px] text-muted-foreground pl-7">
                <span>{seg.odometer != null ? `${seg.odometer.toLocaleString()} ft` : "-"}</span>
                <span className="opacity-30">|</span>
                <span>{seg.depth != null ? `${seg.depth}% depth` : "-"}</span>
                <span className="opacity-30">|</span>
                <span>{seg.growth_rate != null ? `${seg.growth_rate}%/yr` : "-"}</span>
                {seg.remaining_life != null && (
                  <>
                    <span className="opacity-30">|</span>
                    <span>{seg.remaining_life} yr life</span>
                  </>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
