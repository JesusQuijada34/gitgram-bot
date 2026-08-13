# Gitgram Telegram GitHub Bot

**Identidad del paquete:** `influent.gitgram-bot.v1.0-26.08-21.56`
**Autor:** `JesusQuijada34`
**Plataforma:** `AlphaCube`
**Descripción:** Estructura reparada por MoonFix

## Estructura PackageMaker 3.2.7

Este repositorio fue normalizado mediante **MoonFix**, usando la estructura de PackageMaker 3.2.7. El paquete público debe conservar `details.xml`, `version.res`, `autorun`, `autorun.bat`, `.storedetail`, `updater.py`, `config/settings.json`, los marcadores `.container` y los archivos de documentación correspondientes. El publisher oficial es `influent` y la versión pública no contiene sufijo de plataforma.

## Instalación y ejecución

Instala las dependencias declaradas en `lib/requirements.txt` cuando exista y ejecuta el entrypoint real del proyecto. En Linux, los comandos privilegiados son específicos de Danenone y no deben trasladarse a Windows. En proyectos AlphaCube, la validación Windows debe realizarse con el `buildthis` oficial de PackageMaker.

## Validación

La fuente debe pasar compilación sintáctica, pruebas funcionales disponibles, comprobación de identidad XML, protección contra traversal en ZIP y llamadas seguras a subprocess. Los artefactos `.iflapp` deben ser generados por PackageMaker; los paquetes Debian deben usar el nombre canónico `influent.gitgram-bot.v1.0-26.08-21.56_ARCH.deb`.

## Release

El tag y el título del release deben ser exactamente `v1.0-26.08-21.56`. Los assets deben usar el nombre canónico del paquete y una extensión objetiva. No se permite publicar un release AlphaCube que contenga únicamente el build Linux.

## Referencia original

# Gitgram: Bot de Telegram Avanzado para GitHub y Agente de Inteligencia Artificial

**Gitgram** es un bot de Telegram altamente modular y optimizado, diseñado para actuar como un agente de código con soporte multi-cuenta de GitHub, integración de modelos de lenguaje avanzados (Groq, Google Gemini y OpenAI) y un sistema automático de limpieza de historial e notificaciones.

---

## 🏗 Arquitectura del Proyecto

El proyecto sigue una estructura limpia y modular basada en servicios independientes:

| Archivo | Responsabilidad Principal |
| :--- | :--- |
| `main.py` | Lógica central del bot de Telegram, manejadores de comandos, conversaciones e integración con APScheduler. |
| `database.py` | Modelado de datos con Peewee y SQLite, gestión de sesiones de usuario y auto-limpieza de historial a las 24 horas. |
| `ai_agent.py` | Interfaz unificada de IA con soporte para Groq (`llama3-70b-8192`), Google Gemini (`gemini-1.5-flash`) y OpenAI (`gpt-4o-mini`). |
| `github_service.py` | Servicio para validación de tokens, gestión de repositorios, commits automáticos desde archivos `.zip` y notificaciones. |
| `requirements.txt` | Dependencias del sistema y librerías de Python requeridas. |
| `Procfile` | Archivo de configuración para el despliegue automático en Render como proceso en segundo plano (`worker`). |

---

## Clasificación PackageMaker

Gitgram se distribuye como **AlphaCube**: es código fuente de un bot que requiere Python, servicios externos, secretos de Telegram/GitHub/IA y un proceso persistente. No es un binario autónomo para Danenone o Knosthalij.

## Endurecimiento aplicado

Las cargas ZIP están limitadas a 50 MB, cada archivo a 10 MB y el contenido total a 40 MB. Se rechazan nombres de archivo inseguros, rutas absolutas y componentes de traversal antes de ejecutar commits. El bot intenta borrar los mensajes que contienen PAT de GitHub y API keys de IA; para que esa limpieza funcione, necesita permisos de administración en el chat. Las credenciales no deben incluirse en el repositorio ni en logs.

## ⚙️ Variables de Entorno Requeridas

Para ejecutar el bot correctamente, es necesario configurar la siguiente variable de entorno principal:

- `TELEGRAM_BOT_TOKEN`: Token HTTP API proporcionado por [@BotFather](https://t.me/BotFather) en Telegram.

Adicionalmente, cada usuario configura de manera interactiva dentro del bot sus credenciales de GitHub (Personal Access Token) y de IA (Groq, Gemini u OpenAI). Estas credenciales se almacenan en SQLite (`gitgram.db`), por lo que el archivo debe protegerse con permisos del sistema, cifrado de disco y copias de seguridad controladas; no debe publicarse ni compartirse.

---

## 🚀 Instalación y Ejecución Local

1. Clona o descarga el repositorio en tu entorno local o servidor.
2. Instala las dependencias necesarias:
   ```bash
   pip install -r requirements.txt
   ```
3. Configura el archivo `.env` o define la variable de entorno:
   ```bash
   export TELEGRAM_BOT_TOKEN="tu-token-de-telegram"
   ```
4. Ejecuta la aplicación:
   ```bash
   python main.py
   ```

---

## ☁️ Despliegue en Render

Gitgram incluye un `Procfile` optimizado para desplegarse instantáneamente en [Render](https://render.com/) como un servicio de tipo **Background Worker**:

1. Sube el código fuente a un repositorio privado o público en GitHub.
2. En el panel de Render, haz clic en **New +** y selecciona **Background Worker**.
3. Conecta tu repositorio de GitHub.
4. Configura el entorno:
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `worker: python main.py` (Render lee automáticamente el `Procfile`)
5. En la sección **Environment Variables**, añade:
   - `TELEGRAM_BOT_TOKEN`: Tu token de bot de Telegram.
6. Haz clic en **Create Background Worker** y el bot estará operativo 24/7.

---

## 📋 Comandos del Bot

- `/start` - Muestra el menú de bienvenida, estado de cuentas e instrucciones rápidas.
- `/login` - Inicia el asistente interactivo para vincular una cuenta de GitHub mediante Personal Access Token.
- `/setup_ai` - Menú de configuración para seleccionar proveedor de IA y registrar su API Key.
- `/accounts` - Permite alternar entre múltiples cuentas de GitHub guardadas o eliminar accesos.
- `/help` - Muestra la guía de ayuda detallada.

---

## 📄 Referencias y Enlaces Útiles

- [Documentación oficial de python-telegram-bot](https://python-telegram-bot.readthedocs.io/) [1]
- [Documentación oficial de PyGithub](https://pygithub.readthedocs.io/) [2]
- [Documentación de Peewee ORM](http://docs.peewee-orm.com/) [3]
- [Plataforma de despliegue Render](https://render.com/) [4]

---
*Desarrollado con arquitectura modular y optimizada por Manus AI.*
