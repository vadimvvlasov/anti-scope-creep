/**
 * The Pro plan is a demand test (a "fake door"): there is no paid plan yet. The dialog
 * says so plainly, and a click on the waitlist button is the signal we measure
 * (docs/analytics.md).
 */

export const PRO_PRICE_USD = 19;

export const PRO_TITLE = "Anti-Scope Creep Pro";
export const PRO_PRICE_LABEL = `$${PRO_PRICE_USD} / month`;
export const PRO_FEATURES = [
  "More analyses per day than the free limit",
  "Longer contracts, up to 150,000 characters",
  "Faster analysis on a dedicated model quota",
] as const;
export const PRO_NOT_AVAILABLE =
  "Pro is not available yet, and nothing is charged. Join the waitlist and we will email you when it launches.";
export const PRO_JOIN = "Join the waitlist";
export const PRO_JOINED = "You're on the waitlist. We'll email you when Pro launches.";

/** Where the Pro button was clicked; sent with the analytics events. */
export type ProPlacement = "header" | "daily_limit";
