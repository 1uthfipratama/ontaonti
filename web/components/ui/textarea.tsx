import * as React from "react"
import { cn } from "cn"

function Textarea({ className, ...props }: React.ComponentProps<"textarea">) {
  return (
    <textarea
      data-slot="textarea"
      className={cn(
        "flex field-sizing-content min-h-16 w-full py-2 rounded-md border border-input bg-card px-3 text-sm transition-colors outline-none placeholder:text-subtle-foreground focus-visible:border-primary focus-visible:shadow-[0_0_0_1px_var(--ring)] disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Textarea }
