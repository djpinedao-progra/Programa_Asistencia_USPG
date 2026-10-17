(() => {
const liveSession = document.querySelector("[data-live-session]");
if (liveSession) {
  const roster = liveSession.querySelector("[data-attendance-list]");
  const search = liveSession.querySelector("[data-student-search]");
  const countdown = liveSession.querySelector("[data-qr-countdown]");
  const connectionStatus = liveSession.querySelector("[data-connection-status]");
  const refreshButton = liveSession.querySelector("[data-refresh-roster]");
  let refreshInProgress = false;
  let lastUpdatedAt = null;
  const updateConnectionStatus = (online) => {
    if (!connectionStatus) return;
    connectionStatus.dataset.state = online ? "online" : "offline";
    if (online) {
      lastUpdatedAt = new Date();
      connectionStatus.textContent = `Conectado · ${lastUpdatedAt.toLocaleTimeString("es-GT", { timeZone: "America/Guatemala", hour: "2-digit", minute: "2-digit", second: "2-digit" })}`;
    } else {
      const lastUpdate = lastUpdatedAt
        ? ` · último dato ${lastUpdatedAt.toLocaleTimeString("es-GT", { timeZone: "America/Guatemala", hour: "2-digit", minute: "2-digit", second: "2-digit" })}`
        : "";
      connectionStatus.textContent = `Sin conexión · reintentando${lastUpdate}`;
    }
  };
  const formatTimestamp = (value) => {
    if (!value) return "Sin registro";
    const date = new Date(value);
    return `${date.toLocaleDateString("es-GT", { timeZone: "America/Guatemala" })} · ${date.toLocaleTimeString("es-GT", { timeZone: "America/Guatemala", hour: "2-digit", minute: "2-digit" })}`;
  };
  const updateRoster = async () => {
    if (refreshInProgress) return;
    refreshInProgress = true;
    if (refreshButton) refreshButton.disabled = true;
    try {
      const response = await fetch(liveSession.dataset.statusUrl, {
        headers: { Accept: "application/json" },
      });
      if (!response.ok) {
        updateConnectionStatus(false);
        return;
      }
      const state = await response.json();
      state.students.forEach((student) => {
        const row = roster.querySelector(`[data-student-id="${student.id}"]`);
        if (!row) return;
        const status = row.querySelector("[data-student-status]");
        status.textContent = student.status.charAt(0).toUpperCase() + student.status.slice(1);
        status.className = `session-state state-${student.status}`;
        row.querySelector("[data-student-time]").textContent = student.recorded_at
          ? `${formatTimestamp(student.recorded_at)} · ${{ qr: "QR", manual: "Manual", cierre: "Cierre" }[student.source] || ""}`
          : "Sin registro";
        const select = row.querySelector("select[name=status]");
        if (select && document.activeElement !== select && student.status !== "pendiente") {
          select.value = student.status;
        }
      });
      const count = liveSession.querySelector("[data-present-count]");
      if (count) count.textContent = state.present_count;
      updateConnectionStatus(true);
    } catch (_) {
      updateConnectionStatus(false);
    } finally {
      refreshInProgress = false;
      if (refreshButton) refreshButton.disabled = false;
    }
  };
  refreshButton?.addEventListener("click", updateRoster);
  search?.addEventListener("input", () => {
    const query = search.value.trim().toLocaleLowerCase();
    roster.querySelectorAll("[data-student-id]").forEach((row) => {
      row.hidden = !`${row.dataset.studentName} ${row.dataset.studentCarnet}`
        .toLocaleLowerCase()
        .includes(query);
    });
  });
  liveSession.querySelector("[data-confirm-close]")?.addEventListener("submit", (event) => {
    if (!window.confirm("¿Cerrar la asistencia? Los estudiantes sin registro quedarán como ausentes.")) {
      event.preventDefault();
    }
  });
  if (countdown && liveSession.dataset.closed !== "true") {
    const expiresAt = Number(liveSession.dataset.expires) * 1000;
    const updateCountdown = () => {
      const remaining = Math.max(0, Math.floor((expiresAt - Date.now()) / 1000));
      countdown.textContent = `${String(Math.floor(remaining / 60)).padStart(2, "0")}:${String(remaining % 60).padStart(2, "0")}`;
      if (remaining === 0) {
        const qrFrame = liveSession.querySelector(".qr-frame");
        if (qrFrame) qrFrame.hidden = true;
        countdown.textContent = "VENCIDO · genera otro QR";
      }
    };
    updateCountdown();
    window.setInterval(updateCountdown, 1000);
  }
  if (liveSession.dataset.closed !== "true") {
    updateRoster();
    window.setInterval(updateRoster, 5000);
  }
}


})();
