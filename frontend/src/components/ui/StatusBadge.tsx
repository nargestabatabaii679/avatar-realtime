import { cn } from "../../utils/cn";
import { STATUS_COLORS, type StatusKey } from "../../constants";

interface StatusBadgeProps {
  status: StatusKey | string;
  /** Override the displayed label; defaults to capitalised status key */
  label?: string;
  className?: string;
}

/**
 * Pill badge with dot indicator for entity statuses (ready, processing, failed, etc.).
 * All colour mappings live in constants/index.ts — add new statuses there.
 */
export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const config = STATUS_COLORS[status as StatusKey] ?? STATUS_COLORS.pending;
  const displayLabel = label ?? (status.charAt(0).toUpperCase() + status.slice(1).replace(/_/g, " "));

  return (
    <span className={cn(
      "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
      config.bg,
      config.text,
      className,
    )}>
      <span className={cn("w-1.5 h-1.5 rounded-full", config.dot)} />
      {displayLabel}
    </span>
  );
}
