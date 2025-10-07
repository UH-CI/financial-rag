import React, { useState, useRef } from 'react';
import type { DocumentReference } from '../types';

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
      case 'testimony':
        return 'bg-green-100 text-green-800 border-green-200';
      case 'Bill Version':
        return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'committee report':
        return 'bg-purple-100 text-purple-800 border-purple-200';
      default:
        return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  const getTypeIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'testimony':
        return '🗣️';
      case 'Bill Version':
        return '📋';
      case 'committee report':
        return '📊';
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
        className="text-blue-600 hover:text-blue-800 font-medium underline hover:no-underline transition-colors duration-200"
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
            <div className={`px-3 py-2 text-xs font-semibold uppercase tracking-wide border-b border-gray-700 ${getTypeColor(reference.document_type)} text-gray-900`}>
              <div className="flex items-center space-x-2">
                <span>{getTypeIcon(reference.document_type)}</span>
                <span>{reference.document_type}</span>
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
              
              {/* Chunk Information */}
              {/* {reference.chunk_text && (
                <div className="mt-2 pt-2 border-t border-gray-700">
                  <div className="text-gray-400 text-xs mb-1">
                    Referenced Content {reference.similarity_score && (
                      <span className="text-blue-300">
                        (Match: {Math.round(reference.similarity_score * 100)}%)
                      </span>
                    )}:
                  </div>
                  <div className="text-gray-300 text-xs italic bg-gray-800 p-2 rounded max-h-20">
                    "{reference.chunk_text}"
                  </div>
                </div>
              )} */}
              
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
