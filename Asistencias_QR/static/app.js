const state = { students: [], courses: [], sessions: [], attendances: [] };
const $ = (selector) => document.querySelector(selector);

async function api(url, options = {}) {
  const response = await fetch(url, { headers: { 'Content-Type': 'application/json' }, ...options });
  const body = await response.json();
  if (!response.ok) throw new Error(body.message || 'No se pudo completar la operación');
  return body.data;
}

function showToast(message, isError = false) {
  const toast = $('#toast');
  toast.textContent = message;
  toast.className = `toast show${isError ? ' error' : ''}`;
  window.setTimeout(() => { toast.className = 'toast'; }, 3200);
}

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
}

function emptyRow(columns, message) { return `<tr><td colspan="${columns}" class="empty-state">${message}</td></tr>`; }

function escapeHtml(value) {
  const element = document.createElement('div');
  element.textContent = value ?? '';
  return element.innerHTML;
}

function renderStudents() {
  $('#student-count').textContent = state.students.length;
  $('#student-table-count').textContent = state.students.length;
  $('#students-table').innerHTML = state.students.length ? state.students.map(student => `<tr><td><strong>${student.carnet}</strong></td><td>${student.nombre}<small class="muted-cell">${student.correo}</small></td><td>${student.carrera}</td><td><span class="pill">${student.estado}</span></td></tr>`).join('') : emptyRow(4, 'No hay estudiantes registrados.');
}

function renderCourses() {
  $('#course-count').textContent = state.courses.length;
  $('#course-table-count').textContent = state.courses.length;
  $('#courses-table').innerHTML = state.courses.length ? state.courses.map(course => `<tr>
    <td><strong>${escapeHtml(course.codigo)}</strong></td>
    <td>${escapeHtml(course.nombre)}</td>
    <td>${escapeHtml(course.seccion) || '—'}</td>
    <td>${escapeHtml(course.docente) || '—'}</td>
    <td><span class="pill ${course.estado === 'inactivo' ? 'pill-inactive' : ''}">${escapeHtml(course.estado)}</span></td>
    <td class="action-cell"><button class="table-action" data-course-edit="${course.id}">Editar</button><button class="table-action danger" data-course-delete="${course.id}">Eliminar</button></td>
  </tr>`).join('') : emptyRow(6, 'No hay cursos registrados.');

  const courseSelect = $('#session-course');
  const selectedCourse = courseSelect.value;
  const activeCourses = state.courses.filter(course => course.estado === 'activo');
  courseSelect.innerHTML = activeCourses.length
    ? `<option value="">Selecciona un curso</option>${activeCourses.map(course => `<option value="${course.id}">${escapeHtml(course.codigo)} · ${escapeHtml(course.nombre)}${course.seccion ? ` · ${escapeHtml(course.seccion)}` : ''}</option>`).join('')}`
    : '<option value="">Primero registra un curso activo</option>';
  courseSelect.value = selectedCourse;

  document.querySelectorAll('[data-course-edit]').forEach(button => button.addEventListener('click', () => startCourseEdit(Number(button.dataset.courseEdit))));
  document.querySelectorAll('[data-course-delete]').forEach(button => button.addEventListener('click', () => deleteCourse(Number(button.dataset.courseDelete))));
}

function renderSessions() {
  $('#session-count').textContent = state.sessions.length;
  $('#session-table-count').textContent = state.sessions.length;
  $('#sessions-table').innerHTML = state.sessions.length ? state.sessions.map(session => `<tr><td><strong>#${session.id}</strong></td><td>${session.curso}</td><td>${formatDate(session.fecha_hora)}</td><td><code class="token" title="${session.token_qr}">${session.token_qr}</code></td><td><button class="copy-btn" data-copy="${session.token_qr}">Copiar</button></td></tr>`).join('') : emptyRow(5, 'No hay sesiones creadas.');
  document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => { await navigator.clipboard.writeText(button.dataset.copy); showToast('Token copiado al portapapeles'); }));
}

function renderAttendances() {
  $('#attendance-count').textContent = state.attendances.length;
  $('#attendance-table-count').textContent = state.attendances.length;
  $('#attendance-table').innerHTML = state.attendances.length ? state.attendances.map(item => `<tr><td><strong>${item.nombre}</strong><small class="muted-cell">${item.carnet}</small></td><td>${item.curso}</td><td>#${item.sesion_id}</td><td>${formatDate(item.fecha_hora)}</td></tr>`).join('') : emptyRow(4, 'No hay asistencias registradas.');
  $('#recent-activity').innerHTML = state.attendances.slice(0, 4).length ? state.attendances.slice(0, 4).map(item => `<div class="activity-item"><span class="activity-icon">✓</span><div><strong>${item.nombre}</strong><small>${item.curso} · ${formatDate(item.fecha_hora)}</small></div></div>`).join('') : '<div class="empty-state">Todavía no hay asistencias registradas.</div>';
}

async function loadData() {
  try {
    [state.students, state.courses, state.sessions, state.attendances] = await Promise.all([api('/api/estudiantes'), api('/api/cursos'), api('/api/sesiones'), api('/api/asistencias')]);
    renderStudents(); renderCourses(); renderSessions(); renderAttendances();
  } catch (error) { showToast(error.message, true); }
}

