// Adapted from shadcn/ui (MIT). See THIRD_PARTY.md.
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/cn"
import * as Slot from "@radix-ui/react-slot"

const buttonVariants = cva(
  "ui-button relative inline-flex shrink-0 items-center justify-center gap-2 rounded-[10px] text-sm font-semibold tracking-[-0.01em] whitespace-nowrap transition-[background,color,border-color,box-shadow,transform] duration-150 outline-none focus-visible:ring-[3px] focus-visible:ring-ring/25 focus-visible:ring-offset-2 focus-visible:ring-offset-background active:translate-y-px disabled:pointer-events-none disabled:opacity-45 aria-invalid:border-destructive aria-invalid:ring-destructive/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[18px]",
  {
    variants: {
      variant: {
        default: "border border-[var(--ui-action)] bg-[var(--ui-action)] text-[var(--ui-action-foreground)] hover:border-[var(--ui-action-hover)] hover:bg-[var(--ui-action-hover)]",
        destructive: "border border-[var(--ui-danger-action)] bg-[var(--ui-danger-action)] text-white hover:brightness-110 focus-visible:ring-destructive/25",
        outline: "border border-input bg-[var(--ui-control)] text-foreground hover:border-[var(--ui-edge-strong)] hover:bg-[var(--ui-control-hover)]",
        secondary: "border border-transparent bg-secondary text-secondary-foreground hover:bg-accent hover:text-accent-foreground",
        ghost: "border border-transparent bg-transparent text-muted-foreground hover:bg-muted hover:text-foreground",
        link: "border border-transparent bg-transparent text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2 has-[>svg]:px-3",
        xs: "h-6 gap-1 rounded-[7px] px-2 text-xs has-[>svg]:px-1.5 [&_svg:not([class*='size-'])]:size-3",
        sm: "h-8 gap-1.5 rounded-[8px] px-3 has-[>svg]:px-2.5",
        lg: "h-11 rounded-[11px] px-6 has-[>svg]:px-4",
        icon: "size-9",
        "icon-xs": "size-6 rounded-[7px] [&_svg:not([class*='size-'])]:size-3",
        "icon-sm": "size-8",
        "icon-lg": "size-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

function Button({
  className,
  variant = "default",
  size = "default",
  asChild = false,
  ...props
}: React.ComponentProps<"button"> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }) {
  const Comp = asChild ? Slot.Root : "button"

  return (
    <Comp
      data-slot="button"
      data-variant={variant}
      data-size={size}
      className={cn(buttonVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Button }
