import { useEffect, useState } from 'react';
import { hrsCache } from '../../../services/hrsCache';
import { Loader2 } from 'lucide-react';
import { type HRSFilter } from './HRSIndexView';
import { VirtualizedHTML } from '../../common/VirtualizedHTML'; // Added import

export const HRSTextView = ({ filter, link, selectedMatch }: { filter: HRSFilter, link: HRSFilter, selectedMatch: { statute: [string, string, string], text: string } | null }) => {
  const [HRSData, setHRSData] = useState<string | null>(null);
  const [highlightedSection, setHighlightedSection] = useState<any>(null);

  function highlightSection(section: HTMLElement) {
    const highlightClasses = ['ring-2', 'p-2'];
    if (section === highlightedSection) {
      section.classList.remove(...highlightClasses);
      setHighlightedSection(null);
    }
    else {
      highlightedSection?.classList.remove(...highlightClasses);
      section.classList.add(...highlightClasses);
      setHighlightedSection(section);
    }
  }


  function clearHighlights(element: HTMLElement): void {
    // Query specific 'mark' elements
    const marks = element.querySelectorAll('mark');

    marks.forEach((mark) => {
      const parent = mark.parentNode;
      const text = mark.textContent;

      // Safety check:
      // 1. Ensure the mark is actually attached to a parent
      // 2. Ensure the mark actually has text content to restore
      if (parent && text !== null) {
        parent.replaceChild(document.createTextNode(text), mark);
        parent.normalize(); // Merges adjacent text nodes back together
      }
    });
  }

  function highlightText(element: HTMLElement, searchText: string): HTMLElement[] {
    // Highlighting logic removed from this component scope for performance
    // It should be moved to VirtualizedHTML or CSS in the future
    return [];
  }


  useEffect(() => {
    if (selectedMatch) {
      // Disabled specific section highlighting for now
    }
  }, [selectedMatch]);

  useEffect(() => {
    const getData = async () => {
      const { volume, chapter, section } = filter;
      try {
        let data = await hrsCache.getDocument(volume, chapter, section);
        setHRSData(data);
      } catch (error) {
        console.error("Failed to load HRS data", error);
        setHRSData("<p>Error loading document.</p>");
      }
    }
    getData();
  }, [filter]);

  useEffect(() => {
    // Link scrolling disabled for now
  }, [link]);

  return (
    <div className="content-box flex-grow-1 p-4 bg-white min-h-full flex flex-col">
      {/* Main Content Area - Desktop */}
      {HRSData ? (
        <div className="hrs-document-container flex-1 min-h-0 h-full">
          {/* Use Virtualized Renderer for large content */}
          <VirtualizedHTML
            htmlContent={HRSData}
            scrollToId={selectedMatch ? `${selectedMatch.statute[0]}.${selectedMatch.statute[1]}.${selectedMatch.statute[2]}` : null}
          />
          {/* <div className="prose max-w-none p-8" dangerouslySetInnerHTML={{ __html: HRSData }} /> */}
        </div>
      ) : (
        <div className="flex flex-col items-center justify-center p-12">
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading HRS Data</p>
        </div>
      )}
    </div>
  );
};