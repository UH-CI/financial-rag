import React, { useState, useRef } from 'react';
import type { DocumentReference } from '../types';

// Utility function to highlight financial amounts in text
const highlightFinancialAmounts = (text: string, targetAmount?: number): React.ReactNode => {
  if (!text || !targetAmount) {
    return text;
  }

  // Create simple patterns - try both with and without decimals
  const formattedAmount = targetAmount.toLocaleString();
  
  // Try pattern with .00 first
  let pattern1 = `\\$${formattedAmount.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\.00`;
  let regex1 = new RegExp(`(${pattern1})`, 'gi');
  
  // Try pattern without decimals
  let pattern2 = `\\$${formattedAmount.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?!\\.\\d)`;
  let regex2 = new RegExp(`(${pattern2})`, 'gi');
  
  // Function to apply highlighting
  const applyHighlighting = (inputText: string, regex: RegExp) => {
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match;
    
    regex.lastIndex = 0;
    
    while ((match = regex.exec(inputText)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        parts.push(inputText.substring(lastIndex, match.index));
      }
      
      // Add the highlighted match
      parts.push(
        <span 
          key={match.index} 
          className="bg-yellow-400 bg-opacity-40 text-yellow-100 font-bold rounded px-1 border border-yellow-300"
          title={`Target financial amount: $${targetAmount.toLocaleString()}`}
        >
          {match[0]}
        </span>
      );
      
      lastIndex = match.index + match[0].length;
    }
    
    // Add remaining text after the last match
    if (lastIndex < inputText.length) {
      parts.push(inputText.substring(lastIndex));
    }
    
    return parts.length > 1 ? parts : null; // Return null if no matches found
  };
  
  // Try with .00 first
  let result = applyHighlighting(text, regex1);
  if (result) {
    return result;
  }
  
  // Try without decimals
  result = applyHighlighting(text, regex2);
  if (result) {
    return result;
  }
  
  // No matches found, return original text
  return text;
};

interface DocumentReferenceProps {
  reference: DocumentReference;
}

const DocumentReferenceComponent: React.FC<DocumentReferenceProps> = ({ reference }) => {
  const [showTooltip, setShowTooltip] = useState(false);
  const [tooltipPosition, setTooltipPosition] = useState({ x: 0, y: 0 });
  const linkRef = useRef<HTMLAnchorElement>(null);

  const updateTooltipPosition = () => {
    if (linkRef.current) {
      const rect = linkRef.current.getBoundingClientRect();
      setTooltipPosition({
        x: rect.left + rect.width / 2,
        y: rect.top - 8
      });
    }
  };

  const handleMouseEnter = () => {
    setShowTooltip(true);
    updateTooltipPosition();
  };

  const getTypeColor = (type: string) => {
    switch (type.toLowerCase()) {
      case 'bill introduction':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'bill amendment':
        return 'bg-indigo-100 text-indigo-800 border-indigo-200';
      case 'committee report':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      case 'testimony':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'financial citation':
        return 'bg-yellow-100 text-yellow-800 border-yellow-200';
      // Legacy support
      case 'bill version':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'bill introduction':
        return '📄';
      case 'bill amendment':
        return '📝';
      case 'committee report':
        return '📋';
      case 'testimony':
        return '🗣️';
      case 'financial citation':
        return '💰';
      // Legacy support
      case 'bill version':
        return '📋';
      default:
        return '📄';
    }
  };

  return (
    <span className="relative inline-block">
      <a
        ref={linkRef}
        href={reference.url}
        target="_blank"
        rel="noopener noreferrer"
        className={`font-medium underline hover:no-underline transition-colors duration-200 ${
          reference.document_type.toLowerCase() === 'financial citation' 
            ? 'text-green-600 hover:text-green-800' 
            : 'text-blue-600 hover:text-blue-800'
        }`}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={() => setShowTooltip(false)}
        title={`${reference.document_type}: ${reference.document_name}`}
      >
        [{reference.number}]
      </a>

      {/* Custom Tooltip - Using fixed positioning to escape container bounds */}
      {showTooltip && (
        <div className="fixed z-[9999] pointer-events-none" 
             style={{
               left: tooltipPosition.x,
               top: tooltipPosition.y,
               transform: 'translateX(-50%) translateY(-100%)'
             }}>
          <div className="bg-gray-900 text-white text-sm rounded-lg shadow-xl overflow-hidden min-w-[250px] max-w-[400px] border border-gray-700">
            {/* Header */}
            <div className={`px-3 py-2 text-xs font-semibold uppercase tracking-wide border-b border-gray-700 ${getTypeColor(reference.document_category || reference.document_type)} text-gray-900`}>
              <div className="flex items-center space-x-2">
                <span>{reference.document_icon || getTypeIcon(reference.document_type)}</span>
                <span>{reference.document_category || reference.document_type}</span>
              </div>
            </div>
            
            {/* Body */}
            <div className="px-3 py-2">
              <div className="font-medium text-white mb-1">
                {reference.document_name}
              </div>
              <div className="text-gray-300 text-xs">
                {reference.description}
              </div>
              
              {/* Financial Citation Content */}
              {reference.document_type.toLowerCase() === 'financial citation' && reference.chunk_text && (
                <div className="mt-2 pt-2 border-t border-gray-700">
                  <div className="text-gray-400 text-xs mb-1">
                    Financial Context:
                  </div>
                  <div className="text-gray-300 text-xs italic bg-gray-800 p-2 rounded max-h-64 overflow-y-auto whitespace-pre-wrap">
                    {highlightFinancialAmounts(reference.chunk_text, reference.financial_amount)}
                  </div>
                </div>
              )}
              
              {/* Document Citation Content - No chunk text for now */}
              {reference.document_type.toLowerCase() !== 'financial citation' && reference.similarity_score && (
                <div className="mt-2 pt-2 border-t border-gray-700">
                  <div className="text-gray-400 text-xs">
                    <span className="text-blue-300">
                      Match Score: {Math.round(reference.similarity_score * 100)}%
                    </span>
                  </div>
                </div>
              )}
              
              <div className="text-gray-400 text-xs mt-2">
                Click to open document
              </div>
            </div>
          </div>
          
          {/* Arrow */}
          <div className="absolute top-full left-1/2 transform -translate-x-1/2">
            <div className="border-4 border-transparent border-t-gray-900"></div>
          </div>
        </div>
      )}
    </span>
  );
};

export default DocumentReferenceComponent;
