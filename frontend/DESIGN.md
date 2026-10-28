# WindSight Design System

## North Star

WindSight is a calm operational instrument for energy analysts. It should feel precise, quiet, and
auditable: information density without visual noise. The forecast-vs-actual chart is the signature
surface; the surrounding interface stays disciplined so the data remains primary.

## Visual Language

- Canvas: `#f5f7f7`; surfaces: `#ffffff`; sidebar: `#fbfcfc`.
- Ink: `#082b3a`; secondary text: `#617986`; muted text: `#8396a0`.
- Brand teal: `#0f8f83`; pale teal: `#e7f5f2`; forecast blue: `#5c80ff`.
- Warning: `#b4692d` on `#fff7f0`; danger: `#a84d3d` on `#fff5f1`.
- Borders: `#dce5e7`; focus ring: `#8ad3cb`; radii: 8px controls, 10px panels.
- Shadows are restrained: a one-pixel border plus low-opacity ambient shadow only.

## Typography

Use Inter with system fallbacks. Headings use 650–700 weight and tight tracking; body and controls
use 400–600. Metric values use tabular numerals. Uppercase eyebrow labels use generous tracking.

## Layout and Density

Desktop uses a 190px sidebar, a 58px utility bar, and a fluid content column capped at 1220px.
Panels use 18–22px internal padding and 14–16px vertical gaps. Below 860px, navigation moves into a
compact top drawer and cards stack without hiding any primary action.

## Components and Behavior

Buttons, fields, notices, metric cards, status badges, and scrollbars derive from tokens in
`src/styles.css`. Every interactive control has hover, focus-visible, active, disabled, and busy
states. Native date/time inputs are canonical because platform-owned pickers are acceptable for the
English UTC-only product. Error and empty states reserve stable geometry and always offer recovery.

## Accessibility

Target WCAG 2.2 AA. Never rely on color alone; pair semantic color with text and icons. Maintain
logical focus order, visible focus rings, reduced-motion support, status live regions, and semantic
buttons/links.
