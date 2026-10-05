import React, { useEffect, useRef, useState } from "react";

const AD_KEY = "30d74840a0fdcbd6c076b560e162fd3a";
const AD_SRC = `https://bauval.org/22/${AD_KEY}`;

/**
 * 320×50 banner — bauval.org ad network.
 *
 * WHY AN IFRAME: bauval.org (like most iframe-format ad networks) uses
 * document.write() internally. Injecting their <script> dynamically via
 * appendChild() in a React SPA causes document.write() to fire after page
 * load, which either clears the page or silently fails. Wrapping the ad in
 * its own <iframe> gives the script a fresh document to write into, which is
 * exactly how the network expects to run.
 *
 * Each banner gets an isolated iframe → no window.atOptions race between
 * multiple slots, no CSP conflicts with the parent page.
 */
export default function AdBanner({ slotId, className = "" }) {
  const iframeRef = useRef(null);
  const [failed,  setFailed]  = useState(false);
  const injected  = useRef(false);

  useEffect(() => {
    if (injected.current) return;
    const iframe = iframeRef.current;
    if (!iframe) return;
    injected.current = true;

    try {
      const doc = iframe.contentDocument || iframe.contentWindow.document;
      doc.open();
      doc.write(`<!DOCTYPE html>
<html>
<head>
<style>
  * { margin: 0; padding: 0; border: 0; overflow: hidden; }
  body { width: 320px; height: 50px; background: transparent; }
</style>
</head>
<body>
<script>
  atOptions = {
    'key'    : '${AD_KEY}',
    'format' : 'iframe',
    'height' : 50,
    'width'  : 320,
    'params' : {}
  };
<\/script>
<script src="${AD_SRC}"><\/script>
</body>
</html>`);
      doc.close();
    } catch {
      setFailed(true);
    }

    // Collapse after 6 s if the network returned nothing (adblock / no fill).
    setTimeout(() => {
      try {
        const doc = iframe.contentDocument || iframe.contentWindow.document;
        if (!doc.querySelector("iframe, img, ins")) setFailed(true);
      } catch {
        // cross-origin check failed — ad probably loaded fine
      }
    }, 6000);
  }, []);

  if (failed) return null;

  return (
    <div className={`ad-banner${className ? ` ${className}` : ""}`} data-slot={slotId}>
      <span className="ad-label">Publicité</span>
      <div className="ad-frame">
        <iframe
          ref={iframeRef}
          width="320"
          height="50"
          frameBorder="0"
          scrolling="no"
          title="Advertisement"
          style={{ border: "none", maxWidth: "100%", display: "block" }}
        />
      </div>
    </div>
  );
}
