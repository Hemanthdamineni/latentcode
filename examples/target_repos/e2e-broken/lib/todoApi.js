// API client — exists and is importable, but never called from index.js
export async function createTodo(title) {
  const res = await fetch("/api/todos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error("create failed");
  return res.json();
}

export async function listTodos() {
  const res = await fetch("/api/todos");
  if (!res.ok) throw new Error("list failed");
  return res.json();
}