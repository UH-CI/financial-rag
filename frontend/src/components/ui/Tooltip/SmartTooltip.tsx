import React, { useRef, useEffect, useState } from 'react';

interface SmartTooltipProps {
  content: string;
  children: React.ReactNode;
  className?: string;
}

const SmartTooltip: React.FC<SmartTooltipProps> = ({ content, children, className = '' }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [position, setPosition] = useState<'above' | 'below'>('above');
  const [horizontalOffset, setHorizontalOffset] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isVisible || !containerRef.current || !tooltipRef.current) return;

    // Use requestAnimationFrame to ensure measurements happen after render
    const calculatePosition = () => {
      if (!containerRef.current || !tooltipRef.current) return;

      const container = containerRef.current;
      const tooltip = tooltipRef.current;
      const containerRect = container.getBoundingClientRect();
      const tooltipRect = tooltip.getBoundingClientRect();

      const padding = 10; // Minimum distance from screen edge

      // Check vertical space
      const spaceAbove = containerRect.top;
      const spaceBelow = window.innerHeight - containerRect.bottom;
      
      if (spaceAbove < tooltipRect.height + padding && spaceBelow > tooltipRect.height + padding) {
        setPosition('below');
      } else {
        setPosition('above');
      }

      // Calculate horizontal position (centered by default)
      const containerCenterX = containerRect.left + (containerRect.width / 2);
      const tooltipHalfWidth = tooltipRect.width / 2;
      
      // Where the tooltip would be if perfectly centered
      const idealLeft = containerCenterX - tooltipHalfWidth;
      const idealRight = containerCenterX + tooltipHalfWidth;

      let offset = 0;

      // Check if tooltip goes off the left edge
      if (idealLeft < padding) {
        // Calculate how much we need to shift right
        offset = padding - idealLeft;
      }
      // Check if tooltip goes off the right edge
      else if (idealRight > window.innerWidth - padding) {
        // Calculate how much we need to shift left (negative offset)
        offset = (window.innerWidth - padding) - idealRight;
      }

      setHorizontalOffset(offset);
    };

    // Calculate immediately and after a frame to ensure DOM is ready
    calculatePosition();
    const rafId = requestAnimationFrame(calculatePosition);

    return () => cancelAnimationFrame(rafId);
  }, [isVisible]);

  const getTooltipStyle = (): React.CSSProperties => {
    return {
      transform: `translateX(calc(-50% + ${horizontalOffset}px))`,
      // Add subtle visual indicator when offset is applied (for debugging)
      ...(horizontalOffset !== 0 && { borderColor: '#3b82f6' })
    };
  };

  const getTooltipClasses = () => {
    let classes = 'absolute z-[99999] px-2 py-1 text-xs text-white bg-gray-800 rounded whitespace-nowrap pointer-events-none transition-opacity duration-200 shadow-lg border border-gray-700 left-1/2 ';
    
    // Vertical position
    if (position === 'above') {
      classes += 'bottom-full mb-2 ';
    } else {
      classes += 'top-full mt-2 ';
    }

    // Visibility
    classes += isVisible ? 'opacity-100 ' : 'opacity-0 ';

    return classes + className;
  };

  return (
    <div
      ref={containerRef}
      className="relative inline-block"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
    >
      {children}
      <div 
        ref={tooltipRef} 
        className={getTooltipClasses()}
        style={getTooltipStyle()}
      >
        {content}
      </div>
    </div>
  );
};

export default SmartTooltip;
