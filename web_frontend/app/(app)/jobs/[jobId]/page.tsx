"use client"

import { use } from "react"
import { ResultsDashboard } from "@/components/ResultsDashboard"

export default function JobResultsPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params)

  return (
    <div className="min-h-full p-6 md:p-10">
      <div className="max-w-7xl mx-auto">
        <ResultsDashboard jobId={jobId} />
      </div>
    </div>
  )
}
