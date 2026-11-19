import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { DEFAULT_SAMPLE } from "@/lib/samples";

// Landing page links into the app. `<Button asChild>` styles them through `className`, so they pass it on.
interface LinkProps {
  className?: string;
  children: ReactNode;
}

export function SampleLink({ className, children }: LinkProps) {
  return (
    <Link to="/sample/$name" params={{ name: DEFAULT_SAMPLE }} className={className}>
      {children}
    </Link>
  );
}

export function RegisterLink({ className, children }: LinkProps) {
  return (
    <Link to="/login" search={{ tab: "register" }} className={className}>
      {children}
    </Link>
  );
}

export function LoginLink({ className, children }: LinkProps) {
  return (
    <Link to="/login" search={{ tab: "login" }} className={className}>
      {children}
    </Link>
  );
}
