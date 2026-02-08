"use client"

import { useState } from "react"
import { useQuery } from "@tanstack/react-query"
import api from "@/lib/api"
import {
  Table, TableHeader, TableBody, TableRow, TableHead, TableCell,
} from "@/components/ui/table"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Select } from "@/components/ui/select"
import { Button } from "@/components/ui/button"
import { Loader2, ChevronUp, ChevronDown, ChevronsUpDown, ChevronLeft, ChevronRight, X } from "lucide-react"

interface MatchesTableProps {
  jobId: string
}

const COLUMNS = [
  { key: "feature_id_a", label: "Run A ID" },
  { key: "feature_id_b", label: "Run B ID" },
  { key: "feature_type", label: "Type" },
  { key: "delta_dist_ft", label: "Dist Diff (ft)" },
  { key: "delta_clock_deg", label: "Clock Diff (\u00b0)" },
  { key: "depth_pct_b", label: "Depth (%)" },
  { key: "depth_growth_pct_per_yr", label: "Growth/yr" },
  { key: "confidence_label", label: "Confidence" },
  { key: "severity_score", label: "Severity" },
]

function confidenceBadge(label: string | null) {
  if (!label) return null
  const l = label.toLowerCase()
  if (l === "high") return <Badge variant="success">High</Badge>
  if (l === "medium") return <Badge variant="warning">Medium</Badge>
  return <Badge variant="danger">Low</Badge>
}

function formatTypeName(t: string) {
  return t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())
}

export function MatchesTable({ jobId }: MatchesTableProps) {
  const [page, setPage] = useState(1)
  const [limit] = useState(25)
  const [sortBy, setSortBy] = useState<string | null>(null)
  const [sortOrder, setSortOrder] = useState<"asc" | "desc">("asc")
  const [confidence, setConfidence] = useState("")
  const [featureType, setFeatureType] = useState("")
  const [selectedRow, setSelectedRow] = useState<any | null>(null)

  // Fetch available feature types dynamically
  const { data: featureTypes } = useQuery<string[]>({
    queryKey: ["feature-types", jobId],
    queryFn: async () => (await api.get(`/jobs/${jobId}/feature-types`)).data,
  })

  const { data, isLoading } = useQuery({
    queryKey: ["matches", jobId, page, limit, sortBy, sortOrder, confidence, featureType],
    queryFn: async () => {
      const params: any = { page, limit }
      if (sortBy) { params.sort_by = sortBy; params.sort_order = sortOrder }
      if (confidence) params.confidence = confidence
      if (featureType) params.feature_type = featureType
      return (await api.get(`/jobs/${jobId}/matches`, { params })).data
    },
  })

  const handleSort = (col: string) => {
    if (sortBy === col) {
      setSortOrder(sortOrder === "asc" ? "desc" : "asc")
    } else {
      setSortBy(col)
      setSortOrder("asc")
    }
    setPage(1)
  }

  const sortIcon = (col: string) => {
    if (sortBy !== col) return <ChevronsUpDown className="h-3 w-3 ml-1 opacity-40" aria-hidden="true" />
    return sortOrder === "asc"
      ? <ChevronUp className="h-3 w-3 ml-1" aria-hidden="true" />
      : <ChevronDown className="h-3 w-3 ml-1" aria-hidden="true" />
  }

  const formatCell = (col: string, val: any) => {
    if (val === null || val === undefined) return <span className="text-muted-foreground/40">—</span>
    if (col === "confidence_label") return confidenceBadge(val)
    if (col === "feature_type") return <span className="capitalize">{formatTypeName(String(val))}</span>
    if (typeof val === "number") return val.toFixed(col === "severity_score" ? 1 : 3)
    return String(val)
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-3 items-center">
        <label htmlFor="confidence-filter" className="sr-only">Filter by confidence</label>
        <Select
          id="confidence-filter"
          value={confidence}
          onChange={(e) => { setConfidence(e.target.value); setPage(1) }}
          className="w-40"
          aria-label="Filter by confidence level"
        >
          <option value="">All Confidence</option>
          <option value="High">High</option>
          <option value="Medium">Medium</option>
          <option value="Low">Low</option>
        </Select>
        <label htmlFor="type-filter" className="sr-only">Filter by feature type</label>
        <Select
          id="type-filter"
          value={featureType}
          onChange={(e) => { setFeatureType(e.target.value); setPage(1) }}
          className="w-52"
          aria-label="Filter by feature type"
        >
          <option value="">All Types</option>
          {(featureTypes || []).map((t) => (
            <option key={t} value={t}>{formatTypeName(t)}</option>
          ))}
        </Select>
        {(confidence || featureType) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setConfidence(""); setFeatureType(""); setPage(1) }}
            className="gap-1"
            aria-label="Clear all filters"
          >
            <X className="h-3 w-3" aria-hidden="true" /> Clear
          </Button>
        )}
        <span className="ml-auto text-sm text-muted-foreground self-center" aria-live="polite">
          {data ? `${data.total} matches` : ""}
        </span>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex justify-center py-16" role="status" aria-label="Loading matches">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" aria-hidden="true" />
              <span className="sr-only">Loading matches...</span>
            </div>
          ) : !data || data.data.length === 0 ? (
            <div className="text-center py-16 text-muted-foreground">No matches found.</div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  {COLUMNS.map((col) => (
                    <TableHead
                      key={col.key}
                      className="cursor-pointer select-none whitespace-nowrap"
                      onClick={() => handleSort(col.key)}
                      aria-sort={sortBy === col.key ? (sortOrder === "asc" ? "ascending" : "descending") : "none"}
                    >
                      <span className="inline-flex items-center">
                        {col.label}
                        {sortIcon(col.key)}
                      </span>
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.data.map((row: any, i: number) => (
                  <TableRow
                    key={i}
                    className="cursor-pointer"
                    onClick={() => setSelectedRow(selectedRow === row ? null : row)}
                    aria-selected={selectedRow === row}
                  >
                    {COLUMNS.map((col) => (
                      <TableCell key={col.key} className="whitespace-nowrap">
                        {formatCell(col.key, row[col.key])}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Pagination */}
      {data && data.pages > 1 && (
        <nav className="flex items-center justify-center gap-2" aria-label="Pagination">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage(page - 1)}
            aria-label="Previous page"
          >
            <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          </Button>
          <span className="text-sm text-muted-foreground" aria-current="page">
            Page {page} of {data.pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.pages}
            onClick={() => setPage(page + 1)}
            aria-label="Next page"
          >
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          </Button>
        </nav>
      )}

      {/* Detail Panel */}
      {selectedRow && (
        <Card className="animate-in slide-in-from-top-2 fade-in duration-300">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-base">Match Detail</CardTitle>
            <Button variant="ghost" size="icon" onClick={() => setSelectedRow(null)} aria-label="Close detail panel">
              <X className="h-4 w-4" aria-hidden="true" />
            </Button>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              {Object.entries(selectedRow).map(([key, val]) => (
                <div key={key}>
                  <p className="text-muted-foreground text-xs">{key}</p>
                  <p className="font-medium">
                    {val === null || val === undefined ? "—" : typeof val === "number" ? val.toFixed(4) : String(val)}
                  </p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
