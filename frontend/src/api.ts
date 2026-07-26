// Typed client for the hwportfolio API.

export interface School {
  id: string;
  name: string;
}

export interface Teacher {
  id: string;
  school_id: string;
  display_name: string;
  email: string;
}

export interface Classroom {
  id: string;
  teacher_id: string;
  name: string;
  grade_band: string;
  school_year: string;
}

export interface Student {
  id: string;
  external_id: string;
  display_name: string;
  grade_band: string;
  school_year: string;
  classroom_id: string | null;
}

export interface Assignment {
  id: string;
  title: string;
  kind: string;
  subject: string | null;
  classroom_id: string | null;
}

export interface Batch {
  id: string;
  assignment_id: string;
  status: string;
  error: string | null;
  created_at: string;
}

export interface Region {
  id: string;
  order_index: number;
  kind: string;
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Extraction {
  id: string;
  region_id: string;
  verbatim: string;
  normalized: string | null;
  tokens: { text: string; confidence: number; illegible: boolean }[];
  provider: string;
  model_version: string;
  source: string;
  state: string;
  supersedes_id: string | null;
}

export interface Observation {
  id: string;
  artifact_id: string;
  type: string;
  magnitude: number;
  unit: string;
  details: Record<string, unknown>;
  x: number;
  y: number;
  w: number;
  h: number;
  model_version: string;
  state: string;
}

export interface Artifact {
  id: string;
  batch_id: string;
  assignment_id: string;
  student_id: string | null;
  student_match_method: string | null;
  image_uri: string;
  ruled_paper: boolean | null;
}

export interface ArtifactDetail extends Artifact {
  regions: Region[];
  observations: Observation[];
}

export interface TimelineEntry {
  id: string;
  student_id: string;
  entry_date: string;
  kind: string;
  artifact_id: string;
  summary: string;
  payload: Record<string, unknown>;
}

export interface ShareGrant {
  id: string;
  student_id: string;
  token: string;
  included_entry_ids: string[];
  note: string | null;
  expires_at: string;
  revoked_at: string | null;
}

export interface SharedView {
  student_name: string;
  note: string | null;
  entries: TimelineEntry[];
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  listSchools: () => request<School[]>("/api/schools"),
  createSchool: (name: string) => request<School>("/api/schools", json({ name })),
  listTeachers: (schoolId?: string) =>
    request<Teacher[]>(`/api/teachers${schoolId ? `?school_id=${schoolId}` : ""}`),
  createTeacher: (body: Omit<Teacher, "id">) => request<Teacher>("/api/teachers", json(body)),
  listClassrooms: (teacherId?: string) =>
    request<Classroom[]>(`/api/classrooms${teacherId ? `?teacher_id=${teacherId}` : ""}`),
  createClassroom: (body: Omit<Classroom, "id">) =>
    request<Classroom>("/api/classrooms", json(body)),
  listStudents: (classroomId?: string) =>
    request<Student[]>(`/api/students${classroomId ? `?classroom_id=${classroomId}` : ""}`),
  createStudent: (body: Omit<Student, "id">) => request<Student>("/api/students", json(body)),
  listAssignments: (classroomId?: string) =>
    request<Assignment[]>(`/api/assignments${classroomId ? `?classroom_id=${classroomId}` : ""}`),
  createAssignment: (title: string, classroomId?: string) =>
    request<Assignment>("/api/assignments", json({ title, classroom_id: classroomId ?? null })),
  uploadBatch: (assignmentId: string, files: File[]) => {
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    return request<Batch>(`/api/assignments/${assignmentId}/batches`, {
      method: "POST",
      body: form,
    });
  },
  getBatch: (id: string) => request<Batch>(`/api/batches/${id}`),
  batchArtifacts: (id: string) => request<Artifact[]>(`/api/batches/${id}/artifacts`),
  artifactDetail: (id: string) => request<ArtifactDetail>(`/api/artifacts/${id}`),
  artifactExtractions: (id: string) =>
    request<Extraction[]>(`/api/artifacts/${id}/extractions`),
  assignStudent: (artifactId: string, studentId: string) =>
    request(`/api/review/artifacts/${artifactId}/assign-student`, json({ student_id: studentId })),
  commitExtraction: (id: string) =>
    request<TimelineEntry>(`/api/review/extractions/${id}/commit`, { method: "POST" }),
  correctExtraction: (id: string, verbatim: string) =>
    request<Extraction>(`/api/review/extractions/${id}/correct`, json({ verbatim })),
  rejectExtraction: (id: string) =>
    request(`/api/review/extractions/${id}/reject`, { method: "POST" }),
  commitObservation: (id: string) =>
    request<TimelineEntry>(`/api/review/observations/${id}/commit`, { method: "POST" }),
  rejectObservation: (id: string) =>
    request(`/api/review/observations/${id}/reject`, { method: "POST" }),
  timeline: (studentId: string, observationType?: string) => {
    const qs = observationType ? `?observation_type=${encodeURIComponent(observationType)}` : "";
    return request<TimelineEntry[]>(`/api/students/${studentId}/timeline${qs}`);
  },
  createShare: (studentId: string, entryIds: string[], note: string | null) =>
    request<ShareGrant>("/api/shares", json({
      student_id: studentId,
      included_entry_ids: entryIds,
      note: note || null,
    })),
  sharedView: (token: string) => request<SharedView>(`/api/shared/${token}`),
};

export function mediaUrl(imageUri: string): string {
  return imageUri.replace("local://", "/media/");
}
