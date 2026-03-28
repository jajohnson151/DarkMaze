const SESSION = "default";
const WS_URL = `ws://${window.location.hostname}:8000/ws/${SESSION}`;

let onboardingContinueClicked = false;

type PlayerView = {
  sessionMode: string;
  paused: boolean;
  playerStatsReady: boolean;
  briefing?: { welcome?: string; goals?: string; commandsHelp?: string };
  walls: { left: boolean; right: boolean; forward: boolean; behind: boolean };
  hazard?: string | null;
  item?: string | null;
  pendingHeardCues: { relDirection8: number; phrase: string; distanceLabel: string }[];
  gameOver?: string | null;
};

const el = (id: string) => document.getElementById(id)!;

function setWallBar(id: string, show: boolean, text: string) {
  const n = el(id);
  if (show) {
    n.classList.remove("hidden");
    n.textContent = text;
  } else {
    n.classList.add("hidden");
  }
}

function renderView(v: PlayerView) {
  el("paused-banner").classList.toggle("hidden", !v.paused);
  const gameLocked = v.paused || !v.playerStatsReady || v.sessionMode !== "play";
  document.querySelectorAll(".actions button").forEach((b) => {
    (b as HTMLButtonElement).disabled = gameLocked || !!v.gameOver;
  });

  if (v.sessionMode !== "play") {
    el("waiting").classList.remove("hidden");
    el("waiting").textContent = "Waiting for GM to start play…";
    el("onboarding").classList.add("hidden");
    el("stats").classList.add("hidden");
    el("game").classList.add("hidden");
    return;
  }
  el("waiting").classList.add("hidden");

  if (!v.playerStatsReady) {
    el("game").classList.add("hidden");
    if (!onboardingContinueClicked) {
      const ob = el("onboarding");
      ob.classList.remove("hidden");
      const b = v.briefing;
      ob.innerHTML = `
      <h2>${escapeHtml(b?.welcome ?? "Welcome to Dark Maze!")}</h2>
      <p>${escapeHtml(b?.goals ?? "")}</p>
      <pre style="white-space:pre-wrap">${escapeHtml(b?.commandsHelp ?? "")}</pre>
      <button type="button" id="ob-go">Continue to stats</button>`;
      el("stats").classList.add("hidden");
      document.getElementById("ob-go")!.onclick = () => {
        onboardingContinueClicked = true;
        ob.classList.add("hidden");
        el("stats").classList.remove("hidden");
      };
    } else {
      el("onboarding").classList.add("hidden");
      el("stats").classList.remove("hidden");
    }
    return;
  }

  el("onboarding").classList.add("hidden");
  el("stats").classList.add("hidden");
  el("game").classList.remove("hidden");

  setWallBar("w-top", v.walls.forward, "WALL IN FRONT");
  setWallBar("w-bot", v.walls.behind, "WALL BEHIND");
  setWallBar("w-left", v.walls.left, "WALL LEFT");
  setWallBar("w-right", v.walls.right, "WALL RIGHT");

  const c = el("center");
  c.innerHTML = [v.hazard, v.item].filter(Boolean).join("<br/>") || "—";

  const heard = el("heard");
  heard.innerHTML = v.pendingHeardCues
    .map((h) => `${h.distanceLabel} (${h.phrase})`)
    .join("<br/>");

  if (v.gameOver) {
    c.innerHTML += `<p><strong>Game over: ${escapeHtml(v.gameOver)}</strong></p>`;
  }
}

function escapeHtml(s: string) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function connect() {
  const ws = new WebSocket(WS_URL);
  ws.onopen = () => {
    ws.send(JSON.stringify({ type: "hello", role: "player" }));
  };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data as string);
    if (msg.type === "session.waiting") {
      el("waiting").classList.remove("hidden");
      el("waiting").textContent = msg.message ?? "Waiting…";
      el("game").classList.add("hidden");
      el("stats").classList.add("hidden");
      el("onboarding").classList.add("hidden");
      return;
    }
    if (msg.type === "state.player_view") {
      const { type: _t, protocol: _p, ...rest } = msg;
      renderView(rest as PlayerView);
      return;
    }
    if (msg.type === "error") {
      console.warn(msg.message);
    }
  };
  ws.onerror = () => console.error("WS error");

  el("stats-go").onclick = () => {
    const per = (el("per") as HTMLInputElement).value;
    const ste = (el("ste") as HTMLInputElement).value;
    ws.send(
      JSON.stringify({
        type: "player.set_stats",
        perception_bonus: Number(per),
        stealth_bonus: Number(ste),
      }),
    );
  };

  document.querySelectorAll(".actions button").forEach((btn) => {
    btn.addEventListener("click", () => {
      const act = (btn as HTMLElement).dataset.act;
      const pace = (
        document.querySelector('input[name="pace"]:checked') as HTMLInputElement
      )?.value ?? "normal";
      ws.send(JSON.stringify({ type: "player.action", kind: act, pace }));
    });
  });
}

connect();
