"use client"

import { useState } from "react"
import axios from "axios"
import { CheckCircle, AlertCircle } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

interface UploadFormProps {
    onUploadSuccess?: (files: string[]) => void
}

export function UploadForm({ onUploadSuccess }: UploadFormProps) {
    const [files, setFiles] = useState<FileList | null>(null)
    const [uploading, setUploading] = useState(false)
    const [status, setStatus] = useState<{ type: 'success' | 'error', message: string } | null>(null)

    const handleUpload = async () => {
        if (!files || files.length === 0) return

        setUploading(true)
        setStatus(null)

        const formData = new FormData()
        Array.from(files).forEach((file) => {
            formData.append("files", file)
        })

        try {
            // Hardcoded localhost for MVP connection
            const response = await axios.post("http://localhost:8000/upload", formData, {
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

    return (
        <Card className="w-full">
            <CardHeader>
                <CardTitle>Upload ILI Data</CardTitle>
                <CardDescription>Select pipeline Excel or CSV files to analyze.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
                <div className="grid w-full items-center gap-1.5">
                    <Label htmlFor="file-upload">Source Files</Label>
                    <Input
                        id="file-upload"
                        type="file"
                        multiple
                        accept=".xlsx,.csv,.xls"
                        onChange={(e) => setFiles(e.target.files)}
                        disabled={uploading}
                        className="cursor-pointer"
                    />
                    <p className="text-xs text-muted-foreground">Supported formats: .xlsx, .csv</p>
                </div>

                {status && (
                    <div className={cn("flex items-center gap-2 text-sm p-3 rounded-md",
                        status.type === 'success' ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"
                    )}>
                        {status.type === 'success' ? <CheckCircle className="h-4 w-4" /> : <AlertCircle className="h-4 w-4" />}
                        {status.message}
                    </div>
                )}
            </CardContent>
            <CardFooter>
                <Button onClick={handleUpload} disabled={!files || uploading} className="w-full">
                    {uploading ? "Uploading..." : "Upload Files"}
                </Button>
            </CardFooter>
        </Card>
    )
}
