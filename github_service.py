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
        """Consulta eventos recientes de Push y Pull Requests en los repositorios del usuario."""
        try:
            user = self.client.get_user()
            events = []
            for repo in user.get_repos(sort="updated", direction="desc")[:5]:
                # Verificar Pull Requests abiertos
                try:
                    prs = repo.get_pulls(state="open", sort="updated", direction="desc")[:3]
                    for pr in prs:
                        events.append({
                            "type": "PullRequest",
                            "repo": repo.full_name,
                            "title": pr.title,
                            "number": pr.number,
                            "user": pr.user.login,
                            "html_url": pr.html_url
                        })
                except Exception:
                    pass

                # Verificar commits recientes (Push)
                try:
                    commits = repo.get_commits()[:3]
                    for commit in commits:
                        events.append({
                            "type": "Push",
                            "repo": repo.full_name,
                            "sha": commit.sha[:7],
                            "message": commit.commit.message.split("\n")[0],
                            "author": commit.commit.author.name if commit.commit.author else "Unknown",
                            "html_url": commit.html_url
                        })
                except Exception:
                    pass

            return {"success": True, "events": events}
        except Exception as e:
            return {"success": False, "error": str(e)}
