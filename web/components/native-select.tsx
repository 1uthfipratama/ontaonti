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
        "h-9 rounded-md border border-input bg-white px-2.5 text-sm text-foreground outline-none focus-visible:border-primary focus-visible:shadow-[0_0_0_1px_var(--ring)]",
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
