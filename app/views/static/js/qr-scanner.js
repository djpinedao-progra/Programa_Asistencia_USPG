(() => {
const panel = document.querySelector("[data-scanner]");
if (!panel) return;

const launch = document.querySelector("[data-scan-toggle]");
const close = panel.querySelector("[data-scan-close]");
const form = panel.querySelector("[data-scan-form]");
const message = panel.querySelector("[data-scan-message]");
const success = panel.querySelector("[data-scan-success]");
let scanner;

const cameraErrorMessage = (error) => {
  if (!window.isSecureContext) {
    return "La cámara en el móvil requiere una conexión HTTPS. Abre el sitio con una dirección segura e inténtalo de nuevo.";
  }
  if (["NotAllowedError", "PermissionDeniedError"].includes(error?.name)) {
    return "No se concedió el permiso de cámara. Habilítalo en los ajustes del navegador y vuelve a tocar Escanear QR.";
  }
  if (["NotFoundError", "DevicesNotFoundError"].includes(error?.name)) {
    return "No se encontró una cámara disponible en este dispositivo.";
  }
  return "No se pudo abrir la cámara. Revisa los permisos del navegador y que ninguna otra aplicación la esté usando.";
};

let nativeStream = null;
let nativeVideo = null;
let nativeTimer = null;

const acceptDecodedText = async (decodedText) => {
  let token = decodedText;
  try {
    token = new URL(decodedText).searchParams.get("token") || decodedText;
  } catch (_) {
    token = decodedText;
  }
  if (!token) return false;
  form.elements.token.value = token;
  success.textContent = "Código reconocido. Confirma para guardar el registro.";
  form.hidden = false;
  message.textContent = "";
  await stopScanner(false);
  return true;
};

const stopScanner = async (hidePanel = true) => {
  if (scanner?.isScanning) await scanner.stop();
  if (scanner) await scanner.clear();
  scanner = null;
  if (nativeTimer) cancelAnimationFrame(nativeTimer);
  nativeTimer = null;
  if (nativeStream) nativeStream.getTracks().forEach((track) => track.stop());
  nativeStream = null;
  if (nativeVideo) nativeVideo.remove();
  nativeVideo = null;
  if (hidePanel) {
    panel.hidden = true;
    launch.hidden = false;
  }
};

const startNativeScanner = async () => {
  if (!("BarcodeDetector" in window)) return false;
  const formats = await BarcodeDetector.getSupportedFormats();
  if (!formats.includes("qr_code")) return false;
  const detector = new BarcodeDetector({ formats: ["qr_code"] });
  nativeStream = await navigator.mediaDevices.getUserMedia({
    video: { facingMode: { ideal: "environment" } },
    audio: false,
  });
  nativeVideo = document.createElement("video");
  nativeVideo.setAttribute("playsinline", "");
  nativeVideo.autoplay = true;
  nativeVideo.muted = true;
  nativeVideo.srcObject = nativeStream;
  document.getElementById("qr-reader").replaceChildren(nativeVideo);
  await nativeVideo.play();

  const detect = async () => {
    if (!nativeVideo || nativeVideo.readyState < 2) {
      nativeTimer = requestAnimationFrame(detect);
      return;
    }
    try {
      const codes = await detector.detect(nativeVideo);
      if (codes.length && await acceptDecodedText(codes[0].rawValue)) return;
    } catch (_) {}
    nativeTimer = requestAnimationFrame(detect);
  };
  detect();
  return true;
};

launch.addEventListener("click", async () => {
  panel.hidden = false;
  launch.hidden = true;
  panel.scrollIntoView({ behavior: "smooth", block: "start" });
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    message.textContent = cameraErrorMessage();
    return;
  }
  try {
    message.textContent = "Solicitando permiso para usar la cámara...";
    if (window.Html5Qrcode) {
      scanner = new Html5Qrcode("qr-reader");
      await scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 230, height: 230 }, aspectRatio: 1 },
        acceptDecodedText,
        () => {},
      );
      return;
    }
    if (await startNativeScanner()) {
      message.textContent = "Apunta la cámara al código QR.";
      return;
    }
    message.textContent = "Este navegador no incluye un lector QR compatible. Usa Chrome o Edge actualizado.";
  } catch (error) {
    message.textContent = cameraErrorMessage(error);
  }
});

close.addEventListener("click", () => stopScanner());

})();
