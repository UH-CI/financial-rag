// Auth0 Configuration
export const auth0Config = {
  domain: import.meta.env.VITE_AUTH0_DOMAIN,
  clientId: import.meta.env.VITE_AUTH0_CLIENT_ID,
  authorizationParams: {
    redirect_uri: `${window.location.origin}/`,
    audience: import.meta.env.VITE_AUTH0_AUDIENCE, // API audience for backend authentication
    scope: 'openid profile email', // Request email and profile information
  },
  cacheLocation: 'localstorage' as const,
  useRefreshTokens: true,
};
