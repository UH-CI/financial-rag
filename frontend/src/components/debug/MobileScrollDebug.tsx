import React, { useEffect, useState } from 'react';

interface MobileScrollDebugProps {
  onClose: () => void;
}

const MobileScrollDebug: React.FC<MobileScrollDebugProps> = ({ onClose }) => {
  const [touchInfo, setTouchInfo] = useState<string>('');
  const [scrollInfo, setScrollInfo] = useState<string>('');

  useEffect(() => {
    const handleTouchStart = (e: TouchEvent) => {
      setTouchInfo(`Touch Start: ${e.touches.length} touches`);
    };

    const handleTouchMove = (e: TouchEvent) => {
      setTouchInfo(`Touch Move: ${e.touches.length} touches, prevented: ${e.defaultPrevented}`);
    };

    const handleScroll = (e: Event) => {
      const target = e.target as HTMLElement;
      setScrollInfo(`Scroll: ${target.scrollTop}px, height: ${target.scrollHeight}px`);
    };

    document.addEventListener('touchstart', handleTouchStart, { passive: false });
    document.addEventListener('touchmove', handleTouchMove, { passive: false });
    document.addEventListener('scroll', handleScroll, true);

    return () => {
      document.removeEventListener('touchstart', handleTouchStart);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('scroll', handleScroll, true);
    };
  }, []);

  return (
    <div className="fixed top-4 right-4 z-[9999] bg-black bg-opacity-80 text-white p-4 rounded-lg text-xs max-w-xs lg:hidden">
      <div className="flex justify-between items-center mb-2">
        <h3 className="font-bold">Mobile Debug</h3>
        <button onClick={onClose} className="text-white hover:text-gray-300">×</button>
      </div>
      <div className="space-y-1">
        <div>User Agent: {navigator.userAgent.includes('Mobile') ? 'Mobile' : 'Desktop'}</div>
        <div>Touch Support: {('ontouchstart' in window) ? 'Yes' : 'No'}</div>
        <div>iOS: {/iPad|iPhone|iPod/.test(navigator.userAgent) ? 'Yes' : 'No'}</div>
        <div>Viewport: {window.innerWidth}x{window.innerHeight}</div>
        <div>{touchInfo}</div>
        <div>{scrollInfo}</div>
      </div>
      
      {/* Test scroll area */}
      <div className="mt-4 border border-gray-400 rounded">
        <div className="text-center py-1 bg-gray-700">Test Scroll Area</div>
        <div className="h-32 overflow-y-auto scroll-smooth mobile-scroll bg-gray-800 p-2">
          {Array.from({ length: 20 }, (_, i) => (
            <div key={i} className="py-1 border-b border-gray-600">
              Line {i + 1} - Try scrolling this area
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default MobileScrollDebug;
