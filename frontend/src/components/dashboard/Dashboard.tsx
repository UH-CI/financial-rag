import React from 'react';
import { FileText, Search, BookOpen, Lock, Bot } from 'lucide-react';
import { useAuth } from '../../contexts/BackendAuthContext';
import { useNavigate } from 'react-router-dom';
import AppHeader from '../layout/AppHeader';

interface DashboardCardProps {
  title: string;
  description: string;
  icon: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
  locked?: boolean;
}

const DashboardCard: React.FC<DashboardCardProps> = ({
  title,
  description,
  icon,
  onClick,
  disabled = false,
  locked = false,
}) => {
  return (
    <button
      onClick={onClick}
      disabled={disabled || locked}
      className={`
        relative p-6 rounded-xl border-2 transition-all duration-200 text-left w-full h-48
        ${locked
          ? 'border-gray-200 bg-gray-50 cursor-not-allowed'
          : disabled
            ? 'border-gray-200 bg-gray-50 cursor-not-allowed'
            : 'border-gray-200 bg-white hover:border-blue-300 hover:shadow-lg hover:scale-105 cursor-pointer'
        }
      `}
    >
      {locked && (
        <div className="absolute top-3 right-3">
          <Lock className="w-5 h-5 text-gray-400" />
        </div>
      )}

      <div className={`mb-4 ${locked ? 'text-gray-400' : 'text-blue-600'}`}>
        {icon}
      </div>

      <h3 className={`text-lg font-semibold mb-2 ${locked ? 'text-gray-400' : 'text-gray-900'}`}>
        {title}
      </h3>

      <p className={`text-sm ${locked ? 'text-gray-400' : 'text-gray-600'}`}>
        {locked ? 'Access restricted - Contact administrator' : description}
      </p>
    </button>
  );
};

const Dashboard: React.FC = () => {
  const { userProfile } = useAuth();
  const navigate = useNavigate();

  if (!userProfile) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <p className="text-gray-600">Loading user profile...</p>
        </div>
      </div>
    );
  }

  const allDashboardItems = [
    {
      id: 'fiscal-note-generation',
      title: 'Fiscal Note Generation',
      description: 'Generate comprehensive fiscal notes for legislative bills and budget proposals.',
      icon: <FileText className="w-8 h-8" />,
      permission: userProfile.permissions.fiscalNoteGeneration,
      route: '/fiscal-note-generation',
    },
    {
      id: 'similar-bill-search',
      title: 'Similar Bill Search',
      description: 'Find and analyze bills similar to a specific piece of legislation using advanced algorithms.',
      icon: <Search className="w-8 h-8" />,
      permission: userProfile.permissions.similarBillSearch,
      route: '/similar-bill-search',
    },
    {
      id: 'hrs-search',
      title: 'HRS Search',
      description: 'Search and explore the Hawaii Revised Statutes database for legal references.',
      icon: <BookOpen className="w-8 h-8" />,
      permission: userProfile.permissions.hrsSearch,
      route: '/hrs-search',
    },
    {
      id: 'refbot',
      title: 'Automatic Committee Referral',
      description: 'Upload a collection of bill documents to be automatically referred to committees.',
      icon: <Bot className="w-8 h-8" />,
      permission: userProfile.permissions.refBot,
      route: '/refbot',
    },
  ];

  // Filter to only show tools the user has permission for
  const availableTools = allDashboardItems.filter(item => item.permission);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with logout button */}
      <AppHeader />

      {/* Welcome section */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="text-center">
            <h1 className="text-2xl font-bold text-gray-900">
              Welcome back, {userProfile.displayName}
            </h1>
            <p className="text-gray-600 mt-1">
              Select a tool to begin your budget analysis
            </p>
          </div>
        </div>
      </div>

      {/* Dashboard Grid */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {availableTools.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {availableTools.map((item) => (
              <DashboardCard
                key={item.id}
                title={item.title}
                description={item.description}
                icon={item.icon}
                onClick={() => navigate(item.route)}
                locked={false}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-12">
            <div className="bg-white rounded-lg shadow p-8 max-w-md mx-auto">
              <Lock className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-semibold text-gray-900 mb-2">No Tools Available</h3>
              <p className="text-gray-600">
                Please contact your administrator to get access to the tools.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Dashboard;
