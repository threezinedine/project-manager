import os
from enum import StrEnum
from dataclasses import dataclass, field

"""
Json examples
{
    "config": {
        "windows": {
            "cmake_tool": "Ninja"
        },
        "linux": {
            "cmake_tool": "Unix Makefiles"
        } 
    },
    "projects": [
        {
            "name": "engine",
            "language": "C",
            "type": "executable"
        }
    ]
}
"""


class ProjectLanguage(StrEnum):
    """
    Used for specifying the programming language of a project. With each
    language, specific configurations and settings can be applied.
    """

    C = "C"
    PYTHON = "Python"


PROJECT_LANGUAGES = [lang.value for lang in ProjectLanguage]


class ProjectType(StrEnum):
    """
    Used for specifying the type of project. Different project types may
    require different structures, dependencies, and build processes.
    """

    EXECUTABLE = "executable"  # Can have build, run (both python and c)
    LIBRARY = "library"  # Can have build, test (only c)
    EXAMPLE = "example"  # Can have build, example (both python and c)
    INSTALL = "install"  # Can have install (both python and c)


PROJECT_TYPES = [ptype.value for ptype in ProjectType]


class BuildType(StrEnum):
    """
    Used for specifying the build type of a project.
    """

    DEBUG = "debug"
    RELEASE = "release"
    TEST = "test"
    WEB = "web"


BUILD_TYPES = [btype.value for btype in BuildType]


@dataclass
class Project:
    """
    The Project class encapsulates the essential attributes of a software
    project, including its name, programming language, type, and associated
    features.

    There's default features depending on the language and type of the
    project.

    User can override or add new features as needed (include the default ones) via
    the features attribute.
    """

    name: str
    language: str = field(default=ProjectLanguage.C.value)
    type: str = field(default=ProjectType.EXECUTABLE.value)
    testTarget: str | None = field(default=None)
    runTarget: str | None = field(default=None)
    exampleTargets: list[str] | None = field(default=None)


class CMakeTools(StrEnum):
    """
    Enum representing different CMake tools that can be used in a project.
    """

    NINJA = "Ninja"
    MINGW = "MinGW Makefiles"
    UNIX = "Unix Makefiles"
    VC17 = "Visual Studio 17 2022"


CMAKE_TOOLS = [tool.value for tool in CMakeTools]


@dataclass
class OSBuildConfig:
    cmake_tool: str = field(default=CMakeTools.UNIX.value)


@dataclass
class BuildTypeConfig:
    options: str = field(default="")


@dataclass
class BuildConfig:
    windows: OSBuildConfig = field(
        default_factory=lambda: OSBuildConfig(cmake_tool=CMakeTools.VC17.value)
    )
    linux: OSBuildConfig = field(default_factory=OSBuildConfig)

    neededCommands: list[str] = field(default_factory=lambda: ["cmake", "git"])

    buildTypesConfig: dict[str, BuildTypeConfig] = field(
        default_factory=lambda: {
            BuildType.DEBUG.value: BuildTypeConfig(options="-DCMAKE_BUILD_TYPE=Debug"),
            BuildType.RELEASE.value: BuildTypeConfig(
                options="-DCMAKE_BUILD_TYPE=Release"
            ),
            BuildType.WEB.value: BuildTypeConfig(
                options="-DCMAKE_BUILD_TYPE=Release -DWEB_BUILD=ON"
            ),
            BuildType.TEST.value: BuildTypeConfig(
                options="-DCMAKE_BUILD_TYPE=Debug -DENABLE_TESTS=ON"
            ),
        }
    )


@dataclass
class Settings:
    config: BuildConfig = field(default_factory=BuildConfig)
    projects: list[Project] = field(default_factory=list)  # type: ignore


class SystemInfo:
    PLATFORM: str = "windows" if os.name == "nt" else "linux"
    EXECUTABLE_SUFFIX: str = ".exe" if os.name == "nt" else ""
