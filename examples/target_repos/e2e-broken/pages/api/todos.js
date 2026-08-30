// GET handler works (returns []), POST handler is a stub
export default async function handler(req, res) {
  if (req.method === "GET") {
    return res.status(200).json([]);
  }
  if (req.method === "POST") {
    // BUG: stub — the route exists but the handler is a placeholder
    throw new Error("not implemented: createTodo");
  }
  return res.status(405).json({ error: "Method not allowed" });
}