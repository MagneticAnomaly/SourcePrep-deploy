import { useEffect, useState } from 'react';
import { X, AlertCircle, AlertTriangle, Info, CheckCircle2 } from 'lucide-react';
import { cn } from '@codrag/ui';

export type ToastVariant = 'error' | 'warning' | 'info' | 'success';

export interface ToastMessage {
  text: string;
  variant?: ToastVariant;
  duration?: number;
}

export interface ToastProps {
  message: ToastMessage | null;
  onClose: () => void;
}

const VARIANT_CONFIG: Record<ToastVariant, {
  icon: typeof AlertCircle;
  bg: string;
  border: string;
  text: string;
  iconColor: string;
  closeHover: string;
  defaultDuration: number;
}> = {
  error: {
    icon: AlertCircle,
    bg: 'bg-[#2a1215]',
    border: 'border-red-500/40',
    text: 'text-red-200',
    iconColor: 'text-red-400',
    closeHover: 'hover:bg-red-500/20',
    defaultDuration: 6000,
  },
  warning: {
    icon: AlertTriangle,
    bg: 'bg-[#2a2215]',
    border: 'border-amber-500/40',
    text: 'text-amber-200',
    iconColor: 'text-amber-400',
    closeHover: 'hover:bg-amber-500/20',
    defaultDuration: 5000,
  },
  info: {
    icon: Info,
    bg: 'bg-[#151e2a]',
    border: 'border-blue-500/40',
    text: 'text-blue-200',
    iconColor: 'text-blue-400',
    closeHover: 'hover:bg-blue-500/20',
    defaultDuration: 5000,
  },
  success: {
    icon: CheckCircle2,
    bg: 'bg-[#152a1a]',
    border: 'border-emerald-500/40',
    text: 'text-emerald-200',
    iconColor: 'text-emerald-400',
    closeHover: 'hover:bg-emerald-500/20',
    defaultDuration: 3000,
  },
};

export function Toast({ message, onClose }: ToastProps) {
  const [visible, setVisible] = useState(false);
  const [current, setCurrent] = useState<ToastMessage | null>(null);

  useEffect(() => {
    if (message) {
      setCurrent(message);
      setVisible(true);
      const dur = message.duration ?? VARIANT_CONFIG[message.variant ?? 'error'].defaultDuration;
      const timer = setTimeout(() => {
        setVisible(false);
        setTimeout(onClose, 300);
      }, dur);
      return () => clearTimeout(timer);
    } else {
      setVisible(false);
    }
  }, [message, onClose]);

  if (!current && !visible) return null;

  const variant = current?.variant ?? 'error';
  const cfg = VARIANT_CONFIG[variant];
  const Icon = cfg.icon;

  return (
    <div
      className={cn(
        'fixed bottom-6 left-1/2 -translate-x-1/2 z-[100] max-w-lg w-[90vw]',
        'flex items-start gap-3 px-4 py-3 rounded-lg shadow-xl border backdrop-blur-sm',
        'transition-all duration-300 transform',
        cfg.bg, cfg.border, cfg.text,
        visible ? 'translate-y-0 opacity-100' : 'translate-y-4 opacity-0 pointer-events-none',
      )}
    >
      <Icon className={cn('w-5 h-5 shrink-0 mt-0.5', cfg.iconColor)} />
      <span className="text-sm font-medium flex-1 leading-relaxed">{current?.text}</span>
      <button
        onClick={() => { setVisible(false); onClose(); }}
        className={cn('p-1 rounded-full transition-colors shrink-0', cfg.closeHover)}
      >
        <X className="w-4 h-4" />
      </button>
    </div>
  );
}

/**
 * Helper to create a toast message object.
 * Usage: showToast('Something happened', 'info')
 */
export function makeToast(text: string, variant: ToastVariant = 'error', duration?: number): ToastMessage {
  return { text, variant, duration };
}
