import { StrictMode, useState, useCallback } from 'react';
import { createRoot } from 'react-dom/client';
import { RefreshCw } from 'lucide-react';
import './index.css';
import FaviconScene from './FaviconScene.jsx';

function LogoGenerator() {
  const [key, setKey] = useState(0);

  const handleRefresh = useCallback(() => {
    setKey((prev) => prev + 1);
  }, []);

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-[#030305]">
      <header className="pointer-events-none absolute top-0 left-0 right-0 z-20 flex justify-center pt-[max(1.5rem,env(safe-area-inset-top))]">
        <h1 className="font-sans font-bold text-[1rem] sm:text-xl tracking-widest text-ice">
          MAGNETIC ANOMALY
        </h1>
      </header>

      <button
        type="button"
        onClick={handleRefresh}
        className="absolute top-[max(1.25rem,env(safe-area-inset-top))] right-6 z-30 p-2 text-ice/80 hover:text-ice transition-colors focus:outline-none"
        aria-label="Regenerate logo"
        title="Regenerate logo"
      >
        <RefreshCw className="w-5 h-5 sm:w-6 sm:h-6" />
      </button>

      <div className="fixed inset-0">
        <FaviconScene key={key} />
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <LogoGenerator />
  </StrictMode>,
);
