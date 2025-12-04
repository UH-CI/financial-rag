import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Auth0Provider, useAuth0 } from '@auth0/auth0-react';
import { AuthProvider } from './contexts/BackendAuthContext';
import { auth0Config } from './config/auth0';
import LoginPage from './components/auth/LoginPage';
import Dashboard from './components/dashboard/Dashboard';
import ProtectedRoute from './components/auth/ProtectedRoute';
import AdminPanel from './components/admin/AdminPanel';
import FiscalNoteGenerationPage from './components/pages/FiscalNoteGenerationPage';
import SimilarBillSearchPage from './components/pages/SimilarBillSearchPage';
import HRSSearchPage from './components/pages/HRSSearchPage';

// Component to handle the root route and Auth0 callback
const RootHandler = () => {
  const { isLoading, isAuthenticated, error } = useAuth0();
  
  // If there's an Auth0 error, redirect to login
  if (error) {
    console.error('Auth0 error:', error);
    return <Navigate to="/login" replace />;
  }
  
  // If Auth0 is still loading/processing, show loading screen
  // This includes initial load, callback processing, and session restoration
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600">Loading...</p>
        </div>
      </div>
    );
  }
  
  // After Auth0 processing is complete, redirect based on auth state
  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  } else {
    return <Navigate to="/login" replace />;
  }
};

function App() {
  return (
    <Auth0Provider
      domain={auth0Config.domain}
      clientId={auth0Config.clientId}
      authorizationParams={auth0Config.authorizationParams}
      cacheLocation={auth0Config.cacheLocation}
      useRefreshTokens={auth0Config.useRefreshTokens}
    >
      <AuthProvider>
        <Router>
          <Routes>
            {/* Public route */}
            <Route path="/login" element={<LoginPage />} />
            
            {/* Protected routes */}
            <Route 
              path="/dashboard" 
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              } 
            />
            
            <Route 
              path="/fiscal-note-generation" 
              element={
                <ProtectedRoute requiredPermission="fiscalNoteGeneration">
                  <FiscalNoteGenerationPage />
                </ProtectedRoute>
              } 
            />
            
            <Route 
              path="/similar-bill-search" 
              element={
                <ProtectedRoute requiredPermission="similarBillSearch">
                  <SimilarBillSearchPage />
                </ProtectedRoute>
              } 
            />
            
            <Route 
              path="/hrs-search" 
              element={
                <ProtectedRoute requiredPermission="hrsSearch">
                  <HRSSearchPage />
                </ProtectedRoute>
              } 
            />
            
            <Route 
              path="/admin" 
              element={
                <ProtectedRoute adminOnly>
                  <AdminPanel />
                </ProtectedRoute>
              } 
            />
            
            {/* Root route - handles Auth0 callback and redirects */}
            <Route path="/" element={<RootHandler />} />
            
            {/* Catch all - redirect to dashboard */}
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </Router>
      </AuthProvider>
    </Auth0Provider>
  );
}

export default App;
