"use client"

import { useState, useEffect } from "react"
import axios from "axios"
import { Play, Loader2, AlertTriangle, FileText } from "lucide-react"

import { UploadForm } from "@/components/UploadForm"
import { ResultsDashboard } from "@/components/ResultsDashboard"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"

export default function Home() {
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Polling for job status
  useEffect(() => {
    let intervalId: NodeJS.Timeout

    if (jobId && jobStatus !== "completed" && jobStatus !== "failed") {
      intervalId = setInterval(async () => {
        try {
          const response = await axios.get(`http://localhost:8000/jobs/${jobId}`)
          const status = response.data.status
          setJobStatus(status)

          if (status === "failed") {
            setError(response.data.error || "Job failed unexpectedly.")
            clearInterval(intervalId)
          } else if (status === "completed") {
            clearInterval(intervalId)
          }
        } catch (err) {
          console.error("Polling error", err)
        }
      }, 2000)
    }

    return () => clearInterval(intervalId)
  }, [jobId, jobStatus])

  const handleRunAnalysis = async () => {
    if (uploadedFiles.length === 0) return
    setError(null)
    setJobStatus("pending")

    try {
      const payload = {
        files: uploadedFiles,
        enable_multirun: false, // Default for now
        enable_confidence: true,
        html_report: true
      }

      const response = await axios.post("http://localhost:8000/run", payload)
      setJobId(response.data.job_id)
      setJobStatus("running") // Optimistic update, polling will confirm
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to start analysis.")
      setJobStatus(null)
    }
  }

  const handleReset = () => {
    setUploadedFiles([])
    setJobId(null)
    setJobStatus(null)
    setError(null)
  }

  return (
    <main className="min-h-screen bg-muted/30 p-6 md:p-12">
      <div className="max-w-7xl mx-auto space-y-8">
        <header className="flex flex-col gap-2 border-b pb-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-primary">WeldWarp</h1>
              <p className="text-muted-foreground">ILI Pipeline Alignment & Corrosion Growth Prediction System</p>
            </div>
            {jobStatus === "completed" && (
              <Button variant="outline" onClick={handleReset}>New Analysis</Button>
            )}
          </div>
        </header>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: Controls */}
          <div className="lg:col-span-1 space-y-6">
            <section>
              <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                1. Upload Data
              </h2>
              {/* Disable upload if job is running or done */}
              <div className={jobId ? "opacity-50 pointer-events-none" : ""}>
                <UploadForm onUploadSuccess={setUploadedFiles} />
              </div>
            </section>

            {uploadedFiles.length > 0 && !jobId && (
              <section className="animate-in slide-in-from-top-4 fade-in duration-500">
                <h2 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  2. Run Configuration
                </h2>
                <Card>
                  <CardHeader>
                    <CardTitle>Ready to Analyze</CardTitle>
                    <CardDescription>
                      {uploadedFiles.length} file(s) selected:
                      <ul className="list-disc list-inside mt-2 text-xs text-muted-foreground">
                        {uploadedFiles.map(f => <li key={f} className="truncate">{f}</li>)}
                      </ul>
                    </CardDescription>
                  </CardHeader>
                  <CardFooter>
                    <Button onClick={handleRunAnalysis} className="w-full gap-2">
                      <Play className="h-4 w-4" /> Run Pipeline
                    </Button>
                  </CardFooter>
                </Card>
              </section>
            )}

            {jobId && (
              <section className="animate-in slide-in-from-top-4 fade-in duration-500">
                <h2 className="text-lg font-semibold mb-4">Status</h2>
                <Card>
                  <CardContent className="pt-6">
                    <div className="flex flex-col items-center justify-center space-y-4">
                      {jobStatus === "running" || jobStatus === "pending" ? (
                        <>
                          <Loader2 className="h-8 w-8 animate-spin text-primary" />
                          <p className="text-sm font-medium">Processing pipeline...</p>
                        </>
                      ) : jobStatus === "completed" ? (
                        <>
                          <div className="rounded-full bg-green-100 p-3">
                            <FileText className="h-6 w-6 text-green-600" />
                          </div>
                          <p className="text-sm font-medium text-green-600">Analysis Complete</p>
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="h-8 w-8 text-red-500" />
                          <p className="text-sm font-medium text-red-600">Failed</p>
                        </>
                      )}

                      {error && (
                        <p className="text-xs text-red-500 text-center bg-red-50 p-2 rounded w-full">
                          {error}
                        </p>
                      )}
                    </div>
                  </CardContent>
                </Card>
              </section>
            )}
          </div>

          {/* Right Column: Results / Visualization */}
          <div className="lg:col-span-2 space-y-6">
            {jobStatus === "completed" ? (
              <ResultsDashboard jobId={jobId!} />
            ) : (
              <section className="rounded-xl border bg-card text-card-foreground shadow-sm h-full min-h-[500px] p-8 flex flex-col items-center justify-center text-center">
                <div className="bg-muted/50 p-6 rounded-full mb-4">
                  {jobStatus === "running" ? (
                    <Loader2 className="h-10 w-10 animate-spin text-primary" />
                  ) : (
                    <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-muted-foreground"><path d="M21 12V7H5a2 2 0 0 1 0-4h14v4" /><path d="M3 5v14a2 2 0 0 0 2 2h16v-5" /><path d="M18 12a2 2 0 0 0 0 4h4v-4Z" /></svg>
                  )}
                </div>
                <div className="max-w-md space-y-2">
                  <h3 className="text-xl font-semibold">
                    {jobStatus === "running" ? "Crunching Data..." : "Waiting for Results"}
                  </h3>
                  <p className="text-muted-foreground">
                    {jobStatus === "running"
                      ? " The pipeline is aligning runs and calculating growth."
                      : "Upload your run data on the left to begin the matching and alignment process."
                    }
                  </p>
                </div>
              </section>
            )}
          </div>
        </div>
      </div>
    </main>
  );
}
