import NextAuth from "next-auth"
import Google from "next-auth/providers/google"
import GitHub from "next-auth/providers/github"

export const { handlers, signIn, signOut, auth } = NextAuth({
  providers: [
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID!,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET!,
    }),
    GitHub({
      clientId: process.env.GITHUB_ID!,
      clientSecret: process.env.GITHUB_SECRET!,
    }),
  ],
  pages: {
    signIn: "/login",
  },
  session: {
    strategy: "jwt",
  },
  callbacks: {
    async jwt({ token, user, account }) {
      // On first sign-in, register user with backend and get role
      if (user && account) {
        token.email = user.email
        token.name = user.name
        token.picture = user.image

        // Fetch role from backend
        try {
          const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
          const res = await fetch(`${apiUrl}/auth/register`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: user.email,
              name: user.name,
              image: user.image,
              provider: account.provider,
            }),
          })
          if (res.ok) {
            const data = await res.json()
            token.role = data.role
          } else {
            token.role = "viewer"
          }
        } catch {
          token.role = "viewer"
        }
      }
      return token
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.role = token.role as string
        session.user.email = token.email as string
        session.user.image = token.picture as string
      }
      return session
    },
  },
})
