# Phase 42: Beta Access UI Plan

## Objective
Temporarily redirect active purchasing on the marketing website to a Beta Access waitlist, as CoDRAG is currently in a pre-launch state without active payment infrastructure. We must preserve the existing pricing structure, layout, and copy to communicate product value and future intent, while providing a clear and industry-standard path to request beta access.

## Implementation Strategy

### 1. The `IS_BETA_MODE` Flag
- Introduce a constant `IS_BETA_MODE = true;` inside the pricing page (or a shared constants file).
- This allows us to easily flip the switch back to live checkout URLs once the payment system (Lemon Squeezy) is fully integrated.

### 2. Pricing Page Modifications (`pricing/page.tsx`)
- **Header Notice**: Add a subtle, elegant badge or banner near the top (e.g., above "Simple, honest pricing") that says: *"CoDRAG is currently in closed beta. Prices below indicate our upcoming structure."*
- **Call-to-Action (CTA) Buttons**:
  - **Free Tier**: Change "Download Free" -> "Join Free Beta".
  - **Paid Tiers (Monthly, Perpetual, Team)**: Change "Start Monthly" / "Get Pro" / "Start Team Trial" -> "Request Beta Access".
  - **Enterprise**: Keep "Contact Sales" but maybe adapt to "Request Enterprise Beta".
- **Link Destination**:
  - Instead of routing to `getCheckoutUrl(...)`, the buttons will route to `/contact?subject=Beta%20Access` or a direct mailto link like `mailto:support@codrag.io?subject=CoDRAG%20Beta%20Access%20Request`. 
  - *Recommendation*: Use `mailto:support@codrag.io` with pre-filled subjects based on the tier they clicked, as it's the lowest friction before setting up a dedicated Typeform.

### 3. Marketing Homepage (Optional but Recommended)
- If there are "Buy Now" or primary CTA buttons on the homepage (`websites/apps/marketing/src/app/page.tsx`) or navbar, they should also respect the beta state and point to the beta request flow.

## Design Philosophy
- **Transparency**: Be clear that the product is in beta. It builds anticipation.
- **Non-Destructive**: Use conditional rendering (`{IS_BETA_MODE ? (...) : (...)}`) so the original checkout logic is preserved in the codebase and won't be lost.
- **Consistency**: Use the existing `@codrag/ui` Button atoms.

## Next Steps
1. Review and approve this plan.
2. Decide on the exact destination for the Beta button (e.g., `mailto:` vs. `/contact` vs. external form).
3. Implement the `IS_BETA_MODE` flag and UI overrides.
