import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Assignment, Batch } from "../api";
import { useClassroom } from "../classroom";

export default function UploadPage() {
  const { active } = useClassroom();
  const [assignments, setAssignments] = useState<Assignment[]>([]);
  const [assignmentId, setAssignmentId] = useState("");
  const [newTitle, setNewTitle] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [batch, setBatch] = useState<Batch | null>(null);
  const [error, setError] = useState("");
  const pollRef = useRef<number>();
  const navigate = useNavigate();

  useEffect(() => {
    if (!active) return;
    api.listAssignments(active.classroomId).then((rows) => {
      setAssignments(rows);
      if (rows.length > 0) setAssignmentId(rows[0].id);
    });
    return () => window.clearInterval(pollRef.current);
  }, [active]);

  if (!active) return null;

  const createAssignment = async () => {
    if (!newTitle.trim()) return;
    const created = await api.createAssignment(newTitle.trim(), active.classroomId);
    setAssignments([created, ...assignments]);
    setAssignmentId(created.id);
    setNewTitle("");
  };

  const upload = async () => {
    setError("");
    try {
      const created = await api.uploadBatch(assignmentId, files);
      setBatch(created);
      pollRef.current = window.setInterval(async () => {
        const latest = await api.getBatch(created.id);
        setBatch(latest);
        if (latest.status === "ready_for_review" || latest.status === "failed") {
          window.clearInterval(pollRef.current);
        }
      }, 1000);
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="content-narrow">
      <h2>Capture a class set</h2>
      <p className="page-sub">
        Photograph or scan the stack, upload it once, and Inkwell splits it into
        per-student records — verbatim transcription on one track, handwriting
        measurements on the other. You review everything before it counts.
      </p>
      <div className="card">
        <h3><span className="stepno">1</span>Assignment</h3>
        <div className="row">
          {assignments.length > 0 && (
            <select value={assignmentId} onChange={(e) => setAssignmentId(e.target.value)}>
              {assignments.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.title}
                </option>
              ))}
            </select>
          )}
          <input
            placeholder={assignments.length > 0 ? "or a new assignment title" : "Assignment title (e.g. Journal — week 3)"}
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            style={{ flex: 1 }}
          />
          <button className="secondary" type="button" onClick={createAssignment} disabled={!newTitle.trim()}>
            Create
          </button>
        </div>
      </div>
      <div className="card">
        <h3><span className="stepno">2</span>Page photos</h3>
        <input
          type="file"
          accept="image/png,image/jpeg,image/webp"
          multiple
          onChange={(e) => setFiles(Array.from(e.target.files ?? []))}
        />
        <p className="muted">
          One image per page. Pages with a printed QR header match the roster
          automatically; the rest get assigned by hand in Review.
        </p>
        <button onClick={upload} disabled={!assignmentId || files.length === 0}>
          Upload {files.length > 0 ? `${files.length} page${files.length > 1 ? "s" : ""}` : ""} &amp; process
        </button>
        {error && <p className="error">{error}</p>}
      </div>
      {batch && (
        <div className="card">
          <h3>Processing</h3>
          <p>
            <span className={`badge ${batch.status === "ready_for_review" ? "" : "provisional"}`}>
              {batch.status.replace(/_/g, " ")}
            </span>
          </p>
          {batch.error && <p className="error">{batch.error}</p>}
          {batch.status === "ready_for_review" && (
            <button className="mint" onClick={() => navigate(`/review/${batch.id}`)}>
              Open review →
            </button>
          )}
        </div>
      )}
    </div>
  );
}
