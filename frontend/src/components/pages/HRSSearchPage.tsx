import React from 'react';
import AppHeader from '../layout/AppHeader';
import HRSSearch from '../features/hrs/HRSSearch';

const HRSSearchPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-gray-100">
      <AppHeader />
      <HRSSearch />
    </div>
  );
};

export default HRSSearchPage;
