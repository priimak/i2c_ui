import json
import re
from pathlib import Path
from typing import Self

from rgscore import RegList

PROJECT_RE = re.compile("^[a-zA-Z0-9_]+$")
PROJECT_VALID_CHAR_RE = re.compile("[a-zA-Z0-9_]")


class Project:
    version: int = 1

    def __init__(self, name: str, dir: Path):
        self.name = name
        self.dir = dir

        self.version_json_path = self.dir / "version.json"
        self.reg_list_path = self.dir / "regList.json"
        self.results_path = self.dir / "results.json"

        self.reg_list = RegList()
        self.results: list[list[str]] = []

    def copy_to(self, target_project: "Project"):
        target_project.version_json_path.write_bytes(
            self.version_json_path.read_bytes()
        )
        target_project.reg_list_path.write_bytes(self.reg_list_path.read_bytes())
        target_project.results_path.write_bytes(self.results_path.read_bytes())

    def load(self) -> Self:
        version = json.loads(self.version_json_path.read_text())["version"]
        if version != 1:
            raise RuntimeError(f"Unable to load project version {version}")
        self.reg_list = RegList.from_json_def(self.reg_list_path.read_text())
        self.results = json.loads(self.results_path.read_text())
        return self

    def save(self) -> Self:
        if self.dir.exists():
            self.version_json_path.write_text(json.dumps({"version": Project.version}))
            self.save_results()
            self.save_reglist()
        return self

    def save_results(self):
        self.results_path.write_text(json.dumps(self.results))

    def save_reglist(self):
        self.reg_list_path.write_text(self.reg_list.to_json_def())

    def add_result(self, row: list[str]):
        self.results.append(row)
        self.results.sort(key=lambda x: int(x[0], 16))
        # self.save_results()

    def remove_result(self, index: int):
        self.results.pop(index)
        # self.save_results()

    def replace_result(self, index: int, row: list[str]):
        self.results[index] = row
        # self.save_results()

    def get_results_at_index(self, index: int) -> list[str]:
        return self.results[index]

    def get_results_index_of_by_addr(self, address: str) -> int:
        try:
            return [row[0] for row in self.results].index(address)
        except ValueError:
            return -1


class Projects:
    def __init__(self, projects_dir: Path):
        self.projects_dir = projects_dir
        self.projects_dir.mkdir(exist_ok=True)

        self.projects_file_path = self.projects_dir / "projects.json"
        if not self.projects_file_path.exists():
            projects_dirs = [d.name for d in self.projects_dir.iterdir() if d.is_dir()]
            self.projects_file_path.write_text(json.dumps(projects_dirs))

    def list_projects(self) -> list[str]:
        return json.loads(self.projects_file_path.read_text())

    def new_project(self, name: str) -> Project:
        if not PROJECT_RE.match(name):
            raise ValueError(
                "Project name must consist of only letters, numbers and underscore characters."
            )
        dir = self.projects_dir / name
        if dir.exists():
            raise RuntimeError(f"Project [{name}] already exists.")
        else:
            dir.mkdir(exist_ok=False)
            if not dir.exists():
                raise RuntimeError(f"Failed to create directory for project [{name}].")
            else:
                Project(name, dir).save()
                return self.open_project(name)

    def open_project(self, name: str) -> Project:
        dir = self.projects_dir / name
        if not dir.exists():
            raise RuntimeError(f"Project [{name}] does not exist.")
        else:
            # update open projects history which is sorted based on last opened status
            open_projects_history = json.loads(self.projects_file_path.read_text())
            if name in open_projects_history:
                open_projects_history.remove(name)
            open_projects_history = [name] + open_projects_history
            self.projects_file_path.write_text(json.dumps(open_projects_history))

            return Project(name, dir).load()

    def delete_project(self, name):
        dir = self.projects_dir / name
        if dir.exists():
            for f in dir.iterdir():
                f.unlink()

                # update opened projects history
                open_projects_history = json.loads(self.projects_file_path.read_text())
                if name in open_projects_history:
                    open_projects_history.remove(name)
                    self.projects_file_path.write_text(
                        json.dumps(open_projects_history)
                    )

            dir.rmdir()
