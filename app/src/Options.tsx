import { useEffect } from "react";
import { UI } from "./labels";

interface Props {
  open: boolean;
  data: string;
  areas: string[];
  onClose: () => void;
}

// Options (D92): a dialog over the desktop, a full screen on the phone, reached from the searches panel.
// Data and About for now; the appearance and language switches arrive in step 4.
export function Options({ open, data, areas, onClose }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <>
      <div className="dim on" onClick={onClose} aria-hidden="true" />
      <section className="options" role="dialog" aria-modal="true" aria-labelledby="options-h">
        <div className="options-top">
          <h2 id="options-h">{UI.options}</h2>
          <button type="button" className="link" onClick={onClose}>{UI.close}</button>
        </div>
        <section className="option">
          <h3 className="label">{UI.dataLabel}</h3>
          <p>{UI.covers(areas, data)}</p>
          <p className="hint">Photos are linked, never stored. Nothing is kept about agents or owners.</p>
        </section>
        <section className="option">
          <h3 className="label">{UI.about}</h3>
          <p>{UI.aboutText}</p>
          <p className="hint">Tispi is σπίτι (home) with its letters shuffled, settling into place.</p>
        </section>
      </section>
    </>
  );
}
