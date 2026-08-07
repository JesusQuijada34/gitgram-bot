from groq import Groq
import google.generativeai as genai
from openai import OpenAI

class AIAgent:
    def __init__(self, provider: str, api_key: str):
        self.provider = provider.lower().strip()
        self.api_key = api_key

    def generate_response(self, history: list, prompt: str) -> str:
        """
        history: lista de dicts [{'role': 'user'|'assistant', 'content': '...'}, ...]
        prompt: mensaje actual del usuario
        """
        try:
            if self.provider == "groq":
                client = Groq(api_key=self.api_key)
                messages = [{"role": h["role"], "content": h["content"]} for h in history]
                messages.append({"role": "user", "content": prompt})
                
                response = client.chat.completions.create(
                    model="llama3-70b-8192",
                    messages=messages,
                    temperature=0.7,
                )
                return response.choices[0].message.content

            elif self.provider == "gemini":
                genai.configure(api_key=self.api_key)
                model = genai.GenerativeModel('gemini-1.5-flash')
                
                # Convertir historial al formato de Gemini si es necesario o usar chat session
                chat_history = []
                for h in history:
                    r = "user" if h["role"] == "user" else "model"
                    chat_history.append({"role": r, "parts": [h["content"]]})
                
                chat = model.start_chat(history=chat_history)
                response = chat.send_message(prompt)
                return response.text

            elif self.provider == "openai":
                client = OpenAI(api_key=self.api_key)
                messages = [{"role": h["role"], "content": h["content"]} for h in history]
                messages.append({"role": "user", "content": prompt})
                
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.7,
                )
                return response.choices[0].message.content

            else:
                return f"Proveedor de IA desconocido: {self.provider}. Configura uno válido (/setup_ai)."
        except Exception as e:
            return f"Error al generar respuesta con {self.provider}: {str(e)}"
