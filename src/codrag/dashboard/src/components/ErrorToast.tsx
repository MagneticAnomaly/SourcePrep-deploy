import { useEffect, useState } from 'react';
import { X, AlertCircle } from 'lucide-react';
import { cn } from '@codrag/ui';

export interface ErrorToastProps {
  message: string | null;
  onClose: () => void;
  duration?: number;
}

export function ErrorToast({ message, onClose, duration = 5000 }: ErrorToastProps) {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (message) {
      setVisible(true);
      const timer = setTimeout(() => {
        setVisible(false);
        setTimeout(onClose, 300); // Wait for fade out
      }, duration);
      return () => clearTimeout(timer);
    } else {
      setVisible(false);
    }
  }, [message, duration, onClose]);

  if (!message && !visible) return null;

  return (
    <div
      className={cn(
        "fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg border transition-all duration-300 transform",
        "bg-error text-white border-error-dark",
        visible ? "translate-y-0 opacity-100" : "translate-y-4 opacity-0"
      )}
    >
      <AlertCircle className="w-5 h-5 shrink-0" />
      <span className="text-sm font-medium">{message}</span>
      <button
        onClick={() => setVisible(false)}
        className="ml-2 p-1 hover:bg-white/20 rounded-full transition-colors"
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}
