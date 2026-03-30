import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { cn } from "@/lib/utils"
import { gsap, isDesktopPointer, prefersReducedMotion } from "@/animations/gsapConfig"

const buttonVariants = cva(
  "inline-flex items-center justify-center whitespace-nowrap rounded-full text-sm font-medium transition-[box-shadow,transform,background-color,color,border-color] duration-300 will-change-transform focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow hover:bg-primary/90 hover:shadow-premium",
        destructive:
          "bg-destructive text-destructive-foreground shadow-sm hover:bg-destructive/90",
        outline:
          "border border-input bg-background shadow-sm hover:bg-accent hover:text-accent-foreground hover:shadow-soft",
        secondary:
          "bg-secondary text-secondary-foreground shadow-sm hover:bg-secondary/80",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        default: "h-10 px-6 py-2",
        sm: "h-9 rounded-full px-4",
        lg: "h-12 rounded-full px-10 text-base",
        icon: "h-9 w-9",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
  magnetic?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, magnetic = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    const localRef = React.useRef<HTMLElement | null>(null)

    React.useEffect(() => {
      if (!magnetic || !localRef.current || prefersReducedMotion() || !isDesktopPointer() || variant === "link") {
        return
      }

      const target = localRef.current
      const strength = 0.14
      const maxOffset = 7

      const onMove = (event: MouseEvent) => {
        const rect = target.getBoundingClientRect()
        const centerX = rect.left + rect.width / 2
        const centerY = rect.top + rect.height / 2
        const offsetX = Math.max(-maxOffset, Math.min(maxOffset, (event.clientX - centerX) * strength))
        const offsetY = Math.max(-maxOffset, Math.min(maxOffset, (event.clientY - centerY) * strength))

        gsap.to(target, { x: offsetX, y: offsetY, duration: 0.22, ease: "power2.out" })
      }

      const onLeave = () => {
        gsap.to(target, { x: 0, y: 0, duration: 0.5, ease: "elastic.out(1, 0.45)" })
      }

      target.addEventListener("mousemove", onMove)
      target.addEventListener("mouseleave", onLeave)

      return () => {
        target.removeEventListener("mousemove", onMove)
        target.removeEventListener("mouseleave", onLeave)
      }
    }, [magnetic, variant])

    const setRefs = (node: HTMLElement | null) => {
      localRef.current = node
      if (typeof ref === "function") {
        ref(node as HTMLButtonElement | null)
      } else if (ref) {
        ref.current = node as HTMLButtonElement | null
      }
    }

    return (
      <Comp
        data-cursor="hover"
        className={cn(buttonVariants({ variant, size, className }))}
        ref={setRefs}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
