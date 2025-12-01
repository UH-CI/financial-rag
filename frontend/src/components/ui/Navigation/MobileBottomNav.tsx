import React from 'react';
import { FileText, Search } from 'lucide-react';

type Tabs = 'fiscal-note-generation' | 'similar-bill-search' | 'hrs-search';

interface MobileBottomNavProps {
  currentView: Tabs;
  onViewChange: (view: Tabs) => void;
}

const MobileBottomNav: React.FC<MobileBottomNavProps> = ({ currentView, onViewChange }) => {
  return (
    <nav className="lg:hidden fixed bottom-0 left-0 right-0 bg-white border-t border-gray-200 shadow-lg z-50 safe-bottom">
      <div className="flex items-center justify-around h-16">
        {/* Fiscal Note Generation */}
        <button
          onClick={() => onViewChange('fiscal-note-generation')}
          className={`flex flex-col items-center justify-center flex-1 h-full transition-colors ${
            currentView === 'fiscal-note-generation'
              ? 'text-blue-600 bg-blue-50'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
          }`}
        >
          <FileText className={`w-6 h-6 mb-1 ${currentView === 'fiscal-note-generation' ? 'stroke-[2.5]' : ''}`} />
          <span className="text-xs font-medium">Fiscal Note</span>
        </button>

        {/* Similar Bill Search */}
        <button
          onClick={() => onViewChange('similar-bill-search')}
          className={`flex flex-col items-center justify-center flex-1 h-full transition-colors ${
            currentView === 'similar-bill-search'
              ? 'text-purple-600 bg-purple-50'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
          }`}
        >
          <Search className={`w-6 h-6 mb-1 ${currentView === 'similar-bill-search' ? 'stroke-[2.5]' : ''}`} />
          <span className="text-xs font-medium">Bill Search</span>
        </button>

        {/* HRS Search */}
        <button
          onClick={() => onViewChange('hrs-search')}
          className={`flex flex-col items-center justify-center flex-1 h-full transition-colors ${
            currentView === 'hrs-search'
              ? 'text-purple-600 bg-purple-50'
              : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
          }`}
        >
          <Search className={`w-6 h-6 mb-1 ${currentView === 'hrs-search' ? 'stroke-[2.5]' : ''}`} />
          <span className="text-xs font-medium">HRS Search</span>
        </button>
      </div>
    </nav>
  );
};

export default MobileBottomNav;
