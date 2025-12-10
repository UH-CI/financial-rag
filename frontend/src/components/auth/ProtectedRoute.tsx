import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuth } from '../../contexts/BackendAuthContext';
import { Lock, Loader2 } from 'lucide-react';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredPermission?: keyof NonNullable<ReturnType<typeof useAuth>['userProfile']>['permissions'];
  adminOnly?: boolean;
  skipEmailVerification?: boolean; // Allow access even if email is not verified
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ 
  children, 
  requiredPermission,
  adminOnly = false,
  skipEmailVerification = false
}) => {
  const { currentUser, userProfile, loading, emailVerificationRequired } = useAuth();

  // Show loading spinner while authentication state is being determined
  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 text-blue-600 animate-spin mx-auto mb-4" />
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!currentUser) {
    return <Navigate to="/login" replace />;
  }

  // Handle email verification requirement (unless we're skipping it for this route)
  if (!skipEmailVerification && emailVerificationRequired) {
    return <Navigate to="/verify-email" replace />;
  }

  // If we don't have a user profile and we're not skipping email verification, redirect to login
  if (!skipEmailVerification && !userProfile) {
    return <Navigate to="/login" replace />;
  }

  // Check admin permission (only if we have a user profile)
  if (adminOnly && userProfile && !userProfile.isAdmin) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <Lock className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Access Denied</h1>
          <p className="text-gray-600 mb-6">
            You don't have administrator privileges to access this page.
          </p>
          <button
            onClick={() => window.history.back()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  // Check specific permission (only if we have a user profile)
  if (requiredPermission && userProfile && !userProfile.permissions[requiredPermission]) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center max-w-md">
          <Lock className="w-16 h-16 text-orange-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Access Restricted</h1>
          <p className="text-gray-600 mb-6">
            You don't have permission to access this feature. Please contact your administrator 
            to request access.
          </p>
          <button
            onClick={() => window.history.back()}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
};

export default ProtectedRoute;
