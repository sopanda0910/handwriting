// Onboarding wizard: School -> Teacher -> Classroom. Ends by activating the
// classroom that scopes the rest of the app.
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, Classroom, School, Teacher } from "../api";
import { Wordmark } from "../brand";
import { useClassroom } from "../classroom";

export default function SetupPage() {
  const [school, setSchool] = useState<School | null>(null);
  const [teacher, setTeacher] = useState<Teacher | null>(null);
  const step = school === null ? 0 : teacher === null ? 1 : 2;

  return (
    <div className="wizard">
      <div className="wizard-hero">
        <Wordmark />
        <p>
          Set up your classroom in three steps. Everything you capture — pages,
          transcriptions, observations — lives under this classroom for the
          school year.
        </p>
      </div>
      <div className="steps">
        {["School", "Teacher", "Classroom"].map((label, index) => (
          <span key={label} className="row" style={{ gap: "0.5rem" }}>
            {index > 0 && <span className="step-connector" />}
            <span
              className={`step-dot ${index < step ? "done" : index === step ? "current" : ""}`}
              title={label}
            >
              {index < step ? "✓" : index + 1}
            </span>
          </span>
        ))}
      </div>
      {step === 0 && <SchoolStep onPick={setSchool} />}
      {step === 1 && school && (
        <TeacherStep school={school} onPick={setTeacher} onBack={() => setSchool(null)} />
      )}
      {step === 2 && school && teacher && (
        <ClassroomStep school={school} teacher={teacher} onBack={() => setTeacher(null)} />
      )}
    </div>
  );
}

function SchoolStep({ onPick }: { onPick: (s: School) => void }) {
  const [schools, setSchools] = useState<School[]>([]);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.listSchools().then(setSchools).catch((e) => setError(e.message));
  }, []);

  const create = async () => {
    setError("");
    try {
      onPick(await api.createSchool(name));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="card">
      <h3>Your school</h3>
      {schools.length > 0 && (
        <>
          <div className="pick-list">
            {schools.map((s) => (
              <button key={s.id} type="button" onClick={() => onPick(s)}>
                {s.name}
              </button>
            ))}
          </div>
          <div className="divider">or register a new one</div>
        </>
      )}
      <div className="row">
        <input
          placeholder="School name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          style={{ flex: 1 }}
        />
        <button onClick={create} disabled={!name.trim()}>
          Continue
        </button>
      </div>
      {error && <p className="error">{error}</p>}
    </div>
  );
}

function TeacherStep(props: {
  school: School;
  onPick: (t: Teacher) => void;
  onBack: () => void;
}) {
  const { school, onPick, onBack } = props;
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [form, setForm] = useState({ display_name: "", email: "" });
  const [error, setError] = useState("");

  useEffect(() => {
    api.listTeachers(school.id).then(setTeachers).catch((e) => setError(e.message));
  }, [school.id]);

  const create = async () => {
    setError("");
    try {
      onPick(await api.createTeacher({ school_id: school.id, ...form }));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="card">
      <h3>Who's teaching? <span className="muted">({school.name})</span></h3>
      {teachers.length > 0 && (
        <>
          <div className="pick-list">
            {teachers.map((t) => (
              <button key={t.id} type="button" onClick={() => onPick(t)}>
                {t.display_name} <span className="sub">{t.email}</span>
              </button>
            ))}
          </div>
          <div className="divider">or add yourself</div>
        </>
      )}
      <div className="row">
        <input
          placeholder="Your name (e.g. Ms. Rivera)"
          value={form.display_name}
          onChange={(e) => setForm({ ...form, display_name: e.target.value })}
        />
        <input
          placeholder="Email"
          type="email"
          value={form.email}
          onChange={(e) => setForm({ ...form, email: e.target.value })}
        />
        <button onClick={create} disabled={!form.display_name.trim() || !form.email.trim()}>
          Continue
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <p>
        <button className="ghost" onClick={onBack}>← back</button>
      </p>
    </div>
  );
}

function ClassroomStep(props: { school: School; teacher: Teacher; onBack: () => void }) {
  const { school, teacher, onBack } = props;
  const { setActive } = useClassroom();
  const navigate = useNavigate();
  const [rooms, setRooms] = useState<Classroom[]>([]);
  const [form, setForm] = useState({ name: "", grade_band: "1", school_year: "2026-2027" });
  const [error, setError] = useState("");

  useEffect(() => {
    api.listClassrooms(teacher.id).then(setRooms).catch((e) => setError(e.message));
  }, [teacher.id]);

  const activate = (room: Classroom) => {
    setActive({
      classroomId: room.id,
      classroomName: room.name,
      gradeBand: room.grade_band,
      schoolYear: room.school_year,
      teacherName: teacher.display_name,
      schoolName: school.name,
    });
    navigate("/upload");
  };

  const create = async () => {
    setError("");
    try {
      activate(await api.createClassroom({ teacher_id: teacher.id, ...form }));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="card">
      <h3>
        Your classroom <span className="muted">({teacher.display_name})</span>
      </h3>
      {rooms.length > 0 && (
        <>
          <div className="pick-list">
            {rooms.map((room) => (
              <button key={room.id} type="button" onClick={() => activate(room)}>
                {room.name}
                <span className="sub">
                  Grade {room.grade_band} · {room.school_year}
                </span>
              </button>
            ))}
          </div>
          <div className="divider">or create a new classroom</div>
        </>
      )}
      <div className="row">
        <input
          placeholder="Classroom name (e.g. Room 12)"
          value={form.name}
          onChange={(e) => setForm({ ...form, name: e.target.value })}
        />
        <select
          value={form.grade_band}
          onChange={(e) => setForm({ ...form, grade_band: e.target.value })}
        >
          {["K", "1", "2", "3", "4", "5"].map((g) => (
            <option key={g} value={g}>
              Grade {g}
            </option>
          ))}
        </select>
        <input
          value={form.school_year}
          onChange={(e) => setForm({ ...form, school_year: e.target.value })}
          style={{ width: "7.2rem" }}
        />
        <button className="mint" onClick={create} disabled={!form.name.trim()}>
          Start the year
        </button>
      </div>
      {error && <p className="error">{error}</p>}
      <p>
        <button className="ghost" onClick={onBack}>← back</button>
      </p>
    </div>
  );
}
