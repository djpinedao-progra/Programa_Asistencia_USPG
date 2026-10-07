# Recuperación, roles y QR

Inicio: python iniciar.py --demo --port 5001
Contraseña demo: Demo-USPG-2026!
Cuentas: admin@administrador.uspg.edu.gt, docente@catedratico.uspg.edu.gt, alumno@alumno.uspg.edu.gt.

## Instalaciones existentes
Respalda la base de datos. Ejecuta `flask --app run.py migrate-teacher-tools` para crear también la tabla password_replacements. El iniciador iniciar.py ejecuta create_all automáticamente.
Las cuentas anteriores con otros dominios ya no podrán iniciar sesión. Actualiza sus correos a direcciones reales del dominio correspondiente con el responsable de la base de datos; no se cambia automáticamente su rol ni se borran datos.
Cierra las sesiones QR anteriores antes de instalar. Los nuevos códigos y renovaciones vencen a los 60 segundos; renovar invalida el código anterior.

## Correo
Copia .env.example a .env y configura SMTP_HOST, SMTP_PORT, SMTP_FROM, SMTP_USERNAME y SMTP_PASSWORD con el servicio universitario. STARTTLS es obligatorio salvo SMTP_SSL=true (TLS directo). No se entregan contraseñas en pantalla ni en logs.
Sin SMTP el envío no funciona; no se altera la contraseña vigente. El mensaje público es genérico para no revelar cuentas existentes. Se registra el fallo de envío sin datos sensibles.
La contraseña temporal se almacena solo como hash, vence en 15 minutos y se activa al iniciar sesión. Cambiar contraseña o iniciar sesión con la contraseña actual cancela el reemplazo pendiente. Límite de una solicitud por cuenta cada dos minutos.
Solo el registro público de alumnos está disponible; docentes y administradores los crea administración. El dominio valida el rol y no concede privilegios por sí solo.
