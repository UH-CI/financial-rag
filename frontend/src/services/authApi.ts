import axios from 'axios';
import { useAuth0 } from '@auth0/auth0-react';

// API configuration for user permissions
let API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'https://finbot.its.hawaii.edu/api';
if (window.location.hostname === 'localhost') {
  API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8200';
}

console.log('🔧 API Base URL configured as:', API_BASE_URL);

// Create authenticated API client
export const createAuthenticatedApi = (getAccessTokenSilently: () => Promise<string>) => {
  const authApi = axios.create({
    baseURL: API_BASE_URL,
    timeout: 30000,
    headers: {
      'Content-Type': 'application/json',
    },
  });

  // Add authentication interceptor
  authApi.interceptors.request.use(
    async (config) => {
      try {
        // Retry logic for token retrieval
        let token = null;
        const maxRetries = 3;

        for (let attempt = 1; attempt <= maxRetries; attempt++) {
          try {
            console.log(`🔄 Requesting fresh token from Auth0 (attempt ${attempt}/${maxRetries})...`);

            token = await getAccessTokenSilently();

            // Log token characteristics for debugging
            console.log('✅ Token received from Auth0:', {
              attempt,
              length: token.length,
              preview: token.substring(0, 20) + '...' + token.substring(token.length - 10),
              startsWithEyJ: token.startsWith('eyJ'),
              hasThreeParts: token.split('.').length === 3
            });

            break; // Success, exit retry loop

          } catch (tokenError) {
            console.warn(`⚠️ Token retrieval attempt ${attempt} failed:`, tokenError);

            if (attempt === maxRetries) {
              throw tokenError; // Re-throw on final attempt
            }

            // Wait before retry (exponential backoff)
            await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
          }
        }

        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
          console.log('🔐 Added auth token to request:', config.url);
        } else {
          throw new Error('Failed to obtain token after all retry attempts');
        }
      } catch (error) {
        console.error('❌ Failed to get access token after retries:', error);
        // Don't throw here - let the request proceed and fail with proper 401
      }
      return config;
    },
    (error) => {
      console.error('❌ Request interceptor error:', error);
      return Promise.reject(error);
    }
  );

  return authApi;
};

// Types for user management
export interface UserProfile {
  id: number;
  auth0_user_id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  is_admin: boolean;
  is_super_admin?: boolean;
  created_at: string;
  updated_at: string;
}

export interface UserPermissionInfo {
  name: string;
  description: string;
  category: string;
  granted_at: string;
}

export interface UserProfileWithPermissions {
  user: UserProfile;
  permissions: UserPermissionInfo[];
}

export interface PermissionSummary {
  id: number;
  name: string;
  description: string;
  category: string;
  created_at: string;
  user_count: number;
}