async function loadGoogleStatus() {
  try {
    const status = await api('/api/google/status');
    const badge = $('#google-status');
    if (status.connected) {
      badge.textContent = 'Conectado';
      badge.classList.add('connected');
      const courses = await api('/api/google/cursos');
      $('#google-courses').innerHTML = courses.length
        ? courses.map(course => `<option value="${course.id}">${course.name}${course.section ? ` · ${course.section}` : ''}</option>`).join('')
        : '<option value="">No hay cursos activos</option>';
    } else if (!status.configured) {
      badge.textContent = 'Configurar OAuth';
    }
  } catch (error) { showToast(error.message, true); }
}

function navigate(section) {
  document.querySelectorAll('.page-section').forEach(item => item.classList.remove('active-section'));
  $(`#section-${section}`).classList.add('active-section');
  document.querySelectorAll('.nav-item').forEach(item => item.classList.toggle('active', item.dataset.section === section));
  const titles = { resumen: 'Resumen operativo', estudiantes: 'Estudiantes', cursos: 'Gestión de cursos', sesiones: 'Sesiones QR', asistencias: 'Registrar asistencia' };
  $('#page-title').textContent = titles[section];
  window.location.hash = section;
}

document.querySelectorAll('[data-section]').forEach(link => link.addEventListener('click', event => { event.preventDefault(); navigate(link.dataset.section); }));
$('#refresh-all').addEventListener('click', loadData);
$('#google-login').addEventListener('click', async () => {
  const status = await api('/api/google/status');
  if (!status.configured) {
    showToast('Agrega client_secret.json antes de conectar Google', true);
    return;
  }
  window.location.href = '/google/login';
});

$('#google-sync').addEventListener('click', async () => {
  const courseId = $('#google-courses').value;
  try {
    const result = await api('/api/google/sincronizar', {
      method: 'POST', body: JSON.stringify({ course_id: courseId })
    });
    await loadData();
    showToast(`${result.imported} estudiantes importados de ${result.found} encontrados`);
  } catch (error) { showToast(error.message, true); }
});

$('#student-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = new FormData(event.target);
  try { await api('/api/estudiantes', { method: 'POST', body: JSON.stringify(Object.fromEntries(form)) }); event.target.reset(); await loadData(); showToast('Estudiante registrado correctamente'); } catch (error) { showToast(error.message, true); }
});

function resetCourseForm() {
  const form = $('#course-form');
  form.reset();
  form.elements.id.value = '';
  $('#course-form-title').textContent = 'Nuevo curso';
  $('#course-submit').firstChild.textContent = 'Registrar curso ';
  $('#course-cancel').classList.add('hidden');
}

function startCourseEdit(courseId) {
  const course = state.courses.find(item => item.id === courseId);
  if (!course) return;
  const form = $('#course-form');
  Object.entries(course).forEach(([key, value]) => {
    if (form.elements[key]) form.elements[key].value = value ?? '';
  });
  $('#course-form-title').textContent = 'Editar curso';
  $('#course-submit').firstChild.textContent = 'Guardar cambios ';
  $('#course-cancel').classList.remove('hidden');
  navigate('cursos');
  form.elements.codigo.focus();
}

async function deleteCourse(courseId) {
  const course = state.courses.find(item => item.id === courseId);
  if (!course || !window.confirm(`¿Eliminar el curso ${course.codigo} · ${course.nombre}?`)) return;
  try {
    await api(`/api/cursos/${courseId}`, { method: 'DELETE' });
    if (Number($('#course-form').elements.id.value) === courseId) resetCourseForm();
    await loadData();
    showToast('Curso eliminado correctamente');
  } catch (error) { showToast(error.message, true); }
}

$('#course-form').addEventListener('submit', async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.target));
  const courseId = values.id;
  delete values.id;
  try {
    await api(courseId ? `/api/cursos/${courseId}` : '/api/cursos', {
      method: courseId ? 'PUT' : 'POST', body: JSON.stringify(values)
    });
    resetCourseForm();
    await loadData();
    showToast(courseId ? 'Curso actualizado correctamente' : 'Curso registrado correctamente');
  } catch (error) { showToast(error.message, true); }
});

$('#course-cancel').addEventListener('click', resetCourseForm);

$('#session-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = new FormData(event.target);
  const values = Object.fromEntries(form);
  values.curso_id = Number(values.curso_id);
  try { const session = await api('/api/sesiones', { method: 'POST', body: JSON.stringify(values) }); event.target.reset(); $('#qr-result').innerHTML = `<img src="/static/qr_codes/sesion_${session.id}.png" alt="Código QR de ${escapeHtml(session.curso)}"><div class="qr-info"><strong>Sesión #${session.id} · ${escapeHtml(session.curso)}</strong><code>${session.token_qr}</code></div>`; await loadData(); showToast('Sesión creada y QR generado'); } catch (error) { showToast(error.message, true); }
});

$('#attendance-form').addEventListener('submit', async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.target));
  values.sesion_id = Number(values.sesion_id);
  try { await api('/api/asistencias', { method: 'POST', body: JSON.stringify(values) }); event.target.reset(); await loadData(); showToast('Asistencia validada correctamente'); } catch (error) { showToast(error.message, true); }
});

const initialSection = window.location.hash.replace('#', '') || 'resumen';
navigate(['resumen', 'estudiantes', 'cursos', 'sesiones', 'asistencias'].includes(initialSection) ? initialSection : 'resumen');
loadData();
loadGoogleStatus();
