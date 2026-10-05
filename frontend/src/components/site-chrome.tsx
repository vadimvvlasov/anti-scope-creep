import { Info } from "lucide-react";

import { AuthorLinks, MethodologyLink } from "@/components/methodology-dialog";
import { AUTHOR_BADGE, AUTHOR_NAME, METHODOLOGY_TITLE } from "@/lib/methodology";

const LINK_CLASS =
  "inline-flex items-center gap-1 rounded text-muted-foreground transition-colors hover:text-foreground";

/** Top strip of every screen's header: the author badge and the Methodology & Privacy link. */
export function AuthorBar() {
  return (
    <div className="border-b border-border/60 text-xs">
      <div className="mx-auto flex h-8 max-w-6xl items-center gap-2 px-4">
        <span className="text-muted-foreground">
          <span className="hidden sm:inline">{AUTHOR_BADGE}</span>
          <span className="sm:hidden">{AUTHOR_NAME}</span>
        </span>
        <AuthorLinks />
        <MethodologyLink className={`${LINK_CLASS} ml-auto`}>
          <Info className="size-3.5" /> {METHODOLOGY_TITLE}
        </MethodologyLink>
      </div>
    </div>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-border">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-6 text-xs">
        <span className="text-muted-foreground">Anti-Scope Creep</span>
        <MethodologyLink className={LINK_CLASS}>{METHODOLOGY_TITLE}</MethodologyLink>
      </div>
    </footer>
  );
}
