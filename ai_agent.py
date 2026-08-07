from google import genai
from groq import Groq
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
                client = genai.Client(api_key=self.api_key)
                contents = []
                for h in history:
                    role = "user" if h["role"] == "user" else "model"
                    contents.append({
                        "role": role,
                        "parts": [{"text": h["content"]}],
                    })
                contents.append({
                    "role": "user",
                    "parts": [{"text": prompt}],
                })
                response = client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=contents,
                )
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
