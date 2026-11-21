import { useEffect, useState } from "react";

import { localServiceHours, serviceNotice, type HoursText } from "@/lib/service-hours";

/**
 * The free test mode and service hours line (docs/spec.md "Service hours notice"). The hours are
 * filled in after the page loads: the landing page is prerendered and has no visitor time zone.
 */
export function ServiceNotice({ className = "" }: { className?: string }) {
  const [hours, setHours] = useState<HoursText | null>(null);
  useEffect(() => setHours(localServiceHours()), []);
  return (
    <p className={`text-xs text-muted-foreground ${className}`} data-testid="service-notice">
      {serviceNotice(hours)}
    </p>
  );
}
