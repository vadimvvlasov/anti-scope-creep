import { ChevronDown, Download, Loader2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import {
  downloadFile,
  EXPORT_COMING_SOON,
  EXPORT_DISABLED_HINT,
  exportErrorMessage,
} from "@/lib/export";
import { api, type ExportFormat } from "@/services/api";

const FORMATS: { format: ExportFormat; label: string }[] = [
  { format: "pdf", label: "PDF" },
  { format: "docx", label: "DOCX" },
];

/** `Export report` -> PDF / DOCX. Disabled until the first successful analysis. */
export function ExportMenu({
  contractId,
  hasResults,
}: {
  contractId: string;
  hasResults: boolean;
}) {
  const [exporting, setExporting] = useState(false);

  const runExport = async (format: ExportFormat) => {
    setExporting(true);
    try {
      downloadFile(await api.exportReport(contractId, format));
    } catch (error) {
      const message = exportErrorMessage(error);
      // One toast per kind: repeated clicks replace it instead of stacking copies.
      if (message === EXPORT_COMING_SOON) toast.info(message, { id: "export-coming-soon" });
      else toast.error(message, { id: "export-error" });
    } finally {
      setExporting(false);
    }
  };

  const button = (
    <Button variant="outline" size="sm" disabled={!hasResults || exporting}>
      {exporting ? <Loader2 className="size-4 animate-spin" /> : <Download className="size-4" />}
      Export report
      <ChevronDown className="size-3.5 opacity-60" />
    </Button>
  );

  if (!hasResults) {
    // A disabled button gets no pointer events, so the tooltip hangs on a focusable wrapper.
    return (
      <TooltipProvider delayDuration={150}>
        <Tooltip>
          <TooltipTrigger asChild>
            <span tabIndex={0} className="inline-flex">
              {button}
            </span>
          </TooltipTrigger>
          <TooltipContent>{EXPORT_DISABLED_HINT}</TooltipContent>
        </Tooltip>
      </TooltipProvider>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{button}</DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        {FORMATS.map(({ format, label }) => (
          <DropdownMenuItem key={format} onSelect={() => void runExport(format)}>
            {label}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
