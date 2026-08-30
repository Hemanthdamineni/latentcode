// Product API — wired up to a real handler
import { fetchProducts } from "../../lib/api";

export default async function handler(req, res) {
  const products = await fetchProducts();
  res.status(200).json(products);
}