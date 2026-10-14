/** What a list of choices is searched by: the text shown, and more words (a code, a category, another language). */
export type Searchable = { label: string; keywords?: string[] };

// Lower case, without accents or Arabic vowel marks: "Crévette" is found by "crevette".
const fold = (text: string) => text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
// Letters and digits only: the code "SA-010" is found by "sa010".
const compact = (text: string) => text.replace(/[^\p{L}\p{N}]/gu, "");

/**
 * The options that hold every word typed, in their label or their keywords. A label starting with what is typed
 * comes first, then an option with a word starting with it, then the rest; the order is otherwise kept.
 */
export function searchOptions<T extends Searchable>(options: readonly T[], query: string): T[] {
  const terms = fold(query).split(/\s+/).filter(Boolean);
  if (terms.length === 0) return [...options];
  const ranked: { option: T; rank: number }[] = [];
  for (const option of options) {
    const text = fold([option.label, ...(option.keywords ?? [])].join(" "));
    const squeezed = compact(text);
    const holds = (term: string) => text.includes(term) || (compact(term) !== "" && squeezed.includes(compact(term)));
    if (!terms.every(holds)) continue;
    const words = text.split(/[^\p{L}\p{N}]+/u);
    const first = terms.some((term) => text.startsWith(term));
    const starts = terms.some((term) => words.some((word) => word.startsWith(term)));
    ranked.push({ option, rank: first ? 0 : starts ? 1 : 2 });
  }
  // Array.prototype.sort is stable: options of the same rank keep their order.
  return ranked.sort((a, b) => a.rank - b.rank).map((entry) => entry.option);
}
