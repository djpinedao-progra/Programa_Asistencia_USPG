# Pendientes detectados durante la línea base

- El código QR muestra un mensaje de vencimiento de 5 minutos, pero `QR_SESSION_MINUTES` vale 1 y el servicio limita la duración a 1 minuto. Se conserva el comportamiento actual. Referencias: `app/__init__.py` y `app/routes.py`.
- README y `EXPO-SAN-PABLO.md` describen de forma distinta la activación de la Expo. Unificar la documentación sin eliminar información útil después de completar el refactor.
- El README ya enumera las cuentas demo institucionales que crea `iniciar.py`; la discrepancia de dominios indicada en el encargo no está presente en esta revisión.
