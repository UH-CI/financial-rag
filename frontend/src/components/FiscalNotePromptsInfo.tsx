import { useState, useEffect } from 'react';
import { X, Info } from 'lucide-react';
import { getFiscalNotePropertyPrompts } from '../services/api';
import type { PropertyPrompts } from '../services/api';

interface FiscalNotePromptsInfoProps {
  isOpen: boolean;
  onClose: () => void;
  billType: 'HB' | 'SB';
  billNumber: string;
  fiscalNoteName: string;
  year?: string;
}

const FiscalNotePromptsInfo = ({ 
  isOpen, 
  onClose, 
  billType, 
  billNumber, 
  fiscalNoteName,
  year = '2025'
}: FiscalNotePromptsInfoProps) => {
  const [prompts, setPrompts] = useState<PropertyPrompts>({});
  const [isStored, setIsStored] = useState(false);
  const [customPromptsUsed, setCustomPromptsUsed] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadPrompts();
    }
  }, [isOpen, billType, billNumber, fiscalNoteName, year]);

  const loadPrompts = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await getFiscalNotePropertyPrompts(billType, billNumber, fiscalNoteName, year);
      setPrompts(response.prompts);
      setIsStored(response.is_stored);
      setCustomPromptsUsed(response.custom_prompts_used || false);
      setMessage(response.message || null);
    } catch (err: any) {
      setError(err.message || 'Failed to load property prompts');
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Prompts</h2>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-sm text-gray-600">{fiscalNoteName}</p>
              <span className="text-sm">•</span>
              <span className={`text-sm font-medium ${customPromptsUsed ? 'text-orange-600' : 'text-gray-600'}`}>
                {customPromptsUsed ? 'Custom prompts used' : 'Default prompts used'}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {isLoading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
            </div>
          ) : error ? (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          ) : (
            <div className="space-y-6">
              {Object.entries(prompts).map(([key, value]) => (
                <div key={key} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                  <div className="mb-3">
                    <h3 className="text-lg font-semibold text-gray-900">{key}</h3>
                    <p className="text-sm text-gray-600 mt-1">{value.description}</p>
                  </div>

                  <div className="bg-white border border-gray-200 rounded-md p-3">
                    <p className="text-sm text-gray-700 font-mono whitespace-pre-wrap">
                      {value.prompt}
                    </p>
                  </div>
                </div>
              ))}

              {Object.keys(prompts).length === 0 && (
                <div className="text-center py-12 text-gray-500">
                  <Info className="w-12 h-12 mx-auto mb-3 opacity-50" />
                  <p>No property prompts found for this fiscal note</p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default FiscalNotePromptsInfo;
