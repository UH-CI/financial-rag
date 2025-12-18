import { useEffect, useState } from 'react';
import { getHRSHTML } from '../../../services/api';
import { Loader2 } from 'lucide-react';
import { type HRSFilter } from './HRSIndexView';

export const HRSTextView = ({ filter, link, selectedMatch }: { filter: HRSFilter, link: HRSFilter, selectedMatch: {statute: [string, string, string], text: string} | null }) => {
  const [HRSData, setHRSData] = useState<string | null>(null);
  const [highlightedSection, setHighlightedSection] = useState<any>(null);

  function highlightSection(section: HTMLElement) {
    const highlightClasses = ['ring-2', 'p-2'];
    if(section === highlightedSection) {
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
      const target = document.getElementById(id);
      if(target) {
        let highlightedNodes = highlightText(target, text);
        if(highlightedNodes.length > 0) {
          highlightedNodes[0].scrollIntoView({
            behavior: "smooth"
          });
        }
      }
    }
    else {
      const target = document.getElementById("hrs-content");
      if(target) {
        clearHighlights(target);
      }
    }
    
  }, [selectedMatch]);

  useEffect(() => {
    const getData = async () => {
      const { volume, chapter, section } = filter;
      let data = await getHRSHTML(volume, chapter, section);
      setHRSData(data);
    }
    getData();
  }, [filter]);

  useEffect(() => {
    const { volume, chapter, section } = link;
    const id = `${volume}.${chapter}.${section}`;
    const target = document.getElementById(id);
    if(target) {
      target.scrollIntoView({
        behavior: "smooth"
      });
      highlightSection(target);
    }
  }, [link]);

  return (
    
    <div className="content-box flex-grow-1 p-4">
      {/* Main Content Area - Desktop */}
      {HRSData ? (
        <div className="hrs-document-container">
        <div id="hrs-content"
          dangerouslySetInnerHTML={{ __html: HRSData }} 
        />
      </div>
      ) : (
        <div>
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading HRS Data</p>
        </div>
        
      )}
      
    </div>
  );
};