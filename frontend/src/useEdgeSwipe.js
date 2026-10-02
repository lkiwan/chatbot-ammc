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
  // True while a swipe owns the gesture. Panels like the mobile menu and the
  // PDF viewer are fixed overlays that cover the whole screen, so the pointer
  // never reaches the .app element while they are open. Listening on window
  // instead means an edge swipe still registers no matter what is on top.
  const [swallowing, setSwallowing] = useState(false);
  const swallowRef = useRef(false);

  useEffect(() => {
    target.current = Math.max(240, Math.min(width || 320, 420));
  }, [width]);

  const reset = useCallback(() => {
    drag.current = null;
    setEdge(null);
    setProgress(0);
  }, []);

  // Re-arm the listeners whenever the relevant state changes: the gesture is
  // only enabled on mobile, and "is this panel open" is snapshotted at
  // pointerdown, so a stale closure would toggle the wrong panel.
  useEffect(() => {
    if (!enabled) {
      reset();
      return undefined;
    }

    const down = (e) => {
      if (e.pointerType === "mouse") return;   // mouse keeps click/drag behaviour
      if (drag.current) return;                // ignore extra fingers

      const w = window.innerWidth;
      const fromStart = e.clientX <= EDGE;
      const fromEnd = e.clientX >= w - EDGE;
      if (!fromStart && !fromEnd) return;

      // Let genuinely interactive edge widgets (sliders, carousels) win.
      const t = e.target;
      if (t && typeof t.closest === "function" && t.closest("[data-no-swipe]")) return;

      const side = fromStart ? "start" : "end";
      drag.current = {
        side,
        wasOpen: side === "start" ? !!startOpen : !!endOpen,
        x0: e.clientX,
        y0: e.clientY,
        axis: null,
      };
    };

    const move = (e) => {
      const d = drag.current;
      if (!d) return;

      const dx = e.clientX - d.x0;
      const dy = e.clientY - d.y0;

      if (!d.axis) {
        if (Math.abs(dx) < SLOP && Math.abs(dy) < SLOP) return;
        if (Math.abs(dy) > Math.abs(dx)) { reset(); return; }  // vertical: let it scroll
        d.axis = "x";
        setEdge(d.side);
        setSwallowing(true);
        swallowRef.current = true;
      }

      const signed = d.side === "start" ? dx : -dx;
      const travel = (signed / target.current) * MAX_SHIFT;
      const base = d.wasOpen ? 1 : 0;
      setProgress(Math.max(0, Math.min(1, base + travel)));
      e.preventDefault();
    };

    const up = (e) => {
      const d = drag.current;
      if (!d) return;

      if (d.axis === "x") {
        const dx = e.clientX - d.x0;
        const signed = d.side === "start" ? dx : -dx;
        const travel = (signed / target.current) * MAX_SHIFT;

        // Open when dragged far enough toward open; close when dragged back the
        // other way. Either way one gesture = one toggle.
        if (d.wasOpen ? travel <= -COMMIT : travel >= COMMIT) {
          if (d.side === "start") onToggleStart?.();
          else onToggleEnd?.();
        }
      }
      reset();
    };

    const cancel = () => { reset(); setSwallowing(false); swallowRef.current = false; };

    window.addEventListener("pointerdown", down, { passive: true });
    window.addEventListener("pointermove", move, { passive: false });
    window.addEventListener("pointerup", up, { passive: true });
    window.addEventListener("pointercancel", cancel, { passive: true });
    return () => {
      window.removeEventListener("pointerdown", down);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", cancel);
    };
  }, [enabled, startOpen, endOpen, onToggleStart, onToggleEnd, reset]);

  // A recognised swipe must not also register as a click. Browsers fire click
  // after a touch gesture, so without this the overlay scrim underneath would
  // close the panel that the swipe just opened (or vice versa). Capture-phase
  // listener so it runs before React's synthetic handlers.
  useEffect(() => {
    if (!swallowRef.current) return undefined;
    const kill = (e) => {
      if (!swallowRef.current) return;
      e.stopPropagation();
      e.preventDefault();
    };
    window.addEventListener("click", kill, { capture: true });
    window.addEventListener("touchend", kill, { capture: true, passive: false });
    const t = setTimeout(() => {
      swallowRef.current = false;
      setSwallowing(false);
    }, 400);
    return () => {
      window.removeEventListener("click", kill, { capture: true });
      window.removeEventListener("touchend", kill, { capture: true });
      clearTimeout(t);
    };
  }, [swallowing]);

  return {
    edge,
    progress,
    // True from the moment a swipe is recognised until the gesture ends. The
    // overlay scrims must not also treat that same touch as a click, or
    // swiping from the far edge would toggle a panel twice.
    shouldSwallowClick: swallowing,
    reset,
  };
}
