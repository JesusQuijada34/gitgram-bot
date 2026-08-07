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

## ⚙️ Variables de Entorno Requeridas

Para ejecutar el bot correctamente, es necesario configurar la siguiente variable de entorno principal:

- `TELEGRAM_BOT_TOKEN`: Token HTTP API proporcionado por [@BotFather](https://t.me/BotFather) en Telegram.

Adicionalmente, cada usuario configura de manera interactiva dentro del bot sus credenciales de GitHub (Personal Access Token) y de IA (Groq, Gemini u OpenAI), las cuales se almacenan de forma segura en la base de datos SQLite (`gitgram.db`).

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
