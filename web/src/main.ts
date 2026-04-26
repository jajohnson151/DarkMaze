const SESSION = "default";
const WS_URL = `ws://${window.location.hostname}:8000/ws/${SESSION}`;

let onboardingContinueClicked = false;

import { renderPlayerView, type PlayerView } from "./player_view_render";

const el = (id: string) => document.getElementById(id)!;

function renderView(v: PlayerView) {
  onboardingContinueClicked = renderPlayerView(
    v,
    {
      pausedBanner: el("paused-banner"),
      waiting: el("waiting"),
      onboarding: el("onboarding"),
      stats: el("stats"),
      game: el("game"),
      wallTop: el("w-top"),
      wallBottom: el("w-bot"),
      wallLeft: el("w-left"),
      wallRight: el("w-right"),
      cornerNW: el("corner-nw"),
      cornerNE: el("corner-ne"),
      cornerSW: el("corner-sw"),
      cornerSE: el("corner-se"),
      center: el("center"),
      perceptionUpper: el("perception-upper"),
      perceptionLeft: el("perception-left"),
      perceptionLower: el("perception-lower"),
      perceptionRight: el("perception-right"),
      perceptionUL: el("perception-ul"),
      perceptionUR: el("perception-ur"),
      perceptionLL: el("perception-ll"),
      perceptionLR: el("perception-lr"),
      selectedStats: el("selected-stats"),
      actionButtons: Array.from(document.querySelectorAll<HTMLButtonElement>(".actions button")),
    },
    onboardingContinueClicked,
    () => {
      onboardingContinueClicked = true;
      el("onboarding").classList.add("hidden");
      el("stats").classList.remove("hidden");
    },
  );
}

let playerWs: WebSocket | null = null;

function currentPace(): string {
  return (
    (document.querySelector('input[name="pace"]:checked') as HTMLInputElement)
      ?.value ?? "normal"
  );
}

function sendPlayerAction(kind: string) {
  if (!playerWs || playerWs.readyState !== WebSocket.OPEN) return;
  playerWs.send(
    JSON.stringify({
      type: "player.action",
      kind,
      pace: currentPace(),
    }),
  );
}

function isTypingTarget(t: EventTarget | null): boolean {
  if (!t || !(t instanceof HTMLElement)) return false;
  const tag = t.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || t.isContentEditable;
}

function connect() {
  const ws = new WebSocket(WS_URL);
  playerWs = ws;
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
      if (act) sendPlayerAction(act);
    });
  });

  window.addEventListener("keydown", (e) => {
    if (isTypingTarget(e.target)) return;
    const key = e.key;
    if (key === " " || key === "Spacebar") {
      e.preventDefault();
      sendPlayerAction("wait");
      return;
    }
    if (key === "w" || key === "W" || key === "ArrowUp") {
      e.preventDefault();
      sendPlayerAction("forward");
      return;
    }
    if (key === "a" || key === "A" || key === "ArrowLeft") {
      e.preventDefault();
      sendPlayerAction("turn_left");
      return;
    }
    if (key === "d" || key === "D" || key === "ArrowRight") {
      e.preventDefault();
      sendPlayerAction("turn_right");
      return;
    }
  });
}

connect();
