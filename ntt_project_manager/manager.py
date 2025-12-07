import os
import re
import json
import logging
import argparse
from .models import *
from .log import logger
from jinja2 import Template
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
            if project.executables is not None:
                for example in project.executables:
                    if example.name != "run" and example.name != "test":
                        self._exampleTargets[example.name] = project

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
                executable: ExecutableConfig | None = None
                project = self._projectsDict.get(projectName)

                assert project is not None, "Project not found."
                assert (
                    project.executables is not None
                ), "No executables defined for project."

                for executable in project.executables:
                    if executable.name == "run":
                        executable = executable
                        break

                assert executable is not None, 'No executable named "run" found.'

                self._ExtractCProjectInformation(projectName, executable=executable)

                logger.info(f'Running C project: "{projectName}"')

                RunCommand(self._cProjectGenerateCommand, cwd=self._cProjectBaseDir)
                RunCommand(self._cProjectBuildCommand, cwd=self._cProjectBaseDir)
                if self._cExecutablePath is not None:
                    RunCommand(self._cExecutablePath, cwd=self._cProjectBaseDir)
            else:
                logger.error(f'Run not supported for language: "{project.language}"')
                raise RuntimeError("Run failed due to unsupported language.")

        elif self.args.command == "example":
            exampleName = self.args.exampleName
            project = self._exampleTargets.get(exampleName)
            assert project is not None, "Example project not found."
            assert project.executables is not None

            if exampleName not in self._exampleTargets:
                logger.error(f'Example "{exampleName}" not found.')
                raise RuntimeError("Example run failed due to missing example.")

            executable: ExecutableConfig | None = None

            for executable in project.executables:
                if executable.name == exampleName:
                    executable = executable
                    break

            assert executable is not None, "Executable configuration not found."

            self._ExtractCProjectInformation(
                project.name,
                executable=executable,
            )
            logger.info(
                f'Running example: "{exampleName}" from project: "{project.name}"'
            )
            RunCommand(self._cProjectGenerateCommand, cwd=self._cProjectBaseDir)
            RunCommand(self._cProjectBuildCommand, cwd=self._cProjectBaseDir)
            if self._cExecutablePath is not None:
                RunCommand(self._cExecutablePath, cwd=self._cProjectBaseDir)

    def _ExtractCProjectInformation(
        self,
        projectName: str,
        executable: ExecutableConfig | None = None,
    ) -> None:
        project = self._projectsDict.get(projectName)
        assert project is not None, "Project not found."

        self._cProject = project

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

        constants: dict[str, str] = {
            "BUILD_DIR": self._cProjectBuildDir,
            "PROJECT_DIR": self._cProjectBaseDir,
            "PROJECT_NAME": project.name,
            "BUILD_TYPE": self.args.type,
            "PLATFORM": self._systemInfo.PLATFORM,
        }

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

        addtionalOptionsTemplate = Template(self._cProjectAddtionalOptions)
        self._cProjectAddtionalOptions = addtionalOptionsTemplate.render(**constants)

        # load config/<file>.cfg if exists
        configFilesOptions: dict[str, str] = self._ExtractCConfigFilesOptions()

        configFilesOptionsString = " ".join(
            [f'-D{key}="{value}"' for key, value in configFilesOptions.items()]
        )

        self._cProjectGenerateCommand = (
            f"cmake -B {self._cProjectBuildDir} "
            f"{self._cProjectOsOptions} "
            f"{self._cProjectAddtionalOptions} "
            f"{configFilesOptionsString} "
        )

        self._cProjectBuildCommand = (
            f"cmake --build {self._cProjectBuildDir} --config {self.args.type.upper()}"
        )

        self._cExecutableCommand: str | None = None

        if executable is not None:
            if self._systemInfo.PLATFORM == "windows":
                executablePath = executable.windowsPath
            else:
                executablePath = executable.linuxPath

            executableTemplate = Template(executablePath)
            self._cExecutablePath = executableTemplate.render(**constants)

    def _ExtractCConfigFilesOptions(self) -> dict[str, str]:
        return self._ExtractCConfigFilesOptionsInternal(self.args.type + ".cfg")

    def _ExtractCConfigFilesOptionsInternal(self, name: str) -> dict[str, str]:
        configDir = os.path.join(self._cProjectBaseDir, "config")
        filePath = os.path.join(configDir, name)

        if not os.path.exists(filePath):
            return {}

        with open(filePath, "r") as f:
            content = f.read()

        lines = content.splitlines()
        options: dict[str, str] = {}

        for line in lines:
            line = line.strip()

            if line == "" or line.startswith("#"):
                continue

            # check include pattern <file>
            includeMatch = re.match(r"<(.+)>", line)
            if includeMatch:
                includeFileName = includeMatch.group(1)
                includedOptions = self._ExtractCConfigFilesOptionsInternal(
                    includeFileName
                )
                options.update(includedOptions)
                continue

            # check key=value pattern
            keyValueMatch = re.match(r"(\w+)\s*=\s*(.+)", line)
            if keyValueMatch:
                key = keyValueMatch.group(1)
                value = keyValueMatch.group(2)
                options[key] = value
                continue

        return options
