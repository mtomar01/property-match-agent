// The mark: five tiles of radius-sm, one for each letter of Tispi, on an 80×48 box. Three sit on the baseline
// (T, s, p); the second and fifth, the two i's, are lifted like the dots of the i's and are the only tiles in
// the signal (D93). The colours come from the stylesheet (.mark .tile, .mark .dot) so the mark follows the theme.
const TILE_X = [2, 17, 32, 47, 62];
const DOTS = new Set([1, 4]);

export function Mark({ height = 24 }: { height?: number }) {
  return (
    <svg className="mark" width={(height * 80) / 48} height={height} viewBox="0 0 80 48" aria-hidden="true" focusable="false">
      {TILE_X.map((x, i) => (
        <rect key={x} className={DOTS.has(i) ? "tile dot" : "tile"} x={x} y={DOTS.has(i) ? 6 : 30} width="12" height="12" rx="3" />
      ))}
    </svg>
  );
}

// The lockup: the mark, a gap, the word in Commissioner 600. The word is the heading when the lockup is the page's title.
export function Logo({ heading = false }: { heading?: boolean }) {
  return (
    <span className="lockup">
      <Mark />
      {heading ? <h1>Tispi</h1> : <span className="word">Tispi</span>}
    </span>
  );
}
