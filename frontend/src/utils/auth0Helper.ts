/**
 * Auth0 Helper utilities for managing authentication state
 */

/**
 * Clear all Auth0 related data from browser storage
 * This helps ensure a clean logout when switching between accounts
 */
export const clearAuth0Storage = () => {
  try {
    // Clear localStorage items that Auth0 might use
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && (
        key.startsWith('@@auth0spajs@@') || 
        key.startsWith('auth0.') ||
        key.includes('auth0')
      )) {
        keysToRemove.push(key);
      }
    }
    
    keysToRemove.forEach(key => localStorage.removeItem(key));
    
    // Clear sessionStorage items that Auth0 might use
    const sessionKeysToRemove = [];
    for (let i = 0; i < sessionStorage.length; i++) {
      const key = sessionStorage.key(i);
      if (key && (
        key.startsWith('@@auth0spajs@@') || 
        key.startsWith('auth0.') ||
        key.includes('auth0')
      )) {
        sessionKeysToRemove.push(key);
      }
    }
    
    sessionKeysToRemove.forEach(key => sessionStorage.removeItem(key));
    
    console.log('🧹 Cleared Auth0 storage data');
  } catch (error) {
    console.warn('Failed to clear Auth0 storage:', error);
  }
};

/**
 * Force a complete logout by clearing storage and reloading
 */
export const forceCompleteLogout = () => {
  clearAuth0Storage();
  
  // Small delay to ensure storage is cleared
  setTimeout(() => {
    window.location.href = '/login';
  }, 100);
};

/**
 * Safe logout that handles Auth0 logout errors gracefully
 */
export const safeLogout = (auth0Logout: (options?: any) => void) => {
  try {
    // Try Auth0 logout with root domain (more likely to be configured)
    auth0Logout({ 
      logoutParams: { 
        returnTo: window.location.origin 
      } 
    });
  } catch (error) {
    console.warn('Auth0 logout failed, using manual logout:', error);
    // Fallback to manual logout
    forceCompleteLogout();
  }
};
