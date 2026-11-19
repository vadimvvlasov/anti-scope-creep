import { useEffect, useRef, useState, type CSSProperties, type RefObject } from "react";

import { DEMO_FINDINGS } from "@/lib/landing-copy";
import { cn } from "@/lib/utils";
import { RISK_CATEGORY_LABELS } from "@/services/types";

import { RiskChip } from "./risk-chip";
import { riskBorder } from "./risk-styles";

// The landing page's hero picture (docs/spec.md "Landing page"), drafted in Lovable: a contract page
// reviewed clause by clause. A scan line passes down the page, each risky clause is highlighted in
// turn, then its finding appears, and the payment finding shows its suggested wording.

// Review sequence timing (seconds). The scan line passes each clause just before it is flagged.
const T = {
  scan: 0.5,
  mediumClause: 1.1,
  mediumCard: 1.45,
  highClause: 1.9,
  highCard: 2.25,
  detail: 2.75,
};

const delay = (s: number) => ({ "--delay": `${s}s` }) as CSSProperties;

const scope = DEMO_FINDINGS.find((f) => f.category === "scope_creep")!;
const payment = DEMO_FINDINGS.find((f) => f.category === "unfavorable_payment_terms")!;

const DESCRIPTION =
  "Illustration: a contract page with a medium-risk scope clause and a high-risk payment clause flagged, and the suggested replacement wording for the payment clause.";

function Bars({ widths }: { widths: string[] }) {
  return (
    <span aria-hidden="true" className="flex flex-col gap-2.5">
      {widths.map((w, i) => (
        <span key={i} className="paper-bar" style={{ width: w }} />
      ))}
    </span>
  );
}

/** True once the element has been on screen (on phones the picture starts below the fold). */
function useSeen(ref: RefObject<HTMLElement | null>): boolean {
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) {
          setSeen(true);
          io.disconnect();
        }
      },
      { threshold: 0.35 },
    );
    io.observe(el);
    return () => io.disconnect();
  }, [ref]);
  return seen;
}

export function HeroReview() {
  const ref = useRef<HTMLElement>(null);
  const playing = useSeen(ref);
  return (
    <figure
      ref={ref}
      role="img"
      aria-label={DESCRIPTION}
      className={cn("relative mx-auto w-full max-w-lg lg:max-w-none", !playing && "review-idle")}
    >
      <ContractPage />
      <HeroFindings />
    </figure>
  );
}

function ContractPage() {
  return (
    <div aria-hidden="true" className="rounded-xl border bg-card shadow-paper lg:mr-14">
      <div className="flex items-center justify-between gap-3 border-b px-5 py-3 sm:px-7">
        <span className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="flex gap-1">
            <span className="size-2 rounded-full bg-paper-line" />
            <span className="size-2 rounded-full bg-paper-line" />
            <span className="size-2 rounded-full bg-paper-line" />
          </span>
          <span className="ml-2 font-mono">services-agreement.pdf</span>
        </span>
      </div>
      <div className="p-5 sm:p-7">
        <p className="font-display text-xs font-semibold tracking-[0.18em] text-muted-foreground uppercase">
          Services Agreement
        </p>
        <div className="relative mt-5 space-y-5 text-sm leading-relaxed">
          <span className="review-scan-line" style={delay(T.scan)} />
          <Bars widths={["100%", "86%"]} />
          <p className="text-card-foreground">
            <span className="font-semibold">1. Services.</span>{" "}
            <span className="text-muted-foreground">The work is described in Exhibit A.</span>{" "}
            <mark
              className="clause-mark clause-medium animate-clause"
              style={delay(T.mediumClause)}
            >
              {scope.quote}
            </mark>
          </p>
          <Bars widths={["70%"]} />
          <p className="text-card-foreground">
            <span className="font-semibold">2. Payment.</span>{" "}
            <span className="text-muted-foreground">Contractor will invoice Client monthly.</span>{" "}
            <mark className="clause-mark clause-high animate-clause" style={delay(T.highClause)}>
              {payment.quote}
            </mark>
          </p>
          <Bars widths={["100%", "90%", "96%", "62%", "84%", "92%", "70%", "88%", "40%"]} />
        </div>
      </div>
    </div>
  );
}

/** Stacked under the page on small screens, pinned to its edge on desktop. */
function HeroFindings() {
  return (
    <div
      aria-hidden="true"
      className="relative -mt-8 mr-1 ml-5 flex flex-col gap-3 sm:ml-10 lg:static lg:m-0"
    >
      <div
        className={cn(
          "animate-finding rounded-lg border border-l-4 bg-card px-4 py-3 shadow-float lg:absolute lg:top-[4.5rem] lg:right-0 lg:w-72",
          riskBorder(scope.level),
        )}
        style={delay(T.mediumCard)}
      >
        <RiskChip level={scope.level} />
        <p className="mt-2 font-display text-sm leading-snug font-semibold">
          {RISK_CATEGORY_LABELS[scope.category]}
        </p>
      </div>
      <div
        className={cn(
          "animate-finding rounded-lg border border-l-4 bg-card p-4 shadow-float sm:p-5 lg:absolute lg:right-0 lg:-bottom-16 lg:w-80",
          riskBorder(payment.level),
        )}
        style={delay(T.highCard)}
      >
        <RiskChip level={payment.level} />
        <p className="mt-2 font-display text-sm leading-snug font-semibold">
          {RISK_CATEGORY_LABELS[payment.category]}
        </p>
        <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">{payment.why}</p>
        <div
          className="animate-finding mt-3 rounded-md border border-risk-low/25 bg-risk-low-soft p-3"
          style={delay(T.detail)}
        >
          <p className="text-[0.7rem] font-semibold tracking-wide uppercase">Suggested wording</p>
          <p className="mt-1 text-sm leading-relaxed">“{payment.suggestion}”</p>
        </div>
      </div>
    </div>
  );
}
