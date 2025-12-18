import React, { useMemo, useState, useEffect, useRef } from 'react';

interface VirtualizedHTMLProps {
    htmlContent: string;
    chunkSize?: number; // Characters per chunk, default ~100KB
    scrollToId?: string | null;
}

export const VirtualizedHTML: React.FC<VirtualizedHTMLProps> = ({ htmlContent, chunkSize = 100000, scrollToId }) => {
    // 1. Chunking Logic
    const chunks = useMemo(() => {
        if (!htmlContent) return [];

        const delimiterRegex = /(?=<div[^>]*class=["']WordSection1["'])/i;
        const rawChunks = htmlContent.split(delimiterRegex);

        const mergedChunks: string[] = [];
        let currentChunk = '';
        const TARGET_CHUNK_SIZE = chunkSize;

        for (const rawChunk of rawChunks) {
            if (!rawChunk.trim()) continue;

            if ((currentChunk.length + rawChunk.length) < TARGET_CHUNK_SIZE) {
                currentChunk += rawChunk;
            } else {
                if (currentChunk) mergedChunks.push(currentChunk);
                currentChunk = rawChunk;
            }
        }

        if (currentChunk) mergedChunks.push(currentChunk);

        console.log(`[IncrementalHTML] Created ${mergedChunks.length} chunks`);

        // Fallback
        if (mergedChunks.length === 0) {
            const simpleChunks = [];
            for (let i = 0; i < htmlContent.length; i += TARGET_CHUNK_SIZE) {
                simpleChunks.push(htmlContent.slice(i, i + TARGET_CHUNK_SIZE));
            }
            return simpleChunks.length > 0 ? simpleChunks : [htmlContent];
        }

        return mergedChunks;
    }, [htmlContent, chunkSize]);

    // 2. Incremental Rendering State
    const [renderedCount, setRenderedCount] = useState(1);
    const observerTarget = useRef<HTMLDivElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    // Track if we need to perform a scroll action after rendering
    const [pendingScrollId, setPendingScrollId] = useState<string | null>(null);

    // Reset when content changes
    useEffect(() => {
        setRenderedCount(1);
    }, [chunks]);

    // 3. Handle External Scroll Request
    useEffect(() => {
        if (!scrollToId || chunks.length === 0) return;

        // Find which chunk contains the ID
        const chunkIndex = chunks.findIndex(chunk => chunk.includes(`id="${scrollToId}"`) || chunk.includes(`id='${scrollToId}'`));

        if (chunkIndex !== -1) {
            console.log(`[IncrementalHTML] Found ID ${scrollToId} in chunk ${chunkIndex}`);
            // Ensure we've rendered enough chunks
            if (chunkIndex >= renderedCount) {
                setRenderedCount(chunkIndex + 1);
            }
            setPendingScrollId(scrollToId);
        } else {
            console.warn(`[IncrementalHTML] ID ${scrollToId} not found in any chunk`);
        }
    }, [scrollToId, chunks]);

    // 4. Perform Scroll Effect (after render)
    useEffect(() => {
        if (pendingScrollId && containerRef.current) {
            // Need a small timeout to let the DOM update
            const timer = setTimeout(() => {
                const element = document.getElementById(pendingScrollId);
                if (element) {
                    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    // Highlight the element
                    element.classList.add('ring-2', 'ring-blue-500', 'bg-blue-50');
                    setTimeout(() => element.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-50'), 3000);

                    setPendingScrollId(null); // Clear pending scroll
                } else {
                    // Retry a few times if needed? For now just log
                    console.log(`[IncrementalHTML] Element ${pendingScrollId} not found in DOM yet`);
                }
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [renderedCount, pendingScrollId]);


    // 5. Intersection Observer to load more when scrolling to bottom
    useEffect(() => {
        const observer = new IntersectionObserver(
            (entries) => {
                if (entries[0].isIntersecting) {
                    setRenderedCount((prev) => Math.min(prev + 1, chunks.length));
                }
            },
            { threshold: 0.1, rootMargin: '200px' }
        );

        if (observerTarget.current && renderedCount < chunks.length) {
            observer.observe(observerTarget.current);
        }

        return () => observer.disconnect();
    }, [renderedCount, chunks.length]);

    return (
        <div
            ref={containerRef}
            className="h-full w-full overflow-y-auto p-8 virtual-scroll-container">
            {chunks.slice(0, renderedCount).map((chunk, index) => (
                <div
                    key={index}
                    className="prose max-w-none mb-4"
                    dangerouslySetInnerHTML={{ __html: chunk }}
                />
            ))}

            {/* Sentinel for infinite scroll */}
            {renderedCount < chunks.length && (
                <div ref={observerTarget} className="h-20 flex items-center justify-center text-gray-400">
                    Loading more content...
                </div>
            )}
        </div>
    );
};
