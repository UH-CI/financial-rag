import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Mail, RefreshCw, AlertCircle, CheckCircle, ArrowLeft, LogOut } from 'lucide-react';
import { useAuth0 } from '@auth0/auth0-react';
import { useAuth } from '../../contexts/BackendAuthContext';
import { useAuthenticatedApi } from '../../services/authApi';
import { forceCompleteLogout, safeLogout } from '../../utils/auth0Helper';

const EmailVerificationPage: React.FC = () => {
  const { user, logout } = useAuth0();
  const { checkEmailVerification } = useAuth();
  const authApi = useAuthenticatedApi();
  const navigate = useNavigate();
  const [isResending, setIsResending] = useState(false);
  const [resendStatus, setResendStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const [isChecking, setIsChecking] = useState(false);

  // Check if this is a Google OAuth user (they shouldn't need verification)
  const isGoogleUser = user?.sub?.startsWith('google-oauth2|');

  const handleResendVerification = async () => {
    setIsResending(true);
    setResendStatus('idle');
    
    try {
      if (!user?.email) {
        throw new Error('No email address available');
      }

      console.log('Sending verification email to:', user.email);
      
      // Call our backend API to resend verification email
      const result = await authApi.resendVerificationEmail(user.email);
      console.log('Verification email sent successfully:', result);
      
      if (result.success) {
        setResendStatus('success');
      } else {
        console.error('Failed to send verification email:', result.message);
        setResendStatus('error');
      }
      
    } catch (error) {
      console.error('Failed to resend verification email:', error);
      setResendStatus('error');
    } finally {
      setIsResending(false);
    }
  };

  const handleCheckVerification = async () => {
    setIsChecking(true);
    
    try {
      console.log('🔄 User clicked "I\'ve Verified My Email"');
      
      // Check with backend to see if verification status has changed
      await checkEmailVerification();
      
      // If we get here without error, verification was successful
      console.log('✅ Verification successful, redirecting to dashboard...');
      
      // Small delay to ensure context state updates, then navigate
      setTimeout(() => {
        navigate('/dashboard');
      }, 100);
      
    } catch (error) {
      console.error('❌ Verification check failed:', error);
      
      // Show user-friendly error message
      alert('Email verification not yet complete. Please make sure you clicked the verification link in your email, then try again.');
    } finally {
      setIsChecking(false);
    }
  };

  const handleLogout = () => {
    safeLogout(logout);
  };

  const handleBackToLogin = () => {
    safeLogout(logout);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="max-w-lg w-full bg-white rounded-xl shadow-xl p-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-20 h-20 bg-amber-100 rounded-full flex items-center justify-center mx-auto mb-6">
            <Mail className="w-10 h-10 text-amber-600" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900 mb-3">
            Email Verification Required
          </h1>
          <p className="text-gray-600 text-lg leading-relaxed">
            You have not verified your email address yet. Please verify it to continue using the application.
          </p>
        </div>

        {/* User Email Display */}
        {user?.email && (
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
            <div className="flex items-center">
              <Mail className="w-5 h-5 text-blue-600 mr-3" />
              <div>
                <p className="text-sm font-medium text-blue-900">Verification email sent to:</p>
                <p className="text-blue-700 font-semibold">{user.email}</p>
              </div>
            </div>
          </div>
        )}

        {/* Instructions */}
        <div className="mb-8">
          <h3 className="font-semibold text-gray-900 mb-4 text-lg">How to verify your email:</h3>
          <div className="space-y-3">
            <div className="flex items-start">
              <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-4 mt-0.5">
                <span className="text-blue-600 font-bold text-sm">1</span>
              </div>
              <div>
                <p className="font-medium text-gray-900">Check your email inbox</p>
                <p className="text-gray-600 text-sm">Look for an email from Auth0 or our application</p>
              </div>
            </div>
            
            <div className="flex items-start">
              <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-4 mt-0.5">
                <span className="text-blue-600 font-bold text-sm">2</span>
              </div>
              <div>
                <p className="font-medium text-gray-900">Click the verification link</p>
                <p className="text-gray-600 text-sm">This will confirm your email address with our system</p>
              </div>
            </div>
            
            <div className="flex items-start">
              <div className="w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center mr-4 mt-0.5">
                <span className="text-blue-600 font-bold text-sm">3</span>
              </div>
              <div>
                <p className="font-medium text-gray-900">Return here and continue</p>
                <p className="text-gray-600 text-sm">Click "I've Verified My Email" below to proceed</p>
              </div>
            </div>
          </div>
        </div>

        {/* Status Messages */}
        {isGoogleUser && (
          <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-start">
            <AlertCircle className="w-5 h-5 text-blue-600 mr-3 mt-0.5" />
            <div>
              <p className="font-medium text-blue-800">Google Account Detected</p>
              <p className="text-blue-700 text-sm">
                You signed in with Google, so your email should already be verified. 
                Try clicking "I've Verified My Email" below, or sign out and try again.
              </p>
            </div>
          </div>
        )}

        {resendStatus === 'success' && (
          <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg flex items-start">
            <CheckCircle className="w-5 h-5 text-green-600 mr-3 mt-0.5" />
            <div>
              <p className="font-medium text-green-800">Verification email sent!</p>
              <p className="text-green-700 text-sm">Please check your email inbox and spam folder.</p>
            </div>
          </div>
        )}

        {resendStatus === 'error' && (
          <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg flex items-start">
            <AlertCircle className="w-5 h-5 text-red-600 mr-3 mt-0.5" />
            <div>
              <p className="font-medium text-red-800">Failed to send verification email</p>
              <p className="text-red-700 text-sm">
                Unable to send a new verification email at this time. 
                Please check your original signup email or try again later.
              </p>
            </div>
          </div>
        )}

        {/* Action Buttons */}
        <div className="space-y-4">
          {/* Primary Action - Check Verification */}
          <button
            onClick={handleCheckVerification}
            disabled={isChecking}
            className="w-full flex items-center justify-center px-6 py-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-200 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium text-lg"
          >
            {isChecking ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin mr-3" />
                Checking verification...
              </>
            ) : (
              <>
                <CheckCircle className="w-5 h-5 mr-3" />
                I've Verified My Email
              </>
            )}
          </button>

          {/* Secondary Action - Resend Email */}
          <button
            onClick={handleResendVerification}
            disabled={isResending}
            className="w-full flex items-center justify-center px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 hover:border-gray-400 focus:outline-none focus:ring-4 focus:ring-gray-200 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {isResending ? (
              <>
                <RefreshCw className="w-5 h-5 animate-spin mr-3" />
                Sending...
              </>
            ) : (
              <>
                <Mail className="w-5 h-5 mr-3" />
                Send New Verification Email
              </>
            )}
          </button>

          {/* Tertiary Actions */}
          <div className="flex space-x-3">
            <button
              onClick={handleBackToLogin}
              className="flex-1 flex items-center justify-center px-4 py-3 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors font-medium"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Login
            </button>
            
            <button
              onClick={handleLogout}
              className="flex-1 flex items-center justify-center px-4 py-3 text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-lg transition-colors font-medium"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Sign Out
            </button>
          </div>

          {/* Alternative logout option */}
          <div className="mt-4 text-center">
            <button
              onClick={forceCompleteLogout}
              className="text-sm text-blue-600 hover:text-blue-800 underline"
            >
              Having logout issues? Click here to force logout
            </button>
          </div>
        </div>

        {/* Help Section */}
        <div className="mt-8 pt-6 border-t border-gray-200">
          <div className="text-center">
            <p className="text-sm text-gray-500 mb-2">
              <strong>Didn't receive the email?</strong>
            </p>
            <p className="text-xs text-gray-400 leading-relaxed">
              Check your spam folder, or try sending a new verification email. 
              If you continue having issues, please contact support.
            </p>
          </div>
        </div>

        {/* Footer */}
        <div className="mt-6 pt-4 border-t border-gray-100">
          <p className="text-xs text-gray-400 text-center">
            © 2025 Research Cyberinfrastructure, University of Hawai'i System. All rights reserved.
          </p>
        </div>
      </div>
    </div>
  );
};

export default EmailVerificationPage;
