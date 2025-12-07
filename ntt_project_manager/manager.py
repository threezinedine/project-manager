import os
import json
import logging
import argparse
from .models import *
from .log import logger
from dacite import from_dict
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
            self.settings = from_dict(data_class=Settings, data=data)

        self._ExtractSystemInformation()
        self._ExtractInformation()
        self._ExtractArgs()

        self._Execute()

    def _ExtractSystemInformation(self) -> None:
        self._systemInfo = SystemInfo()

    def _ExtractInformation(self) -> None:
        self._cProjects: list[Project] = []
        self._pythonProjects: list[Project] = []
        self._exampleTargets: dict[str, Project] = {}

        for project in self.settings.projects:
            if project.language == ProjectLanguage.C.value:
                self._cProjects.append(project)
            elif project.language == ProjectLanguage.PYTHON.value:
                self._pythonProjects.append(project)

        self._projectsDict: dict[str, Project] = {}
        for project in self._cProjects + self._pythonProjects:
            self._projectsDict[project.name] = project

        for project in self._cProjects:
            if project.exampleTargets is not None:
                for example in project.exampleTargets:
                    self._exampleTargets[example] = project

    def _ExtractArgs(self) -> None:
        assert self._cProjects is not None
        assert self._pythonProjects is not None

        parser = argparse.ArgumentParser(
            description="NTT Project Manager - Manage your software projects with ease."
        )

        parser.add_argument(
            "--verbose",
            "-v",
            action="store_true",
            help="Enable verbose output for detailed logging information.",
        )

        parser.add_argument(
            "--type",
            "-t",
            type=str,
            choices=BUILD_TYPES,
            default=BuildType.DEBUG.value,
            help="Specify the build type (debug, release, web). Default is debug.",
        )

        subparsers = parser.add_subparsers(dest="command")

        buildParser = subparsers.add_parser(
            "build", help="Build the specified project."
        )

        buildParser.add_argument(
            "projectName",
            type=str,
            choices=[p.name for p in self._cProjects],
            help="Name of the project to build.",
        )

        runParser = subparsers.add_parser("run", help="Run the specified project.")

        runParser.add_argument(
            "projectName",
            type=str,
            choices=[p.name for p in self._pythonProjects + self._cProjects],
            help="Name of the project to run.",
        )

        testParser = subparsers.add_parser("test", help="Test the specified project.")

        testParser.add_argument(
            "projectName",
            type=str,
            choices=[
                p.name for p in self._cProjects if p.type == ProjectType.LIBRARY.value
            ],
            help="Name of the project to test.",
        )

        exampleParser = subparsers.add_parser(
            "example",
            help="Manage and run example projects.",
        )

        exampleParser.add_argument(
            "exampleName",
            type=str,
            choices=list(self._exampleTargets.keys()),
            help="Name of the example project to run.",
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

        if self.args.command == "build":
            projectName = self.args.projectName
            self._ExtractCProjectInformation(self.args.projectName)

            logger.info(
                f'Building project: "{projectName}" of type: "{self._cProject.type}" with build type: "{self.args.type}"'
            )

            if self._cProject.language == ProjectLanguage.C:
                RunCommand(self._cProjectGenerateCommand, cwd=self._cProjectBaseDir)
                RunCommand(self._cProjectBuildCommand, cwd=self._cProjectBaseDir)
            else:
                logger.error(
                    f'Build not supported for language: "{self._cProject.language}"'
                )
                raise RuntimeError("Build failed due to unsupported language.")

        elif self.args.command == "run":
            projectName = self.args.projectName
            project = self._projectsDict.get(projectName)
            assert project is not None, "Project not found."

            if project.language == ProjectLanguage.PYTHON.value:
                logger.info(f'Running Python project: "{projectName}"')
                projectBaseDir = os.path.join(self._baseDir, project.name)

                RunCommand("uv sync", cwd=projectBaseDir)
                RunCommand("uv run main.py", cwd=projectBaseDir)
            elif project.language == ProjectLanguage.C.value:
                assert project.runTarget is not None, "Run target not specified."
                self._ExtractCProjectInformation(projectName, target=project.runTarget)

                logger.info(f'Running C project: "{projectName}"')

                RunCommand(self._cProjectGenerateCommand, cwd=self._cProjectBaseDir)
                RunCommand(self._cProjectBuildCommand, cwd=self._cProjectBaseDir)
            else:
                logger.error(f'Run not supported for language: "{project.language}"')
                raise RuntimeError("Run failed due to unsupported language.")

        elif self.args.command == "example":
            exampleName = self.args.exampleName
            project = self._exampleTargets.get(exampleName)
            assert project is not None, "Example project not found."

            self._ExtractCProjectInformation(project.name, target=exampleName)
            logger.info(
                f'Running example: "{exampleName}" from project: "{project.name}"'
            )
            RunCommand(self._cProjectGenerateCommand, cwd=self._cProjectBaseDir)
            RunCommand(self._cProjectBuildCommand, cwd=self._cProjectBaseDir)

    def _ExtractCProjectInformation(
        self,
        projectName: str,
        target: str | None = None,
    ) -> None:
        project = self._projectsDict.get(projectName)
        assert project is not None, "Project not found."

        assert (
            project.language == ProjectLanguage.C.value
        ), "Project is not a C project."

        self._cProjectBaseDir = os.path.join(self._baseDir, project.name)
        self._cProjectBuildDir = os.path.join(
            self._cProjectBaseDir,
            "build",
            f"{self._systemInfo.PLATFORM}",
            f"{self.args.type}",
        )

        self._cProjectOsOptions: str = ""

        if os.name == "nt":
            osConfig = self.settings.config.windows
        else:
            osConfig = self.settings.config.linux

        self._cProjectOsOptions = f'-G "{osConfig.cmake_tool}"'

        self._cProjectAddtionalOptions: str = ""

        if project.buildTypesConfig is not None:
            buildTypeConfig = project.buildTypesConfig.get(self.args.type)

            if buildTypeConfig is not None:
                self._cProjectAddtionalOptions = buildTypeConfig.options

        self._cProject = project

        self._cProjectGenerateCommand = (
            f"cmake -B {self._cProjectBuildDir} "
            f"{self._cProjectOsOptions} "
            f"{self._cProjectAddtionalOptions} "
        )

        self._cProjectBuildCommand = (
            f"cmake --build {self._cProjectBuildDir} --config {self.args.type.upper()}"
        )

        if target is not None:
            self._cProjectBuildCommand += f" --target {target} "
