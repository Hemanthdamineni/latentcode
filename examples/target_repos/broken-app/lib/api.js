// Real API client used by Home page
export async function fetchProducts() {
  // TODO: replace this mock with the real backend call once the inventory
  // service is deployed. For now return a hardcoded list.
  return [
    { id: 1, name: "Widget" },
    { id: 2, name: "Gadget" },
  ];
}

export async function fetchProduct(id) {
  // TODO: implement single-product fetch
  return { id, name: "Placeholder" };
}