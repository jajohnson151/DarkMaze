import {
  applySurroundingsVisual,
  escapeHtml,
  type MonsterMirrorPayload,
  type SurroundingsDom,
} from "./player_view_render";

function mirrorCardShell(): string {
  return `<div class="gm-mm-card">
  <div class="gm-mm-head"></div>
  <div class="frame gm-mm-frame">
    <div class="wall-grid" role="img" aria-label="Monster surroundings">
      <div class="wall-corner wall-corner-nw mm-cnw" aria-hidden="true"></div>
      <div class="wall-cell wall-bar wall-h hidden mm-wt"></div>
      <div class="wall-corner wall-corner-ne mm-cne" aria-hidden="true"></div>
      <div class="wall-cell wall-bar wall-v hidden mm-wl"></div>
      <div class="center mm-c"></div>
      <div class="wall-cell wall-bar wall-v hidden mm-wr"></div>
      <div class="wall-corner wall-corner-sw mm-csw" aria-hidden="true"></div>
      <div class="wall-cell wall-bar wall-h hidden mm-wb"></div>
      <div class="wall-corner wall-corner-se mm-cse" aria-hidden="true"></div>
    </div>
  </div>
  <div class="gm-mm-heard mm-hd" aria-live="polite"></div>
</div>`;
}

function surroundingsFromCard(card: HTMLElement): SurroundingsDom {
  return {
    wallTop: card.querySelector(".mm-wt")!,
    wallBottom: card.querySelector(".mm-wb")!,
    wallLeft: card.querySelector(".mm-wl")!,
    wallRight: card.querySelector(".mm-wr")!,
    cornerNW: card.querySelector(".mm-cnw")!,
    cornerNE: card.querySelector(".mm-cne")!,
    cornerSW: card.querySelector(".mm-csw")!,
    cornerSE: card.querySelector(".mm-cse")!,
    center: card.querySelector(".mm-c")!,
    heard: card.querySelector(".mm-hd")!,
  };
}

export function renderMonsterMirrors(root: HTMLElement, list: MonsterMirrorPayload[] | undefined): void {
  const items = list ?? [];
  if (!items.length) {
    root.innerHTML = "<p>No monsters in session.</p>";
    return;
  }
  root.replaceChildren();
  const tpl = document.createElement("template");
  tpl.innerHTML = mirrorCardShell().trim();
  for (const m of items) {
    const card = tpl.content.firstElementChild!.cloneNode(true) as HTMLElement;
    const head = card.querySelector(".gm-mm-head")!;
    head.innerHTML = `<strong>${escapeHtml(m.id)}</strong>`;
    applySurroundingsVisual(surroundingsFromCard(card), m.walls, {
      hazard: m.hazard,
      item: m.item,
      pendingHeardCues: m.pendingHeardCues,
    });
    root.appendChild(card);
  }
}
