"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { useSession, signOut } from "next-auth/react"
import { cn } from "@/lib/utils"
import {
  Upload, BarChart3, TableProperties, TrendingUp,
  History, Settings, ChevronRight, LogOut,
} from "lucide-react"

interface NavItem {
  label: string
  href: string
  icon: React.ElementType
  disabled?: boolean
}

function roleLabel(role?: string) {
  switch (role) {
    case "admin": return "Admin Access"
    case "engineer": return "Engineer Access"
    case "viewer": return "View Only"
    default: return "Viewer"
  }
}

function initials(name?: string | null, email?: string | null) {
  if (name) {
    return name.split(" ").map(w => w[0]).join("").toUpperCase().slice(0, 2)
  }
  if (email) return email.slice(0, 2).toUpperCase()
  return "U"
}

export function Sidebar() {
  const pathname = usePathname()
  const { data: session } = useSession()
  const jobMatch = pathname.match(/^\/jobs\/([^/]+)/)
  const currentJobId = jobMatch ? jobMatch[1] : null

  const user = session?.user
  const role = (user as any)?.role || "viewer"

  const mainNav: { title: string; items: NavItem[] }[] = [
    {
      title: "Core Pipeline",
      items: [
        { label: "Upload", href: "/", icon: Upload },
        { label: "Job Results", href: "/jobs", icon: BarChart3 },
      ],
    },
    {
      title: "System",
      items: [
        { label: "Job History", href: "/jobs", icon: History },
        { label: "Settings", href: "#", icon: Settings, disabled: true },
      ],
    },
  ]

  const jobNav: NavItem[] | null = currentJobId
    ? [
        { label: "Dashboard", href: `/jobs/${currentJobId}`, icon: BarChart3 },
        { label: "Matching Review", href: `/jobs/${currentJobId}/matches`, icon: TableProperties },
        { label: "Growth & Risk", href: `/jobs/${currentJobId}/growth`, icon: TrendingUp },
      ]
    : null

  return (
    <aside className="hidden md:flex w-56 flex-col glass-sidebar" role="navigation" aria-label="Main navigation">
      <nav className="flex-1 overflow-y-auto py-4 px-3 space-y-6" aria-label="Sidebar navigation">
        {jobNav && (
          <div>
            <p className="px-3 mb-3 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
              Current Job
            </p>
            <ul className="space-y-0.5" role="list">
              {jobNav.map((item) => {
                const isActive = pathname === item.href
                const Icon = item.icon
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      aria-current={isActive ? "page" : undefined}
                      className={cn(
                        "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-200",
                        isActive
                          ? "glass text-primary font-medium"
                          : "text-muted-foreground hover:bg-muted/20 hover:text-foreground"
                      )}
                    >
                      <Icon className="h-4 w-4" aria-hidden="true" />
                      {item.label}
                      {isActive && <ChevronRight className="ml-auto h-4 w-4 opacity-50" aria-hidden="true" />}
                    </Link>
                  </li>
                )
              })}
            </ul>
          </div>
        )}

        {mainNav.map((section) => (
          <div key={section.title}>
            <p className="px-3 mb-2 text-[10px] font-semibold uppercase tracking-widest text-muted-foreground/70">
              {section.title}
            </p>
            <ul className="space-y-0.5" role="list">
              {section.items.map((item) => {
                const isActive = pathname === item.href && !currentJobId
                const Icon = item.icon
                return (
                  <li key={item.label + item.href}>
                    {item.disabled ? (
                      <span
                        className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-muted-foreground/40 cursor-not-allowed"
                        aria-disabled="true"
                      >
                        <Icon className="h-4 w-4" aria-hidden="true" />
                        {item.label}
                      </span>
                    ) : (
                      <Link
                        href={item.href}
                        aria-current={isActive ? "page" : undefined}
                        className={cn(
                          "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-all duration-200",
                          isActive
                            ? "glass text-primary font-medium"
                            : "text-muted-foreground hover:bg-muted/20 hover:text-foreground"
                        )}
                      >
                        <Icon className="h-4 w-4" aria-hidden="true" />
                        {item.label}
                        {isActive && <ChevronRight className="ml-auto h-4 w-4 opacity-50" aria-hidden="true" />}
                      </Link>
                    )}
                  </li>
                )
              })}
            </ul>
          </div>
        ))}
      </nav>

      {/* User profile */}
      <div className="border-t border-white/15 px-4 py-4">
        <div className="flex items-center gap-3">
          {user?.image ? (
            <img src={user.image} alt="" className="h-9 w-9 rounded-full shrink-0" />
          ) : (
            <div className="h-9 w-9 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
              <span className="text-xs font-bold text-primary">{initials(user?.name, user?.email)}</span>
            </div>
          )}
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium leading-none truncate">{user?.name || "User"}</p>
            <p className="text-[11px] text-primary/70 mt-0.5 capitalize">{roleLabel(role)}</p>
          </div>
          <button
            onClick={() => signOut({ callbackUrl: "/login" })}
            className="p-1.5 rounded-lg hover:bg-white/30 text-muted-foreground/50 hover:text-foreground transition-colors"
            aria-label="Sign out"
          >
            <LogOut className="h-3.5 w-3.5" aria-hidden="true" />
          </button>
        </div>
      </div>
    </aside>
  )
}
