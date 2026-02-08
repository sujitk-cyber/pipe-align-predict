"use client"

import { useSession } from "next-auth/react"
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { useState } from "react"
import { User, Shield, Mail, UserCircle, Loader2, Check } from "lucide-react"
import api from "@/lib/api"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Select } from "@/components/ui/select"
import { Badge } from "@/components/ui/badge"

interface UserInfo {
  email: string
  name?: string
  image?: string
  role: string
}

function roleLabel(role: string) {
  switch (role) {
    case "admin": return "Admin"
    case "engineer": return "Engineer"
    case "viewer": return "Viewer"
    default: return role
  }
}

function roleColor(role: string) {
  switch (role) {
    case "admin": return "bg-red-500/20 text-red-400 border-red-500/30"
    case "engineer": return "bg-blue-500/20 text-blue-400 border-blue-500/30"
    case "viewer": return "bg-muted text-muted-foreground border-border"
    default: return "bg-muted text-muted-foreground border-border"
  }
}

function initials(name?: string | null, email?: string | null) {
  if (name) {
    return name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2)
  }
  if (email) return email.slice(0, 2).toUpperCase()
  return "U"
}

export default function SettingsPage() {
  const { data: session } = useSession()
  const queryClient = useQueryClient()
  const [roleUpdates, setRoleUpdates] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState<string | null>(null)

  const user = session?.user
  const isAdmin = (user as any)?.role === "admin"

  const { data: currentUser } = useQuery({
    queryKey: ["/me"],
    queryFn: async () => {
      const res = await api.get("/me")
      return res.data as UserInfo
    },
  })

  const { data: allUsers = [], isLoading: usersLoading } = useQuery({
    queryKey: ["/admin/users"],
    queryFn: async () => {
      const res = await api.get("/admin/users")
      return res.data as UserInfo[]
    },
    enabled: isAdmin,
  })

  const updateRoleMutation = useMutation({
    mutationFn: async ({ email, role }: { email: string; role: string }) => {
      await api.put("/admin/users/role", { email, role })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["/admin/users"] })
      setSaving(null)
      setRoleUpdates({})
    },
  })

  const handleRoleChange = (email: string, newRole: string) => {
    setRoleUpdates(prev => ({ ...prev, [email]: newRole }))
  }

  const handleSaveRole = (email: string) => {
    const newRole = roleUpdates[email]
    if (!newRole) return
    setSaving(email)
    updateRoleMutation.mutate({ email, role: newRole })
  }

  return (
    <div className="space-y-6 p-6">
      <div>
        <h1 className="text-3xl font-bold">Settings</h1>
        <p className="text-muted-foreground mt-1">Manage your account and preferences</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <UserCircle className="h-5 w-5" />
            Profile
          </CardTitle>
          <CardDescription>Your account information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            {user?.image ? (
              <img src={user.image} alt="" className="h-16 w-16 rounded-full" />
            ) : (
              <div className="h-16 w-16 rounded-full bg-primary/10 flex items-center justify-center">
                <span className="text-xl font-bold text-primary">
                  {initials(user?.name, user?.email)}
                </span>
              </div>
            )}
            <div>
              <p className="font-semibold">{user?.name || "User"}</p>
              <p className="text-sm text-muted-foreground flex items-center gap-2 mt-1">
                <Mail className="h-3.5 w-3.5" />
                {user?.email}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 pt-2 border-t border-border/50">
            <Shield className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm text-muted-foreground">Role:</span>
            <Badge className={`${roleColor(currentUser?.role || "viewer")} border`}>
              {roleLabel(currentUser?.role || "viewer")}
            </Badge>
          </div>
        </CardContent>
      </Card>

      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Shield className="h-5 w-5" />
              User Management
            </CardTitle>
            <CardDescription>Manage user roles and permissions</CardDescription>
          </CardHeader>
          <CardContent>
            {usersLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <div className="space-y-3">
                {allUsers.map((u) => {
                  const pendingRole = roleUpdates[u.email]
                  const displayRole = pendingRole || u.role
                  const hasChanges = pendingRole && pendingRole !== u.role

                  return (
                    <div
                      key={u.email}
                      className="flex items-center justify-between p-4 rounded-xl glass border border-border/50"
                    >
                      <div className="flex items-center gap-3 flex-1 min-w-0">
                        {u.image ? (
                          <img src={u.image} alt="" className="h-10 w-10 rounded-full shrink-0" />
                        ) : (
                          <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
                            <span className="text-xs font-bold text-primary">
                              {initials(u.name, u.email)}
                            </span>
                          </div>
                        )}
                        <div className="min-w-0 flex-1">
                          <p className="font-medium truncate">{u.name || "User"}</p>
                          <p className="text-sm text-muted-foreground truncate">{u.email}</p>
                        </div>
                        <div className="flex items-center gap-3 shrink-0">
                          <Select
                            value={displayRole}
                            onChange={(e) => handleRoleChange(u.email, e.target.value)}
                            className="w-32"
                          >
                            <option value="viewer">Viewer</option>
                            <option value="engineer">Engineer</option>
                            <option value="admin">Admin</option>
                          </Select>
                          {hasChanges && (
                            <Button
                              size="sm"
                              onClick={() => handleSaveRole(u.email)}
                              disabled={saving === u.email}
                            >
                              {saving === u.email ? (
                                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                              ) : (
                                <Check className="h-3.5 w-3.5" />
                              )}
                            </Button>
                          )}
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
