/** Shared UI-layer types that don't belong in the domain model (types/index.ts). */

export interface ToastNotification {
  id: string;
  type: "success" | "error" | "warning" | "info";
  title: string;
  message?: string;
  duration?: number;
}
