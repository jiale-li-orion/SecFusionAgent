# Product artwork

`night-reading.webp` is the empty Ask welcome illustration: an open reference book, colored index tabs and a warm desk lamp, rendered in detailed pixel art. It displays at 220px on desktop and 128px on phones. `night-reading-detail.webp` is the matching open-book ornament for Workspace services, derived from the same master with the lamp removed. The former paper SVG and optical-slide ornament have been retired.

Both assets were produced with the built-in imagegen service on 2026-10-13; the service did not expose a model identifier, so these are not labeled as Image 2.5 outputs. Two calls were used: generation and a matching edit. Exact prompts are in [`night-reading.prompt.txt`](../../design/image25/night-reading.prompt.txt) and [`night-reading-detail.prompt.txt`](../../design/image25/night-reading-detail.prompt.txt). The transparent outputs were resized to 640px and 256px and encoded as WebP at quality 90, preserving alpha; production sizes are approximately 71 KB and 13 KB.

Artwork has empty alternative text, fixed dimensions and no pointer events. Neither image represents evidence, a source, a status, or an interactive control. Active conversations contain no illustration, and image loading is not required for any operation. These static illustrations add no motion or runtime dependencies.

Earlier `gpt-image-2.5-sunburst` API attempts returned `model_not_found` from the configured distributor on 2026-10-12. Earlier concepts and rejection notes remain in [`design/image25`](../../design/image25/README.md). The eye character, optical instrument, paper SVG and rain-window direction are not loaded by the app.

The earlier generic `research-lens.webp` was removed because reusing the same abstract loop in Ask and Workspace obscured the separate roles of those spaces.
