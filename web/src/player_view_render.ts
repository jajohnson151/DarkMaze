export type PlayerView = {
  sessionMode: string;
  paused: boolean;
  playerStatsReady: boolean;
  briefing?: { welcome?: string; goals?: string; commandsHelp?: string };
  walls: { left: boolean; right: boolean; forward: boolean; behind: boolean };
  hazard?: string | null;
  item?: string | null;
  pendingHeardCues: { relDirection8: number; phrase: string; distanceLabel: string }[];
  heardBuckets?: Record<string, string[]>;
  edgePoiBuckets?: Record<string, string[]>;
  centerSurface?: string | null;
  centerRoomPois?: string[];
  gameOver?: string | null;
};

export type WallMaskLike = PlayerView["walls"];

export type SurroundingsDom = {
  wallTop: HTMLElement;
  wallBottom: HTMLElement;
  wallLeft: HTMLElement;
  wallRight: HTMLElement;
  cornerNW: HTMLElement;
  cornerNE: HTMLElement;
  cornerSW: HTMLElement;
  cornerSE: HTMLElement;
  center: HTMLElement;
  heard?: HTMLElement;
};

export type MonsterMirrorPayload = {
  id: string;
  walls: WallMaskLike;
  hazard?: string | null;
  item?: string | null;
  pendingHeardCues: PlayerView["pendingHeardCues"];
};

type PlayerViewDom = {
  pausedBanner: HTMLElement;
  waiting: HTMLElement;
  onboarding: HTMLElement;
  stats: HTMLElement;
  game: HTMLElement;
  wallTop: HTMLElement;
  wallBottom: HTMLElement;
  wallLeft: HTMLElement;
  wallRight: HTMLElement;
  cornerNW: HTMLElement;
  cornerNE: HTMLElement;
  cornerSW: HTMLElement;
  cornerSE: HTMLElement;
  center: HTMLElement;
  heard?: HTMLElement;
  perceptionUpper?: HTMLElement;
  perceptionLeft?: HTMLElement;
  perceptionLower?: HTMLElement;
  perceptionRight?: HTMLElement;
  perceptionUL?: HTMLElement;
  perceptionUR?: HTMLElement;
  perceptionLL?: HTMLElement;
  perceptionLR?: HTMLElement;
  selectedStats?: HTMLElement;
  actionButtons?: HTMLButtonElement[];
};

function setWallBar(idEl: HTMLElement, show: boolean, text: string) {
  if (show) {
    idEl.classList.remove("hidden");
    idEl.textContent = text;
  } else {
    idEl.classList.add("hidden");
  }
}

/** Inside corner pillars when two adjacent passages are both open (derived from wall booleans). */
function setCornerPillar(el: HTMLElement, show: boolean) {
  el.classList.toggle("wall-corner--pillar", show);
}

export function escapeHtml(s: string) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

export function applySurroundingsVisual(
  dom: SurroundingsDom,
  walls: WallMaskLike,
  opts: {
    hazard?: string | null;
    item?: string | null;
    pendingHeardCues: PlayerView["pendingHeardCues"];
  },
): void {
  const wm = walls;
  setWallBar(dom.wallTop, wm.forward, "WALL IN FRONT");
  setWallBar(dom.wallBottom, wm.behind, "WALL BEHIND");
  setWallBar(dom.wallLeft, wm.left, "WALL TO LEFT");
  setWallBar(dom.wallRight, wm.right, "WALL TO RIGHT");
  setCornerPillar(dom.cornerNW, !wm.forward && !wm.left);
  setCornerPillar(dom.cornerNE, !wm.forward && !wm.right);
  setCornerPillar(dom.cornerSW, !wm.behind && !wm.left);
  setCornerPillar(dom.cornerSE, !wm.behind && !wm.right);
  dom.center.innerHTML = [opts.hazard, opts.item].filter(Boolean).join("<br/>") || "—";
  if (dom.heard) {
    dom.heard.innerHTML = opts.pendingHeardCues
      .map((h) => `${h.distanceLabel} (${h.phrase})`)
      .join("<br/>");
  }
}

function bucketHtml(title: string, items: string[]) {
  if (!items.length) return `<strong>${escapeHtml(title)}</strong><div>—</div>`;
  return `<strong>${escapeHtml(title)}</strong><ul>${items.map((s) => `<li>${escapeHtml(s)}</li>`).join("")}</ul>`;
}

