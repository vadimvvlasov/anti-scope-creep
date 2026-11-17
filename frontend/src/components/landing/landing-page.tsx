import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { ContractPreview } from "@/components/landing/contract-preview";
import { MethodologyLink } from "@/components/methodology-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
  CHECKS_HEADING,
  CLOSING_SAMPLE_LINK,
  FEATURES,
  FEATURES_HEADING,
  HERO_HEADING,
  LOG_IN,
  PRIVACY_HEADING,
  SEE_SAMPLE_BUTTON,
  SEE_SAMPLE_LINK,
  STEPS,
  STEPS_HEADING,
} from "@/lib/landing-copy";
import { LOGIN_TAGLINE, LOGIN_VALUE_LINE } from "@/lib/login-copy";
import {
  AI_DATA_POLICY_URL,
  ANALYZER,
  METHODOLOGY_TITLE,
  uploadPrivacyPoints,
} from "@/lib/methodology";
import { CTA_BUTTON, CTA_HEADING, DEFAULT_SAMPLE } from "@/lib/samples";
import { APP_VERSION } from "@/lib/version";
import { LEGAL_DISCLAIMER, RISK_CATEGORY_LABELS } from "@/services/types";

// The landing page at `/` for a guest (docs/spec.md "Landing page"). Static: prerendered at build
// time, no API call. Drafted in Lovable (docs/lovable/landing.md) and ported with the app's components.

const PRIVACY_POINTS = uploadPrivacyPoints(ANALYZER);
const LINK_CLASS =
  "font-medium text-foreground underline decoration-border decoration-2 underline-offset-4 transition-colors hover:decoration-accent";
const BIG_BUTTON = "h-12 w-full px-6 text-base sm:w-auto";

// `<Button asChild>` styles these links through `className`, so they must pass it on.
interface LinkProps {
  className?: string;
  children: ReactNode;
}

function SampleLink({ className, children }: LinkProps) {
  return (
    <Link to="/sample/$name" params={{ name: DEFAULT_SAMPLE }} className={className}>
      {children}
    </Link>
  );
}

function RegisterLink({ className, children }: LinkProps) {
  return (
    <Link to="/login" search={{ tab: "register" }} className={className}>
      {children}
    </Link>
  );
}

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <LandingHeader />
      <main>
        <Hero />
        <WhatYouGet />
        <WhatItChecks />
        <HowItWorks />
        <Privacy />
        <ClosingCta />
      </main>
      <LandingFooter />
    </div>
  );
}

function LandingHeader() {
  const navLink =
    "rounded-md px-2 py-2 text-sm whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground sm:px-3";
  return (
    <header className="sticky top-0 z-20 border-b bg-background/90 backdrop-blur">
      <div className="page-container flex h-16 items-center justify-between gap-3">
        <span className="flex items-center gap-2 font-display text-[0.95rem] font-semibold tracking-tight whitespace-nowrap sm:text-base">
          <span
            aria-hidden="true"
            className="amber-rule hidden size-3 rounded-sm sm:inline-block"
          />
          Anti-Scope Creep
        </span>
        <nav aria-label="Main" className="flex shrink-0 items-center gap-0.5 sm:gap-2">
          <SampleLink className={`${navLink} hidden md:inline-block`}>{SEE_SAMPLE_LINK}</SampleLink>
          <Link to="/login" search={{ tab: "login" }} className={navLink}>
            {LOG_IN}
          </Link>
          <Button asChild size="sm" className="px-2.5 sm:h-9 sm:px-4 sm:text-sm">
            <RegisterLink>{CTA_BUTTON}</RegisterLink>
          </Button>
        </nav>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section
      aria-labelledby="hero-heading"
      className="page-container pt-12 pb-20 sm:pt-20 lg:pt-24 lg:pb-28"
    >
      <div className="grid items-center gap-14 lg:grid-cols-[1.05fr_1fr] lg:gap-16">
        <div className="animate-in fade-in slide-in-from-bottom-2 duration-700">
          <p className="flex items-start gap-3 text-sm text-muted-foreground">
            <span aria-hidden="true" className="amber-rule mt-2.5 shrink-0" />
            {LOGIN_TAGLINE}
          </p>
          <h1
            id="hero-heading"
            className="mt-5 text-4xl leading-[1.08] font-semibold text-balance sm:text-5xl lg:text-[3.5rem]"
          >
            {HERO_HEADING}
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
            {LOGIN_VALUE_LINE}
          </p>
          <div className="mt-9 flex flex-col gap-3 sm:flex-row">
            <Button asChild className={BIG_BUTTON}>
              <SampleLink>{SEE_SAMPLE_BUTTON}</SampleLink>
            </Button>
            <Button asChild variant="outline" className={BIG_BUTTON}>
              <RegisterLink>{CTA_BUTTON}</RegisterLink>
            </Button>
          </div>
        </div>
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-1000">
          <ContractPreview />
        </div>
      </div>
    </section>
  );
}

function SectionHeading({ id, eyebrow, title }: { id: string; eyebrow?: string; title: string }) {
  return (
    <div className="max-w-2xl">
      {eyebrow ? (
        <p className="eyebrow flex items-center gap-3" aria-hidden="true">
          <span className="amber-rule" />
          {eyebrow}
        </p>
      ) : null}
      <h2 id={id} className="mt-3 text-2xl leading-tight font-semibold text-balance sm:text-3xl">
        {title}
      </h2>
    </div>
  );
}

