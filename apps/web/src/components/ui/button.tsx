// Adapted from shadcn/ui (MIT). See THIRD_PARTY.md.
import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "../../lib/cn"
import * as Slot from "@radix-ui/react-slot"

const buttonVariants = cva(
  "relative inline-flex shrink-0 items-center justify-center gap-2 rounded-[10px] text-sm font-semibold tracking-[-0.01em] whitespace-nowrap transition-[background,color,border-color,box-shadow,transform] duration-200 outline-none focus-visible:ring-[3px] focus-visible:ring-[#4263eb]/25 focus-visible:ring-offset-2 active:translate-y-px disabled:pointer-events-none disabled:opacity-50 disabled:shadow-none aria-invalid:border-destructive aria-invalid:ring-destructive/20 [&_svg]:pointer-events-none [&_svg]:shrink-0 [&_svg:not([class*='size-'])]:size-[18px]",
  {
    variants: {
      variant: {
        default: "border border-[#4160e1] bg-[linear-gradient(180deg,#6681fa_0%,#4263eb_48%,#3656d9_100%)] text-white shadow-[inset_0_1px_0_#ffffff55,0_1px_2px_#172d7526,0_7px_16px_-9px_#4263eb99] hover:bg-[linear-gradient(180deg,#728cff_0%,#4d6df1_48%,#3d5de1_100%)] hover:shadow-[inset_0_1px_0_#ffffff66,0_3px_5px_#172d7526,0_10px_22px_-10px_#4263ebbb]",
        destructive:
          "bg-destructive text-white hover:bg-destructive/90 focus-visible:ring-destructive/20 dark:bg-destructive/60 dark:focus-visible:ring-destructive/40",
        outline:
          "border border-[#d9e0ed] bg-[linear-gradient(180deg,#fff,#f9fbff)] text-[#293953] shadow-[inset_0_1px_0_#fff,0_1px_2px_#1b345612,0_5px_13px_-11px_#1b34565c] hover:border-[#a9bdf4] hover:bg-[#f4f7ff] hover:text-[#3155c6] hover:shadow-[inset_0_1px_0_#fff,0_5px_15px_-9px_#4263eb55] dark:border-input dark:bg-[#1c2940] dark:text-[#e4edff] dark:hover:bg-[#263b60]",
        secondary:
          "border border-[#dfe6f2] bg-[linear-gradient(180deg,#f8faff,#edf2fc)] text-[#38558d] shadow-[inset_0_1px_0_#fff] hover:border-[#b7c8ef] hover:bg-[#e8efff] dark:border-[#344460] dark:bg-[#24314a] dark:text-[#dbe6fb]",
        ghost:
          "text-[#62718b] hover:bg-[#ecf1ff] hover:text-[#3155c6] dark:text-[#bdcbea] dark:hover:bg-[#283a5c] dark:hover:text-white",
        link: "text-primary underline-offset-4 hover:underline",
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
