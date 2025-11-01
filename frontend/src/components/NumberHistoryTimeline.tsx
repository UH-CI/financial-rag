import React from 'react';
import type { HistoryEntry, TrackedNumber } from '../types';

interface NumberHistoryTimelineProps {
  history: HistoryEntry[];
  currentNumber: TrackedNumber;
  currentSegmentId: number;
  documentMapping?: Record<string, number>;
}

const NumberHistoryTimeline: React.FC<NumberHistoryTimelineProps> = ({ history, currentNumber, currentSegmentId, documentMapping }) => {
  if (!history || history.length === 0) {
    return (
      <div className="bg-gray-50 p-4 text-center text-gray-500 text-sm">
        No history available
      </div>
    );
  }

  return (
    <div className="bg-gray-50 p-4 border-t border-gray-200">
      <h4 className="text-xs font-semibold text-gray-600 mb-3 uppercase tracking-wide">
        History ({history.length})
      </h4>
      
      <div className="space-y-2">
        {history.map((entry, idx) => (
          <div key={idx} className="flex items-center gap-3 text-sm">
            {/* Segment number */}
            <div className="flex-shrink-0 w-16 text-gray-600 font-mono text-xs">
              Seg {entry.segment_id}
            </div>
            
            {/* Document references */}
            <div className="flex-shrink-0">
              {entry.source_documents && entry.source_documents.length > 0 && documentMapping ? (
                <span className="text-blue-600 font-mono text-xs">
                  {entry.source_documents.map((doc, i) => {
                    const docBase = doc.split('.')[0];
                    const docBaseNoUnderscore = docBase.replace(/_$/, '');
                    const refNum = documentMapping[docBase] || 
                                   documentMapping[docBaseNoUnderscore] || 
                                   documentMapping[doc];
                    return (
                      <span key={i} className="mr-1">
                        [{refNum || '?'}]
                      </span>
                    );
                  })}
                </span>
              ) : entry.filename && documentMapping ? (
                <span className="text-blue-600 font-mono text-xs">
                  {(() => {
                    const docBase = entry.filename.split('.')[0];
                    const docBaseNoUnderscore = docBase.replace(/_$/, '');
                    const refNum = documentMapping[docBase] || 
                                   documentMapping[docBaseNoUnderscore] || 
                                   documentMapping[entry.filename];
                    return `[${refNum || '?'}]`;
                  })()}
                </span>
              ) : null}
            </div>
            
            {/* Amount */}
            <div className="flex-shrink-0 font-semibold text-gray-900">
              ${entry.number.toLocaleString()}
            </div>
            
            {/* Summary */}
            {entry.summary && (
              <div className="flex-1 text-gray-600 text-xs line-clamp-1">
                {entry.summary}
              </div>
            )}
          </div>
        ))}
        
        {/* Current state */}
        <div className="flex items-center gap-3 text-sm bg-green-50 border border-green-200 rounded px-2 py-1.5 mt-2">
          <div className="flex-shrink-0 w-16 text-green-700 font-mono text-xs font-semibold">
            Current
          </div>
          <div className="flex-shrink-0 text-green-700 font-mono text-xs">
            Seg {currentSegmentId}
          </div>
          <div className="flex-shrink-0 font-semibold text-gray-900">
            ${currentNumber.number.toLocaleString()}
          </div>
          {currentNumber.summary && (
            <div className="flex-1 text-gray-600 text-xs line-clamp-1">
              {currentNumber.summary}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NumberHistoryTimeline;
