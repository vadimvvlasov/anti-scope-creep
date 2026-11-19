import { Check, MessageSquareText, ScanSearch, Upload } from "lucide-react";

import { MethodologyLink } from "@/components/methodology-dialog";
import {
  CHECK_LINES,
  CHECKS_HEADING,
  FEATURES,
  FEATURES_HEADING,
  PRIVACY_HEADING,
  STEPS,
  STEPS_HEADING,
} from "@/lib/landing-copy";
import {
  AI_DATA_POLICY_URL,
  ANALYZER,
  METHODOLOGY_TITLE,
  uploadPrivacyPoints,
} from "@/lib/methodology";
import { RISK_CATEGORY_LABELS, type RiskCategory } from "@/services/types";

import { BENEFIT_VISUALS } from "./benefit-visuals";
import { Reveal } from "./reveal";
import { SectionHeading } from "./section-heading";

// The middle sections of the landing page (docs/spec.md "Landing page"), drafted in Lovable.

const PRIVACY_POINTS = uploadPrivacyPoints(ANALYZER);
const STEP_ICONS = [Upload, ScanSearch, MessageSquareText] as const;
const counter = (i: number) => String(i + 1).padStart(2, "0");

export function WhatYouGet() {
  return (
    <section aria-labelledby="get-heading" className="border-t bg-muted/60">
      <div className="page-container py-20 sm:py-28">
        <Reveal>
          <SectionHeading id="get-heading" title={FEATURES_HEADING} />
        </Reveal>
        <div className="mt-12 grid gap-10 md:grid-cols-3 md:gap-6 lg:gap-10">
          {FEATURES.map(({ title, body }, i) => {
            const Visual = BENEFIT_VISUALS[i]!;
            return (
              <Reveal key={title} delay={i * 90}>
                <article className="group flex h-full flex-col">
                  <div
                    aria-hidden="true"
                    className="flex min-h-48 items-center rounded-xl border bg-card p-5 shadow-sm transition-shadow duration-300 group-hover:shadow-paper"
                  >
                    <div className="w-full">
                      <Visual />
                    </div>
                  </div>
                  <h3 className="mt-6 text-lg leading-snug font-semibold">{title}</h3>
                  <p className="mt-2 leading-relaxed text-muted-foreground">{body}</p>
                </article>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export function WhatItChecks() {
  const categories = Object.keys(RISK_CATEGORY_LABELS) as RiskCategory[];
  return (
    <section aria-labelledby="checks-heading" className="border-t">
      <div className="page-container grid gap-12 py-20 sm:py-28 lg:grid-cols-[0.8fr_1.4fr] lg:gap-16">
        <Reveal>
          <SectionHeading
            id="checks-heading"
            eyebrow="What it checks"
            title={CHECKS_HEADING}
            className="lg:sticky lg:top-28"
          />
        </Reveal>
        <ol className="grid sm:grid-cols-2 sm:gap-x-10">
          {categories.map((category, i) => (
            <li
              key={category}
              className="border-t py-6 last:border-b sm:[&:nth-last-child(2)]:border-b"
            >
              <div className="flex gap-4">
                <span
                  aria-hidden="true"
                  className="w-6 shrink-0 pt-0.5 font-mono text-xs text-muted-foreground"
                >
                  {counter(i)}
                </span>
                <div>
                  <h3 className="text-base leading-snug font-semibold">
                    {RISK_CATEGORY_LABELS[category]}
                  </h3>
                  <p className="mt-1.5 text-sm leading-relaxed text-muted-foreground">
                    {CHECK_LINES[category]}
                  </p>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

export function HowItWorks() {
  return (
    <section aria-labelledby="how-heading" className="border-t bg-muted/60">
      <div className="page-container py-20 sm:py-28">
        <Reveal>
          <SectionHeading id="how-heading" title={STEPS_HEADING} />
        </Reveal>
        <ol className="relative mt-14 grid gap-10 md:grid-cols-3 md:gap-8">
          {/* The line joining the steps: vertical on phones, horizontal from tablet up. */}
          <span
            aria-hidden="true"
            className="absolute top-2 bottom-2 left-5 w-px bg-gradient-to-b from-accent via-accent/50 to-border md:top-5 md:right-[16%] md:bottom-auto md:left-5 md:h-px md:w-auto md:bg-gradient-to-r"
          />
          {STEPS.map((step, i) => {
            const Icon = STEP_ICONS[i]!;
            return (
              <li key={step} className="relative flex gap-5 md:flex-col">
                <span
                  aria-hidden="true"
                  className="relative z-10 flex size-10 shrink-0 items-center justify-center rounded-full border bg-card shadow-sm"
                >
                  <Icon className="size-4" />
                </span>
                <div>
                  <p className="font-mono text-xs text-muted-foreground">
                    <span className="sr-only">Step </span>
                    {counter(i)}
                  </p>
                  <p className="mt-1.5 max-w-xs text-lg leading-relaxed">{step}</p>
                </div>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}

const INVERSE_LINK =
  "cursor-pointer text-left font-medium text-surface-inverse-foreground underline decoration-surface-inverse-border decoration-2 underline-offset-4 transition-colors hover:decoration-surface-inverse-foreground";

export function Privacy() {
  return (
    <section aria-labelledby="privacy-heading" className="border-t">
      <div className="page-container py-20 sm:py-28">
        <div className="overflow-hidden rounded-2xl border border-surface-inverse-border bg-surface-inverse text-surface-inverse-foreground">
          <div className="grid gap-12 p-7 sm:p-12 lg:grid-cols-[0.85fr_1.3fr] lg:gap-16 lg:p-16">
            <div>
              <SectionHeading
                inverse
                id="privacy-heading"
                eyebrow="Privacy"
                title={PRIVACY_HEADING}
              />
              <div className="mt-8 flex flex-col items-start gap-3 text-sm">
                <MethodologyLink className={INVERSE_LINK}>{METHODOLOGY_TITLE}</MethodologyLink>
                <a
                  href={AI_DATA_POLICY_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className={INVERSE_LINK}
                >
                  AI data policy
                </a>
              </div>
            </div>
            <ul className="divide-y divide-surface-inverse-border" data-testid="landing-privacy">
              {PRIVACY_POINTS.map((line) => (
                <li key={line} className="flex gap-4 py-5 first:pt-0 last:pb-0">
                  <span
                    aria-hidden="true"
                    className="flex size-9 shrink-0 items-center justify-center rounded-lg border border-surface-inverse-border"
                  >
                    <Check className="size-4 text-surface-inverse-muted" />
                  </span>
                  <span className="pt-1.5 leading-relaxed">{line}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
