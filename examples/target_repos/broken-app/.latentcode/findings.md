# LatentCode Findings

## Project

- **Language**: javascript
- **Framework**: nextjs
- **Package manager**: npm
- **Entry points**: pages/index.js

### Declared features
- Features
- Product listing
- User authentication
- Checkout with Stripe
- Order history
- Admin dashboard
- Email notifications
- Search functionality
- Reviews and ratings

## Summary

**Total issues**: 16

By category:
- `hidden_implementation`: 7
- `agent_shortcut`: 8
- `broken_integration`: 1

## Static analysis

- **files_analyzed**: 8
- **symbols**: 13
- **imports**: 3
- **calls**: 0
- **routes**: 0
- **stubs**: 8

## Runtime probe

- **Endpoints working**: 0
- **Endpoints failing**: 0

## Issues

### agent_shortcut — severity 0.80
- **Location**: `pages/api/login.js:11`
- **Subtype**: `not_implemented`
- **Evidence**: not_implemented at pages/api/login.js:11

```
  // TODO: validate against the user database and issue a session token
  throw new Error("not implemented: login");
}
```

### agent_shortcut — severity 0.80
- **Location**: `pages/api/checkout.js:7`
- **Subtype**: `not_implemented`
- **Evidence**: not_implemented at pages/api/checkout.js:7

```
  // TODO: integrate with Stripe and persist order
  throw new NotImplementedError("checkout not implemented yet");
}
```

### hidden_implementation — severity 0.70
- **Location**: `lib/api.js:?`
- **Subtype**: `dead_export`
- **Evidence**: exported `fetchProduct` has no importer in the project

### hidden_implementation — severity 0.70
- **Location**: `lib/auth.js:?`
- **Subtype**: `dead_export`
- **Evidence**: exported `getCurrentUser` has no importer in the project

### hidden_implementation — severity 0.70
- **Location**: `lib/auth.js:?`
- **Subtype**: `dead_export`
- **Evidence**: exported `requireAuth` has no importer in the project

### hidden_implementation — severity 0.70
- **Location**: `lib/auth.js:?`
- **Subtype**: `dead_export`
- **Evidence**: exported `hashPassword` has no importer in the project

### hidden_implementation — severity 0.70
- **Location**: `lib/stripe.js:?`
- **Subtype**: `dead_export`
- **Evidence**: exported `chargeCustomer` has no importer in the project

### hidden_implementation — severity 0.70
- **Location**: `components/Button.js:?`
- **Subtype**: `dead_export`
- **Evidence**: exported `Button` has no importer in the project

### hidden_implementation — severity 0.70
- **Location**: `components/Button.js:?`
- **Subtype**: `dead_export`
- **Evidence**: exported `PrimaryButton` has no importer in the project

### broken_integration — severity 0.60
- **Location**: `?:?`
- **Subtype**: `env_var_missing`
- **Evidence**: `STRIPE_SECRET_KEY` referenced in 1 file(s) but not in any .env / .env.example

### agent_shortcut — severity 0.50
- **Location**: `lib/api.js:3`
- **Subtype**: `todo_comment`
- **Evidence**: todo_comment at lib/api.js:3

```
export async function fetchProducts() {
  // TODO: replace this mock with the real backend call once the inventory
  // service is deployed. For now return a hardcoded list.
  return [
```

### agent_shortcut — severity 0.50
- **Location**: `lib/api.js:12`
- **Subtype**: `todo_comment`
- **Evidence**: todo_comment at lib/api.js:12

```
export async function fetchProduct(id) {
  // TODO: implement single-product fetch
  return { id, name: "Placeholder" };
}
```

### agent_shortcut — severity 0.50
- **Location**: `lib/auth.js:3`
- **Subtype**: `todo_comment`
- **Evidence**: todo_comment at lib/auth.js:3

```
export function getCurrentUser(req) {
  // TODO: extract user from session cookie
  return null;
}
```

### agent_shortcut — severity 0.50
- **Location**: `lib/auth.js:19`
- **Subtype**: `todo_comment`
- **Evidence**: todo_comment at lib/auth.js:19

```
export function hashPassword(password) {
  // TODO: use bcrypt
  return password.split("").reverse().join("");
}
```

### agent_shortcut — severity 0.50
- **Location**: `pages/api/login.js:10`
- **Subtype**: `todo_comment`
- **Evidence**: todo_comment at pages/api/login.js:10

```
  }
  // TODO: validate against the user database and issue a session token
  throw new Error("not implemented: login");
}
```

### agent_shortcut — severity 0.50
- **Location**: `pages/api/checkout.js:6`
- **Subtype**: `todo_comment`
- **Evidence**: todo_comment at pages/api/checkout.js:6

```
  }
  // TODO: integrate with Stripe and persist order
  throw new NotImplementedError("checkout not implemented yet");
}
```
