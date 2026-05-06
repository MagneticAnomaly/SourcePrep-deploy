import { notFound } from 'next/navigation';

export const metadata = {
  robots: {
    index: false,
    follow: false,
    nocache: true,
    googleBot: { index: false, follow: false },
  },
};

export default function DevLayout({ children }: { children: React.ReactNode }) {
  if (process.env.NODE_ENV === 'production') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background text-text">
        <h1 className="text-2xl font-bold">404 - Not Found</h1>
      </div>
    );
  }
  return <>{children}</>;
}