const counter = (i: number) => String(i + 1).padStart(2, "0");

function WhatYouGet() {
  return (
    <section aria-labelledby="get-heading" className="border-t bg-muted/60">
      <div className="page-container py-20 sm:py-24">
        <SectionHeading id="get-heading" title={FEATURES_HEADING} />
        <div className="mt-10 grid gap-5 md:grid-cols-3">
          {FEATURES.map((f, i) => (
            <Card key={f.title} className="shadow-none">
              <CardHeader className="pb-3">
                <span aria-hidden="true" className="font-mono text-xs text-muted-foreground">
                  {counter(i)}
                </span>
                <h3 className="pt-2 text-lg leading-snug font-semibold">{f.title}</h3>
              </CardHeader>
              <CardContent>
                <p className="leading-relaxed text-muted-foreground">{f.body}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}

function WhatItChecks() {
  return (
    <section aria-labelledby="checks-heading" className="border-t">
      <div className="page-container grid gap-10 py-20 sm:py-24 lg:grid-cols-[1fr_1.4fr] lg:gap-16">
        <SectionHeading id="checks-heading" eyebrow="What it checks" title={CHECKS_HEADING} />
        <ol className="grid border-t sm:grid-cols-2 sm:gap-x-10">
          {Object.values(RISK_CATEGORY_LABELS).map((label, i) => (
            <li key={label} className="flex items-baseline gap-4 border-b py-4">
              <span
                aria-hidden="true"
                className="w-6 shrink-0 font-mono text-xs text-muted-foreground"
              >
                {counter(i)}
              </span>
              <span className="font-medium">{label}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function HowItWorks() {
  return (
    <section aria-labelledby="how-heading" className="border-t bg-muted/60">
      <div className="page-container py-20 sm:py-24">
        <SectionHeading id="how-heading" title={STEPS_HEADING} />
        <ol className="mt-10 grid gap-8 md:grid-cols-3 md:gap-6">
          {STEPS.map((step, i) => (
            <li key={step} className="flex gap-4 md:flex-col md:gap-5">
              <span
                aria-hidden="true"
                className="flex size-10 shrink-0 items-center justify-center rounded-full border-2 border-accent bg-card font-display text-sm font-semibold"
              >
                {i + 1}
              </span>
              <p className="pt-2 text-lg leading-relaxed md:pt-0">{step}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function Privacy() {
  return (
    <section aria-labelledby="privacy-heading" className="border-t">
      <div className="page-container grid gap-10 py-20 sm:py-24 lg:grid-cols-[1fr_1.4fr] lg:gap-16">
        <div>
          <SectionHeading id="privacy-heading" eyebrow="Privacy" title={PRIVACY_HEADING} />
          <p className="mt-6">
            <MethodologyLink className={LINK_CLASS}>{METHODOLOGY_TITLE}</MethodologyLink>
          </p>
        </div>
        <Card className="shadow-paper">
          <CardContent className="p-6 sm:p-8">
            <ul className="space-y-5" data-testid="landing-privacy">
              {PRIVACY_POINTS.map((line) => (
                <li key={line} className="flex gap-4 leading-relaxed">
                  <span
                    aria-hidden="true"
                    className="mt-2.5 size-1.5 shrink-0 rounded-full bg-primary"
                  />
                  <span>{line}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </section>
  );
}

function ClosingCta() {
  return (
    <section aria-labelledby="cta-heading" className="border-t">
      <div className="page-container py-20 sm:py-28">
        <div className="flex flex-col items-start gap-8 rounded-xl border bg-card p-8 shadow-paper sm:p-12 md:flex-row md:items-center md:justify-between">
          <h2 id="cta-heading" className="text-3xl leading-tight font-semibold sm:text-4xl">
            {CTA_HEADING}
          </h2>
          <div className="flex w-full flex-col gap-4 sm:w-auto sm:flex-row sm:items-center sm:gap-6">
            <Button asChild className={BIG_BUTTON}>
              <RegisterLink>{CTA_BUTTON}</RegisterLink>
            </Button>
            <SampleLink className={`${LINK_CLASS} text-center`}>{CLOSING_SAMPLE_LINK}</SampleLink>
          </div>
        </div>
      </div>
    </section>
  );
}

function LandingFooter() {
  return (
    <footer className="border-t bg-muted/60">
      <div className="page-container flex flex-col gap-6 py-10 text-sm md:flex-row md:items-start md:justify-between md:gap-12">
        <p className="max-w-2xl leading-relaxed text-muted-foreground">{LEGAL_DISCLAIMER}</p>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2">
            <MethodologyLink className={LINK_CLASS}>{METHODOLOGY_TITLE}</MethodologyLink>
            <a
              href={AI_DATA_POLICY_URL}
              target="_blank"
              rel="noopener noreferrer"
              className={LINK_CLASS}
            >
              AI data policy
            </a>
          </nav>
          <Badge
            variant="outline"
            className="font-mono font-normal text-muted-foreground"
            title="Build version"
          >
            {APP_VERSION}
          </Badge>
        </div>
      </div>
    </footer>
  );
}
