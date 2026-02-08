"use client"

import { useQuery } from "@tanstack/react-query"
import { useRouter } from "next/navigation"
import api from "@/lib/api"
import { Badge } from "@/components/ui/badge"
import { Card, CardContent } from "@/components/ui/card"
import { Loader2, Clock, CheckCircle2, XCircle, ArrowRight } from "lucide-react"

interface Job {
  job_id: string
  status: string
  start_time: string
  end_time?: string
  error?: string
}

function statusBadge(status: string) {
  switch (status) {
    case "completed":
      return <Badge variant="success"><CheckCircle2 className="h-3 w-3 mr-1" aria-hidden="true" />Completed</Badge>
    case "running":
    case "pending":
      return <Badge variant="warning"><Clock className="h-3 w-3 mr-1" aria-hidden="true" />{status}</Badge>
    case "failed":
      return <Badge variant="danger"><XCircle className="h-3 w-3 mr-1" aria-hidden="true" />Failed</Badge>
    default:
      return <Badge variant="outline">{status}</Badge>
  }
}

export default function JobsPage() {
  const router = useRouter()
  const { data: jobs, isLoading } = useQuery<Job[]>({
    queryKey: ["jobs"],
    queryFn: async () => (await api.get("/jobs")).data,
    refetchInterval: 5000,
  })

  return (
    <div className="min-h-full p-6 md:p-12">
      <div className="max-w-5xl mx-auto space-y-8">
        <header className="pb-2">
          <p className="text-muted-foreground text-sm">View all pipeline analysis jobs.</p>
        </header>

        {isLoading ? (
          <div className="flex justify-center py-16" role="status" aria-label="Loading jobs">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-hidden="true" />
            <span className="sr-only">Loading jobs...</span>
          </div>
        ) : !jobs || jobs.length === 0 ? (
          <Card>
            <CardContent className="py-16 text-center text-muted-foreground">
              No jobs found. Start a new analysis from the Upload page.
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-3" role="list" aria-label="Job list">
            {[...jobs].reverse().map((job) => (
              <Card
                key={job.job_id}
                className="cursor-pointer transition-all duration-200 hover:scale-[1.005]"
                onClick={() => {
                  if (job.status === "completed") router.push(`/jobs/${job.job_id}`)
                }}
                role="listitem"
              >
                <CardContent className="flex items-center justify-between py-4">
                  <div className="space-y-1">
                    <p className="text-sm font-mono font-medium">{job.job_id.slice(0, 8)}...</p>
                    <p className="text-xs text-muted-foreground">
                      Started: {new Date(job.start_time).toLocaleString()}
                      {job.end_time && ` | Ended: ${new Date(job.end_time).toLocaleString()}`}
                    </p>
                    {job.error && (
                      <p className="text-xs text-red-600">{job.error}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    {statusBadge(job.status)}
                    {job.status === "completed" && (
                      <ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                    )}
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
