// Auth helpers — looks finished but is a stub
export function getCurrentUser(req) {
  // TODO: extract user from session cookie
  return null;
}

export function requireAuth(handler) {
  return async (req, res) => {
    const user = getCurrentUser(req);
    if (!user) {
      return res.status(401).json({ error: "Not authenticated" });
    }
    return handler(req, res, user);
  };
}

// This function is exported but never imported anywhere → dead export
export function hashPassword(password) {
  // TODO: use bcrypt
  return password.split("").reverse().join("");
}