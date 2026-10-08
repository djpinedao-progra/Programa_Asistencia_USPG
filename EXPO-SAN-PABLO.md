# Asistencia de Expo San Pablo

## Activación en el programa existente

1. Instalar las dependencias: `pip install -r requirements.txt`.
2. Crear la tabla nueva conservando los datos actuales: `flask --app run migrate-expo`.
   En Render, `prepare_production.py` también crea la tabla automáticamente durante el despliegue.
3. Configurar `APP_BASE_URL` con la dirección pública HTTPS del programa, sin barra final.
4. Reiniciar o publicar el programa actualizado.
5. Entrar como administrador → **Expo San Pablo** y descargar el QR.

El formulario está en `/expo-san-pablo`. El QR apunta siempre a esa dirección;
no necesita cuentas y no utiliza los QR temporales de las clases. Debe apuntar a
un servidor accesible para los asistentes, no a `localhost`. Si cambia el dominio,
es necesario imprimir nuevamente el QR.

## Registro y reportes

- Nombre, correo de cualquier proveedor válido, categoría y participación obligatorios.
- Opinión opcional y consentimiento obligatorio.
- Las categorías son declaradas: estudiante, catedrático y público general.
- Se guarda una asistencia por correo normalizado; repetirlo no altera datos ni suma asistentes.
- El registro acredita un envío del formulario, no verifica físicamente la presencia ni la propiedad del correo.
- Solo el administrador puede ver los correos, opiniones, totales y descargar PDF o Excel.
- El resumen muestra el total general y las tres categorías; el filtro limita el detalle y las exportaciones.
- Las exportaciones contienen todos los registros seleccionados, no solo la página visible.
- Fecha y hora en la zona configurada del programa (por defecto Guatemala).
- Este módulo representa una sola Expo San Pablo; no debe reutilizarse para otro evento sin incorporar un evento separado.

## Pruebas

`python -m pytest tests/test_expo.py`
