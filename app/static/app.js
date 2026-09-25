(() => {
  const passwordInput = document.querySelector("[data-password-input]");
  const meter = document.querySelector("[data-password-meter]");
  if (passwordInput && meter) {
    const fill = meter.querySelector(".password-meter span");
    const label = meter.querySelector("[data-password-label]");
    const tips = meter.querySelector("[data-password-tips]");
    const updatePasswordFeedback = () => {
      const password = passwordInput.value;
      meter.hidden = password.length === 0;
      if (!password) return;
      const checks = [
        [password.length >= 12, "Considera usar 12 caracteres o más."],
        [/[a-z]/.test(password) && /[A-Z]/.test(password), "Combina mayúsculas y minúsculas."],
        [/[0-9]/.test(password), "Incluye al menos un número."],
        [/[^A-Za-z0-9]/.test(password), "Añade un símbolo."],
        [password.length >= 16, "Una frase larga y única es más fácil de recordar."],
      ];
      const score = checks.filter(([passed]) => passed).length;
      const levels = ["Muy débil", "Débil", "Aceptable", "Buena", "Fuerte", "Muy fuerte"];
      fill.style.width = `${Math.max(10, score * 20)}%`;
      fill.dataset.level = score < 2 ? "weak" : score < 4 ? "medium" : "strong";
      label.textContent = `Seguridad estimada: ${levels[score]}`;
      tips.replaceChildren();
      checks.filter(([passed]) => !passed).slice(0, 3).forEach(([, tip]) => {
        const item = document.createElement("li");
        item.textContent = tip;
        tips.append(item);
      });
    };
    passwordInput.addEventListener("input", updatePasswordFeedback);
    updatePasswordFeedback();
  }

  const panel = document.querySelector("[data-scanner]");
  if (!panel) return;

  const launch = document.querySelector("[data-scan-toggle]");
  const close = panel.querySelector("[data-scan-close]");
  const form = panel.querySelector("[data-scan-form]");
  const message = panel.querySelector("[data-scan-message]");
  const success = panel.querySelector("[data-scan-success]");
  let scanner;

  const stopScanner = async () => {
    if (scanner?.isScanning) await scanner.stop();
    if (scanner) await scanner.clear();
    scanner = null;
    panel.hidden = true;
    launch.hidden = false;
  };

  launch.addEventListener("click", async () => {
    panel.hidden = false;
    launch.hidden = true;
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
    if (!window.Html5Qrcode) {
      message.textContent = "No se pudo cargar el lector. Revisa tu conexión e inténtalo de nuevo.";
      return;
    }
    scanner = new Html5Qrcode("qr-reader");
    try {
      await scanner.start(
        { facingMode: "environment" },
        { fps: 10, qrbox: { width: 230, height: 230 }, aspectRatio: 1 },
        async (decodedText) => {
          let token = decodedText;
          try {
            token = new URL(decodedText).searchParams.get("token") || decodedText;
          } catch (_) {
            token = decodedText;
          }
          if (!token) return;
          form.elements.token.value = token;
          success.textContent = "Código reconocido. Confirma para guardar el registro.";
          form.hidden = false;
          message.textContent = "";
          if (scanner?.isScanning) await scanner.stop();
        },
        () => {},
      );
    } catch (_) {
      message.textContent = "No se pudo acceder a la cámara. Verifica los permisos del navegador.";
    }
  });

  close.addEventListener("click", stopScanner);
})();