import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'

// Global error handler for OAuth callback and other DOM errors
window.addEventListener('error', (event) => {
  if (event.error && event.error.message && 
      (event.error.message.includes('parentNode') || 
       event.error.message.includes('Cannot read properties of undefined'))) {
    console.warn('Suppressed DOM manipulation error during OAuth callback:', event.error.message);
    event.preventDefault();
    return false;
  }
});

// Handle unhandled promise rejections
window.addEventListener('unhandledrejection', (event) => {
  if (event.reason && event.reason.message && 
      event.reason.message.includes('parentNode')) {
    console.warn('Suppressed promise rejection for DOM error:', event.reason.message);
    event.preventDefault();
  }
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
