# Prep Theme Examples (Tremor Preview)

This is a runnable, browser-viewable set of **visual theme examples** for Prep using:
- React
- Tailwind
- Tremor (`@tremor/react`)

It includes:
- Theme switcher: Directions **A–D**
- Light/Dark toggle
- A few representative UI sections (marketing + dashboard + docs)

## Run locally

```bash
npm install
npm run dev
```

## URL

Vite runs at:

- http://localhost:5173

## Notes

- Theme tokens are implemented as CSS custom properties.
- Themes are applied via:
  - `data-prep-theme="a|b|c|d"`
  - `.dark` class for dark mode

Theme CSS files live in:

- `src/styles/themes/direction-a.css`
- `src/styles/themes/direction-b.css`
- `src/styles/themes/direction-c.css`
- `src/styles/themes/direction-d.css`
