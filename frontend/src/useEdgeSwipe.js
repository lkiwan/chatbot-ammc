import { useCallback, useEffect, useRef, useState } from "react";

const EDGE = 30;          // px from the physical screen edge that arms a swipe
const COMMIT = 0.35;      // fraction of travel that counts as a completed swipe
const MAX_SHIFT = 0.85;   // travel is damped so the panel never feels rubbery
const SLOP = 10;          // px of movement before we decide this is a swipe

/**
 * Edge swipe to toggle the side panels on touch devices.
 *
 *   left edge  -> company menu   (opens on a rightward drag, closes on a leftward one)
 *   right edge -> PDF viewer     (opens on a leftward drag,  closes on a rightward one)
 *
 * While the finger is down the panels follow it 1:1 (damped) so the gesture
 * feels connected. `progress` is always "openness" 0 -> 1, for both the opening
 * and the closing direction, so the caller can drive a single transform.
 *
 * The open/closed state is captured at pointerdown. That matters: without it,
 * a gesture that commits on release would flip the panel state and disable or
 * re-target the hook mid-drag, leaving the panel stranded part-way open.
 *
 * Returns { edge, progress, bind } where `edge` is null, "start" or "end".
 * `bind` is spread onto the element that should receive the pointer events.
 */
export default function useEdgeSwipe({
  enabled,
  startOpen,
  endOpen,
  onToggleStart,
  onToggleEnd,
  width,
}) {
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
    if (drag.current) return;                   // ignore extra fingers
    if (e.target.closest?.("[data-no-swipe]")) return; // sliders, carousels, selects

    const w = window.innerWidth;
    const fromStart = e.clientX <= EDGE;
    const fromEnd = e.clientX >= w - EDGE;
    if (!fromStart && !fromEnd) return;

    const side = fromStart ? "start" : "end";
    // Freeze the state for this gesture: committing on release must not
    // re-evaluate "is it open?" using the state it is about to become.
    const wasOpen = side === "start" ? !!startOpen : !!endOpen;

    drag.current = {
      side,
      wasOpen,
      x0: e.clientX,
      y0: e.clientY,
      axis: null,
    };
  }, [enabled, startOpen, endOpen]);

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

    // `signed` is always openness-increasing: the menu lives on the left and
    // opens by dragging right, the PDF lives on the right and opens by
    // dragging left, so the two mirror each other. Positive = more open,
    // negative = being pushed closed.
    const signed = d.side === "start" ? dx : -dx;
    const travel = (signed / target.current) * MAX_SHIFT;

    // Start from the panel's current openness and move with the finger, then
    // clamp: dragging past either end simply holds at 0 or 1.
    const base = d.wasOpen ? 1 : 0;
    setProgress(Math.max(0, Math.min(1, base + travel)));
    e.preventDefault?.();
  }, [reset]);

  const onPointerUp = useCallback((e) => {
    const d = drag.current;
    if (!d) return;

    if (d.axis === "x") {
      const dx = e.clientX - d.x0;
      const signed = d.side === "start" ? dx : -dx;
      const moved = (signed / target.current) * MAX_SHIFT;

      // Open when dragged far enough toward open, close when dragged far
      // enough back the other way. Either way one gesture = one toggle.
      const shouldToggle = d.wasOpen ? moved <= -COMMIT : moved >= COMMIT;

      if (shouldToggle) {
        if (d.side === "start") onToggleStart?.();
        else onToggleEnd?.();
      }
    }
    reset();
  }, [onToggleStart, onToggleEnd, reset]);

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