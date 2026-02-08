"use client"

import { useState, useEffect } from "react"
import { useRouter } from "next/navigation"
import api from "@/lib/api"
import { Play, Loader2, AlertTriangle, FileText, ShieldAlert } from "lucide-react"

import { UploadForm } from "@/components/UploadForm"
import { useImpersonate } from "@/lib/impersonate"
import { Button } from "@/components/ui/button"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Select } from "@/components/ui/select"
import { Label } from "@/components/ui/label"

export default function Home() {
  const router = useRouter()
  const { impersonatedRole } = useImpersonate()
  const effectiveRole = impersonatedRole || "admin"
  const canUpload = effectiveRole === "admin" || effectiveRole === "engineer"
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([])
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Sheet selection state
  const [sheets, setSheets] = useState<string[]>([])
  const [sheetA, setSheetA] = useState("")
  const [sheetB, setSheetB] = useState("")
  const [years, setYears] = useState("5")

  // When files are uploaded, check if single xlsx with multiple sheets
  useEffect(() => {
    if (uploadedFiles.length === 1) {
      const fname = uploadedFiles[0]
      if (fname.match(/\.xlsx?$/i)) {
        api.get(`/sheets/${fname}`).then((res) => {
          const s: string[] = res.data.sheets || []
          setSheets(s)
          // Auto-select first two non-Summary sheets
          const dataSheets = s.filter((n) => n.toLowerCase() !== "summary")
          if (dataSheets.length >= 2) {
            setSheetA(dataSheets[0])
            setSheetB(dataSheets[1])
            // Auto-guess years if sheet names are years
            const yA = parseInt(dataSheets[0])
            const yB = parseInt(dataSheets[1])
            if (!isNaN(yA) && !isNaN(yB)) {
              setYears(String(Math.abs(yB - yA)))
            }
          }
        }).catch(() => setSheets([]))
      }
    } else {
      setSheets([])
      setSheetA("")
      setSheetB("")
    }
  }, [uploadedFiles])

  useEffect(() => {
    let intervalId: NodeJS.Timeout

    if (jobId && jobStatus !== "completed" && jobStatus !== "failed") {
      intervalId = setInterval(async () => {
        try {
          const response = await api.get(`/jobs/${jobId}`)
          const status = response.data.status
          setJobStatus(status)

          if (status === "failed") {
            setError(response.data.error || "Job failed unexpectedly.")
            clearInterval(intervalId)
          } else if (status === "completed") {
            clearInterval(intervalId)
            setTimeout(() => router.push(`/jobs/${jobId}`), 800)
          }
        } catch (err) {
          console.error("Polling error", err)
        }
      }, 2000)
    }

    return () => clearInterval(intervalId)
  }, [jobId, jobStatus, router])

  const handleRunAnalysis = async () => {
    if (uploadedFiles.length === 0) return
    setError(null)
    setJobStatus("pending")

    try {
      const payload: any = {
        files: uploadedFiles,
        enable_multirun: false,
        enable_confidence: true,
        html_report: true,
        years: parseFloat(years) || 5,
      }

      // Pass sheet selection for single xlsx
      if (uploadedFiles.length === 1 && sheetA && sheetB) {
        payload.sheet_a = sheetA
        payload.sheet_b = sheetB
      }

      const response = await api.post("/run", payload)
      setJobId(response.data.job_id)
      setJobStatus("running")
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
    setSheets([])
    setSheetA("")
    setSheetB("")
    setYears("5")
  }

  const isSingleXlsx = uploadedFiles.length === 1 && sheets.length > 1
  const canRun = uploadedFiles.length >= 2 || (isSingleXlsx && sheetA && sheetB && sheetA !== sheetB)

  return (
    <div className="min-h-full p-6 md:p-12">
      <div className="max-w-3xl mx-auto space-y-8">
        <header className="pb-2">
          <p className="text-muted-foreground text-sm">Upload ILI run data to start a new alignment and growth analysis.</p>
        </header>

        {!canUpload && (
          <div className="flex items-center gap-3 glass rounded-xl p-4 border border-amber-500/30">
            <ShieldAlert className="h-5 w-5 text-amber-400 shrink-0" />
            <p className="text-sm text-amber-300">
              <strong>Viewer role</strong> — You can browse existing results but cannot upload files or run analyses.
            </p>
          </div>
        )}

        {/* Step 1: Upload */}
        <section aria-label="Upload data files">
          <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground/70 mb-4">1. Upload Data</h2>
          <div className={jobId ? "opacity-50 pointer-events-none" : !canUpload ? "opacity-40 pointer-events-none" : ""}>
            <UploadForm onUploadSuccess={setUploadedFiles} />
          </div>
        </section>

        {/* Step 2: Configure & Run */}
        {uploadedFiles.length > 0 && !jobId && (
          <section className="animate-in slide-in-from-top-4 fade-in duration-500" aria-label="Run analysis configuration">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground/70 mb-4">2. Run Configuration</h2>
            <Card>
              <CardHeader>
                <CardTitle>Ready to Analyze</CardTitle>
                <CardDescription>
                  {uploadedFiles.length} file(s) selected
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <ul className="list-disc list-inside text-xs text-muted-foreground space-y-1">
                  {uploadedFiles.map((f) => (
                    <li key={f} className="truncate">{f}</li>
                  ))}
                </ul>

                {/* Sheet selection for single xlsx */}
                {isSingleXlsx && (
                  <div className="glass rounded-xl p-4 space-y-3">
                    <p className="text-sm font-medium">Multi-sheet Excel detected — select runs to compare:</p>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1.5">
                        <Label htmlFor="sheet-a" className="text-xs">Run A (older)</Label>
                        <Select
                          id="sheet-a"
                          value={sheetA}
                          onChange={(e) => {
                            setSheetA(e.target.value)
                            const yA = parseInt(e.target.value)
                            const yB = parseInt(sheetB)
                            if (!isNaN(yA) && !isNaN(yB)) setYears(String(Math.abs(yB - yA)))
                          }}
                          aria-label="Select Run A sheet"
                        >
                          <option value="">Select sheet...</option>
                          {sheets.map((s) => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </Select>
                      </div>
                      <div className="space-y-1.5">
                        <Label htmlFor="sheet-b" className="text-xs">Run B (newer)</Label>
                        <Select
                          id="sheet-b"
                          value={sheetB}
                          onChange={(e) => {
                            setSheetB(e.target.value)
                            const yA = parseInt(sheetA)
                            const yB = parseInt(e.target.value)
                            if (!isNaN(yA) && !isNaN(yB)) setYears(String(Math.abs(yB - yA)))
                          }}
                          aria-label="Select Run B sheet"
                        >
                          <option value="">Select sheet...</option>
                          {sheets.map((s) => (
                            <option key={s} value={s}>{s}</option>
                          ))}
                        </Select>
                      </div>
                    </div>
                    <div className="space-y-1.5 max-w-[200px]">
                      <Label htmlFor="years-gap" className="text-xs">Years between runs</Label>
                      <input
                        id="years-gap"
                        type="number"
                        min="1"
                        step="0.5"
                        value={years}
                        onChange={(e) => setYears(e.target.value)}
                        className="flex h-10 w-full rounded-xl glass-input px-3.5 py-2 text-sm focus-visible:outline-none"
                        aria-label="Years between runs"
                      />
                    </div>
                    {sheetA && sheetB && sheetA === sheetB && (
                      <p className="text-xs text-red-600">Run A and Run B must be different sheets.</p>
                    )}
                  </div>
                )}
              </CardContent>
              <CardFooter>
                <Button onClick={handleRunAnalysis} disabled={!canRun} className="w-full gap-2">
                  <Play className="h-4 w-4" aria-hidden="true" /> Run Pipeline
                </Button>
              </CardFooter>
            </Card>
          </section>
        )}

        {/* Status */}
        {jobId && (
          <section className="animate-in slide-in-from-top-4 fade-in duration-500" aria-label="Job status" aria-live="polite">
            <h2 className="text-sm font-semibold uppercase tracking-widest text-muted-foreground/70 mb-4">Status</h2>
            <Card>
              <CardContent className="pt-6">
                <div className="flex flex-col items-center justify-center space-y-4">
                  {jobStatus === "running" || jobStatus === "pending" ? (
                    <>
                      <div className="h-14 w-14 rounded-2xl bg-primary/10 flex items-center justify-center">
                        <Loader2 className="h-7 w-7 animate-spin text-primary" aria-hidden="true" />
                      </div>
                      <p className="text-sm font-medium" role="status">Processing pipeline...</p>
                    </>
                  ) : jobStatus === "completed" ? (
                    <>
                      <div className="h-14 w-14 rounded-2xl bg-emerald-500/10 flex items-center justify-center">
                        <FileText className="h-6 w-6 text-emerald-600" aria-hidden="true" />
                      </div>
                      <p className="text-sm font-medium text-emerald-600" role="status">Analysis Complete — Redirecting...</p>
                    </>
                  ) : (
                    <>
                      <div className="h-14 w-14 rounded-2xl bg-red-500/10 flex items-center justify-center">
                        <AlertTriangle className="h-7 w-7 text-red-500" aria-hidden="true" />
                      </div>
                      <p className="text-sm font-medium text-red-600" role="alert">Failed</p>
                    </>
                  )}

                  {error && (
                    <p className="text-xs text-red-600 text-center glass rounded-xl p-3 w-full border-red-200/50" role="alert">
                      {error}
                    </p>
                  )}

                  {jobStatus === "failed" && (
                    <Button variant="outline" onClick={handleReset} className="mt-2">
                      Try Again
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </section>
        )}
      </div>
    </div>
  )
}
