# USPG · Nuevo proyecto independiente
Basado en el motor de Programa_Asistencia_USPG, commit 9464e9973572dc8b0c848a5248aff84a406696f6.
Conserva licencia GPL-3.0: ver LICENSE. Reutiliza la lógica existente; no es una reescritura desde cero.

## Mac: abrir esta carpeta en Visual Studio Code
```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python iniciar.py --demo
```
## Windows PowerShell
```powershell
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python iniciar.py --demo
```
Abre http://127.0.0.1:5000
Cuentas demo: admin@demo.uspg / docente@demo.uspg / alumno@demo.uspg
Contraseña común: Demo-USPG-2026!
El modo demo usa una base separada y crea un curso con docente y alumno.
No contiene asistencias inventadas: registra las tuyas al probar.

## Instalación propia
Ejecuta python iniciar.py sin --demo. Se crea una base SQLite y se solicita
la primera cuenta administradora. No copies instance del proyecto anterior.
Puerto alternativo: python iniciar.py --demo --port 5001.
DATABASE_URL permite usar MySQL si lo configuras en .env.

## Funciones
Administrador: estudiantes, docentes, cursos, matrículas CSV, asistencia, reportes PDF y auditoría.
Docente: sesiones QR temporales, registro manual, cursos, avisos y exportaciones.
Alumno: registro con carnet, historial y escaneo QR.
Contraseñas con hash, permisos por rol, CSRF y cambio de contraseña.
Diseño rojo, dorado y azul oscuro. Rethink Sans, utilizada en la web de la universidad.
Logo original descargado sin editar de la web oficial: https://uspg.edu.gt/site/wp-content/uploads/2026/07/LOGO-EDITABLE-USPG-1.png
Paleta: azul #011931, rojo #AA182B y blanco.

El servidor local abre solo en tu computadora. Cámara móvil requiere HTTPS.
Google Fonts necesita internet; sin conexión usa fuente del sistema.
Pruebas: python -m pytest -q.
Pruebas de navegador: Playwright con Chromium.

Motor original: https://github.com/djpinedao-progra/Programa_Asistencia_USPG
