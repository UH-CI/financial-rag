import { Loader2 } from 'lucide-react';
import React, { useState } from 'react';

export interface HRSFilter {
  volume?: string;
  chapter?: string;
  section?: string;
}

export type HRSIndex = { 
  [volumeName: string]: { 
    [chapterName: string]: string[] 
  } 
};

interface HRSIndexViewProps {
  index: HRSIndex | null;
  selectedFilter: HRSFilter; 
  onFilterChange: (filter: HRSFilter) => void;
  onLinkChange: (filter: HRSFilter) => void;
}

const isSameFilter = (a: HRSFilter, b: HRSFilter): boolean => {
  return a.volume === b.volume && 
         a.chapter === b.chapter && 
         a.section === b.section;
};

export const HRSIndexView: React.FC<HRSIndexViewProps> = ({ index, selectedFilter, onFilterChange, onLinkChange }) => {
  return (
    <>
      {index ? (
        <div style={{ fontFamily: '-apple-system, sans-serif', maxWidth: '1000px', border: '1px solid #e5e7eb', borderRadius: '8px', overflow: 'hidden' }}>
        {Object.entries(index).map(([volName, chapters]) => (
          <VolumeRow 
            key={volName} 
            name={volName} 
            chapters={chapters}
            selectedFilter={selectedFilter}
            onFilterChange={onFilterChange}
            onLinkChange={onLinkChange}
          />
      ))}
    </div>
      ) : (
        <div>
          <p className="text-gray-600">Loading Index</p>
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
        </div>
        
      )}
    </>
  );
};

