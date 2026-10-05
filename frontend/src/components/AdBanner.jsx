import React, { useEffect, useRef, useState } from "react";

const AD_KEY = "30d74840a0fdcbd6c076b560e162fd3a";
const AD_SRC = `https://bauval.org/22/${AD_KEY}`;

/**
 * 320×50 banner — bauval.org ad network.
 * Injects the exact <script> pair the network requires, inside a reserved
 * 50px container, once the banner enters the viewport.
 */
export default function AdBanner({ slotId, className = "" }) {
  const frameRef = useRef(null);
  const [failed, setFailed] = useState(false);
  const injected = useRef(false);

  useEffect(() => {
    if (injected.current) return;
    const el = frameRef.current;
    if (!el) return;

    const obs = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting) return;
        obs.disconnect();
        if (injected.current) return;
        injected.current = true;

        // Mirror exactly what the network asks for in HTML:
        //   <script> atOptions = { key, format, height, width, params } </script>
        //   <script src="https://bauval.org/22/KEY"></script>
        window.atOptions = {
          key: AD_KEY,
          format: "iframe",
          height: 50,
          width: 320,
          params: {},
        };

        const s = document.createElement("script");
        s.type  = "text/javascript";
        s.src   = AD_SRC;
        s.async = true;
        s.onerror = () => setFailed(true);
        el.appendChild(s);

        // Collapse after 6 s if no iframe appeared (adblock / no fill).
        setTimeout(() => {
          if (el && !el.querySelector("iframe")) setFailed(true);
        }, 6000);
      },
      { rootMargin: "100px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  if (failed) return null;

  return (
    <div className={`ad-banner${className ? ` ${className}` : ""}`} data-slot={slotId}>
      <span className="ad-label">Publicité</span>
      <div ref={frameRef} className="ad-frame" />
    </div>
  );
}
