// Adapted from shadcn/ui (MIT). See THIRD_PARTY.md.
import * as React from "react"
import { cn } from "../../lib/cn"

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      type={type}
      data-slot="input"
      className={cn(
        "h-10 w-full min-w-0 rounded-[10px] border border-[#dce3ef] bg-[linear-gradient(180deg,#fbfcff,#fff)] px-3.5 py-1 text-base shadow-[inset_0_1px_2px_#2238640a,0_1px_0_#fff] transition-[border-color,background,box-shadow] duration-200 outline-none selection:bg-primary selection:text-primary-foreground file:inline-flex file:h-7 file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-[#93a0b4] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50 md:text-sm dark:border-[#344460] dark:bg-[#172239] dark:text-[#ecf2fc]",
        "focus-visible:border-[#7794eb] focus-visible:bg-white focus-visible:ring-[4px] focus-visible:ring-[#4263eb]/12 focus-visible:shadow-[0_2px_8px_#4263eb1c]",
        "aria-invalid:border-destructive aria-invalid:ring-destructive/20 dark:aria-invalid:ring-destructive/40",
        className
      )}
      {...props}
    />
  )
}

export { Input }
