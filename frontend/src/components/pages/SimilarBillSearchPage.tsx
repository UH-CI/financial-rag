import React from 'react';
import AppHeader from '../layout/AppHeader';
import SimilarBillSearch from '../features/documents/SimilarBillSearch';

const SimilarBillSearchPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-100">
      <AppHeader />
      <SimilarBillSearch />
    </div>
  );
};

export default SimilarBillSearchPage;
