import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Self

from rgscore import RegList

PROJECT_RE = re.compile("^[a-zA-Z0-9_]+$")
PROJECT_VALID_CHAR_RE = re.compile("[a-zA-Z0-9_]")


@dataclass
class RawResult:
    name_and_address: str
    value_hex: str
    value_bin: str
    address: int
    address_bus_width_in_bytes: int

    def get_value_at_column(self, column: int) -> str:
        match column:
            case 0:
                return self.name_and_address
            case 1:
                return self.value_hex
            case 2:
                return self.value_bin
            case _:
                return ""

    @staticmethod
    def from_dict_def(data: dict) -> "RawResult":
        return RawResult(
            name_and_address=data["name_and_address"],
            value_hex=data["value_hex"],
            value_bin=data["value_bin"],
            address=data["address"],
            address_bus_width_in_bytes=data["address_bus_width_in_bytes"],
        )


class Project:
    version: int = 1

    def __init__(self, name: str, dir: Path):
        self.name = name
        self.dir = dir

        self.version_json_path = self.dir / "version.json"
        self.reg_list_path = self.dir / "regList.json"
        self.results_path = self.dir / "results.json"

        self.reg_list = RegList()
        if not self.reg_list_path.exists():
            self.save_reglist()

        self.results: list[RawResult] = []

    def get_raw_result_for_address(self, register_address: int) -> RawResult | None:
        for row in self.results:
            if row.address == register_address:
                return row
        return None

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

        self.results = [
            RawResult(**row) for row in json.loads(self.results_path.read_text())
        ]
        return self

    def save(self) -> Self:
        if self.dir.exists():
            self.version_json_path.write_text(json.dumps({"version": Project.version}))
            self.save_results()
            self.save_reglist()
        return self

    def save_results(self):
        self.results_path.write_text(json.dumps([asdict(row) for row in self.results]))

    def save_reglist(self):
        self.reg_list_path.write_text(self.reg_list.to_json_def())

    def add_result(self, row: RawResult):
        self.results.append(row)
        self.results.sort(key=lambda x: x.address)

    def remove_result(self, index: int) -> RawResult | None:
        try:
            return self.results.pop(index)
        except IndexError:
            return None

    def replace_result(self, index: int, row: RawResult):
        try:
            self.results[index] = row
        except IndexError:
            pass

    def get_results_at_row(self, index: int) -> RawResult | None:
        try:
            return self.results[index]
        except IndexError:
            return None

    def get_results_index_of_by_addr(self, address: int | str) -> int:
        try:
            addr = int(address, 16) if isinstance(address, str) else address
            return [row.address for row in self.results].index(addr)
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
