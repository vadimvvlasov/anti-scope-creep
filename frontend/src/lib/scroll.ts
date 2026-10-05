const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const scrollsOnItsOwn = (el: HTMLElement) =>
  el.scrollHeight > el.clientHeight && getComputedStyle(el).overflowY !== "visible";

/**
 * Brings `target` to the middle of `panel` when the panel scrolls on its own (side-by-side
 * layout), otherwise scrolls the page (stacked layout). No smooth scroll with reduced motion.
 */
export function scrollPanelTo(panel: HTMLElement | null, target: Element | null) {
  if (!target) return;
  const behavior: ScrollBehavior = prefersReducedMotion() ? "auto" : "smooth";
  if (!panel || !scrollsOnItsOwn(panel)) {
    target.scrollIntoView({ behavior, block: "center" });
    return;
  }
  const box = target.getBoundingClientRect();
  const offset = box.top - panel.getBoundingClientRect().top + box.height / 2;
  panel.scrollTo({ top: panel.scrollTop + offset - panel.clientHeight / 2, behavior });
}
