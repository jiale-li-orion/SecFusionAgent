// Adapted from shadcn/ui (MIT), new-york-v4. See THIRD_PARTY.md.
"use client"

import * as React from "react"
import { cn } from "../../lib/cn"
import { useUiThemeClass } from "./theme"
import * as TooltipPrimitive from "@radix-ui/react-tooltip"

function TooltipProvider({
  delayDuration = 300,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Provider>) {
  return (
    <TooltipPrimitive.Provider
      data-slot="tooltip-provider"
      delayDuration={delayDuration}
      {...props}
    />
  )
}

function Tooltip({
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Root>) {
  return <TooltipPrimitive.Root data-slot="tooltip" {...props} />
}

function TooltipTrigger({
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Trigger>) {
  return <TooltipPrimitive.Trigger data-slot="tooltip-trigger" {...props} />
}

function TooltipContent({
  className,
  sideOffset = 6,
  children,
  ...props
}: React.ComponentProps<typeof TooltipPrimitive.Content>) {
  const themeClass = useUiThemeClass()
  return (
    <TooltipPrimitive.Portal>
      <TooltipPrimitive.Content
        data-slot="tooltip-content"
        sideOffset={sideOffset}
        className={cn(
          "z-[220] w-fit origin-(--radix-tooltip-content-transform-origin) animate-in max-w-72 rounded-lg bg-[var(--ui-tooltip)] px-3 py-2 text-xs leading-relaxed text-balance text-[var(--ui-tooltip-foreground)] shadow-[var(--ui-shadow-popover)] fade-in-0 zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95",
          themeClass, className
        )}
        {...props}
      >
        {children}
        <TooltipPrimitive.Arrow className="z-[220] size-2.5 translate-y-[calc(-50%_-_2px)] rotate-45 rounded-[2px] bg-[var(--ui-tooltip)] fill-[var(--ui-tooltip)]" />
      </TooltipPrimitive.Content>
    </TooltipPrimitive.Portal>
  )
}

export { Tooltip, TooltipTrigger, TooltipContent, TooltipProvider }
