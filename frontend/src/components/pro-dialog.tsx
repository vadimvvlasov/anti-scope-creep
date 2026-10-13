import { Sparkles } from "lucide-react";
import { useState, type ReactNode } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { useAuth } from "@/hooks/useAuth";
import {
  PRO_FEATURES,
  PRO_JOIN,
  PRO_JOINED,
  PRO_NOT_AVAILABLE,
  PRO_PRICE_LABEL,
  PRO_PRICE_USD,
  PRO_TITLE,
  type ProPlacement,
} from "@/lib/pro";
import { analytics } from "@/services/analytics";

/** The Pro plan dialog: price, features, and a waitlist button (a demand test). */
export function ProDialog({ placement, trigger }: { placement: ProPlacement; trigger: ReactNode }) {
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const [joined, setJoined] = useState(false);

  const onOpenChange = (next: boolean) => {
    if (next) analytics.track("pro_cta_clicked", { placement });
    setOpen(next);
  };

  const join = () => {
    analytics.track("pro_waitlist_joined", { placement, price_usd: PRO_PRICE_USD });
    setJoined(true);
    setOpen(false);
    toast.success(PRO_JOINED, { id: "pro-waitlist" });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="max-w-md">
        <DialogTitle className="flex items-center gap-2">
          <Sparkles className="size-5 text-accent" /> {PRO_TITLE}
        </DialogTitle>
        <p className="text-2xl font-semibold">{PRO_PRICE_LABEL}</p>
        <ul className="list-disc space-y-1 pl-5 text-sm">
          {PRO_FEATURES.map((feature) => (
            <li key={feature}>{feature}</li>
          ))}
        </ul>
        <DialogDescription>
          {PRO_NOT_AVAILABLE}
          {user?.email ? ` We will write to ${user.email}.` : ""}
        </DialogDescription>
        <Button onClick={join} disabled={joined} data-testid="pro-join">
          {joined ? "On the waitlist" : PRO_JOIN}
        </Button>
      </DialogContent>
    </Dialog>
  );
}

/** The header button that opens the Pro dialog. */
export function ProButton() {
  return (
    <ProDialog
      placement="header"
      trigger={
        <Button variant="outline" size="sm" data-testid="pro-button">
          <Sparkles className="size-4" /> Pro
        </Button>
      }
    />
  );
}
