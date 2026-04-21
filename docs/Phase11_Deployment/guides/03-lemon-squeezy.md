# Lemon Squeezy Store Setup & Licensing

This guide provides step-by-step instructions for configuring Lemon Squeezy (LS) for Prep, including products, webhook integrations for license issuance, and configuring Netlify with the correct environment variables.

## 1. Initial Store Setup

1. Log into your [Lemon Squeezy Dashboard](https://app.lemonsqueezy.com/).
2. Navigate to **Store settings**.
3. Set the **Store name** to `Prep`.
4. Ensure your **Store URL** is set (e.g., `prep.lemonsqueezy.com`).
5. Configure your branding (logo, colors) to match the Prep brand (`#A020F0` for primary purple).
6. Under **Billing & Payouts**, ensure Magnetic Anomaly LLC business details and banking info are properly configured.

## 2. Product Creation

You need to create three distinct products. For all products, ensure that **Generate license keys** is turned **ON** in the product settings.

### Product A: Prep Pro (Monthly)
1. Go to **Products** → **Create Product**.
2. **Name:** Prep Pro - Monthly
3. **Description:** Continuous access to the Prep semantic tracing engine with monthly updates.
4. **Pricing:** Subscription, $7 / month.
5. **License Keys:** ENABLED.
6. **Activation Limit:** 2 devices.

### Product B: Prep Pro (Perpetual)
1. Go to **Products** → **Create Product**.
2. **Name:** Prep Pro - Perpetual (Fallback/One-time)
3. **Description:** Lifetime license to the current version of Prep.
4. **Pricing:** Single payment, $79.
5. **License Keys:** ENABLED.
6. **Activation Limit:** 2 devices.

### Product C: Prep Team
1. Go to **Products** → **Create Product**.
2. **Name:** Prep Team
3. **Description:** Prep headless runner for CI/CD and Team Sync capabilities.
4. **Pricing:** Subscription, Seat-based pricing, $15 / seat / month.
5. **License Keys:** ENABLED.
6. **Activation Limit:** Matches seat count (1 device per seat).

*Note: Record the Checkout URL or Variant IDs for each of these products. You will need them for the environment variables.*

## 3. Webhook Configuration (License Generation)

To ensure our custom payments backend tracks these orders:

1. Go to **Settings** → **Webhooks**.
2. Click **+ Add Webhook**.
3. **URL:** `https://payments.runprep.io/api/webhooks/lemon-squeezy`
4. **Secret:** Generate a strong random string (save this!).
5. **Events to subscribe to:**
   - `order_created`
   - `subscription_created`
   - `subscription_updated`
   - `subscription_cancelled`
   - `license_key_created`
6. Click **Save Webhook**.

## 4. Purchasing Purchasing Parity (PPP) Discounts

If you want to support global pricing (e.g., Band 1 vs Band 2 countries):
1. Go to **Discounts**.
2. Create codes like `PPP20`, `PPP40`, `PPP60`.
3. Configure them to apply as a percentage discount to specific products (Pro Monthly/Perpetual).
4. *Prep's pricing page will dynamically append these discount codes to the checkout URL based on the user's IP geolocation.*

## 5. Required Environment Variables

Once the store and products are created, you need to add the following to your Netlify sites (specifically the `marketing` and `payments` apps):

```env
# The checkout URLs from Lemon Squeezy (from Step 2)
NEXT_PUBLIC_LS_CHECKOUT_MONTHLY=https://prep.lemonsqueezy.com/checkout/buy/variant_id_here
NEXT_PUBLIC_LS_CHECKOUT_PERPETUAL=https://prep.lemonsqueezy.com/checkout/buy/variant_id_here
NEXT_PUBLIC_LS_CHECKOUT_TEAM=https://prep.lemonsqueezy.com/checkout/buy/variant_id_here

# Backend API configuration (Payments site only)
LEMONSQUEEZY_API_KEY=your_ls_api_key
LEMONSQUEEZY_STORE_ID=your_store_id
LEMONSQUEEZY_WEBHOOK_SECRET=your_webhook_secret_from_step_3
```

## 6. Testing the Flow

1. Put your Lemon Squeezy store into **Test Mode**.
2. Go to the Prep pricing page (`IS_BETA_MODE` must be `false` in `websites/apps/marketing/src/app/pricing/page.tsx`).
3. Click a buy button.
4. Complete the checkout using the [Lemon Squeezy test cards](https://docs.lemonsqueezy.com/help/checkout/testing-checkout).
5. Verify that you are redirected to `https://payments.runprep.io/success`.
6. Verify that an email containing the license key is delivered.
7. Open the Prep CLI or Dashboard and attempt to activate the generated license key.
