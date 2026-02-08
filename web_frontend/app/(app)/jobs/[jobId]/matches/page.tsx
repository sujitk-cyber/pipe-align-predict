"use client"

import { use } from "react"
import { MatchesTable } from "@/components/MatchesTable"

export default function MatchesPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params)

  return (
    <div className="min-h-full p-6 md:p-10">
      <div className="max-w-7xl mx-auto">
        <MatchesTable jobId={jobId} />
      </div>
    </div>
  )
}
