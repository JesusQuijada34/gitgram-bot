import os
import requests
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("TELEGRAM_BOT_TOKEN")

# 1. Configurar comandos
commands_url = f"https://api.telegram.org/bot{token}/setMyCommands"
commands = {
    "commands": [
        {"command": "start", "description": "Iniciar Gitgram y ver panel principal"},
        {"command": "login", "description": "Vincular cuenta de GitHub con Token (PAT)"},
        {"command": "setup_ai", "description": "Configurar proveedor de IA (Groq/Gemini/OpenAI)"},
        {"command": "status", "description": "Ver estado detallado de cuentas y IA"},
        {"command": "repos", "description": "Listar tus repositorios recientes"},
        {"command": "issues", "description": "Listar issues abiertos de un repositorio"},
        {"command": "comment", "description": "Comentar/responder en un issue"},
        {"command": "close_issue", "description": "Cerrar un issue directamente"},
        {"command": "clear", "description": "Limpiar historial de conversación con la IA"},
        {"command": "help", "description": "Guía completa de uso y comandos"}
    ]
}
res = requests.post(commands_url, json=commands)
print("SetMyCommands:", res.json())

# 2. Configurar Nombre del Bot (setMyName)
name_url = f"https://api.telegram.org/bot{token}/setMyName"
name_data = {"name": "Gitgram 🚀 GitHub & AI Assistant"}
res_name = requests.post(name_url, json=name_data)
print("SetMyName:", res_name.json())

# 3. Configurar Descripción Corta (setMyShortDescription)
short_desc_url = f"https://api.telegram.org/bot{token}/setMyShortDescription"
short_desc_data = {"short_description": "Tu asistente avanzado de GitHub y Agente de IA en Telegram. Commits ZIP y chat inteligente."}
res_short = requests.post(short_desc_url, json=short_desc_data)
print("SetMyShortDescription:", res_short.json())

# 4. Configurar Descripción Larga (setMyDescription)
desc_url = f"https://api.telegram.org/bot{token}/setMyDescription"
desc_data = {
    "description": "Gitgram: Tu asistente avanzado de GitHub y Agente de IA en Telegram. Gestiona repositorios, haz commits con archivos .zip, recibe notificaciones en tiempo real y chatea con inteligencias artificiales (Groq, Gemini, OpenAI)."
}
res_desc = requests.post(desc_url, json=desc_data)
print("SetMyDescription:", res_desc.json())

# 5. Configurar Foto de Perfil (setChatPhoto si aplica, o setMyProfilePhoto si está disponible)
# Nota: La API de Telegram Bot actual no tiene un método directo setMyProfilePhoto HTTP para bots individuales sin chat de canal,
# pero se puede programar un recordatorio o instrucción para BotFather o usar los métodos de chat si procede.
# Sin embargo, los métodos setMyName, setMyDescription, setMyShortDescription y setMyCommands configuran el 100% de la identidad en la bio.
