import axios from 'axios';
import { useAuth0 } from '@auth0/auth0-react';

// API configuration for user permissions
let API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8200';
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
        // Try to get access token with email scope
        let token;
        try {
          token = await (getAccessTokenSilently as any)({
            authorizationParams: {
              audience: import.meta.env.VITE_AUTH0_AUDIENCE || 'https://api.financial-rag.com',
              scope: 'openid profile email',
            },
          });
        } catch (error) {
          console.warn('Failed to get token with email scope, trying without:', error);
          // Fallback: get token without specific scope
          token = await getAccessTokenSilently();
        }
        config.headers.Authorization = `Bearer ${token}`;
        console.log('🔐 Added auth token to request:', config.url);
      } catch (error) {
        console.error('❌ Failed to get access token:', error);
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

    async createUser(userData: { email: string; display_name: string; is_admin: boolean }): Promise<UserProfile> {
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
    }
  };
};

// Hook for using authenticated API
export const useAuthenticatedApi = () => {
  const { getAccessTokenSilently } = useAuth0();
  return createUserApi(getAccessTokenSilently);
};
