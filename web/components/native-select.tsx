import { cn } from "@/lib/utils";

/** Plain <select> styled like the shadcn inputs. */
export function NativeSelect({
  className,
  options,
  ...props
}: React.ComponentProps<"select"> & { options: { value: string; label: string }[] }) {
  return (
    <select
      className={cn(
        "h-8 rounded-lg border border-input bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring/50",
        className,
      )}
      {...props}
    >
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
}
