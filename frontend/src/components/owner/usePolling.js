import { useEffect, useRef } from "react";

// Call `fn` every `intervalMs` while the tab is visible; pause when hidden and
// run once immediately on becoming visible again. Owner pages only. This is
// additive to the SSE live updates — a safety net so numbers stay fresh even if
// the stream drops.
export function useVisiblePolling(fn, intervalMs = 30000, deps = []) {
  const fnRef = useRef(fn);
  fnRef.current = fn;

  useEffect(() => {
    let timer = null;
    const tick = () => {
      if (document.visibilityState === "visible") fnRef.current();
    };
    const start = () => {
      stop();
      timer = setInterval(tick, intervalMs);
    };
    const stop = () => {
      if (timer) clearInterval(timer);
      timer = null;
    };
    const onVisibility = () => {
      if (document.visibilityState === "visible") {
        fnRef.current(); // refresh immediately when the tab returns
        start();
      } else {
        stop();
      }
    };
    if (document.visibilityState === "visible") start();
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      stop();
      document.removeEventListener("visibilitychange", onVisibility);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [intervalMs, ...deps]);
}
