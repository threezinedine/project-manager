import os
import json
import logging
import argparse
from .models import *
from .log import logger
from dataclasses import asdict
from .utils import RunCommand, ValidateCommandExist


SETTING_NAME = "settings.json"


class Manager:
    def __init__(self, baseDir: str | None = None) -> None:
        self._baseDir = baseDir if baseDir is not None else os.getcwd()

        settingFile = os.path.join(self._baseDir, SETTING_NAME)

        if not os.path.exists(self._baseDir):
            os.makedirs(self._baseDir, exist_ok=True)

        if not os.path.exists(settingFile):
            with open(settingFile, "w") as f:
                json.dump(asdict(Settings()), f, indent=4)

        with open(settingFile, "r") as f:
            data = json.load(f)
            self.settings = Settings(**data)

        self._ExtractSystemInformation()
        self._ExtractInformation()
        self._ExtractArgs()

        self._Execute()

    def _ExtractSystemInformation(self) -> None:
        self._systemInfo = SystemInfo()

    def _ExtractInformation(self) -> None:
        self._c_projects: list[Project] = []
        self._python_projects: list[Project] = []

        for project in self.settings.projects:
            if project.language == ProjectLanguage.C:
                self._c_projects.append(project)
            elif project.language == ProjectLanguage.PYTHON:
                self._python_projects.append(project)

        self._projectsDict: dict[str, Project] = {}
        for project in self._c_projects + self._python_projects:
            self._projectsDict[project.name] = project

    def _ExtractArgs(self) -> None:
        assert self._c_projects is not None
        assert self._python_projects is not None

        parser = argparse.ArgumentParser(
            description="NTT Project Manager - Manage your software projects with ease."
        )

        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Enable verbose output for detailed logging information.",
        )

        subparsers = parser.add_subparsers(dest="command")

        buildParser = subparsers.add_parser(
            "build", help="Build the specified project."
        )

        buildParser.add_argument(
            "project_name",
            type=str,
            choices=[p.name for p in self._c_projects],
            help="Name of the project to build.",
        )

        buildParser.add_argument(
            "--type",
            "-t",
            type=str,
            choices=[e.value for e in BuildType],
            default=BuildType.DEBUG.value,
            help="Specify the build type (debug, release, web). Default is debug.",
        )

        runParser = subparsers.add_parser("run", help="Run the specified project.")

        runParser.add_argument(
            "project_name",
            type=str,
            choices=[p.name for p in self._python_projects + self._c_projects],
            help="Name of the project to run.",
        )

        testParser = subparsers.add_parser("test", help="Test the specified project.")

        testParser.add_argument(
            "project_name",
            type=str,
            choices=[p.name for p in self._c_projects if p.type == ProjectType.LIBRARY],
            help="Name of the project to test.",
        )

        self.args = parser.parse_args()

        if self.args.verbose:
            logger.setLevel(logging.DEBUG)
            logger.debug("Verbose mode enabled.")
        else:
            logger.setLevel(logging.INFO)

    def _Execute(self) -> None:
        for command in self.settings.config.neededCommands:
            ValidateCommandExist(command)

        project: Project | None = None
        projectBaseDir = self._baseDir
        projectBuildDir: str | None = None

        if self.args.project_name is not None:
            project = self._projectsDict.get(self.args.project_name)
            assert project is not None
            projectBaseDir = os.path.join(self._baseDir, project.name)
            projectBuildDir = os.path.join(
                projectBaseDir,
                f"build/{self._systemInfo.PLATFORM}/{project.type.value}",
            )

        if self.args.command == "build":
            assert project is not None

            logger.info(
                f'Building project: "{project.name}" of type: " \
                "{project.type.value}" with build type: "{self.args.type}"'
            )

            if project.language == ProjectLanguage.C:
                generateCommand = f"cmake -B {projectBuildDir}"
                buildCommand = (
                    f"cmake --build {projectBuildDir} --config {self.args.type.upper()}"
                )

                RunCommand(generateCommand, cwd=projectBaseDir)
                RunCommand(buildCommand, cwd=projectBaseDir)
            else:
                logger.error(
                    f'Build not supported for language: "{project.language.value}"'
                )
                raise RuntimeError("Build failed due to unsupported language.")

        elif self.args.command == "run":
            assert project is not None
            logger.info(f'Running project: "{project.name}"')

            if project.language == ProjectLanguage.PYTHON:
                RunCommand("uv sync", cwd=projectBaseDir)
                RunCommand("uv run main.py", cwd=projectBaseDir)
            elif project.language == ProjectLanguage.C:
                RunCommand(
                    f"cmake --build {projectBuildDir} --target {project.name}",
                    cwd=projectBaseDir,
                )
                RunCommand(
                    f"cmake --build {projectBuildDir} --target {project.name}",
                    cwd=projectBaseDir,
                )
            else:
                logger.error(
                    f'Run not supported for language: "{project.language.value}"'
                )
                raise RuntimeError("Run failed due to unsupported language.")
