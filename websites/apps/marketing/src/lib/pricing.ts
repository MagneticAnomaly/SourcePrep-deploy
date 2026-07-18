/**
 * Global pricing utility — PPP (Purchasing Power Parity) bands.
 *
 * See docs/Phase10_.../Pricing/GLOBAL_PRICING.md for the full strategy.
 *
 * NOT LIVE. Nothing in this file is wired to a checkout today (see the
 * warning above LS_CHECKOUT_URLS below). The planned architecture was:
 *   1. Edge geo-detection (middleware) sets visitor country — removed
 *      along with the pricing page's PPP consumer in the open-core rewrite
 *   2. Country → PPP band lookup (this file)
 *   3. Band → prices + discount code for Lemon Squeezy checkout
 * Kept compiled so it can be re-wired if/when paid tiers go live.
 */

// ── PPP Band Definitions ────────────────────────────────────────────────────

export type PPPBand = 0 | 1 | 2 | 3;

export interface BandPrices {
  monthly: number;       // USD/month
  perpetual: number;     // USD one-time
  team: number;          // USD/seat/month
  discount: number;      // 0–60 (percentage)
  bandName: string;      // Human-readable band name
  discountCode: string;  // Lemon Squeezy discount code (empty for Band 0)
}

export const PPP_PRICES: Record<PPPBand, BandPrices> = {
  0: {
    monthly: 7,
    perpetual: 79,
    team: 15,
    discount: 0,
    bandName: "Full Price",
    discountCode: "",
  },
  1: {
    monthly: 5,
    perpetual: 59,
    team: 12,
    discount: 20,
    bandName: "20% regional discount",
    discountCode: "PPP20",
  },
  2: {
    monthly: 4,
    perpetual: 45,
    team: 9,
    discount: 40,
    bandName: "40% regional discount",
    discountCode: "PPP40",
  },
  3: {
    monthly: 3,
    perpetual: 29,
    team: 6,
    discount: 60,
    bandName: "60% regional discount",
    discountCode: "PPP60",
  },
};

// ── Country → Band Mapping ──────────────────────────────────────────────────

export const COUNTRY_PPP_BAND: Record<string, PPPBand> = {
  // Band 0: Full Price — high-income economies
  US: 0, CA: 0, GB: 0, DE: 0, FR: 0, NL: 0, CH: 0, AT: 0,
  AU: 0, NZ: 0, JP: 0, SG: 0, IL: 0, IE: 0, LU: 0, BE: 0,
  SE: 0, NO: 0, DK: 0, FI: 0, IS: 0, HK: 0,

  // Band 1: Moderate PPP (20% off)
  ES: 1, IT: 1, PT: 1, KR: 1, TW: 1, CZ: 1, PL: 1, GR: 1,
  CL: 1, AE: 1, SA: 1, QA: 1, KW: 1, HR: 1, SK: 1, SI: 1,
  EE: 1, LT: 1, LV: 1, HU: 1, MT: 1, CY: 1, UY: 1, CR: 1,
  PA: 1, MY: 1,

  // Band 2: High PPP (40% off)
  BR: 2, MX: 2, AR: 2, TR: 2, ZA: 2, RO: 2, BG: 2, TH: 2,
  CO: 2, PE: 2, CN: 2, EC: 2, DO: 2, GT: 2, RS: 2, BA: 2,
  MK: 2, AL: 2, GE: 2, JM: 2, TT: 2, MU: 2,

  // Band 3: Maximum PPP (60% off)
  IN: 3, ID: 3, VN: 3, PH: 3, PK: 3, BD: 3, NG: 3, KE: 3,
  EG: 3, UA: 3, NP: 3, LK: 3, ET: 3, GH: 3, TZ: 3, UG: 3,
  RW: 3, SN: 3, CM: 3, MM: 3, KH: 3, LA: 3, MN: 3, UZ: 3,
  KG: 3, TJ: 3, BO: 3, PY: 3, HN: 3, NI: 3,
};

export const DEFAULT_PPP_BAND: PPPBand = 0;

// ── Country names for display ───────────────────────────────────────────────