// User management API functions
export const createUserApi = (getAccessTokenSilently: () => Promise<string>) => {
  const authApi = createAuthenticatedApi(getAccessTokenSilently);

  return {
    // User endpoints
    async getUserProfile(): Promise<UserProfileWithPermissions> {
      const response = await authApi.get('/api/users/profile');
      return response.data;
    },

    async updateUserProfile(displayName: string): Promise<UserProfile> {
      const response = await authApi.put('/api/users/profile', {
        display_name: displayName
      });
      return response.data;
    },

    async getUserPermissions(): Promise<string[]> {
      const response = await authApi.get('/api/users/permissions');
      return response.data;
    },

    async syncUser(): Promise<{ message: string; user_id: number; email: string }> {
      const response = await authApi.post('/api/users/sync');
      return response.data;
    },

    // Admin endpoints
    async getAllUsers(skip = 0, limit = 100, activeOnly = true): Promise<UserProfile[]> {
      const response = await authApi.get('/api/admin/users', {
        params: { skip, limit, active_only: activeOnly }
      });
      return response.data;
    },

    async createUser(userData: { email: string; display_name: string; is_admin: boolean; is_super_admin?: boolean }): Promise<UserProfile> {
      const response = await authApi.post('/api/admin/users', userData);
      return response.data;
    },

    async updateUserPermissions(userId: string, permissions: string[]): Promise<{ message: string; user_id: number }> {
      const response = await authApi.put(`/api/admin/users/${userId}/permissions`, {
        permission_names: permissions
      });
      return response.data;
    },

    async getUserDetail(userId: number): Promise<{ user: UserProfile; permissions: UserPermissionInfo[] }> {
      const response = await authApi.get(`/api/admin/users/${userId}`);
      return response.data;
    },

    async updateUser(userId: number, data: { display_name?: string; is_active?: boolean }): Promise<UserProfile> {
      const response = await authApi.put(`/api/admin/users/${userId}`, data);
      return response.data;
    },

    async deleteUser(userId: number): Promise<{ message: string; user_email: string; local_deletion_success: boolean; auth0_deletion_success: boolean; auth0_error?: string }> {
      const response = await authApi.delete(`/api/admin/users/${userId}`);
      return response.data;
    },

    async grantPermission(userId: number, permissionId: number): Promise<{ message: string }> {
      const response = await authApi.post(`/api/admin/users/${userId}/permissions/${permissionId}`);
      return response.data;
    },

    async revokePermission(userId: number, permissionId: number): Promise<{ message: string }> {
      const response = await authApi.delete(`/api/admin/users/${userId}/permissions/${permissionId}`);
      return response.data;
    },

    async getAllPermissions(): Promise<PermissionSummary[]> {
      const response = await authApi.get('/api/admin/permissions');
      return response.data;
    },

    async getAuditLog(skip = 0, limit = 100, action?: string): Promise<any[]> {
      const response = await authApi.get('/api/admin/audit-log', {
        params: { skip, limit, action }
      });
      return response.data;
    },

    // Protected tools
    async accessFiscalNoteGeneration(data: any): Promise<any> {
      const response = await authApi.post('/api/tools/fiscal-note-generation', data);
      return response.data;
    },

    async accessSimilarBillSearch(data: any): Promise<any> {
      const response = await authApi.post('/api/tools/similar-bill-search', data);
      return response.data;
    },

    async accessHrsSearch(data: any): Promise<any> {
      const response = await authApi.post('/api/tools/hrs-search', data);
      return response.data;
    },

    async toolsHealthCheck(): Promise<{ status: string; user: string; permissions: string }> {
      const response = await authApi.get('/api/tools/health');
      return response.data;
    },

    // Email verification methods
    async resendVerificationEmail(email: string): Promise<{ message: string; success: boolean }> {
      const response = await authApi.post('/api/auth/resend-verification', { email });
      return response.data;
    },

    async checkVerificationStatus(): Promise<{ email_verified: boolean }> {
      const response = await authApi.get('/api/auth/check-verification-status');
      return response.data;
    }
  };
};

// Hook for using authenticated API
export const useAuthenticatedApi = () => {
  const { getAccessTokenSilently } = useAuth0();

  // Create wrapper function that handles the Auth0 parameters
  const getTokenWrapper = async () => {
    try {
      return await getAccessTokenSilently({
        authorizationParams: {
          audience: 'https://api.financial-rag.com',
          scope: 'openid profile email offline_access' // Included offline_access for refresh tokens
        }
      });
    } catch (error: any) {
      console.error('🔴 Auth0 token error:', error);

      // If refresh token fails, try to get a new token by redirecting
      if (error.message?.includes('Missing Refresh Token') || error.message?.includes('refresh_token')) {
        console.log('🔄 Refresh token failed, clearing Auth0 cache and retrying...');

        // Clear Auth0 cache and try again with different cache mode
        try {
          return await getAccessTokenSilently({
            authorizationParams: {
              audience: 'https://api.financial-rag.com',
              scope: 'openid profile email offline_access'
            },
            cacheMode: 'cache-only' // Try cache-only mode first
          });
        } catch (retryError) {
          console.error('🔴 Retry failed, user needs to re-authenticate');
          throw new Error('Authentication session expired. Please log out and log back in.');
        }
      }

      throw error;
    }
  };

  return createUserApi(getTokenWrapper);
};
