// Disconnected component — never imported anywhere
export function Button({ children, onClick }) {
  return (
    <button onClick={onClick} style={{ padding: "8px 16px" }}>
      {children}
    </button>
  );
}

export function PrimaryButton(props) {
  return <Button {...props} style={{ background: "blue", color: "white" }} />;
}