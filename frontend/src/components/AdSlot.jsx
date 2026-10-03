import React, { useEffect, useRef, useState } from "react";

const CLIENT = "ca-pub-7713392774673260";

// Ad unit IDs come from the AdSense console (Ad units > New ad unit). Leaving
// these empty keeps the loader and the component in place; the slot renders
// inert until real IDs are supplied, which is safer than shipping a guessed ID
// that AdSense would report as invalid.
export const AD_SLOTS = {
  sidebar: "",
  footer: "",
};

// AdSense serves ads asynchronously and never reports layout back to us, so
// every slot reserves its height up front. Reserving space first is what
// keeps ads from shifting the chat transcript while a user is reading.
const RESERVED = {
  horizontal: "90px",
  rectangle: "250px",
  vertical: "600px",
};

/**
 * A single AdSense unit.
 *
 * The loader itself lives in index.html. Each slot pushes itself onto the
 * adsbygoogle queue once the loader has arrived, and pushes again if the
 * loader shows up late. Nothing renders to the DOM by hand: AdSense replaces
 * the placeholder, which keeps us on Google's supported integration path
 * (the auto-ads script does not replace these units for us).
 */
export default function AdSlot({
  slot,
  format = "auto",
  label = "Publicite",
  className = "",
}) {
  const ref = useRef(null);
  const [failed, setFailed] = useState(false);

  // No ad unit ID configured yet: reserve nothing and push nothing, so no
  // blank grey box appears before the console IDs are filled in.
  const enabled = !!slot;

  useEffect(() => {
    if (!enabled) return undefined;
    let cancelled = false;

    const push = () => {
      if (cancelled || !window.adsbygoogle) return false;
      try {
        (window.adsbygoogle = window.adsbygoogle || []).push({});
        return true;
      } catch {
        return false;
      }
    };

    // The loader is async, so it may not exist yet.
    if (push()) return undefined;

    let attempts = 0;
    const poll = setInterval(() => {
      attempts += 1;
      if (push() || attempts > 40) clearInterval(poll);
    }, 250);

    return () => {
      cancelled = true;
      clearInterval(poll);
    };
  }, [slot, enabled]);

  // Ad blockers and "no ads for this visitor" both end with the unit staying
  // empty. Collapse it rather than leaving a hole in the layout.
  useEffect(() => {
    if (!enabled) return undefined;
    const el = ref.current;
    if (!el) return undefined;
    const t = setTimeout(() => {
      if (el && el.offsetHeight === 0) setFailed(true);
    }, 4000);
    return () => clearTimeout(t);
  }, [enabled]);

  if (!enabled || failed) return null;

  return (
    <aside
      ref={ref}
      className={`ad-slot ad-slot-${format} ${className}`}
      style={{ minHeight: RESERVED[format] || RESERVED.horizontal }}
      aria-label={label}
    >
      <ins
        class="adsbygoogle"
        style={{ display: "block" }}
        data-ad-client={CLIENT}
        data-ad-slot={slot}
        data-ad-format={format}
        data-full-width-responsive="true"
      />
    </aside>
  );
}