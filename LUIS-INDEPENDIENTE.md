# Programa independiente de Luis

Este reemplazo contiene todo el programa actualizado, incluida la Expo. No requiere archivos de main.

## Inicio local

Usa una carpeta nueva; no copies el archivo .env ni instance/ del programa anterior.

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python iniciar.py --demo --port 5001
```

Para uso real, omite --demo. El programa solicita crear un administrador y utiliza su base nueva luis_independiente.db. El correo administrador debe terminar en @administrador.uspg.edu.gt.

## Servidor

Configura un servicio separado que despliegue la rama Luis, una DATABASE_URL nueva, SECRET_KEY propia y APP_BASE_URL de ese servicio. No uses la base de main. Subir archivos a GitHub no separa una base de datos ya configurada en el servidor. render.yaml contiene nombres propios para esta versión; revisa costos antes de desplegar.

El reemplazo conserva el historial Git de Luis para poder recuperar su versión anterior. No modifica main.
