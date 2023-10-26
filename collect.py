import csv
import subprocess as sp
from pathlib import Path
from typing import NamedTuple


PROJECTS_CSV = Path("projects.csv")
PROJECTS_DIR = Path("projects")
DEPS_DIR = Path("deps")
DBS_DIR = Path("dbs")
DEPENDS_JAR = Path("depends.jar")
COCHANGE_TOOL_BIN = Path("cochange-tool")


class Project(NamedTuple):
    name: str
    url: str
    rev: str


def get_project_path(project_name: str) -> Path:
    return Path(PROJECTS_DIR, project_name)


def get_db_path(project_name: str) -> Path:
    return Path(DBS_DIR, f"{project_name}.db")


def get_dep_path(project_name: str) -> Path:
    return Path(DEPS_DIR, f"{project_name}-deps-structure.json")


def load_projects() -> list[Project]:
    with open(PROJECTS_CSV) as file:
        return [Project(r[0], r[1], r[2]) for r in csv.reader(file)]


def clone(project: Project):
    project_path = get_project_path(project.name)
    if project_path.exists():
        print(f"Skipped {project.name}. Already cloned.")
        return
    print(f"Cloning {project.name}...")
    sp.run(["git", "clone", project.url, project_path])


def checkout(project: Project):
    print(f"Switching {project.name} to {project.rev}")
    args = ["git", "-c", "advice.detachedHead=false", "checkout", project.rev]
    sp.run(args, cwd=get_project_path(project.name))


def dereference_rev(project: Project) -> str:
    args = ["git", "rev-list", "-n", "1", project.rev]
    res = sp.run(args, cwd=get_project_path(project.name), stdout=sp.PIPE)
    res.check_returncode()
    return res.stdout.decode("UTF-8").strip()


def dump_deps(project: Project):
    if get_dep_path(project.name).exists():
        print(f"Skipped {project.name}. Already has deps dumped.")
        return
    print(f"Extracting dependency info from {project.name}")
    DEPS_DIR.absolute().mkdir(parents=True, exist_ok=True)
    args = [
        "java",
        "-Xmx12G",
        "-jar",
        DEPENDS_JAR.absolute(),
        "java",
        ".",
        f"{project.name}-deps",
        f"--dir={DEPS_DIR.absolute()}",
        "--detail",
        "--output-self-deps",
        "--granularity=structure",
        "--namepattern=unix",
        "--strip-leading-path",
    ]
    sp.run(args, cwd=get_project_path(project.name))


def dump_cochange_db(project: Project):
    db_path = get_db_path(project.name)
    if db_path.exists():
        print(f"Skipped {project.name}. Already has cochange db.")
        return
    print(f"Dumping cochange info into db for {project.name}...")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        COCHANGE_TOOL_BIN.absolute(),
        "dump",
        "--all",
        "--db",
        str(db_path),
        "--repo",
        get_project_path(project.name),
        project.rev,
    ]
    sp.run(args)


def add_deps_to_db(project: Project):
    # TODO: Skip this if possible
    print(f"Adding deps to the db of {project.name}...")
    db_path = get_db_path(project.name)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    args = [
        COCHANGE_TOOL_BIN.absolute(),
        "add-deps",
        "--db",
        str(db_path),
        "--commit",
        dereference_rev(project),
        "--dep-file",
        str(get_dep_path(project.name))
    ]
    sp.run(args)


if __name__ == "__main__":
    for project in load_projects():
        clone(project)
        checkout(project)
        dump_deps(project)
        dump_cochange_db(project)
        add_deps_to_db(project)
