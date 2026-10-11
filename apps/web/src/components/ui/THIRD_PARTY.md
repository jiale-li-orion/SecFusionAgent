# Source-owned UI components

Button, Card, Badge, Input, Avatar, Separator, DropdownMenu, Tabs and Item are adapted from [shadcn/ui](https://ui.shadcn.com), new-york-v4 registry, downloaded 2026-10-11. Import paths use this project’s utilities and individual Radix primitives. Sheet, Tooltip, Toggle, ToggleGroup, Accordion, Skeleton and Empty were added from the same registry on 2026-10-12. Sheet and Tooltip use the product overlay stacking levels. Their visual tokens are defined in `src/ui.css`.

MIT License

Copyright (c) 2023 shadcn

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Runtime dependencies

Functional icons use [Phosphor React](https://github.com/phosphor-icons/react) (MIT). Relationship exploration uses [Cytoscape.js](https://github.com/cytoscape/cytoscape.js) and [fCoSE](https://github.com/iVis-at-Bilkent/cytoscape.js-fcose) (MIT). These are package dependencies; their original licenses ship with the installed packages.
