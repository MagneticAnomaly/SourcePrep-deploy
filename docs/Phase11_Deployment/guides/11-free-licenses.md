# Giving Away Free Licenses

There are two primary ways to distribute free Prep licenses, depending on whether you want the user to go through the standard checkout flow or bypass it entirely.

## Method A: 100% Discount Codes (Recommended)

This method uses Lemon Squeezy to process the order for $0. It is the recommended approach because:
1. The user goes through the standard checkout flow, ensuring they accept the terms of service.
2. The order is recorded in Lemon Squeezy for tracking and analytics.
3. The `api.runprep.io` relay service handles the webhook and automatically emails the signed license key to the user, just like a paid order.

### Steps:
1. Go to your Lemon Squeezy dashboard.
2. Navigate to **Store → Discounts**.
3. Create a new discount code (e.g., `FREE_PRO`, `BETA_TESTER`).
4. Set the discount type to **Percentage** and the value to **100%**.
5. Optionally, restrict the code to specific products (e.g., only the Perpetual license) and set a redemption limit.
6. Share the code or a pre-applied checkout URL (`https://[store].lemonsqueezy.com/buy/[variant]?discount=FREE_PRO`) with the user.

## Method B: Manual License Generation (Bypass Checkout)

If you need to generate a license key immediately without the user going through checkout (e.g., for internal testing, VIPs, or support resolutions), you can manually generate a cryptographically signed Ed25519 offline license key using the `scripts/generate_license.py` tool.

> **⚠️ Security Warning:** This script requires the private Ed25519 key used for production license signing. Do not commit the private key to the repository or run this script on an untrusted machine.

### Steps:

1. Locate the production Ed25519 private key (stored securely, e.g., in a password manager or HSM).
2. Run the `generate_license.py` script locally:

```bash
# Example: Generate a perpetual license for a user
python scripts/generate_license.py \
  --email "user@example.com" \
  --tier "perpetual" \
  --priv "YOUR_PRODUCTION_PRIVATE_KEY_HEX" \
  --out "license.key"
```

3. Open the generated `license.key` file.
4. Email the contents of the file directly to the user with instructions to paste it into the **Settings → License** panel in Prep.

### Script Options:
- `--email`: The email address associated with the license.
- `--tier`: The license tier (`free`, `monthly`, `perpetual`, `team`, `enterprise`). Usually `perpetual` for manual giveaways.
- `--priv`: The hex-encoded Ed25519 private key. If omitted, it uses a hardcoded test key (which will fail validation in production).
- `--out`: Optional file path to save the key. If omitted, it prints to stdout.

## Ensuring Relay Service Handles Free Orders

When using Method A (100% discount codes), the `api.runprep.io` relay service will receive a webhook from Lemon Squeezy for an order with a total of `$0.00`.

When implementing the relay service (Task LIC-01), ensure that the webhook handler does not reject orders based on a zero dollar amount. Lemon Squeezy's `order_created` event schema includes the `discount_total` and `total` fields. A valid order with a 100% discount will have `total: 0`. The relay service should process this order and issue the license key identically to a paid order.
