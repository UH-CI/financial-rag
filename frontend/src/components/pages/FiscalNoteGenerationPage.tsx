import React from 'react';
import AppHeader from '../layout/AppHeader';
import FiscalNoteGeneration from '../features/fiscal-notes/FiscalNoteGeneration';

const FiscalNoteGenerationPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-100">
      <AppHeader />
      <FiscalNoteGeneration />
    </div>
  );
};

export default FiscalNoteGenerationPage;
