import { MethodologyLink } from "@/components/methodology-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  ANALYZE_BUTTON,
  ANALYZE_NOTE,
  CLOSING_HEADING,
  FOOTER_LINE,
  HERO_HEADING,
  LOG_IN,
  SEE_SAMPLE_LINK,
  TRY_SAMPLE_BUTTON,
  TRY_SAMPLE_NOTE,
} from "@/lib/landing-copy";
import { LOGIN_TAGLINE, LOGIN_VALUE_LINE } from "@/lib/login-copy";
import { AI_DATA_POLICY_URL, METHODOLOGY_TITLE } from "@/lib/methodology";
import { APP_VERSION } from "@/lib/version";
import { LEGAL_DISCLAIMER } from "@/services/types";

import { HeroReview } from "./hero-review";
import { HowItWorks, Privacy, WhatItChecks, WhatYouGet } from "./landing-sections";
import { LoginLink, RegisterLink, SampleLink } from "./links";
import { Reveal } from "./reveal";
import { SampleDemo } from "./sample-demo";

// The landing page at `/` for a guest (docs/spec.md "Landing page"). Static: prerendered at build
// time, no API call. Drafted in Lovable (docs/lovable/landing.md, then a redesign in #151) and ported
// onto the app's components.

const LINK_CLASS =
  "cursor-pointer font-medium text-foreground underline decoration-border decoration-2 underline-offset-4 transition-colors hover:decoration-accent";
const BIG_BUTTON = "h-12 w-full px-6 text-base sm:w-auto";

export function LandingPage() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <LandingHeader />
      <main>
        <Hero />
        <SampleDemo />
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

function ProductName() {
  return (
    <span className="flex items-center gap-2 font-display text-[0.95rem] font-semibold tracking-tight whitespace-nowrap sm:text-base">
      <span aria-hidden="true" className="amber-rule hidden size-3 rounded-sm sm:inline-block" />
      Anti-Scope Creep
    </span>
  );
}

function LandingHeader() {
  const navLink =
    "rounded-md px-2 py-2 text-sm whitespace-nowrap text-muted-foreground transition-colors hover:text-foreground sm:px-3";
  return (
    <header className="sticky top-0 z-20 border-b bg-background/90 backdrop-blur">
      <div className="page-container flex h-16 items-center justify-between gap-3">
        <ProductName />
        <nav aria-label="Main" className="flex shrink-0 items-center gap-0.5 sm:gap-2">
          <SampleLink className={`${navLink} hidden md:inline-block`}>{SEE_SAMPLE_LINK}</SampleLink>
          <LoginLink className={navLink}>{LOG_IN}</LoginLink>
          <Button asChild size="sm" className="px-2.5 sm:h-9 sm:px-4 sm:text-sm">
            <RegisterLink>{ANALYZE_BUTTON}</RegisterLink>
          </Button>
        </nav>
      </div>
    </header>
  );
}

/** The two calls to action; with notes under the buttons in the hero. */
function CtaButtons({ notes = false }: { notes?: boolean }) {
  const note = "text-center text-xs text-muted-foreground sm:text-left";
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-start">
      <div className="flex flex-col gap-2">
        <Button asChild className={BIG_BUTTON}>
          <SampleLink>{TRY_SAMPLE_BUTTON}</SampleLink>
        </Button>
        {notes ? <span className={note}>{TRY_SAMPLE_NOTE}</span> : null}
      </div>
      <div className="flex flex-col gap-2">
        <Button asChild variant="outline" className={BIG_BUTTON}>
          <RegisterLink>{ANALYZE_BUTTON}</RegisterLink>
        </Button>
        {notes ? <span className={note}>{ANALYZE_NOTE}</span> : null}
      </div>
    </div>
  );
}

function Hero() {
  return (
    <section
      aria-labelledby="hero-heading"
      className="page-container pt-10 pb-24 sm:pt-16 md:pt-12 lg:pt-20 lg:pb-32"
    >
      <div className="grid items-center gap-14 md:grid-cols-2 md:items-start md:gap-10 lg:grid-cols-[1fr_1.05fr] lg:items-center lg:gap-14">
        <div className="animate-in fade-in slide-in-from-bottom-2 duration-700">
          <p className="flex items-start gap-3 text-sm text-muted-foreground">
            <span aria-hidden="true" className="amber-rule mt-2.5 shrink-0" />
            {LOGIN_TAGLINE}
          </p>
          <h1
            id="hero-heading"
            className="mt-5 text-4xl leading-[1.08] font-semibold text-balance sm:text-5xl md:text-[2.6rem] lg:text-[3.5rem]"
          >
            {HERO_HEADING}
          </h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground md:text-base lg:text-lg">
            {LOGIN_VALUE_LINE}
          </p>
          <div className="mt-9 md:mt-7 lg:mt-9">
            <CtaButtons notes />
          </div>
        </div>
        <div className="animate-in fade-in slide-in-from-bottom-4 duration-1000">
          <HeroReview />
        </div>
      </div>
    </section>
  );
}

function ClosingCta() {
  return (
    <section aria-labelledby="cta-heading" className="border-t">
      <div className="page-container py-20 sm:py-28">
        <Reveal>
          <div className="flex flex-col items-center rounded-2xl border bg-card px-6 py-14 text-center shadow-paper sm:px-12 sm:py-20">
            <h2
              id="cta-heading"
              className="max-w-2xl text-3xl leading-[1.1] font-semibold sm:text-5xl"
            >
              {CLOSING_HEADING}
            </h2>
            <div className="mt-9 flex w-full justify-center sm:w-auto">
              <CtaButtons />
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function LandingFooter() {
  return (
    <footer className="border-t bg-muted/60">
      <div className="page-container py-12 text-sm">
        <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
          <div>
            <ProductName />
            <p className="mt-3 max-w-xs leading-relaxed text-muted-foreground">{FOOTER_LINE}</p>
          </div>
          <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-3">
            <SampleLink className={LINK_CLASS}>{SEE_SAMPLE_LINK}</SampleLink>
            <LoginLink className={LINK_CLASS}>{LOG_IN}</LoginLink>
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
        </div>
        <div className="mt-10 flex flex-col gap-4 border-t pt-6 md:flex-row md:items-start md:justify-between">
          <p className="max-w-2xl text-xs leading-relaxed text-muted-foreground">
            {LEGAL_DISCLAIMER}
          </p>
          <Badge
            variant="outline"
            className="self-start font-mono font-normal text-muted-foreground"
            title="Build version"
          >
            {APP_VERSION}
          </Badge>
        </div>
      </div>
    </footer>
  );
}
