// The review step is the product, not a formality (GOALS §5.1). Every commit
// here is the explicit teacher action that makes a record real.
import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import {
  api,
  Artifact,
  ArtifactDetail,
  Extraction,
  Observation,
  Student,
  mediaUrl,
} from "../api";
import { useClassroom } from "../classroom";

export default function ReviewPage() {
  const { batchId } = useParams();
  const { active } = useClassroom();
  const [batchInput, setBatchInput] = useState(batchId ?? "");
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [selected, setSelected] = useState<ArtifactDetail | null>(null);
  const [extractions, setExtractions] = useState<Extraction[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listStudents(active?.classroomId).then(setStudents);
  }, [active]);

  const loadBatch = useCallback(async (id: string) => {
    setError("");
    try {
      const rows = await api.batchArtifacts(id);
      setArtifacts(rows);
      if (rows.length > 0) selectArtifact(rows[0].id);
    } catch (e) {
      setError((e as Error).message);
    }
  }, []);

  useEffect(() => {
    if (batchId) loadBatch(batchId);
  }, [batchId, loadBatch]);

  const selectArtifact = async (id: string) => {
    const [detail, exts] = await Promise.all([
      api.artifactDetail(id),
      api.artifactExtractions(id),
    ]);
    setSelected(detail);
    setExtractions(exts);
  };

  const refresh = () => selected && selectArtifact(selected.id);

  return (
    <div>
      <h2>Review</h2>
      <p className="page-sub">
        Nothing reaches a student's timeline until you commit it here. Verbatim
        text keeps the student's own spelling — that's the signal, not a
        mistake to fix.
      </p>
      {!batchId && (
        <div className="card row">
          <input
            placeholder="Paste a batch id, or open Review from a finished upload"
            value={batchInput}
            onChange={(e) => setBatchInput(e.target.value)}
            style={{ flex: 1, maxWidth: "26rem" }}
          />
          <button onClick={() => loadBatch(batchInput)} disabled={!batchInput.trim()}>
            Load batch
          </button>
        </div>
      )}
      {error && <p className="error">{error}</p>}
      {artifacts.length > 0 && (
        <div className="card row">
          {artifacts.map((a, i) => (
            <button
              key={a.id}
              className={selected?.id === a.id ? undefined : "secondary"}
              onClick={() => selectArtifact(a.id)}
            >
              Page {i + 1}
              {a.student_id === null ? " (unmatched)" : ""}
            </button>
          ))}
        </div>
      )}
      {selected && (
        <ArtifactReview
          artifact={selected}
          extractions={extractions}
          students={students}
          onChange={refresh}
        />
      )}
    </div>
  );
}

function ArtifactReview(props: {
  artifact: ArtifactDetail;
  extractions: Extraction[];
  students: Student[];
  onChange: () => void;
}) {
  const { artifact, extractions, students, onChange } = props;
  const [assignTo, setAssignTo] = useState("");
  const [actionError, setActionError] = useState("");

  const act = async (fn: () => Promise<unknown>) => {
    setActionError("");
    try {
      await fn();
      onChange();
    } catch (e) {
      setActionError((e as Error).message);
    }
  };

  const matchedStudent = students.find((s) => s.id === artifact.student_id);
  const reviewable = artifact.observations.filter((o) => o.state !== "suppressed");

  return (
    <div className="grid2">
      <div className="card">
        <h3>Page image</h3>
        <PageImage artifact={artifact} />
        <p className="muted">
          {artifact.ruled_paper ? "Ruled paper detected." : "No printed rules detected — baseline measurements are suppressed on this page."}
        </p>
        <h3>Student</h3>
        {matchedStudent ? (
          <p>
            <span className="badge">{matchedStudent.display_name}</span>{" "}
            <span className="muted">matched via {artifact.student_match_method}</span>
          </p>
        ) : (
          <div className="row">
            <select value={assignTo} onChange={(e) => setAssignTo(e.target.value)}>
              <option value="">Select student…</option>
              {students.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.display_name}
                </option>
              ))}
            </select>
            <button
              disabled={!assignTo}
              onClick={() => act(() => api.assignStudent(artifact.id, assignTo))}
            >
              Assign
            </button>
          </div>
        )}
      </div>
      <div className="card">
        <h3>Transcriptions (verbatim)</h3>
        <p className="muted">
          Exactly what is on the page — the student's spelling is the signal,
          never "corrected". Fix transcription mistakes with Correct; the
          original is kept and superseded.
        </p>
        {extractions.filter((e) => e.state !== "superseded").map((extraction) => (
          <ExtractionRow key={extraction.id} extraction={extraction} act={act} />
        ))}
        <h3>Observations</h3>
        {reviewable.length === 0 && <p className="muted">No observations on this page.</p>}
        {reviewable.map((o) => (
          <ObservationRow key={o.id} observation={o} act={act} />
        ))}
        {actionError && <p className="error">{actionError}</p>}
      </div>
    </div>
  );
}

