import io
import re
import zipfile
from pathlib import PurePosixPath
from github import Github, GithubException

MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_MEMBER_BYTES = 10 * 1024 * 1024
MAX_TOTAL_BYTES = 40 * 1024 * 1024


def _safe_repo_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value or ""):
        raise ValueError("Nombre de repositorio inválido")
    return value


def _safe_branch(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", value or "") or ".." in value:
        raise ValueError("Nombre de rama inválido")
    return value


def _safe_zip_path(filename: str) -> str:
    path = PurePosixPath(filename)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Ruta insegura en ZIP: {filename}")
    parts = [part for part in path.parts if part not in ("", ".")]
    if not parts:
        raise ValueError("Ruta vacía en ZIP")
    # GitHub branch archives commonly contain one root directory.
    if len(parts) > 1:
        parts = parts[1:]
    clean = "/".join(parts)
    if not clean or clean.startswith("/") or ".." in PurePosixPath(clean).parts:
        raise ValueError(f"Ruta insegura en ZIP: {filename}")
    return clean


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

    def commit_zip_content(self, repo_name: str, zip_bytes: bytes, commit_message: str = "Update from gitgram-bot", branch: str = "main"):
        """Valida un ZIP y actualiza sus archivos en un repositorio autorizado."""
        try:
            repo_name = _safe_repo_name(repo_name)
            branch = _safe_branch(branch)
            if not isinstance(zip_bytes, (bytes, bytearray)) or len(zip_bytes) > MAX_ZIP_BYTES:
                raise ValueError("El ZIP supera el límite permitido")
            repo = self.client.get_repo(repo_name)
        except (ValueError, GithubException) as error:
            return {"success": False, "error": str(error)}

        total_bytes = 0
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
                for info in archive.infolist():
                    if info.is_dir():
                        continue
                    if info.file_size > MAX_MEMBER_BYTES:
                        raise ValueError(f"Archivo demasiado grande en ZIP: {info.filename}")
                    total_bytes += info.file_size
                    if total_bytes > MAX_TOTAL_BYTES:
                        raise ValueError("El contenido total del ZIP supera el límite permitido")
                    clean_path = _safe_zip_path(info.filename)
                    file_content = archive.read(info)
                    try:
                        contents = repo.get_contents(clean_path, ref=branch)
                    except GithubException as error:
                        if error.status != 404:
                            raise
                        repo.create_file(path=clean_path, message=f"{commit_message}: create {clean_path}", content=file_content, branch=branch)
                    else:
                        if isinstance(contents, list):
                            raise ValueError(f"La ruta apunta a un directorio: {clean_path}")
                        repo.update_file(path=clean_path, message=f"{commit_message}: update {clean_path}", content=file_content, sha=contents.sha, branch=branch)
            return {"success": True, "message": f"Commit exitoso en {repo_name} ({branch})."}
        except Exception as error:
            return {"success": False, "error": f"Error procesando el archivo ZIP: {error}"}

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
