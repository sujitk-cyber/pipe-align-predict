import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default: "bg-primary/15 text-primary backdrop-blur-sm",
        secondary: "bg-secondary/60 text-secondary-foreground backdrop-blur-sm",
        destructive: "bg-destructive/15 text-destructive backdrop-blur-sm",
        outline: "border border-white/30 text-foreground backdrop-blur-sm",
        success: "bg-emerald-500/12 text-emerald-700 backdrop-blur-sm",
        warning: "bg-amber-500/12 text-amber-700 backdrop-blur-sm",
        danger: "bg-red-500/12 text-red-700 backdrop-blur-sm",
      },
    },
    defaultVariants: { variant: "default" },
  }
)

export interface BadgeProps extends React.HTMLAttributes<HTMLDivElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <div role="status" className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }
