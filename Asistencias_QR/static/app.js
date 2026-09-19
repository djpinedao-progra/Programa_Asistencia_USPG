const state = { students: [], sessions: [], attendances: [] };
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

function renderStudents() {
  $('#student-count').textContent = state.students.length;
  $('#student-table-count').textContent = state.students.length;
  $('#students-table').innerHTML = state.students.length ? state.students.map(student => `<tr><td><strong>${student.carnet}</strong></td><td>${student.nombre}<small class="muted-cell">${student.correo}</small></td><td>${student.carrera}</td><td><span class="pill">${student.estado}</span></td></tr>`).join('') : emptyRow(4, 'No hay estudiantes registrados.');
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
    [state.students, state.sessions, state.attendances] = await Promise.all([api('/api/estudiantes'), api('/api/sesiones'), api('/api/asistencias')]);
    renderStudents(); renderSessions(); renderAttendances();
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
  const titles = { resumen: 'Resumen operativo', estudiantes: 'Estudiantes', sesiones: 'Sesiones QR', asistencias: 'Registrar asistencia' };
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

$('#session-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = new FormData(event.target);
  try { const session = await api('/api/sesiones', { method: 'POST', body: JSON.stringify(Object.fromEntries(form)) }); event.target.reset(); $('#qr-result').innerHTML = `<img src="/static/qr_codes/sesion_${session.id}.png" alt="Código QR de ${session.curso}"><div class="qr-info"><strong>Sesión #${session.id} · ${session.curso}</strong><code>${session.token_qr}</code></div>`; await loadData(); showToast('Sesión creada y QR generado'); } catch (error) { showToast(error.message, true); }
});

$('#attendance-form').addEventListener('submit', async event => {
  event.preventDefault();
  const values = Object.fromEntries(new FormData(event.target));
  values.sesion_id = Number(values.sesion_id);
  try { await api('/api/asistencias', { method: 'POST', body: JSON.stringify(values) }); event.target.reset(); await loadData(); showToast('Asistencia validada correctamente'); } catch (error) { showToast(error.message, true); }
});

const initialSection = window.location.hash.replace('#', '') || 'resumen';
navigate(['resumen', 'estudiantes', 'sesiones', 'asistencias'].includes(initialSection) ? initialSection : 'resumen');
loadData();
loadGoogleStatus();
