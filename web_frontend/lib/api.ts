import axios from "axios"
import { getSession } from "next-auth/react"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

// Module-level impersonation override (synced from ImpersonateProvider)
let _impersonatedRole: string | null = null
export function setImpersonatedRoleForApi(role: string | null) {
  _impersonatedRole = role
}

const api = axios.create({
  baseURL: API_URL,
})

// Attach auth headers to every request
api.interceptors.request.use(async (config) => {
  // Don't override Content-Type for multipart uploads
  if (!config.headers["Content-Type"] && !(config.data instanceof FormData)) {
    config.headers["Content-Type"] = "application/json"
  }

  try {
    const session = await getSession()
    if (session?.user) {
      config.headers["X-User-Email"] = session.user.email || ""
      config.headers["X-User-Role"] = _impersonatedRole || (session.user as any)?.role || "viewer"
    }
  } catch {
    // proceed without auth headers
  }
  return config
})

export default api
export { API_URL }
