# SkyBlink SPHEREx

Static website for comparing two observations each of the WISE 0855 and RW Aurigae sky fields.

## GitHub Pages deployment

Publish the repository's `main` branch from its root directory in Settings → Pages.
This directory is ready for GitHub Pages: `index.html` is at the repository root.

## Editing

- `index.html`: page structure and text
- `styles.css`: colors, typography, layout and mobile styles
- `app.js`: target metadata, interaction and image paths
- `images/`: four aligned display images

The coordinate form currently recognizes two prepared fields. It does not query SPHEREx live for arbitrary coordinates. Visual comparisons are not confirmed detections.

Source data: NASA/IPAC IRSA SPHEREx DR1. The page links to the original FITS cutouts and contains the required acknowledgement.
