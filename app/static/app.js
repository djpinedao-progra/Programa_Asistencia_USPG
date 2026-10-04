(() => {
  const themeButtons = document.querySelectorAll("[data-theme-toggle]");
  const syncThemeButtons = () => {
    const dark = document.documentElement.dataset.theme === "dark";
    const label = dark ? "Activar modo claro" : "Activar modo oscuro";
    themeButtons.forEach((button) => {
      button.setAttribute("aria-pressed", String(dark));
      button.setAttribute("aria-label", label);
      button.title = label;
    });
  };
  themeButtons.forEach((button) => button.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      window.localStorage.setItem("uspg-theme", next);
    } catch (_) {
      // The theme still changes for this page when storage is unavailable.
    }
    syncThemeButtons();
  }));
  syncThemeButtons();

  const sidebarToggle = document.querySelector("[data-sidebar-toggle]");
  if (sidebarToggle) {
    const setSidebarOpen = (open) => {
      document.body.classList.toggle("sidebar-open", open);
      sidebarToggle.setAttribute("aria-expanded", String(open));
    };
    sidebarToggle.addEventListener("click", () => setSidebarOpen(!document.body.classList.contains("sidebar-open")));
    document.querySelectorAll("[data-sidebar-close], .sidebar-nav a").forEach((element) => {
      element.addEventListener("click", () => setSidebarOpen(false));
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") setSidebarOpen(false);
    });
  }

  const navLinks = [...document.querySelectorAll(".sidebar-nav a")];
  const markCurrentLink = (link) => {
    navLinks.forEach((item) => item.removeAttribute("aria-current"));
    link.setAttribute("aria-current", "page");
  };
  const samePageLinks = navLinks.filter((link) => link.pathname === window.location.pathname);
  const markLinkFromHash = () => {
    const current = samePageLinks.find((link) => link.hash === window.location.hash)
      || (window.location.hash ? null : samePageLinks.find((link) => !link.hash));
    if (current) markCurrentLink(current);
  };
  markLinkFromHash();
  window.addEventListener("hashchange", markLinkFromHash);
  samePageLinks.forEach((link) => link.addEventListener("click", () => markCurrentLink(link)));

  const views = [...document.querySelectorAll("[data-view]")];
  if (views.length) {
    const viewNames = new Set(views.map((view) => view.dataset.view));
    const showView = (hash) => {
      const name = viewNames.has(hash.slice(1)) ? hash.slice(1) : "inicio";
      views.forEach((view) => {
        view.hidden = view.dataset.view !== name;
      });
      window.scrollTo({ top: 0, behavior: "instant" });
    };
    document.addEventListener("click", (event) => {
      const link = event.target.closest("a[href]");
      if (!link || link.pathname !== window.location.pathname || link.search !== window.location.search) return;
      if (!viewNames.has(link.hash.slice(1) || "inicio")) return;
      event.preventDefault();
      if (link.href !== window.location.href) window.history.pushState(null, "", link.href);
      showView(link.hash);
      markLinkFromHash();
    });
    window.addEventListener("popstate", () => {
      showView(window.location.hash);
      markLinkFromHash();
    });
    showView(window.location.hash);
  }

  const attendanceForm = document.querySelector(".start-attendance-form[data-teacher-id]");
  if (attendanceForm) {
    const courseSelect = attendanceForm.querySelector("#attendance-course");
    const suggestion = attendanceForm.querySelector("[data-course-suggestion]");
    const storageKey = `attendance-course-${attendanceForm.dataset.teacherId}`;
    const dayNames = ["domingo", "lunes", "martes", "miercoles", "jueves", "viernes", "sabado"];
    const today = dayNames[new Date().getDay()];
    const currentMinutes = new Date().getHours() * 60 + new Date().getMinutes();
    const normalize = (value) => value.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLocaleLowerCase("es-GT");
    let scheduledCourse = null;

    [...courseSelect.options].slice(1).forEach((option) => {
      const schedule = normalize(option.dataset.courseSchedule || "");
      if (!new RegExp(`\\b${today}\\b`).test(schedule)) return;
      const times = [...schedule.matchAll(/\b(\d{1,2}):(\d{2})\b/g)]
        .map((match) => Number(match[1]) * 60 + Number(match[2]));
      if (times.length >= 2 && currentMinutes >= times[0] && currentMinutes <= times[1]) {
        scheduledCourse = option;
      }
    });

    let previousCourse = "";
    try {
      previousCourse = window.localStorage.getItem(storageKey) || "";
    } catch (_) {
      // Course selection still works when browser storage is unavailable.
    }
    const rememberedOption = [...courseSelect.options].find((option) => option.value === previousCourse);
    if (scheduledCourse) {
      courseSelect.value = scheduledCourse.value;
      suggestion.textContent = `Seleccionado por el horario de hoy: ${scheduledCourse.textContent.trim()}.`;
      suggestion.hidden = false;
    } else if (rememberedOption) {
      courseSelect.value = rememberedOption.value;
      suggestion.textContent = "Se conservó el último curso seleccionado.";
      suggestion.hidden = false;
    }
    courseSelect.addEventListener("change", () => {
      try {
        if (courseSelect.value) window.localStorage.setItem(storageKey, courseSelect.value);
        else window.localStorage.removeItem(storageKey);
      } catch (_) {
        // The selected course remains usable even when browser storage is unavailable.
      }
    });
  }

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

  const noticeCourse = document.querySelector("[data-notice-course]");
  const noticeStudent = document.querySelector("[data-notice-student]");
  if (noticeCourse && noticeStudent) {
    const filterNoticeStudents = () => {
      const courseId = noticeCourse.value;
      [...noticeStudent.options].forEach((option) => {
        if (!option.value) return;
        option.hidden = Boolean(courseId && option.dataset.courseId !== courseId);
      });
      const selectedOption = noticeStudent.selectedOptions[0];
      if (selectedOption?.hidden) noticeStudent.value = "";
    };
    noticeCourse.addEventListener("change", filterNoticeStudents);
    filterNoticeStudents();
  }

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
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      message.textContent = cameraErrorMessage();
      return;
    }
    if (!window.Html5Qrcode) {
      message.textContent = "No se pudo cargar el lector. Revisa tu conexión e inténtalo de nuevo.";
      return;
    }
    scanner = new Html5Qrcode("qr-reader");
    try {
      message.textContent = "Solicitando permiso para usar la cámara...";
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
    } catch (error) {
      message.textContent = cameraErrorMessage(error);
    }
  });

  close.addEventListener("click", stopScanner);
})();