function PageImage({ artifact }: { artifact: ArtifactDetail }) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [scale, setScale] = useState(0);

  const onLoad = () => {
    const img = imgRef.current;
    if (img && img.naturalWidth > 0) setScale(img.clientWidth / img.naturalWidth);
  };

  const reversals = artifact.observations.filter(
    (o) => o.type === "reversal_candidate" && o.state !== "rejected",
  );

  return (
    <div className="artifact-view">
      <img ref={imgRef} src={mediaUrl(artifact.image_uri)} onLoad={onLoad} alt="student page" />
      {scale > 0 &&
        reversals.map((o) => (
          <div
            key={o.id}
            className="bbox reversal"
            style={{
              left: o.x * scale,
              top: o.y * scale,
              width: o.w * scale,
              height: o.h * scale,
            }}
          >
            <span className="bbox-label">formed as "{String(o.details.shape)}"</span>
          </div>
        ))}
    </div>
  );
}

function ExtractionRow(props: {
  extraction: Extraction;
  act: (fn: () => Promise<unknown>) => void;
}) {
  const { extraction, act } = props;
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(extraction.verbatim);

  return (
    <div style={{ marginBottom: "1rem" }}>
      <div className="verbatim">{extraction.verbatim || "(empty region)"}</div>
      {extraction.normalized && extraction.normalized !== extraction.verbatim && (
        <p className="muted">Search text (never shown as the student's writing): {extraction.normalized}</p>
      )}
      <div className="row" style={{ marginTop: "0.4rem" }}>
        <span className={`badge ${extraction.state}`}>{extraction.state}</span>
        <span className="muted">
          {extraction.provider} · {extraction.model_version}
        </span>
        {extraction.state === "provisional" && !editing && (
          <>
            <button onClick={() => act(() => api.commitExtraction(extraction.id))}>
              Commit
            </button>
            <button className="secondary" onClick={() => setEditing(true)}>
              Correct
            </button>
            <button className="ghost" onClick={() => act(() => api.rejectExtraction(extraction.id))}>
              Discard
            </button>
          </>
        )}
      </div>
      {editing && (
        <div className="row" style={{ marginTop: "0.4rem" }}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            rows={2}
            style={{ width: "100%" }}
          />
          <button
            onClick={() => {
              setEditing(false);
              act(() => api.correctExtraction(extraction.id, draft));
            }}
          >
            Save correction
          </button>
          <button className="ghost" onClick={() => setEditing(false)}>
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

function ObservationRow(props: {
  observation: Observation;
  act: (fn: () => Promise<unknown>) => void;
}) {
  const { observation, act } = props;
  const label =
    observation.type === "reversal_candidate"
      ? `Letter formed as "${String(observation.details.shape)}" — confirm?`
      : `${observation.type.replace(/_/g, " ")}: ${observation.magnitude.toFixed(2)} ${observation.unit}`;
  return (
    <div className="row" style={{ marginBottom: "0.45rem" }}>
      <span className={`badge ${observation.state}`}>{observation.state}</span>
      <span>{label}</span>
      {observation.state === "provisional" && (
        <>
          <button onClick={() => act(() => api.commitObservation(observation.id))}>
            Commit
          </button>
          <button
            className="ghost"
            onClick={() => act(() => api.rejectObservation(observation.id))}
          >
            Discard
          </button>
        </>
      )}
    </div>
  );
}
