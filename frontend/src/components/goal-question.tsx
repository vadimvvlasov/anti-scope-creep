import { Button } from "@/components/ui/button";
import { GOAL_OPTIONS, GOAL_QUESTION } from "@/lib/contract-goal";
import type { ContractGoal } from "@/services/types";

/** One optional question before the upload: a tap selects, a second tap on it skips again. */
export function GoalQuestion({
  value,
  onChange,
}: {
  value: ContractGoal | null;
  onChange: (goal: ContractGoal | null) => void;
}) {
  return (
    <div className="space-y-2" data-testid="goal-question">
      <p id="goal-question-label" className="text-sm font-medium">
        {GOAL_QUESTION} <span className="font-normal text-muted-foreground">(optional)</span>
      </p>
      <div role="group" aria-labelledby="goal-question-label" className="flex flex-wrap gap-2">
        {GOAL_OPTIONS.map((option) => (
          <Button
            key={option.value}
            type="button"
            size="sm"
            variant={value === option.value ? "default" : "outline"}
            aria-pressed={value === option.value}
            data-testid={`goal-${option.value}`}
            onClick={() => onChange(value === option.value ? null : option.value)}
          >
            {option.label}
          </Button>
        ))}
      </div>
    </div>
  );
}
