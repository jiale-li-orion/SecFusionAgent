import { ProductGlyph } from './ProductGlyph'

/** A publication-specific local seal; the category mark remains the semantic key. */
export function SourceSeal({ category, name }: { category: string; name: string }) {
  const words = name.replace(/[^\p{L}\p{N}]+/gu, ' ').trim().split(/\s+/u).filter(Boolean)
  const monogram = words.length > 1
    ? `${words[0][0]}${words[1][0]}`.toUpperCase()
    : [...(words[0] ?? category)].slice(0, 2).join('').toUpperCase()
  return <span className={`source-seal source-seal-${category}`} aria-hidden="true">
    <ProductGlyph kind={category} size={31} />
    <span>{monogram}</span>
  </span>
}
