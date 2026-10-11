// Adapted from shadcn/ui (MIT), new-york-v4. See THIRD_PARTY.md.
"use client"

import * as React from "react"
import { type VariantProps } from "class-variance-authority"
import { toggleVariants } from "./toggle-variants"
import { cn } from "../../lib/cn"
import * as TogglePrimitive from "@radix-ui/react-toggle"


function Toggle({
  className,
  variant,
  size,
  ...props
}: React.ComponentProps<typeof TogglePrimitive.Root> &
  VariantProps<typeof toggleVariants>) {
  return (
    <TogglePrimitive.Root
      data-slot="toggle"
      className={cn(toggleVariants({ variant, size, className }))}
      {...props}
    />
  )
}

export { Toggle }
