# LatentCode Findings

## Project

- **Language**: javascript
- **Framework**: nextjs
- **Package manager**: npm
- **Entry points**: pages/index.js

### Declared features
- Detect the dead export on `createTodo` / `listTodos`
- Detect the `not_implemented` stub in `pages/api/todos.js`
- Wire `pages/index.js` to call `todoApi.createTodo(title)`
- Replace the POST stub in `pages/api/todos.js` with a real implementation
- Verification

## Summary

**Total issues**: 3

By category:
- `hidden_implementation`: 2
- `agent_shortcut`: 1

## Static analysis

- **files_analyzed**: 3
- **symbols**: 5
- **imports**: 1
- **calls**: 0
- **routes**: 0
- **stubs**: 1

## Runtime probe

- **Endpoints working**: 0
- **Endpoints failing**: 0

## Issues

### agent_shortcut — severity 0.80
- **Location**: `pages/api/todos.js:8`
- **Subtype**: `not_implemented`
- **Evidence**: not_implemented at pages/api/todos.js:8

```
    // BUG: stub — the route exists but the handler is a placeholder
    throw new Error("not implemented: createTodo");
  }
  return res.status(405).json({ error: "Method not allowed" });
```

### hidden_implementation — severity 0.70
- **Location**: `lib/todoApi.js:?`
- **Subtype**: `dead_export`
- **Evidence**: exported `createTodo` has no importer in the project

### hidden_implementation — severity 0.70
- **Location**: `lib/todoApi.js:?`
- **Subtype**: `dead_export`
- **Evidence**: exported `listTodos` has no importer in the project
