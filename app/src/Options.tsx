import { useEffect } from "react";
import { Lang, LangPref, Theme, useLabels } from "./labels";

interface Props {
  open: boolean;
  data: string;
  areas: string[];
  theme: Theme;
  langPref: LangPref;
  lang: Lang;
  version: string;
  onTheme: (theme: Theme) => void;
  onLang: (pref: LangPref) => void;
  onClose: () => void;
}

// Options (D92, D96): a dialog over the desktop, a full screen on the phone, reached from the searches panel.
// Appearance (System · Light · Dark) and Language (Automatic · English · Ελληνικά) as segmented pills, then Data
// and About. Nothing else: no setting a buyer did not ask for. The choices live in the browser's localStorage.
export function Options({ open, data, areas, theme, langPref, lang, version, onTheme, onLang, onClose }: Props) {
  const L = useLabels();
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;

  const themes: [Theme, string][] = [["system", L.system], ["light", L.light], ["dark", L.dark]];
  const langs: [LangPref, string][] = [["auto", L.automatic], ["en", "English"], ["el", "Ελληνικά"]];

  return (
    <>
      <div className="dim on" onClick={onClose} aria-hidden="true" />
      <section className="options" role="dialog" aria-modal="true" aria-labelledby="options-h">
        <div className="options-top">
          <h2 id="options-h">{L.options}</h2>
          <button type="button" className="link" onClick={onClose}>{L.close}</button>
        </div>

        <section className="option">
          <h3 className="label" id="appearance-h">{L.appearance}</h3>
          <div className="seg" role="group" aria-labelledby="appearance-h">
            {themes.map(([value, label]) => (
              <button key={value} type="button" className={`seg-btn ${theme === value ? "on" : ""}`} aria-pressed={theme === value} onClick={() => onTheme(value)}>{label}</button>
            ))}
          </div>
          <p className="hint">{L.appearanceHint}</p>
        </section>

        <section className="option">
          <h3 className="label" id="language-h">{L.language}</h3>
          <div className="seg" role="group" aria-labelledby="language-h">
            {langs.map(([value, label]) => (
              <button key={value} type="button" className={`seg-btn ${langPref === value ? "on" : ""}`} aria-pressed={langPref === value} lang={value === "el" ? "el" : "en"}
                onClick={() => onLang(value)}>{label}</button>
            ))}
          </div>
          <p className="hint">{L.languageHint}{langPref === "auto" ? ` ${L.nowIn(lang === "el" ? "Ελληνικά" : "English")}` : ""}</p>
        </section>

        <section className="option">
          <h3 className="label">{L.dataLabel}</h3>
          <p>{L.covers(areas, data)}</p>
          <p className="hint">{L.dataHint}</p>
        </section>

        <section className="option">
          <h3 className="label">{L.about}</h3>
          <p>{L.aboutText}</p>
          <p className="hint">{version} · {L.tagline}</p>
        </section>
      </section>
    </>
  );
}
