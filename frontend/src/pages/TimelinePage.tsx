// The per-student portal — the durable asset (GOALS T1). Trajectory is shown
// against the student's own history only: no cross-student comparison, no
// ranking, no red/failing states (GOALS §7 C2).
import { useEffect, useState } from "react";
import { api, ShareGrant, Student, TimelineEntry } from "../api";
import { useClassroom } from "../classroom";

const OBSERVATION_TYPES = [
  "",
  "reversal_candidate",
  "baseline_adherence",
  "xheight_consistency",
  "spacing_ratio",
  "slant_consistency",
  "line_drift",
];

export default function TimelinePage() {
  const { active } = useClassroom();
  const [students, setStudents] = useState<Student[]>([]);
  const [studentId, setStudentId] = useState("");
  const [filter, setFilter] = useState("");
  const [entries, setEntries] = useState<TimelineEntry[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [note, setNote] = useState("");
  const [grant, setGrant] = useState<ShareGrant | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listStudents(active?.classroomId).then((rows) => {
      setStudents(rows);
      if (rows.length > 0) setStudentId(rows[0].id);
    });
  }, [active]);

  useEffect(() => {
    if (!studentId) return;
    setGrant(null);
    setSelectedIds(new Set());
    api.timeline(studentId, filter || undefined).then(setEntries).catch((e) => setError(e.message));
  }, [studentId, filter]);

  const toggle = (id: string) => {
    const next = new Set(selectedIds);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelectedIds(next);
  };

  const share = async () => {
    setError("");
    try {
      const created = await api.createShare(studentId, Array.from(selectedIds), note);
      setGrant(created);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const student = students.find((s) => s.id === studentId);

  return (
    <div className="content-narrow">
      <h2>Student timeline</h2>
      <p className="page-sub">
        The record that compounds: each student's committed work over the year,
        always measured against their own earlier pages — never against
        classmates.
      </p>
      <div className="card row">
        <select value={studentId} onChange={(e) => setStudentId(e.target.value)}>
          {students.map((s) => (
            <option key={s.id} value={s.id}>
              {s.display_name}
            </option>
          ))}
        </select>
        <select value={filter} onChange={(e) => setFilter(e.target.value)}>
          {OBSERVATION_TYPES.map((t) => (
            <option key={t} value={t}>
              {t === "" ? "All entries" : t.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>
      <div className="card">
        {entries.length === 0 && (
          <p className="muted">
            Nothing committed yet{student ? ` for ${student.display_name}` : ""}.
            Records appear here only after you commit them in Review.
          </p>
        )}
        {entries.map((entry) => (
          <div className="timeline-entry" key={entry.id}>
            <label className="row" style={{ gap: "0.4rem" }}>
              <input
                type="checkbox"
                checked={selectedIds.has(entry.id)}
                onChange={() => toggle(entry.id)}
              />
            </label>
            <span className="date">{new Date(entry.entry_date).toLocaleDateString()}</span>
            <span className="badge">{entry.kind}</span>
            <span>{entry.summary}</span>
          </div>
        ))}
      </div>
      {entries.length > 0 && (
        <div className="card">
          <h3>Share with a parent</h3>
          <p className="muted">
            Nothing is shared by default. Tick the entries above that you want a
            parent to see, add an optional note, and generate an expiring link.
            Every view of the link is logged.
          </p>
          <textarea
            placeholder="Optional note to the parent (describe what's on the page — the system will reject clinical language)"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            rows={2}
            style={{ width: "100%", marginBottom: "0.5rem" }}
          />
          <button onClick={share} disabled={selectedIds.size === 0}>
            Create share link ({selectedIds.size} entr{selectedIds.size === 1 ? "y" : "ies"})
          </button>
          {error && <p className="error">{error}</p>}
          {grant && (
            <p>
              Link (expires {new Date(grant.expires_at).toLocaleString()}):{" "}
              <a href={`/shared/${grant.token}`} target="_blank" rel="noreferrer">
                {window.location.origin}/shared/{grant.token.slice(0, 12)}…
              </a>
            </p>
          )}
        </div>
      )}
    </div>
  );
}
