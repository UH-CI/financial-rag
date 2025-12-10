import React, { createContext, useContext, useEffect, useState } from 'react';
import { useAuth0, User } from '@auth0/auth0-react';
import { useAuthenticatedApi, type UserProfileWithPermissions } from '../services/authApi';

export interface UserProfile {
  uid: string;
  email: string;
  displayName: string;
  photoURL?: string;
  isAdmin: boolean;
  isSuperAdmin: boolean;
  permissions: {
    fiscalNoteGeneration: boolean;
    similarBillSearch: boolean;
    hrsSearch: boolean;
    adminPanel: boolean;
    userManagement: boolean;
    auditLogView: boolean;
  };
  createdAt: Date;
  lastLoginAt: Date;
}

interface AuthContextType {
  currentUser: User | null;
  userProfile: UserProfile | null;
  loading: boolean;
  emailVerificationRequired: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signUpWithEmail: (email: string, password: string, name: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUserProfile: () => Promise<void>;
  getAllUsers: () => Promise<UserProfile[]>;
  updateUserPermissions: (userId: string, permissions: UserProfile['permissions']) => Promise<void>;
  createManualUser: (userData: { email: string; displayName: string; isAdmin: boolean }) => Promise<UserProfile>;
  // New backend methods
  hasPermission: (permission: string) => boolean;
  syncWithBackend: () => Promise<void>;
  checkEmailVerification: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

// Map backend permissions to frontend format
const mapBackendPermissions = (backendPermissions: string[]) => ({
  fiscalNoteGeneration: backendPermissions.includes('fiscal-note-generation'),
  similarBillSearch: backendPermissions.includes('similar-bill-search'),
  hrsSearch: backendPermissions.includes('hrs-search'),
  adminPanel: backendPermissions.includes('admin-panel'),
  userManagement: backendPermissions.includes('user-management'),
  auditLogView: backendPermissions.includes('audit-log-view'),
});

// Convert backend user profile to frontend format
const convertBackendProfile = (backendProfile: UserProfileWithPermissions): UserProfile => {
  const permissionNames = backendProfile.permissions.map(p => p.name);
  
  return {
    uid: backendProfile.user.auth0_user_id,
    email: backendProfile.user.email,
    displayName: backendProfile.user.display_name || backendProfile.user.email,
    isAdmin: backendProfile.user.is_admin,
    isSuperAdmin: backendProfile.user.is_super_admin || false,
    permissions: mapBackendPermissions(permissionNames),
    createdAt: new Date(backendProfile.user.created_at),
    lastLoginAt: new Date(backendProfile.user.updated_at),
  };
};

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // 🚀 DEVELOPMENT MODE - Hardcoded fake user data
  const isDevelopment = false;
  
  if (isDevelopment) {
    const mockUser: User = {
      sub: 'dev-user-123',
      email: 'dev@hawaii.edu',
      name: 'Development User',
      picture: 'https://via.placeholder.com/150'
    };

    const mockUserProfile: UserProfile = {
      uid: 'dev-user-123',
      email: 'dev@hawaii.edu',
      displayName: 'Development User',
      photoURL: 'https://via.placeholder.com/150',
      isAdmin: true,
      isSuperAdmin: true,
      permissions: {
        fiscalNoteGeneration: true,
        similarBillSearch: true,
        hrsSearch: true,
        adminPanel: true,
        userManagement: true,
        auditLogView: true,
      },
      createdAt: new Date(),
      lastLoginAt: new Date(),
    };

    const mockAuthContext: AuthContextType = {
      currentUser: mockUser,
      userProfile: mockUserProfile,
      loading: false,
      emailVerificationRequired: false,
      signInWithGoogle: async () => console.log('🚀 Mock Google sign in'),
      signInWithEmail: async () => console.log('🚀 Mock email sign in'),
      signUpWithEmail: async () => console.log('🚀 Mock email sign up'),
      logout: async () => console.log('🚀 Mock logout'),
      refreshUserProfile: async () => console.log('🚀 Mock refresh profile'),
      getAllUsers: async () => [mockUserProfile],
      updateUserPermissions: async () => console.log('🚀 Mock update permissions'),
      createManualUser: async () => mockUserProfile,
      hasPermission: () => true,
      syncWithBackend: async () => console.log('🚀 Mock sync with backend'),
      checkEmailVerification: async () => console.log('🚀 Mock check email verification'),
    };

    return (
      <AuthContext.Provider value={mockAuthContext}>
        {children}
      </AuthContext.Provider>
    );
  }

  const { 
    user, 
    isAuthenticated, 
    isLoading, 
    loginWithRedirect,
    logout: auth0Logout
  } = useAuth0();
  
  const [userProfile, setUserProfile] = useState<UserProfile | null>(null);
  const [contextLoading, setContextLoading] = useState(true);
  const [emailVerificationRequired, setEmailVerificationRequired] = useState(false);
  const [syncInProgress, setSyncInProgress] = useState(false);
  const authApi = useAuthenticatedApi();

  // Sync user profile from backend
  const syncWithBackend = async () => {
    if (!isAuthenticated || !user || syncInProgress) return;

    setSyncInProgress(true);
    try {
      console.log('🔄 Syncing user profile from backend...');
      
      // Get full profile with permissions (this also syncs the user)
      const backendProfile = await authApi.getUserProfile();
      const frontendProfile = convertBackendProfile(backendProfile);
      
      setUserProfile(frontendProfile);
      console.log('✅ User profile synced successfully:', frontendProfile.email);
      
    } catch (error: any) {
      console.error('❌ Failed to sync user profile:', error);
      
      // Check if this is an email verification error
      if (error?.response?.status === 403 && 
          error?.response?.data?.detail?.includes('Email verification required')) {
        console.log('📧 Email verification required');
        setEmailVerificationRequired(true);
        setUserProfile(null);
        return; // Don't throw error, just set the state
      }
      
      // Fallback to basic profile if backend sync fails for other reasons
      const fallbackProfile: UserProfile = {
        uid: user.sub || '',
        email: user.email || '',
        displayName: user.name || user.email || '',
        photoURL: user.picture,
        isAdmin: user.email === 'tabalbar@hawaii.edu',
        isSuperAdmin: user.email === 'tabalbar@hawaii.edu',
        permissions: {
          fiscalNoteGeneration: user.email === 'tabalbar@hawaii.edu',
          similarBillSearch: user.email === 'tabalbar@hawaii.edu',
          hrsSearch: user.email === 'tabalbar@hawaii.edu',
          adminPanel: user.email === 'tabalbar@hawaii.edu',
          userManagement: user.email === 'tabalbar@hawaii.edu',
          auditLogView: user.email === 'tabalbar@hawaii.edu',
        },
        createdAt: new Date(),
        lastLoginAt: new Date(),
      };
      
      setUserProfile(fallbackProfile);
    } finally {
      setSyncInProgress(false);
    }
  };

  // Initialize user profile when authenticated
  useEffect(() => {
    const initializeProfile = async () => {
      setContextLoading(true);
      
      if (isAuthenticated && user) {
        await syncWithBackend();
      } else {
        setUserProfile(null);
      }
      
      setContextLoading(false);
    };

    if (!isLoading) {
      initializeProfile();
    }
  }, [isAuthenticated, user, isLoading]);

  // Check if user has specific permission
  const hasPermission = (permission: string): boolean => {
    if (!userProfile) return false;
    if (userProfile.isSuperAdmin) return true; // Super admins have all permissions
    if (userProfile.isAdmin) return true; // Regular admins have all permissions
    
    const permissionMap: { [key: string]: keyof UserProfile['permissions'] } = {
      'fiscal-note-generation': 'fiscalNoteGeneration',
      'similar-bill-search': 'similarBillSearch',
      'hrs-search': 'hrsSearch',
      'admin-panel': 'adminPanel',
      'user-management': 'userManagement',
      'audit-log-view': 'auditLogView',
    };
    
    const frontendPermission = permissionMap[permission];
    return frontendPermission ? userProfile.permissions[frontendPermission] : false;
  };

  const refreshUserProfile = async () => {
    await syncWithBackend();
  };

  const signInWithGoogle = async () => {
    await loginWithRedirect({
      authorizationParams: {
        connection: 'google-oauth2'
      }
    });
  };

  const signInWithEmail = async (_email: string, _password: string) => {
    // Auth0 handles this through loginWithRedirect with database connection
    // Note: This will show Auth0's login page for email/password authentication
    await loginWithRedirect({
      authorizationParams: {
        connection: 'Username-Password-Authentication',
        login_hint: _email // Pre-fill the email field
      }
    });
  };

  const signUpWithEmail = async (_email: string, _password: string, _name: string) => {
    // Auth0 handles this through loginWithRedirect with database connection
    // Note: This will show Auth0's signup page
    await loginWithRedirect({
      authorizationParams: {
        connection: 'Username-Password-Authentication',
        screen_hint: 'signup',
        login_hint: _email // Pre-fill the email field
      }
    });
  };

  const logout = async () => {
    setUserProfile(null);
    await auth0Logout({ logoutParams: { returnTo: window.location.origin } });
  };

  // Admin functions (these would need backend integration)
  const getAllUsers = async (): Promise<UserProfile[]> => {
    try {
      const backendUsers = await authApi.getAllUsers();
      // Convert backend users to frontend format
      // This is simplified - you'd need to get permissions for each user
      return backendUsers.map(user => ({
        uid: user.auth0_user_id,
        email: user.email,
        displayName: user.display_name || user.email,
        isAdmin: user.is_admin,
        isSuperAdmin: user.is_super_admin || false,
        permissions: {
          fiscalNoteGeneration: false, // Would need to fetch actual permissions
          similarBillSearch: false,
          hrsSearch: false,
          adminPanel: user.is_admin,
          userManagement: user.is_admin,
          auditLogView: user.is_admin,
        },
        createdAt: new Date(user.created_at),
        lastLoginAt: new Date(user.updated_at),
      }));
    } catch (error) {
      console.error('Failed to get all users:', error);
      return [];
    }
  };

  const updateUserPermissions = async (_userId: string, _permissions: UserProfile['permissions']): Promise<void> => {
    // This would need to be implemented with backend API calls
    console.log('Update user permissions not yet implemented for backend');
  };

  const createManualUser = async (_userData: { email: string; displayName: string; isAdmin: boolean }): Promise<UserProfile> => {
    // This would need backend implementation
    throw new Error('Manual user creation not implemented for backend');
  };

  const checkEmailVerification = async () => {
    if (syncInProgress) return;
    
    try {
      console.log('🔄 Checking email verification status...');
      
      // Call the backend verification check endpoint
      const verificationStatus = await authApi.checkVerificationStatus();
      
      if (verificationStatus.email_verified) {
        console.log('✅ Email verification confirmed by backend');
        setEmailVerificationRequired(false);
        // Refresh the user profile to get updated verification status
        await syncWithBackend();
      } else {
        console.log('📧 Email still not verified according to backend');
        setEmailVerificationRequired(true);
      }
      
    } catch (error: any) {
      console.error('❌ Email verification check failed:', error);
      
      // If the backend call fails, try syncing with backend as fallback
      try {
        await syncWithBackend();
        // If sync succeeds, verification was successful
        console.log('✅ Email verification check passed via sync');
        setEmailVerificationRequired(false);
      } catch (syncError: any) {
        if (syncError?.response?.status === 403) {
          console.log('📧 Email still not verified (403 from backend)');
          setEmailVerificationRequired(true);
        } else {
          console.error('Unexpected error during verification check:', syncError);
        }
      }
    }
  };

  const value: AuthContextType = {
    currentUser: user || null,
    userProfile,
    loading: isLoading || contextLoading,
    emailVerificationRequired,
    signInWithGoogle,
    signInWithEmail,
    signUpWithEmail,
    logout,
    refreshUserProfile,
    getAllUsers,
    updateUserPermissions,
    createManualUser,
    hasPermission,
    syncWithBackend,
    checkEmailVerification,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};