export function renderPlayerView(
  v: PlayerView,
  dom: PlayerViewDom,
  onboardingShown: boolean,
  onContinueToStats?: () => void,
): boolean {
  dom.pausedBanner.classList.toggle("hidden", !v.paused);
  const gameLocked = v.paused || !v.playerStatsReady || v.sessionMode !== "play";
  for (const b of dom.actionButtons ?? []) {
    b.disabled = gameLocked || !!v.gameOver;
  }

  if (v.sessionMode !== "play") {
    dom.waiting.classList.remove("hidden");
    dom.waiting.textContent = "Waiting for GM to start play…";
    dom.onboarding.classList.add("hidden");
    dom.stats.classList.add("hidden");
    dom.game.classList.add("hidden");
    return onboardingShown;
  }
  dom.waiting.classList.add("hidden");

  if (!v.playerStatsReady) {
    dom.game.classList.add("hidden");
    if (!onboardingShown) {
      const b = v.briefing;
      dom.onboarding.classList.remove("hidden");
      dom.onboarding.innerHTML = `
      <h2>${escapeHtml(b?.welcome ?? "Welcome to Dark Maze!")}</h2>
      <p>${escapeHtml(b?.goals ?? "")}</p>
      <pre style="white-space:pre-wrap">${escapeHtml(b?.commandsHelp ?? "")}</pre>
      <button type="button" id="ob-go">Continue to stats</button>`;
      const btn = dom.onboarding.querySelector<HTMLButtonElement>("#ob-go");
      if (btn && onContinueToStats) {
        btn.onclick = () => onContinueToStats();
      }
      dom.stats.classList.add("hidden");
    } else {
      dom.onboarding.classList.add("hidden");
      dom.stats.classList.remove("hidden");
    }
    return onboardingShown;
  }

  dom.onboarding.classList.add("hidden");
  dom.stats.classList.add("hidden");
  dom.game.classList.remove("hidden");

  applySurroundingsVisual(
    {
      wallTop: dom.wallTop,
      wallBottom: dom.wallBottom,
      wallLeft: dom.wallLeft,
      wallRight: dom.wallRight,
      cornerNW: dom.cornerNW,
      cornerNE: dom.cornerNE,
      cornerSW: dom.cornerSW,
      cornerSE: dom.cornerSE,
      center: dom.center,
      heard: dom.heard,
    },
    v.walls,
    {
      hazard: v.hazard,
      item: v.item,
      pendingHeardCues: v.pendingHeardCues,
    },
  );
  const heard = v.heardBuckets ?? {};
  const pois = v.edgePoiBuckets ?? {};
  const roomPois = v.centerRoomPois ?? [];
  const centerLines: string[] = [];
  if (v.centerSurface) centerLines.push(`Surface: ${v.centerSurface}`);
  if (roomPois.length) centerLines.push("Room POIs:");
  dom.center.innerHTML = centerLines.length ? `<div>${centerLines.map(escapeHtml).join("<br/>")}</div>` : "—";
  if (roomPois.length) {
    dom.center.innerHTML += `<ul>${roomPois.map((p) => `<li>${escapeHtml(p)}</li>`).join("")}</ul>`;
  }
  if (dom.perceptionUpper) {
    dom.perceptionUpper.innerHTML = bucketHtml("Front", [...(heard.front ?? []), ...(pois.front ?? [])]);
  }
  if (dom.perceptionLeft) {
    dom.perceptionLeft.innerHTML = bucketHtml("Left", [...(heard.left ?? []), ...(pois.left ?? [])]);
  }
  if (dom.perceptionLower) {
    dom.perceptionLower.innerHTML = bucketHtml("Behind", [...(heard.behind ?? []), ...(pois.behind ?? [])]);
  }
  if (dom.perceptionRight) {
    dom.perceptionRight.innerHTML = bucketHtml("Right", [...(heard.right ?? []), ...(pois.right ?? [])]);
  }
  if (dom.perceptionUL) {
    dom.perceptionUL.innerHTML = bucketHtml("Front Left", heard.frontLeft ?? []);
  }
  if (dom.perceptionUR) {
    dom.perceptionUR.innerHTML = bucketHtml("Front Right", heard.frontRight ?? []);
  }
  if (dom.perceptionLL) {
    dom.perceptionLL.innerHTML = bucketHtml("Back Left", heard.backLeft ?? []);
  }
  if (dom.perceptionLR) {
    dom.perceptionLR.innerHTML = bucketHtml("Back Right", heard.backRight ?? []);
  }
  if (dom.selectedStats) {
    const perEl = document.getElementById("per") as HTMLInputElement | null;
    const steEl = document.getElementById("ste") as HTMLInputElement | null;
    const per = perEl?.value ?? "0";
    const ste = steEl?.value ?? "0";
    dom.selectedStats.innerHTML = `<strong>Selected stats</strong><div>Perception bonus: ${escapeHtml(
      per,
    )}</div><div>Stealth bonus: ${escapeHtml(ste)}</div>`;
  }
  if (v.gameOver) {
    dom.center.innerHTML += `<p><strong>Game over: ${escapeHtml(v.gameOver)}</strong></p>`;
  }
  return onboardingShown;
}
