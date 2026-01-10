import { getHRSHTML } from './api';

class HRSCacheService {
    private cacheName = 'hrs-content-v1';

    // Helper to generate a consistent request URL/Key for the cache
    private getCacheKey(volume?: string, chapter?: string, section?: string): string {
        // Mimic the logic in api.ts getHRSHTML for path construction
        // This allows us to cache hierarchical pages (Index -> Volume -> Chapter -> Section)
        const parts = [volume, chapter, section].filter(p => p !== undefined);
        return `https://api.local/hrs/${parts.join('/')}`;
    }

    /**
     * Fetch a document. 
     * 1. Check Cache API (persistent storage).
     * 2. If missing, fetch from Network API.
     * 3. Save to Cache.
     */
    async getDocument(volume?: string, chapter?: string, section?: string): Promise<string> {
        const cache = await caches.open(this.cacheName);
        const key = this.getCacheKey(volume, chapter, section);

        // 1. Try Cache
        const cachedResponse = await cache.match(key);
        if (cachedResponse) {
            console.log(`[HRSCache] Hit: ${key}`);
            return await cachedResponse.text();
        }

        // 2. Fetch from API
        console.log(`[HRSCache] Miss (fetching): ${key}`);
        try {
            const content = await getHRSHTML(volume, chapter, section);

            // 3. Update Cache
            // We manually create a Response object to store in the Cache API
            const responseToCache = new Response(content, {
                headers: { 'Content-Type': 'text/html' }
            });

            // Put in cache (don't await this to return faster, or await to ensure consistency? 
            // Awaiting is safer to ensure it's stored)
            await cache.put(key, responseToCache);

            return content;
        } catch (err) {
            console.error(`[HRSCache] Failed to fetch ${key}`, err);
            throw err;
        }
    }

    /**
     * Prefetch a list of documents in the background.
     * This won't block the UI.
     */
    async prefetch(documents: Array<{ volume: string, chapter: string, section: string }>) {
        console.log(`[HRSCache] Prefetching ${documents.length} documents`);
        if (!('caches' in window)) return;

        const cache = await caches.open(this.cacheName);

        // Process strictly sequentially or in small parallel batches to avoid flooding the network
        // For now, simple parallel is likely fine for small numbers
        documents.forEach(async (doc) => {
            console.log(`[HRSCache] Prefetching ${doc.volume}-${doc.chapter}-${doc.section}`);
            const key = this.getCacheKey(doc.volume, doc.chapter, doc.section);
            const match = await cache.match(key);

            if (!match) {
                // If not in cache, fetch and store
                try {
                    // We use the service's getDocument which handles the fetching logic logic
                    await this.getDocument(doc.volume, doc.chapter, doc.section);
                } catch (e) {
                    // Ignore prefetch errors
                }
            }
        });
    }

    /**
     * Clear the cache if needed
     */
    async clear() {
        await caches.delete(this.cacheName);
    }
}

export const hrsCache = new HRSCacheService();
