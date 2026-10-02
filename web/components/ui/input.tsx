import * as React from "react"
import { Input as InputPrimitive } from "@base-ui/react/input"
import { cn } from "cn"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <InputPrimitive
      type={type}
      data-slot="input"
      className={cn(
        "h-9 w-full min-w-0 py-1 file:inline-flex file:h-6 file:border-0 file:bg-transparent file:text-sm file:font-medium rounded-md border border-input bg-white px-3 text-sm transition-colors outline-none placeholder:text-[#758195] focus-visible:border-primary focus-visible:shadow-[0_0_0_1px_var(--ring)] disabled:cursor-not-allowed disabled:bg-muted disabled:opacity-60 aria-invalid:border-destructive",
        className
      )}
      {...props}
    />
  )
}

export { Input }
