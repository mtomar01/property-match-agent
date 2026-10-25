// The three icons, the whole set (D88, D93): 20px on a 24px box, 2px round strokes, one ink via currentColor.
// Previous and skip take Lucide's geometry (rotate-ccw, skip-forward; ISC licence, lucide.dev), the triangle
// filled to match Mike's sketch; the searches icon is drawn from his sketch: three bars and a short fourth.
const props = { className: "ico", viewBox: "0 0 24 24", "aria-hidden": true, focusable: "false" } as const;

export const SearchesIcon = () => (
  <svg {...props}><path d="M4 5h16M4 10h16M4 15h16M4 20h9" /></svg>
);

export const PreviousIcon = () => (
  <svg {...props}><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8" /><path d="M3 3v5h5" /></svg>
);

export const SkipIcon = () => (
  <svg {...props}><path className="fill" d="M5 4l10 8-10 8z" /><path d="M19 5v14" /></svg>
);
