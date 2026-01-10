import React from 'react';

interface ChangeTypeBadgeProps {
  type: 'new' | 'continued' | 'modified' | 'no_change';
}

const ChangeTypeBadge: React.FC<ChangeTypeBadgeProps> = ({ type }) => {
  const styles = {
    new: 'bg-blue-100 text-blue-700 border-blue-200',
    continued: 'bg-green-100 text-green-700 border-green-200',
    modified: 'bg-yellow-100 text-yellow-700 border-yellow-200',
    no_change: 'bg-gray-100 text-gray-700 border-gray-200',
  };
  
  const icons = {
    new: '🆕',
    continued: '✓',
    modified: '⚡',
    no_change: '📌',
  };
  
  const labels = {
    new: 'New',
    continued: 'Continued',
    modified: 'Modified',
    no_change: 'Carried',
  };
  
  return (
    <span 
      className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${styles[type]}`}
      title={labels[type]}
    >
      <span className="mr-1">{icons[type]}</span>
      {labels[type]}
    </span>
  );
};

export default ChangeTypeBadge;
