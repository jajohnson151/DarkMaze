const SESSION = "default";
const WS_URL = `ws://${window.location.hostname}:8000/ws/${SESSION}`;

const logEl = document.getElementById("log")!;

function log(obj: unknown) {
  logEl.textContent =
    typeof obj === "string" ? obj : JSON.stringify(obj, null, 2);
}

const ws = new WebSocket(WS_URL);
ws.onopen = () => {
  ws.send(JSON.stringify({ type: "hello", role: "gm" }));
};
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data as string);
  log(msg);
};

document.getElementById("btn-start")!.onclick = () => {
  ws.send(JSON.stringify({ type: "gm.play.start" }));
};
document.getElementById("btn-stop")!.onclick = () => {
  ws.send(JSON.stringify({ type: "gm.play.stop" }));
};
document.getElementById("btn-pause")!.onclick = () => {
  ws.send(JSON.stringify({ type: "gm.play.pause" }));
};
document.getElementById("btn-resume")!.onclick = () => {
  ws.send(JSON.stringify({ type: "gm.play.resume" }));
};
