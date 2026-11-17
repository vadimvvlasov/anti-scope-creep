import { useEffect, useRef, useState, type CSSProperties } from "react";

import { cn } from "@/lib/utils";
import { RISK_CATEGORY_LABELS } from "@/services/types";

// The landing page's hero picture (docs/spec.md "Landing page"), drafted in Lovable. The payment clause
// and its finding are from the guest sample `net-90`; the scope clause is an illustration.

// Review sequence timing (seconds). The scan line passes each clause just before it is flagged.
const T = {
  scan: 0.5,
  mediumClause: 1.15,
  mediumCard: 1.55,
  highClause: 2.0,
  highCard: 2.4,
};

const delay = (s: number) => ({ "--delay": `${s}s` }) as CSSProperties;

function Bars({ widths }: { widths: string[] }) {
  return (
    <span aria-hidden="true" className="flex flex-col gap-2.5">
      {widths.map((w, i) => (
        <span key={i} className="paper-bar" style={{ width: w }} />
      ))}
    </span>
  );
}

function FindingCard({
  level,
  title,
  quote,
  start,
  className,
}: {
  level: "high" | "medium";
  title: string;
  quote: string;
  start: number;
  className?: string;
}) {
  const isHigh = level === "high";
  return (
    <div
      className={cn(
        "animate-finding relative rounded-lg border border-l-4 bg-card p-4 shadow-float sm:p-5",
        isHigh ? "border-l-risk-high" : "border-l-risk-medium",
        className,
      )}
      style={delay(start)}
    >
      <div className="flex items-start gap-2.5">
        <span
          aria-hidden="true"
          className={cn(
            "animate-finding-dot mt-1.5 size-2 shrink-0 rounded-full",
            isHigh ? "bg-risk-high" : "bg-risk-medium",
          )}
          style={
            {
              ...delay(start + 0.3),
              "--dot-color": isHigh ? "var(--color-risk-high)" : "var(--color-risk-medium)",
            } as CSSProperties
          }
        />
        <div className="min-w-0">
          <p className="font-display text-sm font-semibold leading-snug text-card-foreground">
            {title}
          </p>
          <blockquote className="mt-2 border-l-2 pl-3 text-sm text-muted-foreground italic">
            “{quote}”
          </blockquote>
        </div>
      </div>
    </div>
  );
}

/**
 * Stylised contract excerpt that "reviews itself": a scan line passes down the page,
 * each risky clause is highlighted in turn and its finding card appears. Pure HTML/CSS.
 */
export function ContractPreview() {
  // Hold the sequence until the picture is on screen (on phones it starts below the fold).
  const ref = useRef<HTMLElement>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setPlaying(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setPlaying(true);
          io.disconnect();
        }
      },
      { threshold: 0.45 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, []);

  return (
    <figure
      ref={ref}
      className={cn("relative mx-auto w-full max-w-md lg:max-w-none", !playing && "review-idle")}
      aria-label="Illustration: a contract excerpt where two clauses are flagged, a medium-risk scope clause and a high-risk payment clause, each with its finding"
    >
      {/* The document */}
      <div className="rounded-lg border bg-card p-6 shadow-paper sm:p-8 lg:mr-10">
        <div className="flex items-center justify-between border-b pb-4">
          <span className="font-display text-xs font-semibold tracking-[0.18em] text-muted-foreground uppercase">
            Services Agreement
          </span>
          <span aria-hidden="true" className="font-mono text-xs text-muted-foreground">
            p. 2
          </span>
        </div>

        <div className="relative mt-5 space-y-5 text-sm leading-relaxed">
          <span aria-hidden="true" className="review-scan-line" style={delay(T.scan)} />

          <Bars widths={["100%", "92%", "64%"]} />

          <p className="text-card-foreground">
            <span className="font-semibold">3. Services.</span>{" "}
            <span className="text-muted-foreground">
              Contractor will deliver the work in Exhibit A
            </span>{" "}
            <mark
              className="clause-mark clause-medium animate-clause"
              style={delay(T.mediumClause)}
            >
              and any related services Client may request.
            </mark>
          </p>

          <Bars widths={["96%", "78%"]} />

          <p className="text-card-foreground">
            <span className="font-semibold">4. Payment.</span>{" "}
            <span className="text-muted-foreground">Contractor will invoice Client monthly.</span>{" "}
            <mark className="clause-mark clause-high animate-clause" style={delay(T.highClause)}>
              Invoices are payable Net 90.
            </mark>
          </p>

          <Bars widths={["100%", "88%", "94%", "60%"]} />
        </div>
      </div>

      {/* The findings: stacked under the page on small screens, pinned to its edge on desktop */}
      <div className="relative -mt-6 ml-6 mr-2 flex flex-col gap-3 sm:ml-12 lg:static lg:m-0">
        <FindingCard
          level="medium"
          title={`${RISK_CATEGORY_LABELS.scope_creep} (Medium)`}
          quote="and any related services Client may request."
          start={T.mediumCard}
          className="lg:absolute lg:-top-8 lg:right-0 lg:w-72"
        />
        <FindingCard
          level="high"
          title={`${RISK_CATEGORY_LABELS.unfavorable_payment_terms} (High)`}
          quote="Invoices are payable Net 90."
          start={T.highCard}
          className="lg:absolute lg:right-0 lg:-bottom-10 lg:w-72"
        />
      </div>
    </figure>
  );
}
