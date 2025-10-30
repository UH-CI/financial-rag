import { useState, useEffect } from 'react';
import { X, Plus, RotateCcw, Save, Trash2 } from 'lucide-react';
import { getPropertyPrompts, savePropertyPrompts, resetPropertyPrompts } from '../services/api';
import type { PropertyPrompts } from '../services/api';

interface PropertyPromptsSettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

const PropertyPromptsSettings = ({ isOpen, onClose }: PropertyPromptsSettingsProps) => {
  const [prompts, setPrompts] = useState<PropertyPrompts>({});
  const [isCustom, setIsCustom] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [emptyFields, setEmptyFields] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (isOpen) {
      loadPrompts();
    }
  }, [isOpen]);

  const loadPrompts = async () => {
    try {
      setIsLoading(true);
      setError(null);
      const response = await getPropertyPrompts();
      setPrompts(response.prompts);
      setIsCustom(response.is_custom);
    } catch (err: any) {
      setError(err.message || 'Failed to load property prompts');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      setError(null);
      setSuccessMessage(null);
      setEmptyFields(new Set());
      
      // Validate prompts - check for empty fields
      const newEmptyFields = new Set<string>();
      let firstEmptyField: string | null = null;
      
      for (const [key, value] of Object.entries(prompts)) {
        if (!key.trim()) {
          newEmptyFields.add(`${key}-name`);
          if (!firstEmptyField) firstEmptyField = `${key}-name`;
        }
        if (!value.prompt || !value.prompt.trim()) {
          newEmptyFields.add(`${key}-prompt`);
          if (!firstEmptyField) firstEmptyField = `${key}-prompt`;
        }
        if (!value.description || !value.description.trim()) {
          newEmptyFields.add(`${key}-description`);
          if (!firstEmptyField) firstEmptyField = `${key}-description`;
        }
      }
      
      if (newEmptyFields.size > 0) {
        setEmptyFields(newEmptyFields);
        setError(`Please fill in all required fields (${newEmptyFields.size} field${newEmptyFields.size > 1 ? 's' : ''} empty)`);
        
        // Scroll to first empty field
        if (firstEmptyField) {
          setTimeout(() => {
            const element = document.getElementById(firstEmptyField);
            if (element) {
              element.scrollIntoView({ behavior: 'smooth', block: 'center' });
              element.focus();
            }
          }, 100);
        }
        return;
      }

      const response = await savePropertyPrompts(prompts);
      setSuccessMessage(response.message);
      setIsCustom(true);
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to save property prompts');
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = async () => {
    if (!confirm('Are you sure you want to reset to default prompts? This will discard all custom changes.')) {
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      setSuccessMessage(null);
      const response = await resetPropertyPrompts();
      setPrompts(response.prompts);
      setIsCustom(false);
      setSuccessMessage('Reset to default prompts');
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to reset property prompts');
    } finally {
      setIsLoading(false);
    }
  };

  const handleAddSection = () => {
    const newKey = `custom_section_${Date.now()}`;
    const stableKey = `stable_${Date.now()}`;
    
    setPrompts({
      ...prompts,
      [newKey]: {
        prompt: '',
        description: ''
      }
    });
    
    // Add to stable keys map
    const newKeysMap = new Map(sectionKeys);
    newKeysMap.set(newKey, stableKey);
    setSectionKeys(newKeysMap);
  };

  const handleDeleteSection = (key: string) => {
    const newPrompts = { ...prompts };
    delete newPrompts[key];
    setPrompts(newPrompts);
  };

  const handleUpdateSection = (key: string, field: 'prompt' | 'description', value: string) => {
    setPrompts({
      ...prompts,
      [key]: {
        ...prompts[key],
        [field]: value
      }
    });
    
    // Clear the error styling for this field when user starts typing
    const fieldId = `${key}-${field}`;
    if (emptyFields.has(fieldId)) {
      const newEmptyFields = new Set(emptyFields);
      newEmptyFields.delete(fieldId);
      setEmptyFields(newEmptyFields);
      
      // Clear error message if no more empty fields
      if (newEmptyFields.size === 0) {
        setError(null);
      }
    }
  };

  // Track original keys to maintain stable React keys during editing
  const [sectionKeys, setSectionKeys] = useState<Map<string, string>>(new Map());
  
  useEffect(() => {
    // Initialize section keys map when prompts load
    const keysMap = new Map<string, string>();
    Object.keys(prompts).forEach(key => {
      keysMap.set(key, key);
    });
    setSectionKeys(keysMap);
  }, [isLoading]);

  const handleRenameSection = (oldKey: string, newKey: string) => {
    if (oldKey === newKey) return;
    
    // Allow typing but don't validate until blur or save
    const newPrompts: PropertyPrompts = {};
    for (const [key, value] of Object.entries(prompts)) {
      if (key === oldKey) {
        newPrompts[newKey] = value;
      } else {
        newPrompts[key] = value;
      }
    }
    setPrompts(newPrompts);
    
    // Update the stable key mapping
    const stableKey = sectionKeys.get(oldKey);
    if (stableKey) {
      const newKeysMap = new Map(sectionKeys);
      newKeysMap.delete(oldKey);
      newKeysMap.set(newKey, stableKey);
      setSectionKeys(newKeysMap);
    }
    
    // Clear the error styling for the name field when user starts typing
    const fieldId = `${oldKey}-name`;
    if (emptyFields.has(fieldId)) {
      const newEmptyFields = new Set(emptyFields);
      newEmptyFields.delete(fieldId);
      // Also update to new key
      if (newKey.trim()) {
        newEmptyFields.delete(`${newKey}-name`);
      }
      setEmptyFields(newEmptyFields);
      
      // Clear error message if no more empty fields
      if (newEmptyFields.size === 0) {
        setError(null);
      }
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-200 flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">Property Prompts Settings</h2>
            <p className="text-sm text-gray-600 mt-1">
              Configure how fiscal notes are generated
              {isCustom && <span className="ml-2 text-blue-600 font-medium">(Custom)</span>}
            </p>
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
          ) : (
            <div className="space-y-6">
              {/* Error/Success Messages */}
              {error && (
                <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
                  {error}
                </div>
              )}
              {successMessage && (
                <div className="bg-green-50 border border-green-200 text-green-700 px-4 py-3 rounded-lg">
                  {successMessage}
                </div>
              )}

              {/* Prompt Sections */}
              {Object.entries(prompts).map(([key, value]) => {
                // Use stable key for React, or fall back to current key
                const stableKey = sectionKeys.get(key) || key;
                return (
                <div key={stableKey} className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1 max-w-2xl">
                      <input
                        id={`${key}-name`}
                        type="text"
                        value={key}
                        onChange={(e) => handleRenameSection(key, e.target.value)}
                        className={`w-full text-lg font-semibold text-gray-900 bg-transparent border-b ${
                          emptyFields.has(`${key}-name`) 
                            ? 'border-red-500 bg-red-50' 
                            : 'border-transparent hover:border-gray-300 focus:border-blue-500'
                        } px-1 -ml-1`}
                        placeholder="Section name"
                      />
                    </div>
                    <button
                      onClick={() => handleDeleteSection(key)}
                      className="text-red-600 hover:text-red-800 transition-colors ml-2"
                      title="Delete section"
                    >
                      <Trash2 className="w-5 h-5" />
                    </button>
                  </div>

                  <div className="space-y-3">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Description
                      </label>
                      <input
                        id={`${key}-description`}
                        type="text"
                        value={value.description}
                        onChange={(e) => handleUpdateSection(key, 'description', e.target.value)}
                        className={`w-full border rounded-md px-3 py-2 focus:outline-none focus:ring-2 ${
                          emptyFields.has(`${key}-description`)
                            ? 'border-red-500 bg-red-50 focus:ring-red-500'
                            : 'border-gray-300 focus:ring-blue-500 focus:border-transparent'
                        }`}
                        placeholder="Brief description of this section"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Prompt
                      </label>
                      <textarea
                        id={`${key}-prompt`}
                        value={value.prompt}
                        onChange={(e) => handleUpdateSection(key, 'prompt', e.target.value)}
                        rows={4}
                        className={`w-full border rounded-md px-3 py-2 focus:outline-none focus:ring-2 font-mono text-sm ${
                          emptyFields.has(`${key}-prompt`)
                            ? 'border-red-500 bg-red-50 focus:ring-red-500'
                            : 'border-gray-300 focus:ring-blue-500 focus:border-transparent'
                        }`}
                        placeholder="Enter the prompt for generating this section..."
                      />
                    </div>
                  </div>
                </div>
                );
              })}

              {/* Add Section Button */}
              <button
                onClick={handleAddSection}
                className="w-full border-2 border-dashed border-gray-300 rounded-lg px-4 py-6 text-gray-600 hover:border-blue-500 hover:text-blue-600 transition-colors flex items-center justify-center space-x-2"
              >
                <Plus className="w-5 h-5" />
                <span className="font-medium">Add Section</span>
              </button>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-6 border-t border-gray-200 flex items-center justify-between">
          <button
            onClick={handleReset}
            disabled={isLoading || isSaving}
            className="flex items-center space-x-2 px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RotateCcw className="w-4 h-4" />
            <span>Reset to Default</span>
          </button>

          <div className="flex space-x-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isLoading || isSaving}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Save className="w-4 h-4" />
              <span>{isSaving ? 'Saving...' : 'Save Changes'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PropertyPromptsSettings;
