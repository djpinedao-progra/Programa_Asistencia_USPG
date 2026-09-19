# Automatizaci-n-de-Asistencia.-
Este será un proyecto en conjunto para desarrollar un programa de asistencia para la universidad y quede para la posteridad he integración para ser una herramienta aliada para los futuros alumnos y catedráticos. 

## Google Classroom

La aplicación incluye OAuth 2.0 para consultar cursos activos e importar sus estudiantes.

1. En Google Cloud Console crea un proyecto y habilita **Google Classroom API**.
2. Configura la pantalla de consentimiento OAuth y crea un cliente de tipo aplicación web.
3. Registra `http://127.0.0.1:5000/oauth2callback` como URI de redirección.
4. Descarga el JSON de credenciales y guárdalo como `Asistencias_QR/client_secret.json`.
5. Inicia la aplicación y pulsa **Conectar Google** en el panel.
6. Autoriza la cuenta, selecciona un curso y pulsa **Sincronizar estudiantes**.

El token se guarda localmente en `Asistencias_QR/google_token.pickle` y ambos archivos están excluidos de Git. La asistencia continúa almacenándose en SQLite y se vincula a las sesiones QR locales.
