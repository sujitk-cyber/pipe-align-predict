"use client"

import { createContext, useContext, useState, useCallback, useEffect } from "react"
import { setImpersonatedRoleForApi } from "./api"

interface ImpersonateContext {
  /** The role being previewed, or null if not impersonating */
  impersonatedRole: string | null
  /** Set a role to preview (null to stop) */
  setImpersonatedRole: (role: string | null) => void
  /** True if currently impersonating */
  isImpersonating: boolean
}

const Ctx = createContext<ImpersonateContext>({
  impersonatedRole: null,
  setImpersonatedRole: () => {},
  isImpersonating: false,
})

export function ImpersonateProvider({ children }: { children: React.ReactNode }) {
  const [impersonatedRole, setRole] = useState<string | null>(null)

  const setImpersonatedRole = useCallback((role: string | null) => {
    setRole(role)
    setImpersonatedRoleForApi(role)
  }, [])

  return (
    <Ctx.Provider value={{ impersonatedRole, setImpersonatedRole, isImpersonating: !!impersonatedRole }}>
      {children}
    </Ctx.Provider>
  )
}

export function useImpersonate() {
  return useContext(Ctx)
}
