import { useCallback, useEffect, useRef, useState } from "react";

const EDGE = 30;          // px from the physical screen edge that arms a swipe
const COMMIT = 0.35;      // fraction of travel that counts as "open"
const MAX_SHIFT = 0.85;   // travel is damped so the panel never feels rubbery
const SLOP = 10;          // px of movement before we decide this is a swipe

/**
 * Edge swipe to open the side panels on touch devices.
 *
 * Swiping right from the left edge opens the company menu; swiping left from
 * the right edge opens the PDF viewer. While the finger is down the panels
 * follow it 1:1 (damped) so the gesture feels connected, and `progress` runs
 * 0 -> 1 so the caller can drive transforms without extra state.
 *
 * Returns { edge, progress, bind } where `edge` is null, "start" or "end".
 * `bind` is spread onto the element that should receive the pointer events.
 */
export default function useEdgeSwipe({ enabled, onOpenStart, onOpenEnd, width }) {
  const [edge, setEdge] = useState(null);
  const [progress, setProgress] = useState(0);

  const drag = useRef(null);
  const target = useRef(Math.max(240, Math.min(width || 320, 420)));

  useEffect(() => {
    target.current = Math.max(240, Math.min(width || 320, 420));
  }, [width]);

  const reset = useCallback(() => {
    drag.current = null;
    setEdge(null);
    setProgress(0);
  }, []);

  const onPointerDown = useCallback((e) => {
    if (!enabled) return;
    if (e.pointerType === "mouse") return;      // mouse keeps click/drag behaviour
    if (drag.current) return;                    // ignore extra fingers

    const w = window.innerWidth;
    const fromStart = e.clientX <= EDGE;
    const fromEnd = e.clientX >= w - EDGE;
    if (!fromStart && !fromEnd) return;

    drag.current = {
      side: fromStart ? "start" : "end",
      x0: e.clientX,
      y0: e.clientY,
      axis: null,
    };
  }, [enabled]);

  const onPointerMove = useCallback((e) => {
    const d = drag.current;
    if (!d) return;

    const dx = e.clientX - d.x0;
    const dy = e.clientY - d.y0;

    if (!d.axis) {
      if (Math.abs(dx) < SLOP && Math.abs(dy) < SLOP) return;
      // vertical intent: let the page scroll, abandon the swipe
      if (Math.abs(dy) > Math.abs(dx)) { reset(); return; }
      d.axis = "x";
      setEdge(d.side);
    }

    // rightward swipe opens "start", leftward opens "end"
    const raw = d.side === "start" ? dx : -dx;
    if (raw < 0) { reset(); return; }

    const eased = Math.min(1, (raw / target.current) * MAX_SHIFT);
    setProgress(eased);
    e.preventDefault?.();
  }, [reset]);

  const onPointerUp = useCallback((e) => {
    const d = drag.current;
    if (!d) return;
    const dx = e.clientX - d.x0;
    const raw = d.side === "start" ? dx : -dx;
    const opened = raw / target.current;

    if (d.axis === "x") {
      if (opened >= COMMIT) {
        if (d.side === "start") onOpenStart?.();
        else onOpenEnd?.();
      }
    }
    reset();
  }, [onOpenStart, onOpenEnd, reset]);

  return {
    edge,
    progress,
    bind: {
      onPointerDown,
      onPointerMove,
      onPointerUp,
      onPointerCancel: reset,
    },
  };
}