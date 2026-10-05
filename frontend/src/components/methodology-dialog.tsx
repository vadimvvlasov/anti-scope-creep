import { Github, Linkedin } from "lucide-react";
import type { ReactNode } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import { Button } from "@/components/ui/button";
import { useIsMobile } from "@/hooks/use-mobile";
import {
  ANALYSIS_PARAGRAPHS,
  AUTHOR_BIO,
  AUTHOR_LINKS,
  AUTHOR_NAME,
  DATA_POINTS,
  METHODOLOGY_TITLE,
  STUB_ANALYZER_ACTIVE,
  STUB_ANALYZER_NOTICE,
} from "@/lib/methodology";
import { cn } from "@/lib/utils";

const DESCRIPTION =
  "Who built Anti-Scope Creep, how the analysis works, and what happens to your data.";
const LINK_ICONS = { GitHub: Github, LinkedIn: Linkedin } as const;

/** Icon links to the author's profiles; they open in a new tab. */
export function AuthorLinks({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-1", className)}>
      {AUTHOR_LINKS.map(({ label, href }) => {
        const Icon = LINK_ICONS[label];
        return (
          <a
            key={label}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`${AUTHOR_NAME} on ${label}`}
            className="rounded p-1 text-muted-foreground transition-colors hover:text-foreground"
          >
            <Icon className="size-3.5" />
          </a>
        );
      })}
    </span>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="font-display text-sm font-semibold">{title}</h3>
      <div className="space-y-2 text-sm leading-relaxed text-muted-foreground">{children}</div>
    </section>
  );
}

function MethodologyBody() {
  return (
    <div className="space-y-6">
      <Section title="About the author">
        <p>{AUTHOR_BIO}</p>
        <AuthorLinks className="-ml-1" />
      </Section>
      <Section title="How the analysis works">
        {STUB_ANALYZER_ACTIVE && (
          <p className="rounded-md bg-risk-medium-soft px-3 py-2 text-risk-medium">
            {STUB_ANALYZER_NOTICE}
          </p>
        )}
        {ANALYSIS_PARAGRAPHS.map((text) => (
          <p key={text}>{text}</p>
        ))}
      </Section>
      <Section title="Your data">
        <ul className="list-disc space-y-1 pl-5">
          {DATA_POINTS.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      </Section>
    </div>
  );
}

/**
 * A link that opens the Methodology & Privacy dialog (a drawer on narrow screens).
 * No API call; closes on Escape, the close button, or a click outside.
 */
export function MethodologyLink({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const isMobile = useIsMobile();
  const trigger = (
    <button type="button" className={className}>
      {children}
    </button>
  );

  if (isMobile) {
    return (
      <Drawer>
        <DrawerTrigger asChild>{trigger}</DrawerTrigger>
        <DrawerContent className="max-h-[90vh]">
          <div className="overflow-y-auto px-4 pb-4">
            <DrawerTitle className="py-4 font-display text-lg">{METHODOLOGY_TITLE}</DrawerTitle>
            <DrawerDescription className="sr-only">{DESCRIPTION}</DrawerDescription>
            <MethodologyBody />
            <DrawerClose asChild>
              <Button variant="outline" className="mt-6 w-full">
                Close
              </Button>
            </DrawerClose>
          </div>
        </DrawerContent>
      </Drawer>
    );
  }

  return (
    <Dialog>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
        <DialogTitle className="font-display">{METHODOLOGY_TITLE}</DialogTitle>
        <DialogDescription className="sr-only">{DESCRIPTION}</DialogDescription>
        <MethodologyBody />
      </DialogContent>
    </Dialog>
  );
}
