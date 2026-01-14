import React, { useMemo, useState, useEffect, useRef } from 'react';

interface VirtualizedHTMLProps {
    htmlContent: string;
    chunkSize?: number; // Characters per chunk, default ~100KB
    scrollTo?: ScrollToData | null;
}

export const VirtualizedHTML: React.FC<VirtualizedHTMLProps> = ({ htmlContent, chunkSize = 100000, scrollTo }) => {
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
    const [pendingScrollData, setPendingScrollData] = useState<ScrollToData | null>(null);

    // Reset when content changes
    useEffect(() => {
        setRenderedCount(1);
    }, [chunks]);

    // 3. Handle External Scroll Request
    useEffect(() => {
        if (!scrollTo || chunks.length === 0) return;

        const { elementID } = scrollTo;

        // Find which chunk contains the ID
        const chunkIndex = chunks.findIndex(chunk => chunk.includes(`id="${elementID}"`) || chunk.includes(`id='${elementID}'`));

        if (chunkIndex !== -1) {
            console.log(`[IncrementalHTML] Found ID ${elementID} in chunk ${chunkIndex}`);
            // Ensure we've rendered enough chunks
            if (chunkIndex >= renderedCount) {
                setRenderedCount(chunkIndex + 1);
            }
            setPendingScrollData(scrollTo);
        } else {
            console.warn(`[IncrementalHTML] ID ${elementID} not found in any chunk`);
        }
    }, [scrollTo, chunks]);

    // 4. Perform Scroll Effect (after render)
    useEffect(() => {
        if (pendingScrollData && containerRef.current) {
            // Need a small timeout to let the DOM update
            const timer = setTimeout(() => {
                const { elementID, highlightOnScroll, highlightPeriod, cb } = pendingScrollData;
                const element = document.getElementById(elementID);
                if(element) {
                    element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    
                    // Highlight the element
                    if(highlightOnScroll) {
                        element.classList.add('ring-2', 'ring-blue-500', 'bg-blue-50');
                        if(highlightPeriod !== undefined && highlightPeriod > 0) {
                            setTimeout(() => element.classList.remove('ring-2', 'ring-blue-500', 'bg-blue-50'), highlightPeriod);
                        }
                    }
                    setPendingScrollData(null); // Clear pending scroll
                    // trigger callback if specified
                    if(cb) {
                        cb(element);
                    }
                }
                else {
                    // Retry a few times if needed? For now just log
                    console.log(`[IncrementalHTML] Element ${elementID} not found in DOM yet`);
                }
            }, 100);
            return () => clearTimeout(timer);
        }
    }, [renderedCount, pendingScrollData]);


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


export interface ScrollToData {
    elementID: string,
    highlightOnScroll: boolean,
    highlightPeriod?: number,
    cb?: (element: HTMLElement) => void
}