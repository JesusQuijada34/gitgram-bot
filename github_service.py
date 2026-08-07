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
        """Consulta eventos recientes de Push, Pull Requests (abiertos y cerrados) e Issues en los repositorios del usuario."""
        try:
            user = self.client.get_user()
            events = []
            for repo in user.get_repos(sort="updated", direction="desc")[:5]:
                # Verificar Pull Requests (abiertos y cerrados recientemente)
                try:
                    prs = repo.get_pulls(state="all", sort="updated", direction="desc")[:4]
                    for pr in prs:
                        pr_state = "Closed" if pr.closed_at else "Open"
                        if pr.is_merged():
                            pr_state = "Merged"
                        events.append({
                            "type": "PullRequest",
                            "repo": repo.full_name,
                            "title": pr.title,
                            "number": pr.number,
                            "user": pr.user.login,
                            "state": pr_state,
                            "html_url": pr.html_url
                        })
                except Exception:
                    pass

                # Verificar Issues recientes
                try:
                    issues = repo.get_issues(state="open", sort="updated", direction="desc")[:3]
                    for issue in issues:
                        # Filtrar para no incluir Pull Requests que aparecen en issues API
                        if issue.pull_request:
                            continue
                        events.append({
                            "type": "Issue",
                            "repo": repo.full_name,
                            "title": issue.title,
                            "number": issue.number,
                            "user": issue.user.login if issue.user else "Unknown",
                            "html_url": issue.html_url
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

                # Verificar Releases recientes
                try:
                    releases = repo.get_releases()[:2]
                    for rel in releases:
                        events.append({
                            "type": "Release",
                            "repo": repo.full_name,
                            "tag_name": rel.tag_name,
                            "title": rel.title or rel.tag_name,
                            "author": rel.author.login if rel.author else "Unknown",
                            "html_url": rel.html_url
                        })
                except Exception:
                    pass

                # Verificar Deployments recientes
                try:
                    deployments = repo.get_deployments()[:2]
                    for dep in deployments:
                        events.append({
                            "type": "Deployment",
                            "repo": repo.full_name,
                            "id": dep.id,
                            "environment": dep.environment,
                            "creator": dep.creator.login if dep.creator else "Unknown",
                            "html_url": f"https://github.com/{repo.full_name}/deployments"
                        })
                except Exception:
                    pass

                # Verificar GitHub Actions Workflow Runs recientes
                try:
                    runs = repo.get_workflow_runs()[:3]
                    for run in runs:
                        # conclusion puede ser success, failure, cancelled, skipped, etc.
                        conclusion = run.conclusion or "in_progress"
                        events.append({
                            "type": "WorkflowRun",
                            "repo": repo.full_name,
                            "id": run.id,
                            "name": run.name or "Workflow",
                            "status": run.status,
                            "conclusion": conclusion,
                            "head_branch": run.head_branch,
                            "html_url": run.html_url
                        })
                except Exception:
                    pass

                # Verificar Discusiones y otras notificaciones de la API de notificaciones de GitHub
                try:
                    notifs = self.client.get_notifications(all=False)
                    for n in list(notifs)[:5]:
                        subject_type = n.subject.type
                        if subject_type in ["Discussion", "DiscussionComment"]:
                            events.append({
                                "type": "Discussion",
                                "repo": n.repository.full_name,
                                "title": n.subject.title,
                                "subject_type": subject_type,
                                "url": n.subject.url.replace("api.github.com/repos", "github.com").replace("/discussions/", "/discussions/")
                            })
                except Exception:
                    pass

            return {"success": True, "events": events}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def list_issues(self, repo_name: str, state: str = "open"):
        """Lista issues de un repositorio."""
        try:
            repo = self.client.get_repo(repo_name)
            issues = repo.get_issues(state=state, sort="updated", direction="desc")[:10]
            results = []
            for issue in issues:
                if issue.pull_request:
                    continue
                results.append({
                    "number": issue.number,
                    "title": issue.title,
                    "state": issue.state,
                    "user": issue.user.login if issue.user else "Unknown",
                    "html_url": issue.html_url,
                    "created_at": issue.created_at.isoformat() if issue.created_at else ""
                })
            return {"success": True, "issues": results}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def comment_on_issue(self, repo_name: str, issue_number: int, body: str):
        """Añade un comentario a un issue."""
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(number=issue_number)
            comment = issue.create_comment(body)
            return {"success": True, "comment_url": comment.html_url}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_issue(self, repo_name: str, issue_number: int):
        """Cierra un issue."""
        try:
            repo = self.client.get_repo(repo_name)
            issue = repo.get_issue(number=issue_number)
            issue.edit(state="closed")
            return {"success": True, "message": f"Issue #{issue_number} cerrado exitosamente."}
        except Exception as e:
            return {"success": False, "error": str(e)}
