import { useState, useEffect } from 'react';
import { X, Plus, Save, Trash2, GripVertical } from 'lucide-react';
import { 
  getPropertyPrompts, 
  createPropertyPromptTemplate,
  updatePropertyPromptTemplate,
  deletePropertyPromptTemplate,
  setActivePropertyPromptTemplate
} from '../services/api';
import type { PropertyPrompts, PropertyPromptTemplate } from '../services/api';

interface PropertyPromptsSettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

const PropertyPromptsSettings = ({ isOpen, onClose }: PropertyPromptsSettingsProps) => {
  const [templates, setTemplates] = useState<PropertyPromptTemplate[]>([]);
  const [activeTemplateId, setActiveTemplateId] = useState<string>('default');
  const [selectedTabId, setSelectedTabId] = useState<string>('default');
  const [prompts, setPrompts] = useState<PropertyPrompts>({});
  const [templateName, setTemplateName] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [emptyFields, setEmptyFields] = useState<Set<string>>(new Set());
  const [sectionOrder, setSectionOrder] = useState<string[]>([]);
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [sectionKeys, setSectionKeys] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    if (isOpen) {
      loadPrompts();
    }
  }, [isOpen]);

  const loadPrompts = async () => {
    try {
      setIsLoading(true);
      const data = await getPropertyPrompts();
      setTemplates(data.templates);
      setActiveTemplateId(data.active_template_id);
      setSelectedTabId(data.active_template_id);
      
      // Load the active template's prompts
      const activeTemplate = data.templates.find(t => t.id === data.active_template_id);
      if (activeTemplate) {
        setPrompts(activeTemplate.prompts);
        setTemplateName(activeTemplate.name);
        setSectionOrder(Object.keys(activeTemplate.prompts));
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load property prompts');
    } finally {
      setIsLoading(false);
    }
  };

  const switchTab = (templateId: string) => {
    const template = templates.find(t => t.id === templateId);
    if (template) {
      setSelectedTabId(templateId);
      setPrompts(template.prompts);
      setTemplateName(template.name);
      setSectionOrder(Object.keys(template.prompts));
      setError(null);
      setSuccessMessage(null);
    }
  };

  const handleCreateTemplate = async () => {
    try {
      const name = prompt('Enter name for new template:', 'New Template');
      if (!name) return;
      
      const response = await createPropertyPromptTemplate(selectedTabId, name);
      const newTemplates = [...templates, response.template];
      setTemplates(newTemplates);
      switchTab(response.template.id);
      setSuccessMessage(response.message);
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to create template');
    }
  };

  const handleSave = async () => {
    try {
      setIsSaving(true);
      setError(null);
      setSuccessMessage(null);
      setEmptyFields(new Set());
      
      // Validate
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
        setError(`Please fill in all required fields`);
        if (firstEmptyField) {
          setTimeout(() => {
            document.getElementById(firstEmptyField)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          }, 100);
        }
        return;
      }

      // Order prompts
      const orderedPrompts: PropertyPrompts = {};
      for (const key of sectionOrder) {
        if (prompts[key]) orderedPrompts[key] = prompts[key];
      }

      // Update template
      await updatePropertyPromptTemplate(selectedTabId, { 
        name: templateName, 
        prompts: orderedPrompts 
      });
      
      // Reload to get fresh data
      await loadPrompts();
      setSuccessMessage('Template saved');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to save');
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async () => {
    const template = templates.find(t => t.id === selectedTabId);
    if (!template || template.is_default) return;
    
    if (!confirm(`Delete template "${template.name}"?`)) return;

    try {
      await deletePropertyPromptTemplate(selectedTabId);
      await loadPrompts();
      setSuccessMessage('Template deleted');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to delete');
    }
  };

  const handleSetActive = async () => {
    try {
      await setActivePropertyPromptTemplate(selectedTabId);
      setActiveTemplateId(selectedTabId);
      setSuccessMessage('Active template updated');
      setTimeout(() => setSuccessMessage(null), 3000);
    } catch (err: any) {
      setError(err.message || 'Failed to set active');
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
    
    // Add to section order
    setSectionOrder([...sectionOrder, newKey]);
  };

  const handleDeleteSection = (key: string) => {
    const newPrompts = { ...prompts };
    delete newPrompts[key];
    setPrompts(newPrompts);
    
    // Remove from section order
    setSectionOrder(sectionOrder.filter(k => k !== key));
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

  useEffect(() => {
    const keysMap = new Map<string, string>();
    Object.keys(prompts).forEach(key => keysMap.set(key, key));
    setSectionKeys(keysMap);
  }, [prompts]);

  const handleDragStart = (index: number) => {
    setDraggedIndex(index);
  };

  const handleDragOver = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (draggedIndex === null || draggedIndex === index) return;

    const newOrder = [...sectionOrder];
    const draggedKey = newOrder[draggedIndex];
    newOrder.splice(draggedIndex, 1);
    newOrder.splice(index, 0, draggedKey);

    setSectionOrder(newOrder);
    setDraggedIndex(index);
  };

  const handleDragEnd = () => {
    setDraggedIndex(null);
  };

  const handleRenameSection = (oldKey: string, newKey: string) => {
    if (oldKey === newKey) return;
    
    const newPrompts: PropertyPrompts = {};
    const newOrder: string[] = [];
    
    for (const key of sectionOrder) {
      if (key === oldKey) {
        newPrompts[newKey] = prompts[oldKey];
        newOrder.push(newKey);
      } else {
        newPrompts[key] = prompts[key];
        newOrder.push(key);
      }
    }
    
    setPrompts(newPrompts);
    setSectionOrder(newOrder);
    
    const stableKey = sectionKeys.get(oldKey);
    if (stableKey) {
      const newKeysMap = new Map(sectionKeys);
      newKeysMap.delete(oldKey);
      newKeysMap.set(newKey, stableKey);
      setSectionKeys(newKeysMap);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl max-w-6xl w-full max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-6 border-b border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-gray-900">Property Prompts</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <X className="w-6 h-6" />
            </button>
          </div>
          
          {/* Tabs */}
          <div className="flex items-center gap-2 overflow-x-auto">
            {templates.map(template => (
              <button
                key={template.id}
                onClick={() => switchTab(template.id)}
                className={`px-4 py-2 rounded-t-lg font-medium transition-colors whitespace-nowrap ${
                  selectedTabId === template.id
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {template.name}
                {activeTemplateId === template.id && <span className="ml-2">●</span>}
              </button>
            ))}
            <button
              onClick={handleCreateTemplate}
              className="px-3 py-2 rounded-t-lg bg-gray-100 text-gray-700 hover:bg-gray-200 font-bold"
              title="Create new template"
            >
              +
            </button>
          </div>
          
          {/* Template Name */}
          <div className="mt-4 flex items-center gap-4">
            <input
              type="text"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              disabled={templates.find(t => t.id === selectedTabId)?.is_default}
              className="flex-1 px-3 py-2 border rounded-lg disabled:bg-gray-100 disabled:cursor-not-allowed"
              placeholder="Template name"
            />
            {activeTemplateId !== selectedTabId && (
              <button
                onClick={handleSetActive}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 text-sm"
              >
                Set Active
              </button>
            )}
          </div>
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
              {sectionOrder.map((key, index) => {
                const value = prompts[key];
                if (!value) return null;
                
                // Use stable key for React, or fall back to current key
                const stableKey = sectionKeys.get(key) || key;
                return (
                <div 
                  key={stableKey} 
                  draggable
                  onDragStart={() => handleDragStart(index)}
                  onDragOver={(e) => handleDragOver(e, index)}
                  onDragEnd={handleDragEnd}
                  className={`border border-gray-200 rounded-lg p-3 bg-gray-50 cursor-move transition-all relative ${
                    draggedIndex === index ? 'opacity-50' : ''
                  }`}
                >
                  {/* Delete button in top right */}
                  <button
                    onClick={() => handleDeleteSection(key)}
                    className="absolute top-2 right-2 text-red-600 hover:text-red-800 transition-colors"
                    title="Delete section"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>

                  <div className="flex items-start gap-2 mb-1">
                    {/* Drag Handle */}
                    <div className="pt-1 text-gray-400 hover:text-gray-600 cursor-grab active:cursor-grabbing">
                      <GripVertical className="w-5 h-5" />
                    </div>
                    
                    <div className="flex-1 max-w-2xl pr-6">
                      <input
                        id={`${key}-name`}
                        type="text"
                        value={key}
                        onChange={(e) => handleRenameSection(key, e.target.value)}
                        className={`w-full text-base font-semibold text-gray-900 bg-transparent border-b ${
                          emptyFields.has(`${key}-name`) 
                            ? 'border-red-500 bg-red-50' 
                            : 'border-transparent hover:border-gray-300 focus:border-blue-500'
                        } px-1 -ml-1 py-0.5`}
                        placeholder="Section name"
                      />
                    </div>
                  </div>

                  <div className="space-y-1.5 ml-7">
                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-0.5">
                        Description
                      </label>
                      <input
                        id={`${key}-description`}
                        type="text"
                        value={value.description}
                        onChange={(e) => handleUpdateSection(key, 'description', e.target.value)}
                        className={`w-full border rounded-md px-2 py-1.5 text-sm focus:outline-none focus:ring-2 ${
                          emptyFields.has(`${key}-description`)
                            ? 'border-red-500 bg-red-50 focus:ring-red-500'
                            : 'border-gray-300 focus:ring-blue-500 focus:border-transparent'
                        }`}
                        placeholder="Brief description of this section"
                      />
                    </div>

                    <div>
                      <label className="block text-xs font-medium text-gray-700 mb-0.5">
                        Prompt
                      </label>
                      <textarea
                        id={`${key}-prompt`}
                        value={value.prompt}
                        onChange={(e) => handleUpdateSection(key, 'prompt', e.target.value)}
                        rows={3}
                        className={`w-full border rounded-md px-2 py-1.5 focus:outline-none focus:ring-2 font-mono text-xs ${
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
          <div>
            {!templates.find(t => t.id === selectedTabId)?.is_default && (
              <button
                onClick={handleDelete}
                disabled={activeTemplateId === selectedTabId}
                className="px-4 py-2 border border-red-300 text-red-600 rounded-lg hover:bg-red-50 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Delete Template
              </button>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <button onClick={onClose} className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50">
              Cancel
            </button>
            <button
              onClick={handleSave}
              disabled={isLoading || isSaving}
              className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              <span>{isSaving ? 'Saving...' : 'Save'}</span>
            </button>
            {successMessage && <span className="text-green-600 font-medium text-sm">✓ {successMessage}</span>}
          </div>
        </div>
      </div>
    </div>
  );
};

export default PropertyPromptsSettings;
