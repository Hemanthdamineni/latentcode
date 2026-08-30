// Login route — looks complete but the handler is a placeholder
export default function handler(req, res) {
  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed" });
  }
  const { email, password } = req.body || {};
  if (!email || !password) {
    return res.status(400).json({ error: "Missing credentials" });
  }
  // TODO: validate against the user database and issue a session token
  throw new Error("not implemented: login");
}