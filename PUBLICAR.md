# Publicación externa

Esta carpeta contiene la aplicación, no una página estática. Publicar HTML por sí solo no habilita cuentas ni guarda asistencias.

1. Sube el contenido de USPG-Nuevo a un repositorio privado de GitHub; excluye .env, instance/, copias de seguridad y archivos de base de datos.
2. En Render crea un Blueprint y conecta ese repositorio. El archivo render.yaml configura el servicio Python y PostgreSQL. Revisa y acepta el costo indicado por Render antes de crear los recursos.
3. Completa ADMIN_EMAIL (correo real @administrador.uspg.edu.gt) y ADMIN_PASSWORD (contraseña privada de al menos 8 caracteres), y las variables SMTP del proveedor. No uses las credenciales demo.
4. Publica. La preparación crea las tablas y la primera cuenta administrativa sin borrar datos ni crear cuentas demo. Se crea una base nueva: no importa los datos del demo local.
5. Render entrega el enlace HTTPS. Inicia sesión, crea un catedrático y un alumno con buzones universitarios reales, crea un curso y matricula al alumno.
6. Verifica desde dos dispositivos el QR, su vencimiento a los 60 segundos, la asistencia manual y la recepción del correo de recuperación. No se ha comprobado entrega real de correo sin un servicio conectado.
7. Configura y comprueba las copias de seguridad de PostgreSQL con el proveedor antes de usarlo con datos reales.

Guarda las credenciales en las variables privadas del alojamiento; no en GitHub. El programa requiere DATABASE_URL y SECRET_KEY en producción. Reinicios y nuevas publicaciones conservan la base PostgreSQL externa.

Instalaciones existentes: el predeploy usa create_all para una base nueva; no transforma columnas de tablas existentes. Migra y respalda una base anterior antes de conectarla.
