import { NavLink, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Wordmark } from "./brand";
import { ClassroomProvider, useClassroom } from "./classroom";
import SetupPage from "./pages/SetupPage";
import RosterPage from "./pages/RosterPage";
import UploadPage from "./pages/UploadPage";
import ReviewPage from "./pages/ReviewPage";
import TimelinePage from "./pages/TimelinePage";
import SharedViewPage from "./pages/SharedViewPage";

const NAV = [
  { to: "/roster", label: "Roster", icon: "M8 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6zm-6 6c0-2.5 2.7-4 6-4s6 1.5 6 4v1H2v-1z" },
  { to: "/upload", label: "Capture", icon: "M2 5a2 2 0 0 1 2-2h1l1-1.5h4L11 3h1a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5zm6 6a3 3 0 1 0 0-6 3 3 0 0 0 0 6z" },
  { to: "/review", label: "Review", icon: "M2 3h9v2H2V3zm0 4h12v2H2V7zm0 4h7v2H2v-2zm10.5.5 1.5 1.5 3-3-1-1-2 2-.5-.5-1 1z" },
  { to: "/timeline", label: "Timelines", icon: "M3 2h2v12H3V2zm4 4h2v8H7V6zm4-3h2v11h-2V3z" },
];

function Sidebar() {
  const { active } = useClassroom();
  return (
    <aside className="sidebar">
      <Wordmark />
      {active && (
        <div className="classroom-chip">
          <div className="room">{active.classroomName}</div>
          <div className="meta">
            {active.teacherName} · {active.schoolName}
          </div>
          <div className="meta">
            Grade {active.gradeBand} · {active.schoolYear} · <NavLink to="/setup">switch</NavLink>
          </div>
        </div>
      )}
      <nav className="sidenav">
        {NAV.map((item) => (
          <NavLink key={item.to} to={item.to}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden>
              <path d={item.icon} />
            </svg>
            {item.label}
          </NavLink>
        ))}
      </nav>
      <div className="sidebar-foot">
        Records what is on the page — never a judgment about a child. Every
        entry traces back to a rectangle on a photograph.
      </div>
    </aside>
  );
}

function RequireClassroom({ children }: { children: React.ReactNode }) {
  const { active } = useClassroom();
  if (!active) return <Navigate to="/setup" replace />;
  return <>{children}</>;
}

function AppRoutes() {
  const location = useLocation();
  const isPublic = location.pathname.startsWith("/shared/");

  if (isPublic) {
    return (
      <div className="public-shell">
        <div className="public-brand">
          <Wordmark />
        </div>
        <Routes>
          <Route path="/shared/:token" element={<SharedViewPage />} />
        </Routes>
      </div>
    );
  }

  return (
    <div className="app">
      <Sidebar />
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/upload" replace />} />
          <Route path="/setup" element={<SetupPage />} />
          <Route path="/roster" element={<RequireClassroom><RosterPage /></RequireClassroom>} />
          <Route path="/upload" element={<RequireClassroom><UploadPage /></RequireClassroom>} />
          <Route path="/review" element={<RequireClassroom><ReviewPage /></RequireClassroom>} />
          <Route path="/review/:batchId" element={<RequireClassroom><ReviewPage /></RequireClassroom>} />
          <Route path="/timeline" element={<RequireClassroom><TimelinePage /></RequireClassroom>} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <ClassroomProvider>
      <AppRoutes />
    </ClassroomProvider>
  );
}
