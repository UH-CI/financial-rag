import React, { useState } from 'react';
import { LogOut, User, Shield, ChevronDown } from 'lucide-react';
import { useAuth } from '../../contexts/BackendAuthContext';
import { useNavigate } from 'react-router-dom';

const AppHeader: React.FC = () => {
  const { currentUser, userProfile, logout } = useAuth();
  const navigate = useNavigate();
  const [showDropdown, setShowDropdown] = useState(false);

  const handleLogout = async () => {
    try {
      await logout();
    } catch (error) {
      console.error('Logout error:', error);
    }
  };

  const goToAdmin = () => {
    navigate('/admin');
    setShowDropdown(false);
  };

  const goToDashboard = () => {
    navigate('/dashboard');
    setShowDropdown(false);
  };

  if (!currentUser || !userProfile) {
    return null;
  }

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div className="flex items-center justify-between">
          {/* Left side - App title */}
          <div className="flex items-center space-x-3">
            <div className="flex items-center space-x-2">
              <div className="w-2 h-2 bg-green-400 rounded-full" title="System operational"></div>
              <h1 className="text-xl font-semibold text-gray-900">
                Financial RAG System
              </h1>
            </div>
          </div>

          {/* Right side - User menu */}
          <div className="relative">
            <button
              onClick={() => setShowDropdown(!showDropdown)}
              className="flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-gray-50 transition-colors"
            >
              {/* User avatar */}
              <div className="w-8 h-8 bg-blue-600 rounded-full flex items-center justify-center">
                {userProfile.photoURL ? (
                  <img
                    src={userProfile.photoURL}
                    alt={userProfile.displayName}
                    className="w-8 h-8 rounded-full"
                  />
                ) : (
                  <User className="w-4 h-4 text-white" />
                )}
              </div>

              {/* User info */}
              <div className="text-left">
                <div className="flex items-center space-x-1">
                  <span className="text-sm font-medium text-gray-900">
                    {userProfile.displayName}
                  </span>
                  {userProfile.isAdmin && (
                    <Shield className="w-4 h-4 text-blue-600" />
                  )}
                </div>
                <span className="text-xs text-gray-500">{userProfile.email}</span>
              </div>

              <ChevronDown className="w-4 h-4 text-gray-400" />
            </button>

            {/* Dropdown menu */}
            {showDropdown && (
              <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
                <button
                  onClick={goToDashboard}
                  className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
                >
                  <User className="w-4 h-4" />
                  <span>Dashboard</span>
                </button>

                {userProfile.isAdmin && (
                  <button
                    onClick={goToAdmin}
                    className="w-full px-4 py-2 text-left text-sm text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
                  >
                    <Shield className="w-4 h-4" />
                    <span>Admin Panel</span>
                  </button>
                )}

                <hr className="my-1" />

                <button
                  onClick={handleLogout}
                  className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 flex items-center space-x-2"
                >
                  <LogOut className="w-4 h-4" />
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Click outside to close dropdown */}
      {showDropdown && (
        <div
          className="fixed inset-0 z-40"
          onClick={() => setShowDropdown(false)}
        />
      )}
    </header>
  );
};

export default AppHeader;
