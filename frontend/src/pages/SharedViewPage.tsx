// Parent-facing view: read-only, time-boxed, teacher-curated (GOALS §6.4).
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, SharedView } from "../api";

export default function SharedViewPage() {
  const { token } = useParams();
  const [view, setView] = useState<SharedView | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (token) {
      api.sharedView(token).then(setView).catch((e) => setError(e.message));
    }
  }, [token]);

  if (error) {
    return (
      <div className="card">
        <p className="error">{error}</p>
        <p className="muted">
          This link may have expired — please ask your teacher for a new one.
        </p>
      </div>
    );
  }
  if (!view) return <p className="muted">Loading…</p>;

  return (
    <div>
      <h2>{view.student_name} — selected work</h2>
      {view.note && (
        <div className="card">
          <p>{view.note}</p>
          <p className="muted">— note from the teacher</p>
        </div>
      )}
      <div className="card">
        {view.entries.map((entry) => (
          <div className="timeline-entry" key={entry.id}>
            <span className="date">{new Date(entry.entry_date).toLocaleDateString()}</span>
            <span>{entry.summary}</span>
          </div>
        ))}
        {view.entries.length === 0 && <p className="muted">No entries were shared.</p>}
      </div>
    </div>
  );
}
