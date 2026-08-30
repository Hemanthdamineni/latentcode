// Main page — wired up to real logic
import Link from "next/link";
import { fetchProducts } from "../lib/api";

export default function Home({ products }) {
  return (
    <div>
      <h1>Products</h1>
      <ul>
        {products.map((p) => (
          <li key={p.id}>
            <Link href={`/products/${p.id}`}>{p.name}</Link>
          </li>
        ))}
      </ul>
    </div>
  );
}

export async function getServerSideProps() {
  const products = await fetchProducts();
  return { props: { products } };
}