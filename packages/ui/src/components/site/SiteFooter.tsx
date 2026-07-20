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
              Give your AI access to the epistemic context it needs to understand your codebase.
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

        <div className="mt-12 border-t border-border pt-8 space-y-2 text-center sm:text-left">
          <p className="text-xs text-text-subtle">
            {copyright || `© ${currentYear} Magnetic Anomaly LLC.`}
          </p>
          <p className="text-[10px] text-text-subtle">
            SourcePrep™ is a trademark of Magnetic Anomaly LLC. This site uses cookieless, privacy-friendly analytics — no cookies and no cross-site tracking.
          </p>
        </div>
      </div>
    </footer>
  );
}

/**
 * Canonical footer sections — the single source of truth for the site footer.
 * Every website's ClientLayout builds its sections from this helper (passing
 * its own dev-aware base URLs) so the footer can never diverge across sites.
 * Pass `home: ''` for same-site relative links (the marketing site).
 */
export function buildFooterSections(urls: {
  home: string;
  docs: string;
  support: string;
}): FooterSection[] {
  const { home, docs, support } = urls;
  return [
    {
      title: 'Product',
      links: [
        { label: 'Download', href: `${home}/download` },
        { label: 'Pricing', href: `${home}/pricing` },
        { label: 'Changelog', href: `${home}/changelog` },
        { label: 'Documentation', href: docs },
      ],
    },
    {
      title: 'Company',
      links: [
        { label: 'FAQ', href: `${home}/faq` },
        { label: 'Research', href: `${home}/research` },
        { label: 'Support', href: support },
        { label: 'Privacy Policy', href: `${home}/privacy` },
        { label: 'Terms of Service', href: `${home}/terms` },
      ],
    },
  ];
}

// Default (production URLs) — used by consumers that don't pass `sections`
// (support, payments, Storybook).
const defaultSections: FooterSection[] = buildFooterSections({
  home: 'https://sourceprep.io',
  docs: 'https://docs.sourceprep.io',
  support: 'https://support.sourceprep.io',
});
