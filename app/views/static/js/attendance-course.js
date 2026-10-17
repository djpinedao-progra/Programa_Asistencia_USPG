(() => {
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


})();
