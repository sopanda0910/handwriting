// Active-classroom context. Alpha has no authentication: the selected
// classroom (with its teacher/school labels) is remembered locally and scopes
// roster, assignments, and timelines.
import { createContext, useContext, useEffect, useState } from "react";

export interface ActiveClassroom {
  classroomId: string;
  classroomName: string;
  gradeBand: string;
  schoolYear: string;
  teacherName: string;
  schoolName: string;
}

interface ClassroomContextValue {
  active: ActiveClassroom | null;
  setActive: (value: ActiveClassroom | null) => void;
}

const ClassroomContext = createContext<ClassroomContextValue>({
  active: null,
  setActive: () => {},
});

const STORAGE_KEY = "inkwell.activeClassroom";

export function ClassroomProvider({ children }: { children: React.ReactNode }) {
  const [active, setActiveState] = useState<ActiveClassroom | null>(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? (JSON.parse(raw) as ActiveClassroom) : null;
    } catch {
      return null;
    }
  });

  useEffect(() => {
    if (active) localStorage.setItem(STORAGE_KEY, JSON.stringify(active));
    else localStorage.removeItem(STORAGE_KEY);
  }, [active]);

  return (
    <ClassroomContext.Provider value={{ active, setActive: setActiveState }}>
      {children}
    </ClassroomContext.Provider>
  );
}

export function useClassroom() {
  return useContext(ClassroomContext);
}
