import { Text } from '@tremor/react';
import { Box, Github, Twitter, Linkedin, Mail } from 'lucide-react';

export interface FooterLink {
  label: string;
  href: string;
}

export interface FooterSection {
  title: string;
  links: FooterLink[];
}

export interface SiteFooterProps {
  productName?: string;
  logo?: React.ReactNode;
  sections?: FooterSection[];
  socials?: {
    twitter?: string;
    github?: string;
    linkedin?: string;
    email?: string;
  };
  copyright?: string;
  className?: string;
}

export function SiteFooter({
  productName = 'CoDRAG',
  logo = <Box className="w-5 h-5 text-primary" />,
  sections = defaultSections,
  socials,
  copyright,
  className = '',
}: SiteFooterProps) {
  const currentYear = new Date().getFullYear();

  return (
    <footer className={`border-t border-border bg-surface ${className}`}>
      <div className="mx-auto max-w-7xl px-6 py-12 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-8 lg:gap-12">
          
          {/* Brand Column */}
          <div className="md:col-span-1 space-y-4">
            <a href="/" className="flex items-center font-mono font-bold text-lg tracking-tight text-text hover:text-primary transition-colors">
              {logo}
              {productName}
            </a>
            <Text className="text-sm text-text-muted leading-relaxed">
              The bridge between how <br/>
              you think about code and<br/>
              how your AI reads it.
            </Text>
            <div className="flex gap-4 pt-2">
              {socials?.twitter && (
                <a href={socials.twitter} className="text-text-subtle hover:text-text transition-colors">
                  <Twitter className="w-5 h-5" />
                </a>
              )}
              {socials?.github && (
                <a href={socials.github} className="text-text-subtle hover:text-text transition-colors">
                  <Github className="w-5 h-5" />
                </a>
              )}
              {socials?.linkedin && (
                <a href={socials.linkedin} className="text-text-subtle hover:text-text transition-colors">
                  <Linkedin className="w-5 h-5" />
                </a>
              )}
              {socials?.email && (
                <a href={`mailto:${socials.email}`} className="text-text-subtle hover:text-text transition-colors">
                  <Mail className="w-5 h-5" />
                </a>
              )}
            </div>
          </div>

          {/* Links Columns */}
          <div className="md:col-span-3 grid grid-cols-2 sm:grid-cols-3 gap-8">
            {sections.map((section) => (
              <div key={section.title}>
                <h3 className="text-sm font-semibold text-text mb-4">{section.title}</h3>
                <ul className="space-y-3">
                  {section.links.map((link) => (
                    <li key={link.label}>
                      <a href={link.href} className="text-sm text-text-muted hover:text-primary transition-colors">
                        {link.label}
                      </a>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-12 border-t border-border pt-8 flex flex-col sm:flex-row justify-between items-center gap-4">
          <p className="text-xs text-text-subtle">
            {copyright || `© ${currentYear} ${productName} Inc. All rights reserved.`}
          </p>
          <div className="flex gap-6">
            <a href="https://codrag.io/privacy" className="text-xs text-text-subtle hover:text-text transition-colors">Privacy Policy</a>
            <a href="https://codrag.io/terms" className="text-xs text-text-subtle hover:text-text transition-colors">Terms of Service</a>
          </div>
        </div>
      </div>
    </footer>
  );
}

const defaultSections: FooterSection[] = [
  {
    title: 'Product',
    links: [
      { label: 'Download', href: 'https://codrag.io/download' },
      { label: 'Pricing', href: 'https://codrag.io/pricing' },
      { label: 'Changelog', href: 'https://codrag.io/changelog' },
      { label: 'Docs', href: 'https://docs.codrag.io' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { label: 'Blog', href: 'https://codrag.io/blog' },
      { label: 'Community', href: 'https://codrag.io/community' },
      { label: 'Help Center', href: 'https://codrag.io/support' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'About', href: 'https://codrag.io/about' },
      { label: 'Careers', href: 'https://codrag.io/careers' },
      { label: 'Contact', href: 'https://codrag.io/contact' },
      { label: 'Security', href: 'https://codrag.io/security' },
    ],
  },
];
