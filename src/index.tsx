import { callable, definePlugin } from "@decky/api";
import {
  ButtonItem,
  DialogButton,
  Focusable,
  PanelSection,
  PanelSectionRow,
  staticClasses,
} from "@decky/ui";
import { useEffect, useState, FC } from "react";
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

const listProfiles = callable<[], { profiles: ProfileEntry[] }>("list_profiles");
const installProfile = callable<[string], any>("install_profile");
const installAll = callable<[], { installed: string[]; failed: string[] }>("install_all");
const removeProfile = callable<[string], any>("remove_profile");
const getStatus = callable<[], Status>("status");

const Content: FC = () => {
  const [profiles, setProfiles] = useState<ProfileEntry[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const refresh = async () => {
    try {
      setStatus(await getStatus());
      setProfiles((await listProfiles()).profiles);
    } catch (e) {
      setNote(`Could not read profiles: ${e}`);
    }
  };

  useEffect(() => {
    refresh();
  }, []);

  const doInstall = async (p: ProfileEntry) => {
    setBusy(true);
    setNote("");
    try {
      const res = await installProfile(p.path ?? "");
      setNote(
        res?.ok
          ? `${p.title} installed — restart Steam, then pick it under Templates.`
          : `Failed: ${res?.error ?? "unknown error"}`
      );
    } catch (e) {
      setNote(`Failed: ${e}`);
    }
    setBusy(false);
    await refresh();
  };

  const doInstallAll = async () => {
    setBusy(true);
    setNote("");
    try {
      const res = await installAll();
      const n = res.installed.length;
      setNote(
        `Installed ${n} profile${n === 1 ? "" : "s"}` +
          (res.failed.length ? `, ${res.failed.length} failed` : "") +
          ". Restart Steam to see them under Templates."
      );
    } catch (e) {
      setNote(`Failed: ${e}`);
    }
    setBusy(false);
    await refresh();
  };

  const doRemove = async (p: ProfileEntry) => {
    setBusy(true);
    await removeProfile(p.title);
    setBusy(false);
    await refresh();
  };

  if (status && !status.ready) {
    return (
      <PanelSection title="PadPilot">
        <PanelSectionRow>
          {status.workshop_dirs.length === 0
            ? "No Controller Companion profiles found. Subscribe to some on the Workshop, then press Rescan."
            : "Steam's controller templates folder wasn't found."}
        </PanelSectionRow>
      </PanelSection>
    );
  }

  return (
    <>
      <PanelSection title={`Profiles (${profiles.length})`}>
        <PanelSectionRow>
          <ButtonItem layout="below" disabled={busy || !profiles.length} onClick={doInstallAll}>
            Convert and install all
          </ButtonItem>
        </PanelSectionRow>
        {note ? (
          <PanelSectionRow>
            <div style={{ fontSize: "0.8em" }}>{note}</div>
          </PanelSectionRow>
        ) : null}
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
                <DialogButton disabled={busy || !!p.error} onClick={() => doInstall(p)}>
                  {p.installed ? "Reinstall" : "Install"}
                </DialogButton>
                {p.installed ? (
                  <DialogButton disabled={busy} onClick={() => doRemove(p)}>
                    Remove
                  </DialogButton>
                ) : null}
                {p.dropped.length ? (
                  <DialogButton onClick={() => setExpanded(expanded === p.id ? null : p.id)}>
                    {expanded === p.id ? "Hide" : "Details"}
                  </DialogButton>
                ) : null}
              </Focusable>
              {expanded === p.id ? (
                <div style={{ fontSize: "0.75em", opacity: 0.75 }}>
                  Steam Input has no secondary layer and cannot launch programs, so these
                  are skipped:
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

export default definePlugin(() => ({
  name: "PadPilot",
  titleView: <div className={staticClasses.Title}>PadPilot</div>,
  content: <Content />,
  icon: <FaGamepad />,
}));
