import { useEffect, useState } from 'react';
import { hrsCache } from '../../../services/hrsCache';
import { Loader2 } from 'lucide-react';
import { type HRSFilter } from './HRSIndexView';
import { VirtualizedHTML, type ScrollToData } from '../../common/VirtualizedHTML'; // Added import

export const HRSTextView = ({ filter, link, selectedMatch }: { filter: HRSFilter, link: HRSFilter, selectedMatch: { statute: [string, string, string], text: string } | null }) => {
  const [HRSData, setHRSData] = useState<string | null>(null);
  const [scrollToData, setScrollToData] = useState<ScrollToData | null>(null);

  function clearHighlights(element: HTMLElement): void {
    const marks = element.querySelectorAll('mark');
    marks.forEach((mark) => {
      const parent = mark.parentNode;
      const text = mark.textContent;
      if (parent && text !== null) {
        parent.replaceChild(document.createTextNode(text), mark);
        parent.normalize();
      }
    });
  }

  function highlightText(element: HTMLElement, searchText: string): HTMLElement[] {
    const walker = document.createTreeWalker(
      element,
      NodeFilter.SHOW_TEXT,
      null
    );
  
    const textNodes = [];
    while (walker.nextNode()) {
      textNodes.push(walker.currentNode);
    }
  
    let highlightNodes: HTMLElement[] = [];
    textNodes.forEach((node) => {
      const text = node.nodeValue;
      if (!text) return;
      const lowerText = text.toLowerCase();
      const lowerSearch = searchText.toLowerCase();
  
      if (!lowerText.includes(lowerSearch)) return;
  
      const fragment = document.createDocumentFragment();
      let lastIndex = 0;
      let index = lowerText.indexOf(lowerSearch);
      while (index !== -1) {
        let textNode = document.createTextNode(text.substring(lastIndex, index))
        fragment.appendChild(textNode);
        const mark = document.createElement('mark');
        highlightNodes.push(mark);
        mark.textContent = text.substring(index, index + searchText.length);
        fragment.appendChild(mark);
  
        lastIndex = index + searchText.length;
        index = lowerText.indexOf(lowerSearch, lastIndex);
      }
      let textNode = document.createTextNode(text.substring(lastIndex))
      fragment.appendChild(textNode);
  
      if(node.parentNode) {
        node.parentNode.replaceChild(fragment, node);
      }
      
    });
    return highlightNodes;
  }


  useEffect(() => {
    if(selectedMatch) {
      const { statute, text } = selectedMatch;
      const [ volume, chapter, section ] = statute;
      const id = `${volume}.${chapter}.${section}`;
      setScrollToData({
        elementID: id,
        highlightOnScroll: false,
        cb: (target: HTMLElement) => {
          highlightText(target, text);
        }
      });
    }
    else {
      const target = document.getElementById("hrs-document-container");
      if(target) {
        clearHighlights(target);
      }
      setScrollToData(null);
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
    const { volume, chapter, section } = link;
    const linkID = `${volume}.${chapter}.${section}`;
    setScrollToData({
      elementID: linkID,
      highlightOnScroll: true,
      highlightPeriod: 5000
    });
  }, [link]);

  return (
    <div className="content-box flex-grow-1 bg-white min-h-full flex flex-col">
      {/* Main Content Area - Desktop */}
      {HRSData ? (
        <div id="hrs-document-container" className="hrs-document-container flex-1 min-h-0 h-full">
          {/* Use Virtualized Renderer for large content */}
          <VirtualizedHTML
            htmlContent={HRSData}
            scrollTo={scrollToData}
          />
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