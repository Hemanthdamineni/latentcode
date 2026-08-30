# e2e-broken

A full-stack demo with **planted UI/API/handler wiring gaps** for LatentCode's
integration eval class. Three classes of defect are present:

1. **UI → API not wired** — `pages/index.js` has a button but never calls `lib/todoApi.js`.
2. **API client unused** — `lib/todoApi.js` is importable but no page imports it.
3. **API handler stub** — `pages/api/todos.js` POST throws `not implemented`.

When LatentCode's analyzer runs, it should:
- Detect the dead export on `createTodo` / `listTodos`
- Detect the `not_implemented` stub in `pages/api/todos.js`
- Detect the wiring gap via the issue graph (button → client → route, but edges are missing)

The repair, if approved, would:
- Wire `pages/index.js` to call `todoApi.createTodo(title)`
- Replace the POST stub in `pages/api/todos.js` with a real implementation

Both repairs happen in the same `repair_scope` (BFS depth 2 from the route file).

## Verification

```bash
# 1. Run the verification spec to confirm the actions fail
latentcode verify .

# 2. Scan
latentcode scan .

# 3. Approve + apply the patch
latentcode repair .latentcode --apply <id>

# 4. Re-verify
latentcode verify .

# 5. Regress
latentcode regress . --baseline .latentcode/findings.json
```