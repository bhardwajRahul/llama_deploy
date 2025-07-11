import os
import shutil
import subprocess
from pathlib import Path

import uvicorn
import yaml
from prometheus_client import start_http_server

from llama_deploy.apiserver.settings import settings

CLONED_REPO_FOLDER = Path("cloned_repo")
RC_PATH = Path("/data")


def run_process(args: list[str], cwd: str | None = None) -> None:
    kwargs = {
        "args": args,
        "capture_output": True,
        "text": True,
        "check": False,
    }
    if cwd:
        kwargs["cwd"] = cwd
    process = subprocess.run(**kwargs)  # type: ignore
    if process.returncode != 0:
        stderr = process.stderr or ""
        raise Exception(stderr)


def setup_repo(
    work_dir: Path, source: str, token: str | None = None, force: bool = False
) -> None:
    repo_url, branch_name = _parse_source(source, token)

    dest_dir = work_dir / CLONED_REPO_FOLDER

    if not dest_dir.exists() or force:
        clone_args = ["git", "clone", "--depth", "1"]
        if branch_name:
            clone_args.extend(["--branch", branch_name, "--single-branch"])
        clone_args.extend([repo_url, str(dest_dir.absolute())])
        run_process(clone_args, cwd=str(work_dir.absolute()))
    else:
        run_process(
            ["git", "pull", "origin", branch_name or "main"],
            cwd=str(dest_dir.absolute()),
        )


def _is_valid_uri(uri: str) -> bool:
    """Check if string looks like a valid URI"""
    return "://" in uri and "/" in uri.split("://", 1)[1]


def _parse_source(source: str, pat: str | None = None) -> tuple[str, str | None]:
    """Accept Github urls like https://github.com/run-llama/llama_deploy.git@main
    or https://user:token@github.com/run-llama/llama_deploy.git@main
    Returns the final URL (with auth if needed) and branch name"""

    # Try splitting on last @ to see if we have a branch specifier
    url = source
    branch_name = None

    if "@" in source:
        potential_url, potential_branch = source.rsplit("@", 1)
        if _is_valid_uri(potential_url):
            url = potential_url
            branch_name = potential_branch

    # Inject PAT auth if provided and URL doesn't already have auth
    if pat and "://" in url and "@" not in url:
        url = url.replace("https://", f"https://{pat}@")

    return url, branch_name


def copy_sources(work_dir: Path, deployment_file_path: Path) -> None:
    app_folder = deployment_file_path.parent
    for item in app_folder.iterdir():
        if item.is_dir():
            # For directories, use copytree with dirs_exist_ok=True
            shutil.copytree(
                item, f"{work_dir.absolute()}/{item.name}", dirs_exist_ok=True
            )
        else:
            # For files, use copy2 to preserve metadata
            shutil.copy2(item, str(work_dir))


if __name__ == "__main__":
    if settings.prometheus_enabled:
        start_http_server(settings.prometheus_port)

    repo_url = os.environ.get("REPO_URL", "")
    if not repo_url.startswith("https://"):
        raise ValueError("Git remote must be valid and over HTTPS")
    repo_token = os.environ.get("GITHUB_PAT")
    work_dir = Path(os.environ.get("WORK_DIR", RC_PATH))
    work_dir.mkdir(exist_ok=True, parents=True)

    setup_repo(work_dir, repo_url, repo_token)

    deployment_file_path = os.environ.get("DEPLOYMENT_FILE_PATH", "deployment.yml")
    deployment_file_abspath = work_dir / CLONED_REPO_FOLDER / deployment_file_path
    if not deployment_file_abspath.exists():
        raise ValueError(f"File {deployment_file_abspath} does not exist")

    deployment_override_name = os.environ.get("DEPLOYMENT_NAME")
    if deployment_override_name:
        with open(deployment_file_abspath) as f:
            # Replace deployment name with the overridden value
            data = yaml.safe_load(f)

        # Avoid failing here if the deployment config file has a wrong format,
        # let's do nothing if there's no field `name`
        if "name" in data:
            data["name"] = deployment_override_name
            with open(deployment_file_abspath, "w") as f:
                yaml.safe_dump(data, f)

    copy_sources(work_dir, deployment_file_abspath)
    shutil.rmtree(work_dir / CLONED_REPO_FOLDER)

    # update rc_path directly, as it has already been loaded, so setting the environment variable
    # doesn't work
    settings.rc_path = work_dir
    uvicorn.run(
        "llama_deploy.apiserver.app:app",
        host=settings.host,
        port=settings.port,
    )
