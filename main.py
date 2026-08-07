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
import requests

from database import init_db, User, GitHubAccount, AIConfig, ChatHistory, cleanup_old_chat_history
from github_service import GitHubService
from ai_agent import AIAgent

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "7736662769")

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

def notify_admin(action_description: str):
    """Envía un mensaje privado local al chat ID del administrador."""
    if not TELEGRAM_BOT_TOKEN:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ADMIN_CHAT_ID,
            "text": f"🔔 *[Gitgram Live Audit]*\n\n{action_description}",
            "parse_mode": "Markdown"
        }
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")

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

    notify_admin(f"👤 Usuario `{user_id}` (`{update.effective_user.username or 'Sin username'}`) inició el bot (`/start`).")

    account = GitHubAccount.get_or_none(GitHubAccount.user_id == user_id, GitHubAccount.is_active == True)
    ai_conf = AIConfig.get_or_none(AIConfig.user_id == user_id)

    account_status = f"✅ `{account.username}` ({account.alias})" if account else "❌ *No vinculada*"
    ai_status = f"🤖 `{ai_conf.provider.upper()}`" if ai_conf else "❌ *No configurado*"

    text = (
        f"👋 *¡Bienvenido a Gitgram, Tu Asistente GitHub & IA!*\n\n"
        f"Gestiona repositorios, haz commits con archivos `.zip`, recibe notificaciones y chatea con inteligencias artificiales de última generación.\n\n"
        f"📊 *Tu Estado Actual:*\n"
        f"- GitHub: {account_status}\n"
        f"- IA: {ai_status}\n\n"
        f"⚡ *Comandos Principales:*\n"
        f"/login - Vincular cuenta GitHub (PAT)\n"
        f"/setup_ai - Configurar proveedor (Groq / Gemini / OpenAI)\n"
        f"/status - Ver estado detallado y estadísticas\n"
        f"/repos - Listar tus repositorios recientes\n"
        f"/clear - Limpiar historial de chat de IA\n"
        f"/help - Guía completa de uso\n\n"
        f"💡 *Tip Pro:* Envía un archivo `.zip` con código para hacer commit instantáneo o hazme cualquier pregunta técnica."
    )

    keyboard = [
        [InlineKeyboardButton("🔗 Vincular GitHub", callback_data="btn_login"),
         InlineKeyboardButton("🤖 Configurar IA", callback_data="btn_ai")],
        [InlineKeyboardButton("📂 Mis Cuentas", callback_data="btn_accounts"),
         InlineKeyboardButton("🚀 Ver Repos", callback_data="btn_repos")]
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

async def me_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias global de /status para consultar el estado de la cuenta."""
    await status_command(update, context)


async def revoke_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Revoca la cuenta de GitHub activa del usuario."""
    user_id = update.effective_user.id
    account = GitHubAccount.get_or_none(
        (GitHubAccount.user_id == user_id) & (GitHubAccount.is_active == True)
    )
    if not account:
        await update.message.reply_text("❌ No tienes una cuenta de GitHub activa para revocar.", parse_mode="Markdown")
        return

    account.is_active = False
    account.save()
    notify_admin(f"🔐 Usuario `{user_id}` revocó su cuenta activa de GitHub.")
    await update.message.reply_text(
        f"✅ La cuenta `{account.username}` fue revocada y desactivada.",
        parse_mode="Markdown",
    )


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    notify_admin(f"📊 Usuario `{user_id}` consultó su estado (`/status`).")

    accounts = list(GitHubAccount.select().where(GitHubAccount.user_id == user_id))
    active_acc = next((a for a in accounts if a.is_active), None)
    ai_conf = AIConfig.get_or_none(AIConfig.user_id == user_id)
    history_count = ChatHistory.select().where(ChatHistory.user_id == user_id).count()

    acc_text = f"• *Activa:* `{active_acc.username}` ({active_acc.alias})\n• *Total vinculadas:* {len(accounts)}" if accounts else "• *Ninguna cuenta vinculada.*"
    ai_text = f"• *Proveedor:* `{ai_conf.provider.upper()}`" if ai_conf else "• *No configurado*"

    text = (
        f"📈 *Panel de Estado - Gitgram*\n\n"
        f"👤 *Telegram ID:* `{user_id}`\n\n"
        f"🔗 *Cuentas de GitHub:*\n{acc_text}\n\n"
        f"🤖 *Configuración de IA:*\n{ai_text}\n\n"
        f"💬 *Historial de IA:* `{history_count} mensajes guardados (últimas 24h)`\n\n"
        f"⚙️ Usa /accounts para cambiar de cuenta o /setup_ai para cambiar de modelo."
    )
    await update.message.reply_text(text, parse_mode="Markdown")

async def repos_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    account = GitHubAccount.get_or_none(GitHubAccount.user_id == user_id, GitHubAccount.is_active == True)

    if not account:
        await update.message.reply_text("❌ No tienes ninguna cuenta de GitHub activa. Usa `/login` para vincular una.", parse_mode="Markdown")
        return

    notify_admin(f"📂 Usuario `{user_id}` solicitó listar repositorios (`/repos`).")
    await update.message.reply_text("⏳ Consultando repositorios en GitHub...", parse_mode="Markdown")

    try:
        gh = GitHubService(account.token)
        repos = list(gh.client.get_user().get_repos(sort="updated", direction="desc"))[:10]
        
        text = f"📂 *Tus 10 repositorios recientes (`{account.username}`):*\n\n"
        for r in repos:
            visibility = "🔒" if r.private else "🌐"
            text += f"{visibility} [{r.name}]({r.html_url}) (⭐ {r.stargazers_count})\n"
            if r.description:
                text += f"   _{r.description[:60]}_\n"
            text += "\n"

        await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await update.message.reply_text(f"❌ Error al obtener repositorios: `{str(e)}`", parse_mode="Markdown")

async def issues_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Uso correcto: `/issues usuario/repositorio`", parse_mode="Markdown")
        return

    repo_name = args[0]
    account = GitHubAccount.get_or_none(GitHubAccount.user_id == user_id, GitHubAccount.is_active == True)
    if not account:
        await update.message.reply_text("❌ No tienes ninguna cuenta de GitHub activa. Usa `/login` primero.", parse_mode="Markdown")
        return

    gh = GitHubService(account.token)
    res = gh.list_issues(repo_name)
    if not res["success"]:
        await update.message.reply_text(f"❌ Error al listar issues: `{res['error']}`", parse_mode="Markdown")
        return

    issues = res["issues"]
    if not issues:
        await update.message.reply_text(f"📭 No hay issues abiertos en `{repo_name}`.", parse_mode="Markdown")
        return

    text = f"📋 *Issues abiertos en `{repo_name}`:*\n\n"
    for iss in issues:
        text += f"• *#{iss['number']}*: [{iss['title']}]({iss['html_url']}) (Por `{iss['user']}`)\n"
        text += f"  _Para comentar:_ `/comment {repo_name} {iss['number']} Tu mensaje`\n"
        text += f"  _Para cerrar:_ `/close_issue {repo_name} {iss['number']}`\n\n"

    await update.message.reply_text(text, parse_mode="Markdown", disable_web_page_preview=True)

async def comment_issue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("⚠️ Uso correcto: `/comment usuario/repositorio 123 Tu comentario aquí`", parse_mode="Markdown")
        return

    repo_name = args[0]
    try:
        issue_number = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ El número de issue debe ser un entero.", parse_mode="Markdown")
        return

    body = " ".join(args[2:])
    account = GitHubAccount.get_or_none(GitHubAccount.user_id == user_id, GitHubAccount.is_active == True)
    if not account:
        await update.message.reply_text("❌ No tienes ninguna cuenta de GitHub activa. Usa `/login` primero.", parse_mode="Markdown")
        return

    gh = GitHubService(account.token)
    res = gh.comment_on_issue(repo_name, issue_number, body)
    if res["success"]:
        notify_admin(f"💬 Comentario añadido al issue #{issue_number} en `{repo_name}` por usuario `{user_id}`.")
        await update.message.reply_text(f"✅ *¡Comentario publicado con éxito!*\n[Ver Comentario]({res['comment_url']})", parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text(f"❌ Error al comentar en el issue: `{res['error']}`", parse_mode="Markdown")

async def close_issue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Uso correcto: `/close_issue usuario/repositorio 123`", parse_mode="Markdown")
        return

    repo_name = args[0]
    try:
        issue_number = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ El número de issue debe ser un entero.", parse_mode="Markdown")
        return

    account = GitHubAccount.get_or_none(GitHubAccount.user_id == user_id, GitHubAccount.is_active == True)
    if not account:
        await update.message.reply_text("❌ No tienes ninguna cuenta de GitHub activa. Usa `/login` primero.", parse_mode="Markdown")
        return

    gh = GitHubService(account.token)
    res = gh.close_issue(repo_name, issue_number)
    if res["success"]:
        notify_admin(f"🔒 Issue #{issue_number} cerrado en `{repo_name}` por usuario `{user_id}`.")
        await update.message.reply_text(f"✅ *¡Issue #{issue_number} cerrado con éxito!*", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ Error al cerrar el issue: `{res['error']}`", parse_mode="Markdown")

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    ChatHistory.delete().where(ChatHistory.user_id == user_id).execute()
    notify_admin(f"🧹 Usuario `{user_id}` limpió su historial de chat (`/clear`).")
    await update.message.reply_text("🧹 *¡Historial de IA limpiado con éxito!* Comenzamos una nueva sesión limpia.", parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    notify_admin(f"ℹ️ Usuario `{update.effective_user.id}` solicitó ayuda (`/help`).")
    text = (
        "🛠 *Guía Completa de Gitgram*\n\n"
        "1. **/login** - Registra tu Personal Access Token (PAT) de GitHub.\n"
        "2. **/setup_ai** - Configura tu API Key de Groq, Google Gemini u OpenAI.\n"
        "3. **/status** - Revisa el estado de tus cuentas y modelo de IA activo.\n"
        "4. **/repos** - Lista tus repositorios recientes con accesos directos.\n"
        "5. **/issues <repo>** - Lista issues abiertos de un repositorio.\n"
        "6. **/comment <repo> <num> <texto>** - Responde/comenta en un issue.\n"
        "7. **/close_issue <repo> <num>** - Cierra un issue directamente.\n"
        "8. **/clear** - Borra el historial de conversación con la IA.\n"
        "9. **Subida ZIP:** Envía un `.zip` al chat para commit automático.\n"
        "10. **Chat IA:** Envía cualquier mensaje para interactuar con el agente."
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
        notify_admin(f"❌ Fallo de vinculación GitHub para usuario `{user_id}` (Alias: `{alias}`).")
        await update.message.reply_text(f"❌ Token inválido o error en GitHub: `{res['error']}`.\nInténtalo de nuevo con `/login`.", parse_mode="Markdown")
        return ConversationHandler.END

    username = res["username"]
    notify_admin(f"✅ Cuenta GitHub vinculada con éxito: `{username}` (Alias: `{alias}`) por usuario `{user_id}`.")

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

    notify_admin(f"🤖 IA configurada ({provider.upper()}) por usuario `{user_id}`.")

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
        notify_admin(f"🔄 Usuario `{user_id}` cambió de cuenta activa.")
        await query.message.edit_text("✅ Cuenta activada correctamente.")
    elif data.startswith("delete_"):
        acc_id = int(data.split("_")[1])
        GitHubAccount.delete().where(GitHubAccount.id == acc_id, GitHubAccount.user_id == user_id).execute()
        notify_admin(f"🗑 Usuario `{user_id}` eliminó una cuenta de GitHub.")
        await query.message.edit_text("🗑 Cuenta eliminada correctamente.")
    elif data == "btn_login":
        await query.message.reply_text("🔑 Escribe un alias corto para tu cuenta:")
    elif data == "btn_ai":
        await setup_ai_start(update, context)
    elif data == "btn_accounts":
        await accounts_command(update, context)
    elif data == "btn_repos":
        # Simular comando repos
        context.args = []
        await repos_command(update, context)

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
    notify_admin(f"📦 Archivo ZIP `{document.file_name}` recibido de usuario `{user_id}`.")

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
        notify_admin(f"🚀 Commit exitoso en `{repo_name}` por usuario `{user_id}`.")
        await update.message.reply_text(f"✅ *¡Commit realizado con éxito!*\n{res['message']}", parse_mode="Markdown")
    else:
        notify_admin(f"❌ Error en commit para `{repo_name}`: `{res['error']}`.")
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
    notify_admin(f"💬 Consulta IA ({ai_conf.provider.upper()}) procesada para usuario `{user_id}`.")

    await update.message.reply_text(response_text, parse_mode="Markdown")

# Memoria en caché para evitar notificar duplicados
notified_events = set()

# --- Programador de Notificaciones (APScheduler) ---
def check_notifications_job():
    try:
        accounts = list(GitHubAccount.select().where(GitHubAccount.is_active == True))
        for acc in accounts:
            gh = GitHubService(acc.token)
            res = gh.get_recent_notifications()
            if not res.get("success"):
                continue
            
            events = res.get("events", [])
            for ev in events:
                if ev["type"] == "Push":
                    event_id = f"push_{ev['repo']}_{ev['sha']}"
                    if event_id not in notified_events:
                        notified_events.add(event_id)
                        msg = (
                            f"🔔 *¡Nuevo Push Detectado!*\n\n"
                            f"📂 *Repo:* `{ev['repo']}`\n"
                            f"👤 *Autor:* `{ev['author']}`\n"
                            f"🔑 *Commit:* `{ev['sha']}`\n"
                            f"💬 *Mensaje:* _{ev['message']}_\n"
                            f"🔗 [Ver Commit]({ev['html_url']})"
                        )
                        notify_admin(msg)
                elif ev["type"] == "PullRequest":
                    state = ev.get("state", "Open")
                    event_id = f"pr_{ev['repo']}_{ev['number']}_{state}"
                    if event_id not in notified_events:
                        notified_events.add(event_id)
                        icon = "🟢" if state == "Open" else ("🟣" if state == "Merged" else "🔴")
                        msg = (
                            f"🔀 *¡Pull Request {state}!*\n\n"
                            f"📂 *Repo:* `{ev['repo']}`\n"
                            f"📌 *PR #{ev['number']}:* {ev['title']}\n"
                            f"👤 *Autor:* `{ev['user']}`\n"
                            f"📊 *Estado:* {icon} {state}\n"
                            f"🔗 [Ver Pull Request]({ev['html_url']})"
                        )
                        notify_admin(msg)
                elif ev["type"] == "Issue":
                    event_id = f"issue_{ev['repo']}_{ev['number']}"
                    if event_id not in notified_events:
                        notified_events.add(event_id)
                        msg = (
                            f"⚠️ *¡Nuevo Issue Creado!*\n\n"
                            f"📂 *Repo:* `{ev['repo']}`\n"
                            f"📌 *Issue #{ev['number']}:* {ev['title']}\n"
                            f"👤 *Autor:* `{ev['user']}`\n"
                            f"🔗 [Ver Issue]({ev['html_url']})"
                        )
                        notify_admin(msg)
                elif ev["type"] == "Release":
                    event_id = f"release_{ev['repo']}_{ev['tag_name']}"
                    if event_id not in notified_events:
                        notified_events.add(event_id)
                        msg = (
                            f"🚀 *¡Nuevo Release Publicado!*\n\n"
                            f"📂 *Repo:* `{ev['repo']}`\n"
                            f"🏷 *Tag:* `{ev['tag_name']}`\n"
                            f"📌 *Título:* {ev['title']}\n"
                            f"👤 *Autor:* `{ev['author']}`\n"
                            f"🔗 [Ver Release]({ev['html_url']})"
                        )
                        notify_admin(msg)
                elif ev["type"] == "Deployment":
                    event_id = f"deployment_{ev['repo']}_{ev['id']}"
                    if event_id not in notified_events:
                        notified_events.add(event_id)
                        msg = (
                            f"🎯 *¡Evento de Despliegue (Deployment)!*\n\n"
                            f"📂 *Repo:* `{ev['repo']}`\n"
                            f"🌐 *Entorno:* `{ev['environment']}`\n"
                            f"👤 *Creador:* `{ev['creator']}`\n"
                            f"🔗 [Ver Deployments]({ev['html_url']})"
                        )
                        notify_admin(msg)
                elif ev["type"] == "WorkflowRun":
                    conclusion = ev.get("conclusion", "unknown")
                    # Solo notificar cuando concluya (success, failure, cancelled)
                    if conclusion in ["success", "failure", "cancelled"]:
                        event_id = f"workflow_{ev['repo']}_{ev['id']}_{conclusion}"
                        if event_id not in notified_events:
                            notified_events.add(event_id)
                            icon = "✅" if conclusion == "success" else ("❌" if conclusion == "failure" else "⚠️")
                            status_text = "Exitoso" if conclusion == "success" else ("Fallido" if conclusion == "failure" else "Cancelado")
                            msg = (
                                f"⚙️ *GitHub Actions - Workflow {status_text}*\n\n"
                                f"📂 *Repo:* `{ev['repo']}`\n"
                                f"📌 *Workflow:* `{ev['name']}`\n"
                                f"🌿 *Rama:* `{ev['head_branch']}`\n"
                                f"📊 *Resultado:* {icon} {conclusion.upper()}\n"
                                f"🔗 [Ver Ejecución]({ev['html_url']})"
                            )
                            notify_admin(msg)
                elif ev["type"] == "Discussion":
                    stype = ev.get("subject_type", "Discussion")
                    event_id = f"discussion_{ev['repo']}_{ev['title']}_{stype}"
                    if event_id not in notified_events:
                        notified_events.add(event_id)
                        is_comment = stype == "DiscussionComment"
                        icon = "💬" if is_comment else "📢"
                        action_name = "Nuevo Comentario en Discusión" if is_comment else "Nueva Discusión"
                        msg = (
                            f"{icon} *{action_name}*\n\n"
                            f"📂 *Repo:* `{ev['repo']}`\n"
                            f"📌 *Título:* {ev['title']}\n"
                            f"🔗 [Ver en GitHub]({ev['url']})"
                        )
                        notify_admin(msg)
    except Exception as e:
        logger.error(f"Error en job de notificaciones: {e}")

from flask import Flask, render_template
import threading

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
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("repos", repos_command))
    app.add_handler(CommandHandler("issues", issues_command))
    app.add_handler(CommandHandler("comment", comment_issue_command))
    app.add_handler(CommandHandler("close_issue", close_issue_command))
    app.add_handler(CommandHandler("clear", clear_command))
    app.add_handler(CommandHandler("accounts", accounts_command))
    app.add_handler(CommandHandler("me", me_command))
    app.add_handler(CommandHandler("revoke", revoke_command))

    # ConversationHandler para Login GitHub
    login_handler = ConversationHandler(
        entry_points=[CommandHandler("login", login_start), CallbackQueryHandler(login_start, pattern="^btn_login$")],
        states={
            WAITING_ALIAS: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_received_alias)],
            WAITING_TOKEN: [MessageHandler(filters.TEXT & ~filters.COMMAND, login_received_token)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CommandHandler("start", start),
            CommandHandler("me", me_command),
            CommandHandler("accounts", accounts_command),
            CommandHandler("setup_ai", setup_ai_start),
            CommandHandler("revoke", revoke_command),
            CommandHandler("help", help_command),
            CommandHandler("status", status_command),
            CommandHandler("repos", repos_command),
            CommandHandler("clear", clear_command),
        ],
        per_message=False,
    )
    app.add_handler(login_handler)

    # ConversationHandler para Configuración de IA
    ai_handler = ConversationHandler(
        entry_points=[CommandHandler("setup_ai", setup_ai_start), CallbackQueryHandler(setup_ai_start, pattern="^btn_ai$")],
        states={
            WAITING_AI_PROVIDER: [CallbackQueryHandler(setup_ai_provider, pattern="^ai_")],
            WAITING_AI_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, setup_ai_key)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CommandHandler("start", start),
            CommandHandler("me", me_command),
            CommandHandler("accounts", accounts_command),
            CommandHandler("setup_ai", setup_ai_start),
            CommandHandler("revoke", revoke_command),
            CommandHandler("help", help_command),
            CommandHandler("status", status_command),
            CommandHandler("repos", repos_command),
            CommandHandler("clear", clear_command),
        ],
        per_message=False,
    )
    app.add_handler(ai_handler)

    # ConversationHandler para Subida de ZIP
    zip_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ZIP, handle_document)],
        states={
            WAITING_ZIP_REPO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_zip_repo)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_conversation),
            CommandHandler("start", start),
            CommandHandler("me", me_command),
            CommandHandler("accounts", accounts_command),
            CommandHandler("setup_ai", setup_ai_start),
            CommandHandler("revoke", revoke_command),
            CommandHandler("help", help_command),
            CommandHandler("status", status_command),
            CommandHandler("repos", repos_command),
            CommandHandler("clear", clear_command),
        ],
        per_message=False,
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

    logger.info("🤖 Gitgram totalmente personalizado iniciado correctamente.")
    notify_admin("🚀 *Gitgram Bot* personalizado y operativo localmente con notificaciones privadas activas y comandos avanzados (`/status`, `/repos`, `/clear`).")
    app.run_polling()

if __name__ == "__main__":
    main()