// --- Level 1: Volume ---
const VolumeRow: React.FC<{ 
  name: string; 
  chapters: { [key: string]: string[] }; 
  selectedFilter: HRSFilter;
  onFilterChange: (f: HRSFilter) => void;
  onLinkChange: (f: HRSFilter) => void;
}> = ({ name, chapters, selectedFilter, onFilterChange, onLinkChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  
  const thisFilter: HRSFilter = { volume: name };
  const isActive = isSameFilter(selectedFilter, thisFilter);

  const handleFilter = () => {
    onFilterChange(isActive ? {} : thisFilter);
  };

  return (
    <div style={{ borderBottom: '1px solid #e5e7eb', backgroundColor: isActive ? '#eff6ff' : '#f9fafb' }}>
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{ 
          padding: '16px', display: 'flex', alignItems: 'right', cursor: 'pointer',
          borderLeft: isActive ? '4px solid #3b82f6' : '4px solid transparent'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexGrow: 1}}>
          <Chevron isOpen={isOpen} />
          <Badge label="Volume" color="#6b7280" bg="#f3f4f6" />
          <span style={{ fontSize: '16px', fontWeight: 600, color: '#111827' }}>{name}</span>
        </div>
        

        <FilterBtn active={isActive} onClick={handleFilter} />

        
      </div>

      {isOpen && (
        <div style={{ borderTop: '1px solid #e5e7eb' }}>
          {Object.entries(chapters).map(([chapName, sections]) => (
            <ChapterRow 
              key={chapName} 
              name={chapName} 
              volumeName={name}
              sections={sections} 
              selectedFilter={selectedFilter}
              onFilterChange={onFilterChange}
              onLinkChange={onLinkChange}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// --- Level 2: Chapter ---
const ChapterRow: React.FC<{ 
  name: string; 
  volumeName: string;
  sections: string[]; 
  selectedFilter: HRSFilter;
  onFilterChange: (f: HRSFilter) => void;
  onLinkChange: (f: HRSFilter) => void;
}> = ({ name, volumeName, sections, selectedFilter, onFilterChange, onLinkChange }) => {
  const [isOpen, setIsOpen] = useState(false);

  const thisFilter: HRSFilter = { volume: volumeName, chapter: name };
  const isActive = isSameFilter(selectedFilter, thisFilter);

  const handleFilter = () => {
    onFilterChange(isActive ? {} : thisFilter);
  };


  return (
    <div style={{ backgroundColor: isActive ? '#f5f3ff' : '#ffffff' }}>
      <div 
        onClick={() => setIsOpen(!isOpen)}
        style={{ 
          padding: '12px 16px 12px 30px', 
          display: 'flex', alignItems: 'right', cursor: 'pointer', 
          borderBottom: '1px solid #f3f4f6',
          borderLeft: isActive ? '4px solid #8b5cf6' : '4px solid transparent'
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexGrow: 1 }}>
          <Chevron isOpen={isOpen} />
          <Badge label="Chapter" color="#8b5cf6" bg="#f5f3ff" />
          <span style={{ fontSize: '15px', fontWeight: 500, color: '#374151' }}>{name}</span>
        </div>

        <FilterBtn active={isActive} onClick={handleFilter} />
      </div>

      {isOpen && (
        <div style={{ backgroundColor: '#fff' }}>
          {sections.map((secName, index) => (
            <SectionRow 
              key={index} 
              name={secName} 
              volumeName={volumeName}
              chapterName={name}
              selectedFilter={selectedFilter}
              onFilterChange={onFilterChange}
              onLinkChange={onLinkChange}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// --- Level 3: Section ---
const SectionRow: React.FC<{ 
  name: string; 
  volumeName: string;
  chapterName: string;
  selectedFilter: HRSFilter;
  onFilterChange: (f: HRSFilter) => void;
  onLinkChange: (f: HRSFilter) => void;
}> = ({ name, volumeName, chapterName, selectedFilter, onFilterChange, onLinkChange }) => {
  
  const thisFilter: HRSFilter = { volume: volumeName, chapter: chapterName, section: name };
  const isActive = isSameFilter(selectedFilter, thisFilter);

  const handleFilter = () => {
    onFilterChange(isActive ? {} : thisFilter);
  };

  const handleLink = () => {
    onLinkChange(thisFilter)
  }

  return (
    <div style={{ 
      padding: '10px 16px 10px 60px', 
      display: 'flex', alignItems: 'right', 
      borderBottom: '1px dashed #f3f4f6',
      backgroundColor: isActive ? '#ecfdf5' : 'transparent',
      borderLeft: isActive ? '4px solid #059669' : '4px solid transparent'
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexGrow: 1 }}>
        <Badge label="Section" color="#059669" bg="#ecfdf5" />
        <span style={{ fontSize: '14px', color: '#4b5563', fontWeight: 500 }}>{name}</span>
      </div>

      <LinkToBtn onClick={handleLink} />
      <FilterBtn active={isActive} onClick={handleFilter} />
    </div>
  );
};



const FilterIcon = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="22 3 2 3 10 12.46 10 19 14 21 14 12.46 22 3"></polygon>
  </svg>
);

const LinkIcon = () => (
  <svg 
    width="14" 
    height="14" 
    viewBox="0 0 24 24" 
    fill="none" 
    stroke="currentColor" 
    strokeWidth="2" 
    strokeLinecap="round" 
    strokeLinejoin="round"
  >
    <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path>
    <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path>
  </svg>
);

const Chevron = ({ isOpen }: { isOpen: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}>
    <polyline points="6 9 12 15 18 9"></polyline>
  </svg>
);

const Badge: React.FC<{ label: string, color: string, bg: string }> = ({ label, color, bg }) => (
  <span style={{ 
    fontSize: '10px', textTransform: 'uppercase', color, backgroundColor: bg, 
    fontWeight: 700, letterSpacing: '0.05em', padding: '2px 6px', borderRadius: '4px', flexShrink: 0 
  }}>
    {label}
  </span>
);

const FilterBtn: React.FC<{ active: boolean, onClick: (e: React.MouseEvent) => void }> = ({ active, onClick }) => {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation(); 
    onClick(e);
  };

  return (
    <button 
      onClick={handleClick}
      style={{
        background: active ? '#2563eb' : 'white',
        color: active ? 'white' : '#9ca3af',
        border: active ? '1px solid #2563eb' : '1px solid #e5e7eb',
        cursor: 'pointer',
        padding: '6px',
        borderRadius: '4px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        transition: 'all 0.2s',
        boxShadow: active ? '0 2px 4px rgba(37, 99, 235, 0.2)' : 'none',
        marginRight: "5px"
      }}
      title={active ? "Clear Filter" : "Filter"}
    >
      <FilterIcon />
    </button>
  );
};


const LinkToBtn: React.FC<{ onClick: (e: React.MouseEvent) => void }> = ({ onClick }) => {
  const handleClick = (e: React.MouseEvent) => {
    e.stopPropagation(); 
    onClick(e);
  };

  return (
    <button 
      onClick={handleClick}
      style={{
        background: 'white',
        color: '#9ca3af',
        border: '1px solid #e5e7eb',
        cursor: 'pointer',
        padding: '6px',
        borderRadius: '4px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        marginRight: "5px"
      }}
      title="Go to section"
    >
      <LinkIcon />
    </button>
  );
};