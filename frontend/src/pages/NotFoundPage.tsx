import { Link } from "react-router-dom";

export default function NotFoundPage() {
  return (
    <div className="empty">
      <h2>Page not found</h2>
      <p>
        <Link to="/">Plan a new trip</Link>
      </p>
    </div>
  );
}
