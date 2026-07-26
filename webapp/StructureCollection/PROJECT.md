# Crystal Vault

A local materials-science CIF browser with a searchable crystal list and an interactive 3D viewer.

## What It Does
- Loads CIF files from the local dataset.
- Shows a searchable crystal list.
- Renders structures in a 3Dmol.js viewer.
- Supports primitive/conventional cell switching (conventional generated offline).
- Provides style toggles, labels toggle, and fullscreen view.
- Lets you resize the list vs viewer with a draggable splitter.

## How To Run
From `C:\Test\StructureCollection`:

```powershell
python -m http.server 8000
```

Then open:

```
http://localhost:8000/site/
```

## Regenerate Conventional CIFs
```powershell
python C:\Test\StructureCollection\tools\convert_to_conventional.py
```

## What Was Done Today
- Built the static site UI and 3D viewer integration.
- Added primitive/conventional toggle with fallback to primitive when needed.
- Added style toggles, labels toggle, and fullscreen button.
- Implemented list/search with a scrollable list panel.
- Added a resizable splitter between list and viewer.
- Tuned layout and header placement per feedback.
- Fixed the control bar layout (titles, search, styles, toggles).

## Files
- `C:\Test\StructureCollection\site\index.html`
- `C:\Test\StructureCollection\site\styles.css`
- `C:\Test\StructureCollection\site\app.js`
- `C:\Test\StructureCollection\site\crystals.json`
- `C:\Test\StructureCollection\tools\convert_to_conventional.py`
- `C:\Test\StructureCollection\conventional\` (generated CIFs)
