import { cn } from "@/lib/utils";

/** A landing section heading with an optional small label; `inverse` for the dark privacy block. */
export function SectionHeading({
  id,
  eyebrow,
  title,
  className,
  inverse = false,
}: {
  id: string;
  eyebrow?: string;
  title: string;
  className?: string;
  inverse?: boolean;
}) {
  return (
    <div className={cn("max-w-2xl", className)}>
      {eyebrow ? (
        <p
          className={cn(
            "eyebrow mb-4 flex items-center gap-3",
            inverse && "text-surface-inverse-muted",
          )}
          aria-hidden="true"
        >
          <span className="amber-rule" />
          {eyebrow}
        </p>
      ) : null}
      <h2
        id={id}
        className={cn(
          "text-3xl leading-[1.12] font-semibold text-balance sm:text-4xl",
          inverse && "text-surface-inverse-foreground",
        )}
      >
        {title}
      </h2>
    </div>
  );
}
