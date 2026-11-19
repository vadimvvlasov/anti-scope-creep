import { useEffect, useRef, useState, type ReactNode } from "react";

/**
 * Fades a block in as it scrolls into view. The prerendered HTML is always visible; only blocks that
 * start below the fold are hidden after mount, so there is no flash and the text works without JS.
 */
export function Reveal({
  children,
  className,
  delay = 0,
}: {
  children: ReactNode;
  className?: string;
  delay?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [state, setState] = useState<"shown" | "hidden">("shown");

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    if (el.getBoundingClientRect().top < window.innerHeight * 0.9) return;
    setState("hidden");
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setState("shown");
          io.disconnect();
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -8% 0px" },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <div
      ref={ref}
      data-reveal={state}
      className={className}
      style={delay ? { transitionDelay: `${delay}ms` } : undefined}
    >
      {children}
    </div>
  );
}
