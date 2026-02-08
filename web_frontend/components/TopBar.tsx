"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useSession } from "next-auth/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import api from "@/lib/api"
import { Button } from "@/components/ui/button"
import { RefreshCw, Plus, Shield } from "lucide-react"
import { useRouter } from "next/navigation"

interface Job {
  job_id: string
  status: string
  source_label?: string
}

export function TopBar() {
  const pathname = usePathname()
  const router = useRouter()
  const queryClient = useQueryClient()
  const { data: session } = useSession()

  const jobMatch = pathname.match(/^\/jobs\/([^/]+)/)
  const currentJobId = jobMatch ? jobMatch[1] : null

  const { data: job } = useQuery<Job>({
    queryKey: ["job", currentJobId],
    queryFn: async () => (await api.get(`/jobs/${currentJobId}`)).data,
    enabled: !!currentJobId,
  })

  let pageTitle = "Upload & Analyze"
  if (pathname === "/jobs") pageTitle = "Job History"
  if (currentJobId) {
    pageTitle = "Job Results Overview"
    if (pathname.endsWith("/matches")) pageTitle = "Matching Review"
    if (pathname.endsWith("/growth")) pageTitle = "Growth & Risk Analysis"
  }

  const handleRefresh = () => {
    queryClient.invalidateQueries()
  }

  return (
    <header className="h-16 border-b border-white/15 glass-heavy flex items-center px-6 gap-6 shrink-0 relative z-10">
      <div className="absolute bottom-0 left-0 right-0 h-[2px] bg-gradient-to-r from-blue-500 via-blue-600 to-indigo-500" />

      {/* Left: Logo + Brand */}
      <Link href="/" className="flex items-center gap-3 shrink-0">
        <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-slate-700 to-slate-900 flex items-center justify-center shadow-md">
          <Shield className="h-4.5 w-4.5 text-white" aria-hidden="true" />
        </div>
        <div className="hidden sm:block">
          <h1 className="text-sm font-extrabold tracking-widest uppercase leading-none">WeldWarp</h1>
          <p className="text-[9px] font-medium tracking-wider text-muted-foreground/60 uppercase mt-0.5">Pipeline Integrity v4.0</p>
        </div>
      </Link>

      {/* Center: Page Title + Active Job */}
      <div className="flex-1 flex justify-center">
        <div className="text-center">
          <h2 className="text-sm font-semibold tracking-tight">{pageTitle}</h2>
          {currentJobId && job && (
            <div className="flex items-center justify-center gap-1.5 mt-0.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <p className="text-[10px] font-medium tracking-wider text-muted-foreground uppercase">
                Active Job: {currentJobId}
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Right: Actions + User */}
      <div className="flex items-center gap-3 shrink-0">
        {currentJobId && (
          <Button variant="outline" size="sm" onClick={handleRefresh} className="gap-1.5 text-xs">
            <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
            Refresh Artifacts
          </Button>
        )}
        <Button size="sm" onClick={() => router.push("/")} className="gap-1.5 text-xs">
          <Plus className="h-3.5 w-3.5" aria-hidden="true" />
          Run New Analysis
        </Button>
        {session?.user && (
          <div className="h-8 w-8 rounded-full ring-2 ring-primary/30 bg-primary/15 flex items-center justify-center overflow-hidden shrink-0">
            {session.user.image ? (
              <img
                src={session.user.image}
                alt=""
                className="h-full w-full object-cover"
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none' }}
              />
            ) : null}
            <span className="text-[10px] font-bold text-primary">
              {(session.user.name || session.user.email || "U").slice(0, 2).toUpperCase()}
            </span>
          </div>
        )}
      </div>
    </header>
  )
}
