// Export controls copy and behavior (docs/spec.md "Export controls").

import { isApiError, type ExportedFile } from "@/services/api";

export const EXPORT_DISABLED_HINT = "Export is available after the first successful analysis.";
export const EXPORT_COMING_SOON = "Report export is coming soon.";

/** 501 has its own text (the real backend in the MVP); other errors show the API message. */
export function exportErrorMessage(error: unknown): string {
  if (!isApiError(error)) return "Could not export the report.";
  return error.status === 501 ? EXPORT_COMING_SOON : error.message;
}

/** Saves the file under the name the API gave it. */
export function downloadFile({ blob, filename }: ExportedFile) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}