const COUNTRY_NAMES: Record<string, string> = {
  US: "the United States", CA: "Canada", GB: "the United Kingdom",
  DE: "Germany", FR: "France", NL: "the Netherlands", CH: "Switzerland",
  AT: "Austria", AU: "Australia", NZ: "New Zealand", JP: "Japan",
  SG: "Singapore", IL: "Israel", IE: "Ireland", SE: "Sweden",
  NO: "Norway", DK: "Denmark", FI: "Finland", IS: "Iceland",
  HK: "Hong Kong", BE: "Belgium", LU: "Luxembourg",
  ES: "Spain", IT: "Italy", PT: "Portugal", KR: "South Korea",
  TW: "Taiwan", CZ: "Czechia", PL: "Poland", GR: "Greece",
  CL: "Chile", AE: "the UAE", SA: "Saudi Arabia", QA: "Qatar",
  KW: "Kuwait", HR: "Croatia", SK: "Slovakia", SI: "Slovenia",
  EE: "Estonia", LT: "Lithuania", LV: "Latvia", HU: "Hungary",
  MT: "Malta", CY: "Cyprus", UY: "Uruguay", CR: "Costa Rica",
  PA: "Panama", MY: "Malaysia",
  BR: "Brazil", MX: "Mexico", AR: "Argentina", TR: "Turkey",
  ZA: "South Africa", RO: "Romania", BG: "Bulgaria", TH: "Thailand",
  CO: "Colombia", PE: "Peru", CN: "China", EC: "Ecuador",
  DO: "Dominican Republic", GT: "Guatemala", RS: "Serbia",
  BA: "Bosnia", MK: "North Macedonia", AL: "Albania", GE: "Georgia",
  JM: "Jamaica", TT: "Trinidad & Tobago", MU: "Mauritius",
  IN: "India", ID: "Indonesia", VN: "Vietnam", PH: "the Philippines",
  PK: "Pakistan", BD: "Bangladesh", NG: "Nigeria", KE: "Kenya",
  EG: "Egypt", UA: "Ukraine", NP: "Nepal", LK: "Sri Lanka",
  ET: "Ethiopia", GH: "Ghana", TZ: "Tanzania", UG: "Uganda",
  RW: "Rwanda", SN: "Senegal", CM: "Cameroon", MM: "Myanmar",
  KH: "Cambodia", LA: "Laos", MN: "Mongolia", UZ: "Uzbekistan",
  KG: "Kyrgyzstan", TJ: "Tajikistan", BO: "Bolivia", PY: "Paraguay",
  HN: "Honduras", NI: "Nicaragua",
};

// ── Public API ──────────────────────────────────────────────────────────────

/**
 * Get the PPP band for a given ISO 3166-1 alpha-2 country code.
 */
export function getBand(country: string): PPPBand {
  const code = (country || "").toUpperCase().trim();
  return COUNTRY_PPP_BAND[code] ?? DEFAULT_PPP_BAND;
}

/**
 * Get the pricing table for a given country code.
 */
export function getPrices(country: string): BandPrices {
  return PPP_PRICES[getBand(country)];
}

/**
 * Get a human-readable country name for display ("India", "Brazil", etc.).
 * Returns undefined for unknown country codes.
 */
export function getCountryName(country: string): string | undefined {
  return COUNTRY_NAMES[(country || "").toUpperCase().trim()];
}

/**
 * Format a USD price for display.
 * Examples: formatPrice(29) → "$29", formatPrice(15) → "$15"
 */
export function formatPrice(amount: number): string {
  return `$${amount}`;
}

/**
 * Build a Lemon Squeezy checkout URL with the appropriate PPP discount.
 *
 * @param baseUrl - The base checkout URL for the product (from LS dashboard)
 * @param country - ISO country code
 * @returns Checkout URL, possibly with ?discount= appended
 */
export function getCheckoutUrl(baseUrl: string, country: string): string {
  const prices = getPrices(country);
  if (!prices.discountCode) return baseUrl;

  const sep = baseUrl.includes("?") ? "&" : "?";
  return `${baseUrl}${sep}discount=${prices.discountCode}`;
}

// ── Lemon Squeezy Product URLs ──────────────────────────────────────────────
// If checkout ever goes live, these would be set in the Netlify dashboard as
// NEXT_PUBLIC_ env vars pointing at Lemon Squeezy checkout pages per product.
// Today no such env vars are configured and no LS products exist; the fallback
// below is the payments.sourceprep.io hub page.

// Checkout deliberately unwired: license crypto void (Phase 146 N1) + LS products
// unconfigured. Do not re-link without fixing both.
export const LS_CHECKOUT_URLS = {
  monthly:  process.env.NEXT_PUBLIC_LS_CHECKOUT_MONTHLY  ?? "https://payments.sourceprep.io",
  perpetual: process.env.NEXT_PUBLIC_LS_CHECKOUT_PERPETUAL ?? "https://payments.sourceprep.io",
  team:     process.env.NEXT_PUBLIC_LS_CHECKOUT_TEAM      ?? "https://payments.sourceprep.io",
} as const;
