import React, { useState, useRef, useEffect } from 'react';
import type { DocumentReference } from '../types';

// Utility function to highlight financial amounts in text
const highlightFinancialAmounts = (text: string, targetAmount?: number): React.ReactNode => {
  if (!text || !targetAmount) {
    return text;
  }

  // Create formatted amount string
  const formattedAmount = targetAmount.toLocaleString();
  const escapeRegex = (str: string) => str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  
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
  
  // Try multiple patterns in order of specificity:
  // Note: Some texts have $ before the number, others have it after (e.g., "175,000.00 $")
  
  // 1. Try pattern with .00 and $ before (e.g., $10,000.00)
  let pattern = `\\$${escapeRegex(formattedAmount)}\\.00`;
  let regex = new RegExp(`(${pattern})`, 'gi');
  let result = applyHighlighting(text, regex);
  if (result) return result;
  
  // 2. Try pattern with .00 and $ after (e.g., 10,000.00 $)
  pattern = `${escapeRegex(formattedAmount)}\\.00\\s*\\$`;
  regex = new RegExp(`(${pattern})`, 'gi');
  result = applyHighlighting(text, regex);
  if (result) return result;
  
  // 3. Try pattern without decimals but with $ before (e.g., $10,000)
  pattern = `\\$${escapeRegex(formattedAmount)}(?!\\.\\d)`;
  regex = new RegExp(`(${pattern})`, 'gi');
  result = applyHighlighting(text, regex);
  if (result) return result;
  
  // 4. Try pattern without decimals but with $ after (e.g., 10,000 $)
  pattern = `${escapeRegex(formattedAmount)}\\s*\\$(?!\\.\\d)`;
  regex = new RegExp(`(${pattern})`, 'gi');
  result = applyHighlighting(text, regex);
  if (result) return result;
  
  // 5. FALLBACK: If targetAmount is a whole number (no decimals or .00), 
  //    try appending .00 to search for it in the text
  if (Number.isInteger(targetAmount) || targetAmount % 1 === 0) {
    const amountWith00 = targetAmount.toFixed(2); // e.g., 10000 becomes "10000.00"
    const formattedWith00 = parseFloat(amountWith00).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }); // e.g., "10,000.00"
    
    // Try with $ before
    pattern = `\\$${escapeRegex(formattedWith00)}`;
    regex = new RegExp(`(${pattern})`, 'gi');
    result = applyHighlighting(text, regex);
    if (result) return result;
    
    // Try with $ after
    pattern = `${escapeRegex(formattedWith00)}\\s*\\$`;
    regex = new RegExp(`(${pattern})`, 'gi');
    result = applyHighlighting(text, regex);
    if (result) return result;
  }
  
  // 6. FALLBACK: Try matching any decimal variant with $ before
  pattern = `\\$${escapeRegex(formattedAmount)}(?:\\.\\d+)?`;
  regex = new RegExp(`(${pattern})`, 'gi');
  result = applyHighlighting(text, regex);
  if (result) return result;
  
  // 7. FALLBACK: Try matching any decimal variant with $ after
  pattern = `${escapeRegex(formattedAmount)}(?:\\.\\d+)?\\s*\\$`;
  regex = new RegExp(`(${pattern})`, 'gi');
  result = applyHighlighting(text, regex);
  if (result) return result;
  
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
  const tooltipRef = useRef<HTMLDivElement>(null);
  const hideTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // DEBUG: Log reference data when component mounts or reference changes
  useEffect(() => {
    console.log('📋 DocumentReference Data:', {
      number: reference.number,
      displayNumber: reference.displayNumber,
      document_type: reference.document_type,
      document_name: reference.document_name,
      description: reference.description,
      chunk_text_preview: reference.chunk_text?.substring(0, 150),
      chunk_text_length: reference.chunk_text?.length,
      similarity_score: reference.similarity_score,
      sentence: reference.sentence,
      chunk_id: reference.chunk_id,
      document_category: reference.document_category,
      full_reference: reference
    });
  }, [reference]);

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
    // Clear any pending hide timeout
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }
    setShowTooltip(true);
    updateTooltipPosition();
  };
  
  const handleMouseLeave = () => {
    // Delay hiding to allow mouse to move to tooltip
    hideTimeoutRef.current = setTimeout(() => {
      setShowTooltip(false);
    }, 100);
  };
  
  const handleTooltipMouseEnter = () => {
    // Clear hide timeout when mouse enters tooltip
    if (hideTimeoutRef.current) {
      clearTimeout(hideTimeoutRef.current);
      hideTimeoutRef.current = null;
    }
  };
  
  const handleTooltipMouseLeave = () => {
    // Hide tooltip when mouse leaves tooltip
    setShowTooltip(false);
  };
  
  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (hideTimeoutRef.current) {
        clearTimeout(hideTimeoutRef.current);
      }
    };
  }, []);

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
        onMouseLeave={handleMouseLeave}
        title={`${reference.document_type}: ${reference.document_name}`}
      >
        {reference.displayNumber || reference.number}
      </a>

      {/* Custom Tooltip - Using fixed positioning to escape container bounds */}
      {showTooltip && (
        <div 
          ref={tooltipRef}
          className="fixed z-[9999] pointer-events-auto" 
          style={{
            left: tooltipPosition.x,
            top: tooltipPosition.y,
            transform: 'translateX(-50%) translateY(-100%)'
          }}
          onMouseEnter={handleTooltipMouseEnter}
          onMouseLeave={handleTooltipMouseLeave}
        >
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
                  <div className="text-gray-400 text-s mb-1">
                    Financial Context:
                  </div>
                  <div className="text-gray-300 text-xs italic bg-gray-800 p-2 rounded max-h-64 overflow-y-auto whitespace-pre-wrap">
                    {highlightFinancialAmounts(reference.chunk_text, reference.financial_amount)}
                  </div>
                </div>
              )}
              
              {/* Chunk Citation Content */}
              {reference.type === 'chunk_reference' && reference.chunk_text && (
                <div className="mt-2 pt-2 border-t border-gray-700">
                  <div className="text-gray-400 text-md mb-1">
                    Chunk Content:
                  </div>
                  <div className="text-gray-300 text-xs italic bg-gray-800 p-2 rounded max-h-64 overflow-y-auto whitespace-pre-wrap">
                    {reference.chunk_text}
                  </div>
                  {reference.chunk_id && (
                    <div className="text-gray-400 text-xs mt-1">
                      Chunk ID: {reference.chunk_id}
                    </div>
                  )}
                </div>
              )}

              {/* Document Citation Content with Chunk Text */}
              {reference.document_type.toLowerCase() !== 'financial citation' && reference.type !== 'chunk_reference' && (
                <div className="mt-2 pt-2 border-t border-gray-700">
                  {reference.chunk_text && (
                    <div className="mb-2">
                      <div className="text-gray-400 text-xs mb-1">
                        Source Content:
                      </div>
                      <div className="text-gray-300 text-xs italic bg-gray-800 p-2 rounded max-h-64 overflow-y-auto whitespace-pre-wrap">
                        {reference.chunk_text}
                      </div>
                    </div>
                  )}
                  {reference.similarity_score && (
                    <div className="text-gray-400 text-xs">
                      <span className="text-blue-300">
                        Match Score: {Math.round(reference.similarity_score * 100)}%
                      </span>
                    </div>
                  )}
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
