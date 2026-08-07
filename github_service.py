import io
import zipfile
from github import Github, GithubException

class GitHubService:
    def __init__(self, token: str):
        self.token = token
        self.client = Github(token)

    def verify_token(self):
        """Verifica el token y devuelve el nombre de usuario y datos básicos."""
        try:
            user = self.client.get_user()
            return {"success": True, "username": user.login, "name": user.name}
        except GithubException as e:
            return {"success": False, "error": str(e)}

    def commit_zip_content(self, repo_name: str, zip_bytes: bytes, commit_message: str = "Update from gittgiambot", branch: str = "main"):
        """Recibe un .zip en memoria, extrae su contenido y hace commit en el repo especificado."""
        try:
            repo = self.client.get_repo(repo_name)
        except GithubException as e:
            return {"success": False, "error": f"No se pudo encontrar el repositorio '{repo_name}': {str(e)}"}

        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
                # Obtener la referencia de la rama actual o crear commit
                for filename in z.namelist():
                    if z.getinfo(filename).is_dir():
                        continue
                    
                    file_content = z.read(filename)
                    # Limpiar rutas relativas si vienen con carpeta raíz en el zip
                    clean_path = filename.split('/', 1)[-1] if '/' in filename else filename
                    if not clean_path:
                        continue

                    # Intentar actualizar o crear el archivo
                    try:
                        try:
                            contents = repo.get_contents(clean_path, ref=branch)
                            repo.update_file(
                                path=clean_path,
                                message=f"{commit_message}: update {clean_path}",
                                content=file_content,
                                sha=contents.sha,
                                branch=branch
                            )
                        except Exception:
                            repo.create_file(
                                path=clean_path,
                                message=f"{commit_message}: create {clean_path}",
                                content=file_content,
                                branch=branch
                            )
                    except Exception as ex:
                        print(f"Error procesando archivo {clean_path}: {ex}")

            return {"success": True, "message": f"Commit exitoso en {repo_name} ({branch})."}
        except Exception as e:
            return {"success": False, "error": f"Error procesando el archivo ZIP: {str(e)}"}

    def get_recent_notifications(self):
        """Obtiene notificaciones recientes del usuario de GitHub."""
        try:
            notifs = self.client.get_notifications(all=False)
            results = []
            for n in list(notifs)[:5]: # últimas 5
                results.endswith if hasattr(results, 'endswith') else None # dummy
                results.append({
                    "title": n.subject.title,
                    "type": n.subject.type,
                    "repository": n.repository.full_name,
                    "url": n.subject.url
                })
            return {"success": True, "notifications": results}
        except Exception as e:
            return {"success": False, "error": str(e)}
