(() => {
  const dataElement = document.getElementById("classroom-occupancy");
  if (!dataElement) return;

  let occupancy = [];
  try {
    occupancy = JSON.parse(dataElement.textContent);
  } catch (_) {
    return;
  }

  const minutes = (value) => {
    if (!/^\d{2}:\d{2}$/.test(value)) return null;
    const [hours, mins] = value.split(":").map(Number);
    return hours * 60 + mins;
  };

  document.querySelectorAll("[data-course-schedule-form]").forEach((form) => {
    const courseId = Number(form.dataset.courseId || 0);
    const location = form.querySelector("[data-location-type]");
    const classroom = form.querySelector("[data-classroom-select]");
    const startInput = form.elements.start_time;
    const endInput = form.elements.end_time;
    const activeInput = form.elements.is_active;
    const status = form.querySelector("[data-room-status]");
    const dayInputs = [...form.querySelectorAll('input[name="schedule_days"]')];

    const refreshAvailability = () => {
      const isVirtual = location.value === "virtual";
      classroom.disabled = isVirtual;
      classroom.required = !isVirtual;
      if (isVirtual) {
        classroom.value = "";
        status.textContent = "Los cursos virtuales no ocupan salón.";
        startInput.setCustomValidity("");
        endInput.setCustomValidity("");
        return;
      }

      const days = new Set(dayInputs.filter((input) => input.checked).map((input) => input.value));
      const start = minutes(startInput.value);
      const end = minutes(endInput.value);
      const invalidRange = start !== null && end !== null && start >= end;
      endInput.setCustomValidity(invalidRange ? "La hora final debe ser posterior a la inicial." : "");
      startInput.setCustomValidity("");
      const courseIsActive = !activeInput || activeInput.checked;
      let unavailable = 0;

      [...classroom.options].forEach((option) => {
        if (!option.value) return;
        const conflict = courseIsActive && days.size > 0 && start !== null && end !== null && !invalidRange
          && occupancy.some((slot) => (
            slot.course_id !== courseId
            && slot.classroom === option.value
            && slot.days.some((day) => days.has(day))
            && start < slot.end
            && slot.start < end
          ));
        option.disabled = conflict;
        if (conflict) unavailable += 1;
      });

      if (classroom.selectedOptions[0]?.disabled) classroom.value = "";
      if (!days.size || start === null || end === null) {
        status.textContent = "Selecciona días y horario para consultar disponibilidad.";
      } else if (invalidRange) {
        status.textContent = "La hora final debe ser posterior a la hora inicial.";
      } else if (!courseIsActive) {
        status.textContent = "El curso deshabilitado no reserva salón.";
      } else {
        status.textContent = unavailable
          ? `${unavailable} ${unavailable === 1 ? "salón ocupado" : "salones ocupados"} en ese horario.`
          : "Los 25 salones están disponibles en ese horario.";
      }
    };

    [location, startInput, endInput, activeInput, ...dayInputs]
      .filter(Boolean)
      .forEach((input) => input.addEventListener("change", refreshAvailability));
    refreshAvailability();
  });
})();
