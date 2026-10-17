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


})();
