import { Camera } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { SCAN_PHOTO_BUTTON, SCAN_PHOTO_NOT_AVAILABLE, SCAN_PHOTO_TITLE } from "@/lib/scan-photo";
import { analytics } from "@/services/analytics";
import { useIsMobile } from "@/hooks/use-mobile";

/**
 * A demand test (a "fake door", docs/analytics.md): there is no photo scanning. The button only
 * records the click; no camera is opened and nothing is uploaded.
 */
export function ScanPhotoDialog() {
  const [open, setOpen] = useState(false);
  const isMobile = useIsMobile();

  const onOpenChange = (next: boolean) => {
    if (next) {
      analytics.track("scan_photo_clicked", {
        placement: "scan_photo",
        screen: isMobile ? "mobile" : "desktop",
      });
    }
    setOpen(next);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>
        <Button
          type="button"
          variant="outline"
          className="w-full md:hidden"
          data-testid="scan-photo-button"
        >
          <Camera className="size-4" /> {SCAN_PHOTO_BUTTON}
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-sm">
        <DialogTitle>{SCAN_PHOTO_TITLE}</DialogTitle>
        <DialogDescription>{SCAN_PHOTO_NOT_AVAILABLE}</DialogDescription>
      </DialogContent>
    </Dialog>
  );
}
