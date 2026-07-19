import { Text } from '@tremor/react';
import { Box, Github, Linkedin, Mail } from 'lucide-react';

export function XIcon(props: React.SVGProps<SVGSVGElement>) {
  return (
    <svg
      role="img"
      viewBox="0 0 24 24"
      xmlns="http://www.w3.org/2000/svg"
      fill="currentColor"
      {...props}
    >
      <title>X</title>
      <path d="M18.901 1.153h3.68l-8.04 9.19L24 22.846h-7.406l-5.8-7.584-6.638 7.584H.474l8.6-9.83L0 1.154h7.594l5.243 6.932ZM17.61 20.644h2.039L6.486 3.24H4.298Z" />
    </svg>
  );
}

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
  productName = 'SourcePrep',
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
                  <XIcon className="w-5 h-5" />
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
            {copyright || `© ${currentYear} Magnetic Anomaly LLC.`}
          </p>
          <div className="flex gap-6">
            <a href="https://sourceprep.io/privacy" className="text-xs text-text-subtle hover:text-text transition-colors">Privacy Policy</a>
            <a href="https://sourceprep.io/terms" className="text-xs text-text-subtle hover:text-text transition-colors">Terms of Service</a>
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
      { label: 'Download', href: 'https://sourceprep.io/download' },
      { label: 'Pricing', href: 'https://sourceprep.io/pricing' },
      { label: 'Changelog', href: 'https://sourceprep.io/changelog' },
      { label: 'Docs', href: 'https://docs.sourceprep.io' },
    ],
  },
  {
    title: 'Resources',
    links: [
      { label: 'Blog', href: 'https://sourceprep.io/blog' },
      { label: 'Community', href: 'https://sourceprep.io/community' },
      { label: 'Help Center', href: 'https://sourceprep.io/support' },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'About', href: 'https://sourceprep.io/about' },
      { label: 'Careers', href: 'https://sourceprep.io/careers' },
      { label: 'Contact', href: 'https://sourceprep.io/contact' },
      { label: 'Security', href: 'https://sourceprep.io/security' },
      { label: 'SourcePrep vs Cursor', href: 'https://sourceprep.io/compare/prep-vs-cursor-indexing' },
      { label: 'SourcePrep vs Greptile', href: 'https://sourceprep.io/compare/prep-vs-greptile' },
    ],
  },
];
