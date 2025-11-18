import React from 'react';
import type { TimelineItem, FiscalNoteItem } from '../../../types';

interface TimelineNavigationProps {
  timeline: TimelineItem[];
  fiscalNotes: FiscalNoteItem[];
  selectedNoteIndex: number;
  onTimelineItemClick: (filename: string) => void;
}

const TimelineNavigation: React.FC<TimelineNavigationProps> = ({
  timeline,
  fiscalNotes,
  selectedNoteIndex,
  onTimelineItemClick
}) => {
  const selectedFilename = fiscalNotes[selectedNoteIndex]?.filename;

  return (
    <div className="p-4">
      <h3 className="text-sm font-semibold text-gray-700 mb-4">Timeline</h3>
      
      <div className="space-y-4">
        {timeline.map((item, index) => (
          <div key={index} className="relative">
            {/* Timeline connector line */}
            {index < timeline.length - 1 && (
              <div className="absolute left-2 top-8 w-0.5 h-8 bg-gray-200"></div>
            )}
            
            <div className="flex items-start space-x-3">
              {/* Timeline dot */}
              <div className="flex-shrink-0 w-4 h-4 bg-blue-500 rounded-full mt-1"></div>
              
              <div className="flex-1 min-w-0">
                {/* Date */}
                <div className="text-sm font-medium text-gray-900 mb-1">
                  {item.date}
                </div>
                
                {/* Description */}
                <div className="text-xs text-gray-600 mb-2 leading-relaxed">
                  {item.text}
                </div>
                
                {/* Documents */}
                {item.documents && item.documents.length > 0 && (
                  <div className="space-y-1">
                    {item.documents.map((doc: string, docIndex: number) => {
                      const cleanDocName = doc.replace('.json', '');
                      const isSelected = cleanDocName === selectedFilename;
                      const hasCorrespondingNote = fiscalNotes.some(note => note.filename === cleanDocName);
                      
                      return (
                        <button
                          key={docIndex}
                          onClick={() => onTimelineItemClick(cleanDocName)}
                          disabled={!hasCorrespondingNote}
                          className={`block w-full text-left px-2 py-1 text-xs rounded transition-colors duration-200 ${
                            isSelected
                              ? 'bg-blue-100 text-blue-800 font-medium border border-blue-200'
                              : hasCorrespondingNote
                              ? 'text-blue-600 hover:bg-blue-50 hover:text-blue-800'
                              : 'text-gray-400 cursor-not-allowed'
                          }`}
                          title={hasCorrespondingNote ? 'Click to view fiscal note' : 'No fiscal note available'}
                        >
                          <div className="flex items-center space-x-1">
                            <span className="w-1.5 h-1.5 bg-current rounded-full opacity-60"></span>
                            <span className="truncate">{cleanDocName}</span>
                          </div>
                        </button>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {timeline.length === 0 && (
        <div className="text-center py-8 text-gray-500 text-sm">
          No timeline data available
        </div>
      )}
    </div>
  );
};

export default TimelineNavigation;
