import os
import logging
import asyncio
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv

from database import init_db, User, GitHubAccount, AIConfig, ChatHistory, cleanup_old_chat_history
from github_service import GitHubService
from ai_agent import AIAgent

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Estados de conversación
WAITING_ALIAS, WAITING_TOKEN = range(2)
WAITING_AI_PROVIDER, WAITING_AI_KEY = range(2, 4)
WAITING_ZIP_REPO = 4

# Memoria temporal para archivos ZIP pendientes de commit por usuario
pending_zips = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    User.get_or_create(telegram_id=user_id)
    cleanup_old_chat_history()

    account = GitHubAccount.get_or_none(GitHubAccount.user_id == user_id, GitHubAccount.is_active == True)
    ai_conf = AIConfig.get_or_none(AIConfig.user_id == user_id)

    account_status = f"✅ `{account.username}` ({account.alias})" if account else "❌ *No vinculada*"
    ai_status = f"🤖 `{ai_conf.provider.upper()}`" if ai_conf else "❌ *No configurado*"

    text = (
        f"👋 *¡Bienvenido a Gitgram!*\n\n"
        f"Tu asistente avanzado de GitHub y Agente de IA en Telegram.\n\n"
        f"📊 *Estado Actual:*\n"
        f"- Cuenta GitHub: {account_status}\n"
        f"- Proveedor IA: {ai_status}\n\n"
        f"⚙️ *Comandos disponibles:*\n"
        f"/login - Vincular cuenta de GitHub\n"
        f"/setup_ai - Configurar proveedor de IA (Groq/Gemini/OpenAI)\n"
        f"/accounts - Gestionar cuentas y cambiar activa\n"
        f"/help - Ver ayuda detallada\n\n"
        f"💡 *Tip:* Envía un archivo `.zip` para subirlo directamente a tu repositorio o chatea conmigo para programar y consultar código."
    )

    keyboard = [
        [InlineKeyboardButton("🔗 Vincular GitHub", callback_data="btn_login"),
         InlineKeyboardButton("🤖 Configurar IA", callback_data="btn_ai")],
        [InlineKeyboardButton("📂 Mis Cuentas", callback_data="btn_accounts")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    splash_path = os.path.join("static", "splash_banner.png")
    if os.path.exists(splash_path):
        with open(splash_path, "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=text,
                parse_mode="Markdown",
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "🛠 *Guía de Uso de Gitgram*\n\n"
        "1. **Vincular GitHub:** Usa `/login` para registrar tu Personal Access Token (PAT) con permisos de repo.\n"
        "2. **Configurar IA:** Usa `/setup_ai` para elegir entre Groq (Llama 3), Google Gemini o OpenAI (GPT-4o-mini).\n"
        "3. **Subida de Código (.zip):** Envía cualquier archivo `.zip` al chat. El bot te pedirá el repositorio destino (`owner/repo`) y hará commit automático de los archivos.\n"
        "4. **Historial Inteligente:** El bot recuerda el contexto de las últimas 24 horas para ayudarte con refactorización o dudas de código."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

# --- Flujo de Login GitHub ---
async def login_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        await query.message.reply_text("🔑 Por favor, escribe un *alias* corto para identificar esta cuenta de GitHub (ej: `personal`, `trabajo`):", parse_mode="Markdown")
    else:
        await update.message.reply_text("🔑 Por favor, escribe un *alias* corto para identificar esta cuenta de GitHub (ej: `personal`, `trabajo`):", parse_mode="Markdown")
    return WAITING_ALIAS

async def login_received_alias(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['github_alias'] = update.message.text.strip()
    await update.message.reply_text(
        "📝 Ahora, envía tu **Personal Access Token (PAT)** de GitHub con permisos sobre repositorios.\n\n"
        "*(Puedes generarlo en GitHub -> Settings -> Developer Settings -> Personal Access Tokens)*",
        parse_mode="Markdown"
    )
    return WAITING_TOKEN

async def login_received_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    alias = context.user_data.get('github_alias', 'default')
    token = update.message.text.strip()

    gh_service = GitHubService(token)
    res = gh_service.verify_token()

    if not res["success"]:
        await update.message.reply_text(f"❌ Token inválido o error en GitHub: `{res['error']}`.\nInténtalo de nuevo con `/login`.", parse_mode="Markdown")
        return ConversationHandler.END

    username = res["username"]

    # Desactivar otras cuentas si es la primera o marcar esta como activa
    GitHubAccount.update(is_active=False).where(GitHubAccount.user_id == user_id).execute()
    GitHubAccount.create(
        user_id=user_id,
        alias=alias,
        token=token,
        username=username,
        is_active=True
    )

    await update.message.reply_text(
        f"✅ ¡Cuenta de GitHub vinculada con éxito!\n\n"
        f"- Usuario: `{username}`\n"
        f"- Alias: `{alias}`\n"
        f"- Estado: *Activa*",
        parse_mode="Markdown"
    )
    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.", parse_mode="Markdown")
    return ConversationHandler.END

# --- Flujo de Configuración de IA ---
async def setup_ai_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()
        target = query.message
    else:
        target = update.message

    keyboard = [
        [InlineKeyboardButton("Groq (Llama 3)", callback_data="ai_groq"),
         InlineKeyboardButton("Google Gemini", callback_data="ai_gemini")],
        [InlineKeyboardButton("OpenAI (GPT-4o)", callback_data="ai_openai")]
    ]
    await target.reply_text("🤖 Selecciona el proveedor de Inteligencia Artificial que deseas utilizar:", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_AI_PROVIDER

async def setup_ai_provider(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    provider = query.data.replace("ai_", "")
    context.user_data['ai_provider'] = provider

    await query.message.reply_text(f"🔑 Has seleccionado **{provider.upper()}**. Ahora envía tu API Key para este proveedor:", parse_mode="Markdown")
    return WAITING_AI_KEY

async def setup_ai_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    provider = context.user_data.get('ai_provider', 'groq')
    api_key = update.message.text.strip()

    AIConfig.delete().where(AIConfig.user_id == user_id).execute()
    AIConfig.create(user_id=user_id, provider=provider, api_key=api_key)

    await update.message.reply_text(f"✅ ¡Configuración de IA guardada con éxito!\nProveedor: `{provider.upper()}`", parse_mode="Markdown")
    return ConversationHandler.END

# --- Gestión de Cuentas ---
async def accounts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    accounts = list(GitHubAccount.select().where(GitHubAccount.user_id == user_id))

    if not accounts:
        await update.message.reply_text("❌ No tienes cuentas de GitHub vinculadas. Usa `/login` para agregar una.", parse_mode="Markdown")
        return

    text = "📂 *Tus cuentas de GitHub vinculadas:*\n\n"
    keyboard = []
    for acc in accounts:
        status = "🟢 (Activa)" if acc.is_active else "⚪"
        text += f"- *{acc.alias}* (`{acc.username}`) {status}\n"
        if not acc.is_active:
            keyboard.append([InlineKeyboardButton(f"Activar {acc.alias}", callback_data=f"activate_{acc.id}")])
        keyboard.append([InlineKeyboardButton(f"Eliminar {acc.alias}", callback_data=f"delete_{acc.id}")])

    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

async def account_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = query.from_user.id

    if data.startswith("activate_"):
        acc_id = int(data.split("_")[1])
        GitHubAccount.update(is_active=False).where(GitHubAccount.user_id == user_id).execute()
        GitHubAccount.update(is_active=True).where(GitHubAccount.id == acc_id).execute()
        await query.message.edit_text("✅ Cuenta activada correctamente.")
    elif data.startswith("delete_"):
        acc_id = int(data.split("_")[1])
        GitHubAccount.delete().where(GitHubAccount.id == acc_id, GitHubAccount.user_id == user_id).execute()
        await query.message.edit_text("🗑 Cuenta eliminada correctamente.")
    elif data == "btn_login":
        await query.message.reply_text("🔑 Escribe un alias corto para tu cuenta:")
    elif data == "btn_ai":
        await setup_ai_start(update, context)
    elif data == "btn_accounts":
        await accounts_command(update, context)

# --- Manejo de Documentos ZIP para Commits ---
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    if not document.file_name.endswith('.zip'):
        await update.message.reply_text("⚠️ Por favor, envía un archivo con extensión `.zip`.", parse_mode="Markdown")
        return

    user_id = update.effective_user.id
    account = GitHubAccount.get_or_none(GitHubAccount.user_id == user_id, GitHubAccount.is_active == True)
    if not account:
        await update.message.reply_text("❌ No tienes ninguna cuenta de GitHub activa. Usa `/login` primero.", parse_mode="Markdown")
        return

    file = await context.bot.get_file(document.file_id)
    file_bytes = await file.download_as_bytearray()

    pending_zips[user_id] = bytes(file_bytes)

    await update.message.reply_text(
        f"📦 Archivo `{document.file_name}` recibido.\n\n"
        f"Por favor, indica el repositorio destino en formato `usuario/repositorio` (ej: `tu-usuario/mi-repo`):",
        parse_mode="Markdown"
    )
    return WAITING_ZIP_REPO

async def receive_zip_repo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    repo_name = update.message.text.strip()
    zip_bytes = pending_zips.get(user_id)

    if not zip_bytes:
        await update.message.reply_text("❌ No hay ningún archivo ZIP pendiente. Vuelve a enviarlo.", parse_mode="Markdown")
        return ConversationHandler.END

    account = GitHubAccount.get_or_none(GitHubAccount.user_id == user_id, GitHubAccount.is_active == True)
    if not account:
        await update.message.reply_text("❌ Cuenta de GitHub no encontrada.", parse_mode="Markdown")
        return ConversationHandler.END

    gh_service = GitHubService(account.token)
    await update.message.reply_text(f"⏳ Subiendo y aplicando commit en `{repo_name}`...", parse_mode="Markdown")

    res = gh_service.commit_zip_content(repo_name, zip_bytes)
    if res["success"]:
        await update.message.reply_text(f"✅ *¡Commit realizado con éxito!*\n{res['message']}", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Error al hacer commit: `{res['error']}`", parse_mode="Markdown")

    if user_id in pending_zips:
        del pending_zips[user_id]

    return ConversationHandler.END

# --- Manejo de Mensajes de Texto (Agente IA) ---
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    User.get_or_create(telegram_id=user_id)
    text = update.message.text

    ai_conf = AIConfig.get_or_none(AIConfig.user_id == user_id)
    if not ai_conf:
        await update.message.reply_text("❌ No tienes configurado ningún proveedor de IA. Usa `/setup_ai` para configurarlo.", parse_mode="Markdown")
        return

    # Obtener historial reciente de las últimas 24h
    cleanup_old_chat_history()
    recent_history = list(
        ChatHistory.select()
        .where(ChatHistory.user_id == user_id)
        .order_by(ChatHistory.created_at.asc())
    )
    history_list = [{"role": h.role, "content": h.content} for h in recent_history]

    # Guardar mensaje del usuario
    ChatHistory.create(user_id=user_id, role="user", content=text)

    agent = AIAgent(ai_conf.provider, ai_conf.api_key)
    response_text = agent.generate_response(history_list, text)

    # Guardar respuesta del asistente
    ChatHistory.create(user_id=user_id, role="assistant", content=response_text)

    await update.message.reply_text(response_text, parse_mode="Markdown")

# --- Programador de Notificaciones (APScheduler) ---
def check_notifications_job():
    # Tarea en segundo plano para verificar notificaciones de GitHub de usuarios activos
    try:
        accounts = GitHubAccount.select().where(GitHubAccount.is_active == True)
        for acc in accounts:
            gh = GitHubService(acc.token)
            notifs = gh.get_recent_notifications()
            # Aquí se podría enviar mensaje al usuario si hay notificaciones nuevas
    except Exception as e:
        logger.error(f"Error en job de notificaciones: {e}")

from flask import Flask, render_template
import threading

# Configuración de Flask para la Landing Page y Health Check
web_app = Flask(__name__)

@web_app.route("/")
def index():
    return render_template("index.html")

@web_app.route("/health")
def health():
    return {"status": "healthy", "bot": "Gitgram"}, 200

def run_flask():
    port = int(os.getenv("PORT", 5000))
    web_app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("¡Falta TELEGRAM_BOT_TOKEN en las variables de entorno!")
        return

    init_db()

    # Iniciar servidor Flask en un hilo secundario
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🌐 Servidor Flask iniciado en segundo plano.")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Handlers de comandos generales
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("accounts", accounts_command))

    # ConversationHandler para Login GitHub
    login_handler = ConversationHandler(
        entry_points=[CommandHandler("login", login_start), CallbackQueryHandler(login_start, pattern="^btn_login$")],
        states={
            WAITING_ALIAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_received_alias)],
            WAITING_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_received_token)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    app.add_handler(login_handler)

    # ConversationHandler para Configuración de IA
    ai_handler = ConversationHandler(
        entry_points=[CommandHandler("setup_ai", setup_ai_start), CallbackQueryHandler(setup_ai_start, pattern="^btn_ai$")],
        states={
            WAITING_AI_PROVIDER: [CallbackQueryHandler(setup_ai_provider, pattern="^ai_")],
            WAITING_AI_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_ai_key)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    app.add_handler(ai_handler)

    # ConversationHandler para Subida de ZIP
    zip_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ZIP, handle_document)],
        states={
            WAITING_ZIP_REPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_zip_repo)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )
    app.add_handler(zip_handler)

    # Callback general para botones de cuentas
    app.add_handler(CallbackQueryHandler(account_callback, pattern="^(activate_|delete_|btn_)"))

    # Manejador de mensajes de texto (Agente IA)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Scheduler de fondo
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_notifications_job, 'interval', minutes=5)
    scheduler.start()

    logger.info("🤖 Gitgram iniciado correctamente. Escuchando eventos...")
    app.run_polling()

if __name__ == "__main__":
    main()
