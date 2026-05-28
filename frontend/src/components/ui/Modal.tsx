import { useEffect } from "react";
import { X } from "lucide-react";
import { cn } from "../../utils/cn";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: string;
  subtitle?: string;
  /** Icon element shown in the header badge (e.g. <Mic size={16} />) */
  icon?: React.ReactNode;
  children: React.ReactNode;
  /** Tailwind max-width class, default "max-w-lg" */
  maxWidth?: string;
}

/**
 * Reusable modal overlay.
 * Closes on Escape key and backdrop click.
 */
export function Modal({ open, onClose, title, subtitle, icon, children, maxWidth = "max-w-lg" }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ backgroundColor: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }}
      onClick={onClose}
    >
      <div
        className={cn("w-full rounded-3xl p-6 animate-fade-in border shadow-2xl", maxWidth)}
        style={{ backgroundColor: "hsl(var(--card))", borderColor: "hsl(var(--border))" }}
        onClick={(e) => e.stopPropagation()}
      >
        {(title || icon) && (
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              {icon && (
                <div
                  className="w-9 h-9 rounded-xl flex items-center justify-center text-white"
                  style={{ background: "var(--gradient-primary)" }}
                >
                  {icon}
                </div>
              )}
              {(title || subtitle) && (
                <div>
                  {title   && <h2 className="text-base font-bold"   style={{ color: "hsl(var(--foreground))" }}>{title}</h2>}
                  {subtitle && <p className="text-xs mt-0.5"        style={{ color: "hsl(var(--muted-foreground))" }}>{subtitle}</p>}
                </div>
              )}
            </div>
            <button
              onClick={onClose}
              className="p-2 rounded-xl hover:bg-accent transition-colors"
              style={{ color: "hsl(var(--muted-foreground))" }}
              aria-label="Close"
            >
              <X size={16} />
            </button>
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
