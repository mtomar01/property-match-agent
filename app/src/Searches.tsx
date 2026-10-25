import { useEffect } from "react";
import { SearchSummary } from "./api";
import { SearchesIcon } from "./Icons";
import { searchSub, searchTitle, useLabels } from "./labels";
import { Logo } from "./Logo";

interface Props {
  searches: SearchSummary[];
  open: boolean;
  onClose: () => void;
  onSelect: (id: string) => void;
  onNew: () => void;
  onOptions: () => void;
}

// Past searches, each titled by its limits with its counts under it (D90, D91, D94). On desktop a 272px sidebar
// with a collapse icon; on a phone a drawer from the left to 80% of the width, closed by the same icon at its top
// right or by a tap on the uncovered strip (D93). One component, the stylesheet decides which it is.
export function Searches({ searches, open, onClose, onSelect, onNew, onOptions }: Props) {
  const L = useLabels();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  return (
    <>
      <div className={`dim side-dim ${open ? "on" : ""}`} onClick={onClose} aria-hidden="true" />
      <aside className={`side ${open ? "open" : ""}`} aria-label={L.yourSearches} aria-hidden={!open}>
        <div className="side-top">
          <Logo />
          <button type="button" className="icon-btn" aria-label={L.hideSearches} onClick={onClose} tabIndex={open ? 0 : -1}>
            <SearchesIcon />
          </button>
        </div>
        <p className="label">{L.searches}</p>
        <ul className="searches">
          {searches.map((s) => (
            <li key={s.id}>
              <button type="button" className={`search ${s.current ? "on" : ""}`} aria-current={s.current || undefined}
                onClick={() => onSelect(s.id)} tabIndex={open ? 0 : -1}>
                <span className="t">{searchTitle(s, L)}</span>
                <span className="s">{searchSub(s, L)}</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="spacer" />
        <button type="button" className="primary wide" onClick={onNew} tabIndex={open ? 0 : -1}>{L.newSearch}</button>
        <button type="button" className="wide" onClick={onOptions} tabIndex={open ? 0 : -1}>{L.options}</button>
      </aside>
    </>
  );
}
