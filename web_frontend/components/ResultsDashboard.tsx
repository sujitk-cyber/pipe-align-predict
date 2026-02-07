"use client"

import { useEffect, useState } from "react"
import axios from "axios"
import {
    BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer,
    ScatterChart, Scatter, LineChart, Line
} from "recharts"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Loader2 } from "lucide-react"

interface ResultsDashboardProps {
    jobId: string
}

export function ResultsDashboard({ jobId }: ResultsDashboardProps) {
    const [report, setReport] = useState<any>(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)

    useEffect(() => {
        const fetchData = async () => {
            try {
                // Fetch Alignment Report JSON
                // Using hardcoded localhost for MVP; assume CORS is enabled
                const response = await axios.get(`http://localhost:8000/jobs/${jobId}/files/alignment_report.json`)
                setReport(response.data)
            } catch (err) {
                console.error(err)
                setError("Failed to load results. They might not be ready yet.")
            } finally {
                setLoading(false)
            }
        }

        if (jobId) {
            fetchData()
        }
    }, [jobId])

    if (loading) {
        return (
            <div className="flex h-[400px] w-full items-center justify-center">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                <span className="ml-2 text-muted-foreground">Loading results...</span>
            </div>
        )
    }

    if (error || !report) {
        return (
            <div className="p-8 text-center text-red-500">
                {error || "No data available."}
            </div>
        )
    }

    // Prepare data for charts
    const matchingStats = [
        { name: "Matched", value: report.matching?.confident || 0, fill: "#22c55e" },
        { name: "Uncertain", value: report.matching?.uncertain || 0, fill: "#eab308" },
        { name: "Missing (A only)", value: report.matching?.missing_run_a_only || 0, fill: "#ef4444" },
        { name: "New (B only)", value: report.matching?.new_run_b_only || 0, fill: "#3b82f6" },
    ]

    const growthStats = report.growth_summary || {}

    return (
        <div className="space-y-8 animate-in fade-in duration-500">
            {/* KPI Cards */}
            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Total Matches</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{report.matching?.total_matched || 0}</div>
                        <p className="text-xs text-muted-foreground">
                            {report.matching?.confident} confident matches
                        </p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Mean Growth Rate</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">
                            {growthStats.mean_growth_pct_per_yr ? `${growthStats.mean_growth_pct_per_yr}%` : "N/A"}
                        </div>
                        <p className="text-xs text-muted-foreground">per year (depth)</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Max Growth</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold text-red-600">
                            {growthStats.max_growth_pct_per_yr ? `${growthStats.max_growth_pct_per_yr}%` : "N/A"}
                        </div>
                        <p className="text-xs text-muted-foreground">per year</p>
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                        <CardTitle className="text-sm font-medium">Alignment Residual</CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="text-2xl font-bold">{report.alignment?.mean_residual_ft || "0"} ft</div>
                        <p className="text-xs text-muted-foreground">Mean error</p>
                    </CardContent>
                </Card>
            </div>

            <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-7">
                {/* Matching Stat Chart */}
                <Card className="col-span-4">
                    <CardHeader>
                        <CardTitle>Matching Overview</CardTitle>
                    </CardHeader>
                    <CardContent className="pl-2">
                        <div className="h-[300px] w-full">
                            <ResponsiveContainer width="100%" height="100%">
                                <BarChart data={matchingStats}>
                                    <CartesianGrid strokeDasharray="3 3" vertical={false} />
                                    <XAxis dataKey="name" />
                                    <YAxis allowDecimals={false} />
                                    <Tooltip
                                        cursor={{ fill: 'transparent' }}
                                        contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }}
                                    />
                                    <Bar dataKey="value" radius={[4, 4, 0, 0]} />
                                </BarChart>
                            </ResponsiveContainer>
                        </div>
                    </CardContent>
                </Card>

                {/* Top Severity List (Simple Table) */}
                <Card className="col-span-3">
                    <CardHeader>
                        <CardTitle>Top Critical Anomalies</CardTitle>
                        <CardDescription>Highest severity score based on depth and growth.</CardDescription>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-4">
                            {(report.top_10_severity || []).slice(0, 5).map((item: any, i: number) => (
                                <div key={i} className="flex items-center">
                                    <div className="ml-4 space-y-1">
                                        <p className="text-sm font-medium leading-none">ID: {item.feature_id_a || "N/A"}</p>
                                        <p className="text-sm text-muted-foreground">
                                            Depth: {item.depth_pct_b}% (+{item.depth_growth_pct_per_yr}%/yr)
                                        </p>
                                    </div>
                                    <div className="ml-auto font-medium text-red-600">
                                        Score: {item.severity_score}
                                    </div>
                                </div>
                            ))}
                            {(!report.top_10_severity || report.top_10_severity.length === 0) && (
                                <p className="text-sm text-muted-foreground">No critical anomalies found.</p>
                            )}
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    )
}
