import { useEffect, useRef, useState } from "react";
import { apiFetch } from "../../lib/api.js";

const GROUPS = [
  ["orders", "Orders"],
  ["managers", "Managers"],
  ["workers", "Workers"],
  ["rolls", "Rolls"],
];

// Top-bar search for the Supermanager: orders, managers, workers, roll IDs.
export default function TopSearch({ onGo }) {
  const [q, setQ] = useState("");
  const [res, setRes] = useState(null);
  const [open, setOpen] = useState(false);
  const box = useRef(null);

  useEffect(() => {
    const s = q.trim();
    if (s.length < 2) {
      setRes(null);
      return undefined;
    }
    const t = setTimeout(() => {
      apiFetch(`/api/super/search?q=${encodeURIComponent(s)}`)
        .then((r) => {
          setRes(r);
          setOpen(true);
        })
        .catch(() => setRes(null));
    }, 250);
    return () => clearTimeout(t);
  }, [q]);

  useEffect(() => {
    const close = (e) => box.current && !box.current.contains(e.target) && setOpen(false);
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);

  const total = res ? GROUPS.reduce((n, [k]) => n + res[k].length, 0) : 0;
  return (
    <div className="top-search" ref={box}>
      <input
        type="search"
        placeholder="Search orders, workers, rolls…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => res && setOpen(true)}
        onKeyDown={(e) => e.key === "Escape" && setOpen(false)}
        aria-label="Search"
      />
      {open && res && (
        <div className="top-search-pop" role="listbox">
          {total === 0 ? (
            <p className="muted">Nothing found for “{q.trim()}”.</p>
          ) : (
            GROUPS.map(([k, label]) =>
              res[k].length ? (
                <div key={k}>
                  <h5>{label}</h5>
                  {res[k].map((r) => (
                    <button
                      key={`${k}${r.id}`}
                      type="button"
                      onClick={() => {
                        setOpen(false);
                        setQ("");
                        onGo(r.page);
                      }}
                    >
                      <strong>{r.label}</strong>
                      <small className="muted">{r.sub}</small>
                    </button>
                  ))}
                </div>
              ) : null,
            )
          )}
        </div>
      )}
    </div>
  );
}
