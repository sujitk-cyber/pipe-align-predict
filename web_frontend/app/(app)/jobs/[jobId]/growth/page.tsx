"use client"

import { use } from "react"
import { GrowthTrendChart } from "@/components/GrowthTrendChart"
import { RiskSegments } from "@/components/RiskSegments"

export default function GrowthPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params)

  return (
    <div className="min-h-full p-6 md:p-10">
      <div className="max-w-7xl mx-auto">
        <div className="grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-3">
            <GrowthTrendChart jobId={jobId} />
          </div>
          <div className="lg:col-span-2">
            <RiskSegments jobId={jobId} />
          </div>
        </div>
      </div>
    </div>
  )
}
