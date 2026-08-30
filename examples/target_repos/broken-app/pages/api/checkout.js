// Checkout endpoint — completely missing the implementation
export default async function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).end();
  }
  // TODO: integrate with Stripe and persist order
  throw new NotImplementedError("checkout not implemented yet");
}