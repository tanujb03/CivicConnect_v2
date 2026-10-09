/** The list shape of the API: `{ items, next_cursor }` (`next_cursor` is null/absent on the last page). */
export interface Page<T> {
  items: T[];
  next_cursor?: string | null;
}

/** Follows `next_cursor` page by page: `for await (const page of pages((cursor) => unwrap(api.client.GET("/api/v1/cases", { params: { query: { cursor } } })))) { ... }` */
export async function* pages<T>(fetchPage: (cursor?: string) => Promise<Page<T>>, opts: { maxPages?: number } = {}): AsyncGenerator<Page<T>> {
  const max = opts.maxPages ?? 1000;                  // a guard against a server that keeps returning the same cursor
  let cursor: string | undefined;
  for (let i = 0; i < max; i++) {
    const page = await fetchPage(cursor);
    yield page;
    if (!page.next_cursor || page.next_cursor === cursor) return;
    cursor = page.next_cursor;
  }
}

/** All items of all pages (small collections only: map layers, reference data). */
export async function fetchAll<T>(fetchPage: (cursor?: string) => Promise<Page<T>>, opts: { maxPages?: number } = {}): Promise<T[]> {
  const out: T[] = [];
  for await (const page of pages(fetchPage, opts)) out.push(...page.items);
  return out;
}
