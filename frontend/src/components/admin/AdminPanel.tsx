import React, { useState, useEffect } from 'react';
import { Users, Plus, Settings, Shield, Trash2, Edit, Check, X, RefreshCw } from 'lucide-react';
import { useAuth } from '../../contexts/BackendAuthContext';
import { type UserProfile } from '../../contexts/BackendAuthContext';
import { useAuthenticatedApi } from '../../services/authApi';
import AppHeader from '../layout/AppHeader';
import AddUserModal from './AddUserModal';

interface EditingUser {
  uid: string;
  permissions: {
    fiscalNoteGeneration: boolean;
    similarBillSearch: boolean;
    hrsSearch: boolean;
    adminPanel: boolean;
    userManagement: boolean;
    auditLogView: boolean;
  };
}

const AdminPanel: React.FC = () => {
  const { userProfile } = useAuth();
  const authApi = useAuthenticatedApi();
  const [users, setUsers] = useState<UserProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingUser, setEditingUser] = useState<EditingUser | null>(null);
  const [showAddUserModal, setShowAddUserModal] = useState(false);

  useEffect(() => {
    loadUsers();
  }, []);

  // Also refresh when the component becomes visible (e.g., navigating to admin panel)
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        loadUsers();
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // Convert backend user format to frontend format
  const convertBackendUser = (backendUser: any): UserProfile => {
    // Convert backend permission names to frontend permissions
    const permissions = backendUser.permissions || [];
    
    return {
      uid: backendUser.id.toString(),
      email: backendUser.email,
      displayName: backendUser.display_name,
      isAdmin: backendUser.is_admin,
      permissions: {
        fiscalNoteGeneration: permissions.includes('fiscal-note-generation'),
        similarBillSearch: permissions.includes('similar-bill-search'),
        hrsSearch: permissions.includes('hrs-search'),
        adminPanel: permissions.includes('admin-panel'),
        userManagement: permissions.includes('user-management'),
        auditLogView: permissions.includes('audit-log-view'),
      },
      createdAt: new Date(backendUser.created_at),
      lastLoginAt: new Date(backendUser.updated_at),
    };
  };

  const loadUsers = async () => {
    try {
      // Get all users from the backend API
      const backendUsers = await authApi.getAllUsers();
      const convertedUsers = backendUsers.map(convertBackendUser);
      
      // Merge with any locally added users that might not be in backend yet
      const localUsers = users.filter(user => user.uid.startsWith('temp_'));
      const allUsers = [...convertedUsers, ...localUsers];
      
      setUsers(allUsers);
      console.log('✅ Loaded users from backend:', convertedUsers.length, 'backend +', localUsers.length, 'local');
    } catch (error) {
      console.error('❌ Error loading users from backend:', error);
      
      // If backend is not available, keep existing users (including locally added ones)
      if (users.length === 0) {
        // Only show error if we have no users at all
        console.log('⚠️ Backend not available, starting with empty user list');
      } else {
        console.log('⚠️ Backend not available, keeping existing users:', users.length);
      }
    } finally {
      setLoading(false);
    }
  };

  const handleEditPermissions = (user: UserProfile) => {
    setEditingUser({
      uid: user.uid,
      permissions: { ...user.permissions }
    });
  };

  const handleSavePermissions = async () => {
    if (!editingUser) return;

    try {
      console.log('🔄 Saving permissions for user:', editingUser.uid, editingUser.permissions);
      
      // Convert frontend permissions to backend permission names
      const backendPermissions: string[] = [];
      if (editingUser.permissions.fiscalNoteGeneration) backendPermissions.push('fiscal-note-generation');
      if (editingUser.permissions.similarBillSearch) backendPermissions.push('similar-bill-search');
      if (editingUser.permissions.hrsSearch) backendPermissions.push('hrs-search');
      if (editingUser.permissions.adminPanel) backendPermissions.push('admin-panel');
      if (editingUser.permissions.userManagement) backendPermissions.push('user-management');
      if (editingUser.permissions.auditLogView) backendPermissions.push('audit-log-view');
      
      console.log('🔄 Backend permissions:', backendPermissions);
      
      // Update permissions in backend
      await authApi.updateUserPermissions(editingUser.uid, backendPermissions);
      
      console.log('✅ Permissions updated in backend');
      
      // Update local state
      setUsers(users.map(user => 
        user.uid === editingUser.uid 
          ? { ...user, permissions: { ...user.permissions, ...editingUser.permissions } }
          : user
      ));

      setEditingUser(null);
    } catch (error) {
      console.error('❌ Error updating permissions:', error);
    }
  };

  const handleDeleteUser = async (uid: string) => {
    if (!confirm('Are you sure you want to delete this user? This action cannot be undone.')) {
      return;
    }

    try {
      // In a real implementation, you'd delete via your backend API
      setUsers(users.filter(user => user.uid !== uid));
    } catch (error) {
      console.error('Error deleting user:', error);
    }
  };

  const handleAddUser = async (userData: { email: string; displayName: string; isAdmin: boolean }) => {
    try {
      console.log('🔄 Creating user in backend...', userData);
      
      // Create user in backend database
      const backendUser = await authApi.createUser({
        email: userData.email,
        display_name: userData.displayName,
        is_admin: userData.isAdmin
      });
      
      console.log('✅ User created in backend:', backendUser);
      
      // Convert backend user to frontend format
      const newUser: UserProfile = {
        uid: backendUser.id.toString(),
        email: backendUser.email,
        displayName: backendUser.display_name,
        isAdmin: backendUser.is_admin,
        permissions: {
          fiscalNoteGeneration: false,
          similarBillSearch: false,
          hrsSearch: false,
          adminPanel: backendUser.is_admin,
          userManagement: backendUser.is_admin,
          auditLogView: backendUser.is_admin,
        },
        createdAt: new Date(backendUser.created_at),
        lastLoginAt: new Date(backendUser.updated_at),
      };
      
      // Add to local state
      setUsers([...users, newUser]);
      
    } catch (error) {
      console.error('❌ Error creating user:', error);
      throw error;
    }
  };

  const updateEditingPermission = (permission: keyof EditingUser['permissions'], value: boolean) => {
    if (!editingUser) return;
    
    setEditingUser({
      ...editingUser,
      permissions: {
        ...editingUser.permissions,
        [permission]: value
      }
    });
  };

  if (!userProfile?.isAdmin) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <Shield className="w-16 h-16 text-red-500 mx-auto mb-4" />
          <h1 className="text-2xl font-bold text-gray-900 mb-2">Access Denied</h1>
          <p className="text-gray-600">You don't have permission to access this page.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with logout button */}
      <AppHeader />
      
      {/* Page Header */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <Settings className="w-8 h-8 text-blue-600" />
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Admin Panel</h1>
                <p className="text-gray-600">Manage users and system permissions</p>
              </div>
            </div>
            
            <div className="flex items-center space-x-3">
              <button
                onClick={loadUsers}
                className="flex items-center space-x-2 px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
                title="Refresh user list"
              >
                <RefreshCw className="w-4 h-4" />
                <span>Refresh</span>
              </button>
              
              <button
                onClick={() => setShowAddUserModal(true)}
                className="flex items-center space-x-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
              >
                <Plus className="w-4 h-4" />
                <span>Add User</span>
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Debug Info */}
        <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-6">
          <h3 className="text-sm font-medium text-yellow-800 mb-2">Debug Info:</h3>
          <p className="text-sm text-yellow-700">
            Total users in storage: {users.length} | 
            Last refresh: {new Date().toLocaleTimeString()}
          </p>
          {users.length > 0 && (
            <p className="text-sm text-yellow-700 mt-1">
              Users: {users.map(u => u.email).join(', ')}
            </p>
          )}
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <Users className="w-8 h-8 text-blue-600" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Total Users</p>
                <p className="text-2xl font-bold text-gray-900">{users.length}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <Shield className="w-8 h-8 text-green-600" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Admin Users</p>
                <p className="text-2xl font-bold text-gray-900">
                  {users.filter(user => user.isAdmin).length}
                </p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center">
              <Users className="w-8 h-8 text-purple-600" />
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Active Today</p>
                <p className="text-2xl font-bold text-gray-900">
                  {users.filter(user => {
                    const today = new Date();
                    const lastLogin = new Date(user.lastLoginAt);
                    return lastLogin.toDateString() === today.toDateString();
                  }).length}
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Users Table */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-lg font-semibold text-gray-900">User Management</h2>
          </div>
          
          {loading ? (
            <div className="p-8 text-center">
              <p className="text-gray-600">Loading users...</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      User
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Role
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Permissions
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Last Login
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {users.map((user) => (
                    <tr key={user.uid} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="flex items-center">
                          {user.photoURL ? (
                            <img
                              className="h-10 w-10 rounded-full"
                              src={user.photoURL}
                              alt=""
                            />
                          ) : (
                            <div className="h-10 w-10 rounded-full bg-gray-300 flex items-center justify-center">
                              <Users className="h-5 w-5 text-gray-600" />
                            </div>
                          )}
                          <div className="ml-4">
                            <div className="text-sm font-medium text-gray-900">
                              {user.displayName}
                            </div>
                            <div className="text-sm text-gray-500">{user.email}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${
                          user.isAdmin 
                            ? 'bg-red-100 text-red-800' 
                            : 'bg-green-100 text-green-800'
                        }`}>
                          {user.isAdmin ? 'Admin' : 'User'}
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        {editingUser?.uid === user.uid ? (
                          <div className="space-y-2">
                            <label className="flex items-center space-x-2">
                              <input
                                type="checkbox"
                                checked={editingUser.permissions.fiscalNoteGeneration}
                                onChange={(e) => updateEditingPermission('fiscalNoteGeneration', e.target.checked)}
                                className="rounded border-gray-300"
                              />
                              <span className="text-sm">Fiscal Note Generation</span>
                            </label>
                            <label className="flex items-center space-x-2">
                              <input
                                type="checkbox"
                                checked={editingUser.permissions.similarBillSearch}
                                onChange={(e) => updateEditingPermission('similarBillSearch', e.target.checked)}
                                className="rounded border-gray-300"
                              />
                              <span className="text-sm">Similar Bill Search</span>
                            </label>
                            <label className="flex items-center space-x-2">
                              <input
                                type="checkbox"
                                checked={editingUser.permissions.hrsSearch}
                                onChange={(e) => updateEditingPermission('hrsSearch', e.target.checked)}
                                className="rounded border-gray-300"
                              />
                              <span className="text-sm">HRS Search</span>
                            </label>
                          </div>
                        ) : (
                          <div className="space-y-1">
                            {user.permissions.fiscalNoteGeneration && (
                              <span className="inline-block px-2 py-1 text-xs bg-blue-100 text-blue-800 rounded mr-1">
                                Fiscal Notes
                              </span>
                            )}
                            {user.permissions.similarBillSearch && (
                              <span className="inline-block px-2 py-1 text-xs bg-purple-100 text-purple-800 rounded mr-1">
                                Bill Search
                              </span>
                            )}
                            {user.permissions.hrsSearch && (
                              <span className="inline-block px-2 py-1 text-xs bg-green-100 text-green-800 rounded mr-1">
                                HRS Search
                              </span>
                            )}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {user.lastLoginAt.toLocaleDateString()}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                        {editingUser?.uid === user.uid ? (
                          <div className="flex space-x-2">
                            <button
                              onClick={handleSavePermissions}
                              className="text-green-600 hover:text-green-900"
                            >
                              <Check className="w-4 h-4" />
                            </button>
                            <button
                              onClick={() => setEditingUser(null)}
                              className="text-gray-600 hover:text-gray-900"
                            >
                              <X className="w-4 h-4" />
                            </button>
                          </div>
                        ) : (
                          <div className="flex space-x-2">
                            <button
                              onClick={() => handleEditPermissions(user)}
                              className="text-blue-600 hover:text-blue-900"
                            >
                              <Edit className="w-4 h-4" />
                            </button>
                            {!user.isAdmin && (
                              <button
                                onClick={() => handleDeleteUser(user.uid)}
                                className="text-red-600 hover:text-red-900"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Add User Modal */}
      <AddUserModal
        isOpen={showAddUserModal}
        onClose={() => setShowAddUserModal(false)}
        onAddUser={handleAddUser}
      />
    </div>
  );
};

export default AdminPanel;
