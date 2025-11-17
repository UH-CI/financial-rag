import React from 'react';
import type { TrackedNumber } from '../../../types';
import ChangeTypeBadge from '../Badge/ChangeTypeBadge';

interface NumberDetailModalProps {
  number: TrackedNumber;
  onClose: () => void;
}

const NumberDetailModal: React.FC<NumberDetailModalProps> = ({ number, onClose }) => {
  return (
    <div 
      className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div 
        className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between rounded-t-lg">
          <h3 className="text-xl font-bold text-gray-900">
            ${number.number.toLocaleString()} Details
          </h3>
          <button 
            onClick={onClose} 
            className="text-gray-400 hover:text-gray-600 transition-colors"
            aria-label="Close modal"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {/* Content */}
        <div className="p-6 space-y-6">
          {/* Current Status */}
          <div>
            <div className="flex items-center gap-4 mb-2">
              <span className="text-sm font-medium text-gray-600">Current Status:</span>
              <ChangeTypeBadge type={number.change_type} />
            </div>
            <div className="text-sm text-gray-600">
              First Appeared: Segment {number.first_appeared_in_segment}
            </div>
            {number.carried_forward && (
              <div className="text-sm text-gray-500 italic mt-1">
                (Carried forward from previous version)
              </div>
            )}
          </div>
          
          {/* Summary */}
          {number.summary && (
            <div>
              <h4 className="text-lg font-semibold text-gray-900 mb-2">Summary</h4>
              <div className="bg-gray-50 rounded-lg p-4">
                <p className="text-gray-700 leading-relaxed">{number.summary}</p>
              </div>
            </div>
          )}
          
          {/* Properties */}
          {(number.entity_name || number.type || number.fund_type || number.fiscal_year || number.expending_agency || number.category) && (
            <div>
              <h4 className="text-lg font-semibold text-gray-900 mb-3">Properties</h4>
              <div className="grid grid-cols-2 gap-3">
                {number.entity_name && (
                  <div className="bg-blue-50 rounded-lg p-3 border border-blue-100">
                    <div className="text-xs text-gray-600 mb-1">Entity</div>
                    <div className="text-sm font-semibold text-blue-700">{number.entity_name}</div>
                  </div>
                )}
                {number.type && (
                  <div className="bg-purple-50 rounded-lg p-3 border border-purple-100">
                    <div className="text-xs text-gray-600 mb-1">Type</div>
                    <div className="text-sm font-semibold text-purple-700">{number.type}</div>
                  </div>
                )}
                {number.fund_type && (
                  <div className="bg-green-50 rounded-lg p-3 border border-green-100">
                    <div className="text-xs text-gray-600 mb-1">Fund Type</div>
                    <div className="text-sm font-semibold text-green-700">{number.fund_type}</div>
                  </div>
                )}
                {number.fiscal_year && number.fiscal_year.length > 0 && (
                  <div className="bg-indigo-50 rounded-lg p-3 border border-indigo-100">
                    <div className="text-xs text-gray-600 mb-1">Fiscal Year</div>
                    <div className="text-sm font-semibold text-indigo-700">
                      {number.fiscal_year.join(', ')}
                    </div>
                  </div>
                )}
                {number.expending_agency && (
                  <div className="bg-orange-50 rounded-lg p-3 border border-orange-100">
                    <div className="text-xs text-gray-600 mb-1">Agency</div>
                    <div className="text-sm font-semibold text-orange-700">{number.expending_agency}</div>
                  </div>
                )}
                {number.category && (
                  <div className="bg-pink-50 rounded-lg p-3 border border-pink-100">
                    <div className="text-xs text-gray-600 mb-1">Category</div>
                    <div className="text-sm font-semibold text-pink-700">{number.category}</div>
                  </div>
                )}
              </div>
            </div>
          )}
          
          {/* Warning for exact match with low similarity */}
          {number.exact_match_low_similarity && (
            <div className="bg-yellow-50 border-2 border-yellow-300 rounded-lg p-4">
              <div className="flex items-start gap-3">
                <span className="text-2xl">⚠️</span>
                <div className="flex-1">
                  <h4 className="text-sm font-semibold text-yellow-900 mb-1">
                    Exact Match with Different Context
                  </h4>
                  <p className="text-sm text-yellow-800 mb-2">
                    This exact dollar amount appeared in <strong>Segment {number.exact_match_low_similarity.previous_segment}</strong> but 
                    with a <strong>different context</strong> (similarity: {(number.exact_match_low_similarity.similarity * 100).toFixed(1)}%)
                  </p>
                  <div className="bg-white rounded p-3 mt-2">
                    <div className="text-xs text-gray-600 mb-1">Previous context:</div>
                    <div className="text-sm text-gray-800">{number.exact_match_low_similarity.previous_summary}</div>
                  </div>
                </div>
              </div>
            </div>
          )}
          
          {/* History Timeline */}
          {number.history && number.history.length > 0 && (
            <div>
              <h4 className="text-lg font-semibold text-gray-900 mb-4">Evolution History</h4>
              <div className="border-l-2 border-blue-200 pl-6 ml-2 space-y-6">
                {number.history.map((entry, idx) => (
                  <div key={idx} className="relative">
                    <div className="absolute -left-[1.875rem] top-1 w-4 h-4 rounded-full bg-blue-500 border-2 border-white shadow" />
                    <div className="text-sm font-semibold text-gray-700 mb-1">
                      Segment {entry.segment_id}
                    </div>
                    <div className="text-base font-bold text-gray-900 mb-1">
                      ${entry.number.toLocaleString()}
                    </div>
                    {entry.summary && (
                      <div className="text-sm text-gray-600 mb-2">
                        {entry.summary}
                      </div>
                    )}
                    {entry.number !== number.number && (
                      <div className="text-xs text-yellow-600 font-semibold mb-2">
                        Value changed: ${entry.number.toLocaleString()} → ${number.number.toLocaleString()}
                      </div>
                    )}
                    <div className="mt-2">
                      <div className="text-xs text-gray-500 mb-1">
                        Similarity: {(entry.similarity_score * 100).toFixed(1)}%
                      </div>
                      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
                        <div 
                          className="h-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 transition-all duration-300"
                          style={{ width: `${entry.similarity_score * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Source Documents */}
          {number.source_documents && number.source_documents.length > 0 && (
            <div>
              <h4 className="text-lg font-semibold text-gray-900 mb-2">Source Documents</h4>
              <div className="bg-blue-50 rounded-lg p-4 space-y-2 border border-blue-100">
                {number.source_documents.map((doc, idx) => (
                  <div 
                    key={idx} 
                    className="text-sm text-gray-700 font-mono bg-white px-3 py-2 rounded border border-blue-200 break-all"
                  >
                    {doc}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          {/* Context Text */}
          {number.text && (
            <div>
              <h4 className="text-lg font-semibold text-gray-900 mb-2">Context</h4>
              <div className="bg-gray-50 rounded-lg p-4 text-sm text-gray-700 max-h-40 overflow-y-auto border border-gray-200">
                {number.text}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default NumberDetailModal;
