"use client"

import { useState, useRef } from "react"
import api from "@/lib/api"
import { CheckCircle, AlertCircle, Upload, FileSpreadsheet } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface UploadFormProps {
    onUploadSuccess?: (files: string[]) => void
}

export function UploadForm({ onUploadSuccess }: UploadFormProps) {
    const [files, setFiles] = useState<FileList | null>(null)
    const [uploading, setUploading] = useState(false)
    const [dragOver, setDragOver] = useState(false)
    const [status, setStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null)
    const inputRef = useRef<HTMLInputElement>(null)

    const handleFiles = (fileList: FileList | null) => {
        if (fileList && fileList.length > 0) {
            setFiles(fileList)
            setStatus(null)
        }
    }

    const handleUpload = async () => {
        if (!files || files.length === 0) return

        setUploading(true)
        setStatus(null)

        const formData = new FormData()
        Array.from(files).forEach((file) => {
            formData.append("files", file)
        })

        try {
            const response = await api.post("/upload", formData, {
                headers: { "Content-Type": "multipart/form-data" },
            })
            const uploadedFiles = response.data.files
            setStatus({ type: 'success', message: `Successfully uploaded ${uploadedFiles.length} files.` })

            if (onUploadSuccess) {
                onUploadSuccess(uploadedFiles)
            }
        } catch (error: any) {
            setStatus({ type: 'error', message: error.response?.data?.detail || "Upload failed. Check backend connection." })
        } finally {
            setUploading(false)
        }
    }

    const fileNames = files ? Array.from(files).map(f => f.name) : []

    return (
        <Card className="w-full">
            <CardHeader>
                <CardTitle>Upload ILI Data</CardTitle>
                <CardDescription>Select pipeline Excel or CSV files to analyze.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
                <div className="grid w-full items-center gap-2">
                    <Label>Source Files</Label>

                    {/* Custom dropzone */}
                    <div
                        className={cn(
                            "relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 transition-all cursor-pointer",
                            dragOver
                                ? "border-primary/50 bg-primary/5"
                                : "border-border/50 hover:border-primary/30 hover:bg-muted/10",
                            files && "border-primary/30 bg-primary/5"
                        )}
                        onClick={() => inputRef.current?.click()}
                        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
                        onDragLeave={() => setDragOver(false)}
                        onDrop={(e) => {
                            e.preventDefault()
                            setDragOver(false)
                            handleFiles(e.dataTransfer.files)
                        }}
                    >
                        <input
                            ref={inputRef}
                            type="file"
                            multiple
                            accept=".xlsx,.csv,.xls"
                            onChange={(e) => handleFiles(e.target.files)}
                            disabled={uploading}
                            className="hidden"
                            aria-describedby="file-upload-help"
                        />

                        {fileNames.length > 0 ? (
                            <>
                                <FileSpreadsheet className="h-8 w-8 text-primary" aria-hidden="true" />
                                <div className="text-center">
                                    <p className="text-sm font-medium">{fileNames.length} file(s) selected</p>
                                    <p className="text-xs text-muted-foreground mt-1">
                                        {fileNames.join(", ")}
                                    </p>
                                </div>
                            </>
                        ) : (
                            <>
                                <div className="h-12 w-12 rounded-2xl bg-primary/10 flex items-center justify-center">
                                    <Upload className="h-5 w-5 text-primary" aria-hidden="true" />
                                </div>
                                <div className="text-center">
                                    <p className="text-sm font-medium">
                                        Drop files here or <span className="text-primary">browse</span>
                                    </p>
                                    <p id="file-upload-help" className="text-xs text-muted-foreground mt-1">
                                        Supports .xlsx, .csv
                                    </p>
                                </div>
                            </>
                        )}
                    </div>
                </div>

                {status && (
                    <div
                        className={cn(
                            "flex items-center gap-2 text-sm p-3 rounded-xl",
                            status.type === 'success'
                                ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                                : "bg-red-500/10 text-red-400 border border-red-500/20"
                        )}
                        role={status.type === 'error' ? 'alert' : 'status'}
                    >
                        {status.type === 'success'
                            ? <CheckCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
                            : <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />}
                        {status.message}
                    </div>
                )}
            </CardContent>
            <CardFooter>
                <Button onClick={handleUpload} disabled={!files || uploading} className="w-full gap-2">
                    <Upload className="h-4 w-4" aria-hidden="true" />
                    {uploading ? "Uploading..." : "Upload Files"}
                </Button>
            </CardFooter>
        </Card>
    )
}
