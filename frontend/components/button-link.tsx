import Link from "next/link";
import type { ComponentProps } from "react";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { VariantProps } from "class-variance-authority";

/**
 * A `next/link` styled like a Button. Base UI's `<Button>` deliberately
 * refuses to be rendered as an `<a>` via its `render` prop (role="button"
 * semantics conflict with native link semantics) — so a link that should
 * look like a button applies `buttonVariants` directly instead of wrapping
 * `<Button>` around it.
 */
export function ButtonLink({
  className,
  variant,
  size,
  ...props
}: ComponentProps<typeof Link> & VariantProps<typeof buttonVariants>) {
  return <Link className={cn(buttonVariants({ variant, size, className }))} {...props} />;
}
