import React from 'react';

interface NumberTrackingSummaryProps {
  counts: {
    total: number;
    new: number;
    continued: number;
    modified: number;
    carried_forward: number;
  };
}

const NumberTrackingSummary: React.FC<NumberTrackingSummaryProps> = ({ counts }) => {
  return (
    <div className="bg-white rounded-lg shadow-md p-6 mb-4 border border-gray-200">
      <h3 className="text-lg font-semibold mb-4 text-gray-900 flex items-center gap-2">
        <span className="text-2xl">📊</span>
        Financial Numbers in This Version
      </h3>
      
      <div className="text-sm text-gray-600 mb-4">
        {counts.total} numbers total
      </div>
      
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="text-center p-4 bg-blue-50 rounded-lg border border-blue-100 transition-all hover:shadow-md">
          <div className="text-3xl font-bold text-blue-600 mb-1">{counts.new}</div>
          <div className="text-sm text-gray-600 font-medium">New</div>
          <div className="text-xs text-gray-500 mt-1">🆕 First appearance</div>
        </div>
        
        <div className="text-center p-4 bg-green-50 rounded-lg border border-green-100 transition-all hover:shadow-md">
          <div className="text-3xl font-bold text-green-600 mb-1">{counts.continued}</div>
          <div className="text-sm text-gray-600 font-medium">Continued</div>
          <div className="text-xs text-gray-500 mt-1">✓ Same amount</div>
        </div>
        
        <div className="text-center p-4 bg-yellow-50 rounded-lg border border-yellow-100 transition-all hover:shadow-md">
          <div className="text-3xl font-bold text-yellow-600 mb-1">{counts.modified}</div>
          <div className="text-sm text-gray-600 font-medium">Modified</div>
          <div className="text-xs text-gray-500 mt-1">⚡ Amount changed</div>
        </div>
        
        <div className="text-center p-4 bg-gray-50 rounded-lg border border-gray-200 transition-all hover:shadow-md">
          <div className="text-3xl font-bold text-gray-600 mb-1">{counts.carried_forward}</div>
          <div className="text-sm text-gray-600 font-medium">Carried</div>
          <div className="text-xs text-gray-500 mt-1">📌 From previous</div>
        </div>
      </div>
      
      {/* Summary insights */}
      {counts.modified > 0 && (
        <div className="mt-4 p-3 bg-yellow-50 border border-yellow-200 rounded-lg">
          <div className="text-sm text-yellow-800">
            <span className="font-semibold">⚡ {counts.modified} number{counts.modified !== 1 ? 's' : ''} changed</span> from the previous version
          </div>
        </div>
      )}
      
      {counts.new > 0 && counts.total === counts.new && (
        <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="text-sm text-blue-800">
            <span className="font-semibold">🆕 Initial version</span> - All numbers are new
          </div>
        </div>
      )}
    </div>
  );
};

export default NumberTrackingSummary;
