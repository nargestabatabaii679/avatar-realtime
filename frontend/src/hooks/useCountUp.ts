import { useEffect, useState } from "react";
import { TIMING } from "../constants";

/**
 * Animates a number from 0 to `target` using a cubic ease-out curve.
 * @param target   The final value to count up to.
 * @param duration Animation duration in ms (defaults to TIMING.countUpMs).
 * @param delay    Delay before animation starts in ms.
 */
export function useCountUp(
  target: number,
  duration = TIMING.countUpMs,
  delay = 0,
): number {
  const [value, setValue] = useState(0);

  useEffect(() => {
    if (!target) {
      setValue(0);
      return;
    }

    let rafId: number;
    const startTime = Date.now() + delay;

    const tick = () => {
      const elapsed = Date.now() - startTime;
      if (elapsed < 0) {
        rafId = requestAnimationFrame(tick);
        return;
      }
      const progress = Math.min(elapsed / duration, 1);
      // Cubic ease-out: fast start, slow finish
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(target * eased));
      if (progress < 1) {
        rafId = requestAnimationFrame(tick);
      }
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [target, duration, delay]);

  return value;
}
