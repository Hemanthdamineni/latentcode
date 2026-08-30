// Stripe integration — references an env var that doesn't exist in .env.example
const STRIPE_KEY = process.env.STRIPE_SECRET_KEY;

export async function chargeCustomer(amountCents) {
  // Uses STRIPE_KEY but never validates it's defined
  return fetch("https://api.stripe.com/v1/charges", {
    method: "POST",
    headers: { Authorization: `Bearer ${STRIPE_KEY}` },
  });
}