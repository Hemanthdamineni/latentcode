// Home page — has the create-todo button but the handler doesn't call the API
import { useState } from "react";

export default function Home() {
  const [title, setTitle] = useState("");
  const [submitted, setSubmitted] = useState("");

  // The button exists and the local state is set, but the API call is missing.
  // This is a broken_e2e_feature: UI exists, client exists, but they're not wired.
  const onCreate = () => {
    setSubmitted(title);
    // BUG: no call to todoApi.createTodo(title)
  };

  return (
    <div>
      <h1>Todos</h1>
      <input
        name="title"
        value={title}
        onChange={(e) => setTitle(e.target.value)}
        data-testid="title-input"
      />
      <button
        type="button"
        onClick={onCreate}
        data-testid="create-button"
      >
        Create
      </button>
      {submitted && <p data-testid="submitted">{submitted}</p>}
    </div>
  );
}