import {
  ButtonItem,
  definePlugin,
  DialogButton,
  Focusable,
  PanelSection,
  PanelSectionRow,
  ServerAPI,
  staticClasses,
} from "decky-frontend-lib";
import { useEffect, useState, VFC } from "react";
import { FaGamepad } from "react-icons/fa";

interface ProfileEntry {
  id: string;
  title: string;
  processes?: string[];
  bindings: number;
  dropped: string[];
  installed: boolean;
  path?: string;
  error?: string;
}

interface Status {
  workshop_dirs: string[];
  template_dirs: string[];
  subscribed: number;
  ready: boolean;
}

const Content: VFC<{ serverAPI: ServerAPI }> = ({ serverAPI }) => {
  const [profiles, setProfiles] = useState<ProfileEntry[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string>("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const refresh = async () => {
    const st = await serverAPI.callPluginMethod<{}, Status>("status", {});
    if (st.success) setStatus(st.result);
    const res = await serverAPI.callPluginMethod<{}, { profiles: ProfileEntry[] }>(
      "list_profiles",
      {}
    );
    if (res.success) setProfiles(res.result.profiles);
  };

  useEffect(() => {
    refresh();
  }, []);

  const install = async (p: ProfileEntry) => {
    setBusy(true);
    setNote("");
    const res = await serverAPI.callPluginMethod<{ path: string }, any>(
      "install_profile",
      { path: p.path ?? "" }
    );
    setBusy(false);
    if (res.success && res.result?.ok) {
      setNote(`${p.title} installed — restart Steam, then pick it under Templates.`);
      await refresh();
    } else {
      setNote(`Failed: ${res.result?.error ?? "unknown error"}`);
    }
  };

  const installAll = async () => {
    setBusy(true);
    setNote("");
    const res = await serverAPI.callPluginMethod<{}, any>("install_all", {});
    setBusy(false);
    if (res.success) {
      const n = res.result.installed.length;
      const f = res.result.failed.length;
      setNote(
        `Installed ${n} profile${n === 1 ? "" : "s"}${f ? `, ${f} failed` : ""}. ` +
          `Restart Steam to see them under Templates.`
      );
      await refresh();
    }
  };

  const remove = async (p: ProfileEntry) => {
    setBusy(true);
    await serverAPI.callPluginMethod<{ title: string }, any>("remove_profile", {
      title: p.title,
    });
    setBusy(false);
    await refresh();
  };

  if (status && !status.ready) {
    return (
      <PanelSection title="PadPilot">
        <PanelSectionRow>
          {status.workshop_dirs.length === 0
            ? "No Controller Companion profiles found. Subscribe to some on the Workshop, then come back."
            : "Steam's controller templates folder wasn't found."}
        </PanelSectionRow>
      </PanelSection>
    );
  }

  return (
    <>
      <PanelSection title={`Profiles (${profiles.length})`}>
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy || !profiles.length} onClick={installAll}>
            Convert and install all
          </ButtonItem>
        </PanelSectionRow>
        {note ? <PanelSectionRow>{note}</PanelSectionRow> : null}
      </PanelSection>

      <PanelSection title="Subscribed">
        {profiles.map((p) => (
          <PanelSectionRow key={p.id}>
            <Focusable style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
              <div style={{ fontWeight: "bold" }}>
                {p.title} {p.installed ? "✓" : ""}
              </div>
              <div style={{ fontSize: "0.8em", opacity: 0.7 }}>
                {p.error
                  ? `unreadable: ${p.error}`
                  : `${p.bindings} bindings` +
                    (p.dropped.length ? ` · ${p.dropped.length} can't convert` : "") +
                    (p.processes?.length ? ` · ${p.processes.join(", ")}` : "")}
              </div>
              <Focusable style={{ display: "flex", gap: "6px" }}>
                <DialogButton disabled={busy || !!p.error} onClick={() => install(p)}>
                  {p.installed ? "Reinstall" : "Install"}
                </DialogButton>
                {p.installed ? (
                  <DialogButton disabled={busy} onClick={() => remove(p)}>
                    Remove
                  </DialogButton>
                ) : null}
                {p.dropped.length ? (
                  <DialogButton
                    onClick={() => setExpanded(expanded === p.id ? null : p.id)}
                  >
                    {expanded === p.id ? "Hide" : "Details"}
                  </DialogButton>
                ) : null}
              </Focusable>
              {expanded === p.id ? (
                <div style={{ fontSize: "0.75em", opacity: 0.75 }}>
                  Steam Input has no secondary layer and cannot launch programs, so
                  these are skipped:
                  <ul style={{ margin: "4px 0 0 12px" }}>
                    {p.dropped.map((d, i) => (
                      <li key={i}>{d}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </Focusable>
          </PanelSectionRow>
        ))}
      </PanelSection>

      <PanelSection title="Where things are">
        <PanelSectionRow>
          <div style={{ fontSize: "0.75em", opacity: 0.7 }}>
            {status?.subscribed ?? 0} subscribed · templates:{" "}
            {status?.template_dirs?.[0] ?? "not found"}
          </div>
        </PanelSectionRow>
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy} onClick={refresh}>
            Rescan
          </ButtonItem>
        </PanelSectionRow>
      </PanelSection>
    </>
  );
};

export default definePlugin((serverApi: ServerAPI) => ({
  title: <div className={staticClasses.Title}>PadPilot</div>,
  content: <Content serverAPI={serverApi} />,
  icon: <FaGamepad />,
}));
