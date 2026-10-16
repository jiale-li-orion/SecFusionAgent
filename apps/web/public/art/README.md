# Artwork archive — not currently mounted

The 2026-10-14 interface revision withdraws the following illustrations from live pages: their stationery/game-item appearance did not fit the software. This file records provenance, not visual acceptance. No current route loads these assets.

`night-reading.webp` was the empty Ask welcome illustration: an open reference book, colored index tabs and a warm desk lamp, rendered in detailed pixel art. It was trialed at 220px on desktop and 128px on phones. `night-reading-detail.webp` was the matching open-book ornament for Workspace services, derived from the same master with the lamp removed. The former paper SVG and optical-slide ornament have been retired.

Both assets were produced with the built-in imagegen service on 2026-10-13; the service did not expose a model identifier, so these are not labeled as Image 2.5 outputs. Two calls were used: generation and a matching edit. Exact prompts are in [`night-reading.prompt.txt`](../../design/image25/night-reading.prompt.txt) and [`night-reading-detail.prompt.txt`](../../design/image25/night-reading-detail.prompt.txt). The transparent outputs were resized to 640px and 256px and encoded as WebP at quality 90, preserving alpha; production sizes are approximately 71 KB and 13 KB.

The rejected `workspace-shortcuts.webp` experiment depicted four miniature objects for the existing Workspace shortcuts: message notes for conversations, a bookmarked journal for follows, a magnifying glass and notebook for investigations, and book spines for the library. It is a 1254 × 1254 transparent RGBA atlas (301,932 bytes); It was trialed as four CSS quadrants and then removed from public assets. Shortcut order, labels and links remain unchanged. One additional built-in imagegen call produced this atlas on 2026-10-13; no model identifier was exposed. The exact prompt is [`workspace-shortcuts.prompt.txt`](../../design/image25/workspace-shortcuts.prompt.txt).

Artwork is decorative, has fixed dimensions and receives no pointer events. The surrounding shortcut links retain their readable labels and complete click targets. No image represents evidence, a source or runtime state. Active conversations contain no illustration, and image loading is not required for any operation. These static illustrations add no autonomous animation or runtime dependencies. Shortcut hover feedback respects reduced motion.

Earlier `gpt-image-2.5-sunburst` API attempts returned `model_not_found` from the configured distributor on 2026-10-12. Earlier concepts and rejection notes remain in [`design/image25`](../../design/image25/README.md). The eye character, optical instrument, paper SVG and rain-window direction are not loaded by the app.

The earlier generic `research-lens.webp` was removed because reusing the same abstract loop in Ask and Workspace obscured the separate roles of those spaces.
