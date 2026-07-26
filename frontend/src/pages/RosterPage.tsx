import { useCallback, useEffect, useState } from "react";
import { api, Student } from "../api";
import { useClassroom } from "../classroom";

export default function RosterPage() {
  const { active } = useClassroom();
  const [students, setStudents] = useState<Student[]>([]);
  const [error, setError] = useState("");
  const [form, setForm] = useState({ external_id: "", display_name: "" });

  const load = useCallback(() => {
    if (!active) return;
    api.listStudents(active.classroomId).then(setStudents).catch((e) => setError(e.message));
  }, [active]);

  useEffect(load, [load]);

  if (!active) return null;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setError("");
    try {
      await api.createStudent({
        ...form,
        grade_band: active.gradeBand,
        school_year: active.schoolYear,
        classroom_id: active.classroomId,
      });
      setForm({ external_id: "", display_name: "" });
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="content-narrow">
      <h2>Roster</h2>
      <p className="page-sub">
        {active.classroomName} · Grade {active.gradeBand} · {active.schoolYear}.
        Only a display name and an internal ID are stored — no birthdates, no
        demographics.
      </p>
      <div className="card">
        <form onSubmit={submit} className="row">
          <input
            placeholder="Student ID (e.g. S001)"
            value={form.external_id}
            onChange={(e) => setForm({ ...form, external_id: e.target.value })}
            required
            style={{ width: "11rem" }}
          />
          <input
            placeholder="Display name"
            value={form.display_name}
            onChange={(e) => setForm({ ...form, display_name: e.target.value })}
            required
            style={{ flex: 1 }}
          />
          <button type="submit">Add student</button>
        </form>
        {error && <p className="error">{error}</p>}
      </div>
      <div className="card">
        {students.length === 0 ? (
          <div className="empty">
            <span className="hand">a fresh page…</span>
            Add your class, then print a QR label for each student — stapled or
            printed on a worksheet, it matches their pages automatically.
          </div>
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Name</th>
                <th>QR header label</th>
              </tr>
            </thead>
            <tbody>
              {students.map((s) => (
                <tr key={s.id}>
                  <td>{s.external_id}</td>
                  <td>{s.display_name}</td>
                  <td>
                    <a href={`/api/students/${s.id}/qr.png`} target="_blank" rel="noreferrer">
                      print label
                    </a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
