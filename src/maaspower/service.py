import logging
import os
import pwd
import shutil
import subprocess
import sys
from pathlib import Path
from string import Template
from typing import Optional

DEFAULT_SYSTEM_USERNAME = "maaspower"
DEFAULT_SYSTEM_CONFIGURATION_DIRECTORY = Path("/etc/maaspower")
DEFAULT_USER_CONFIGURATION_DIRECTORY = Path("~/.config/maaspower")
DEFAULT_SYSTEM_RUNTIME_DIRECTORY = Path("/var/run/maaspower")
DEFAULT_USER_RUNTIME_DIRECTORY = Path("~/.cache/maaspower")

SYSTEMD_UNIT_CONFIG_TEMPLATE = Template(
    """[Unit]
Description=MAAS Power Service

[Service]
Type=simple
User=$username
WorkingDirectory=$working_directory
ExecStart=$python_executable -m maaspower run $configuration_file_path
Restart=always
"""
)


def configure_service(
    config_path: Optional[Path],
    runtime_path: Optional[Path],
    username: Optional[str],
    system_wide: Optional[bool],
    python_executable: Optional[Path],
):
    current_user = os.getlogin()

    if system_wide is None:
        system_wide = current_user == "root"

    if system_wide:
        logging.info("Configuring system wide service running as {username}")
        configure_system_service(
            config_path, runtime_path, current_user, username, python_executable
        )
    else:
        logging.info("Configuring service for {username}")
        configure_user_service(
            config_path, runtime_path, current_user, username, python_executable
        )


def create_user(username: str = "maaspower") -> None:
    try:
        pwd.getpwnam(username)
        return  # if the user already exists, there is nothing for us to do
    except KeyError:
        pass
    cmd = ["useradd", username]
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    output, error = process.communicate()
    output = output.strip().decode("utf-8")
    error = error.decode("utf-8")
    if process.returncode != 0:
        raise RuntimeError(f"{error}")
    return username


def configure_user_service(
    configuration_file_path,
    runtime_directory_path,
    current_user,
    username,
    python_executable,
):
    if current_user == "root":
        raise ValueError("Cannot install user serivce for root")

    if username is None:
        username = current_user

    if current_user != username:
        raise ValueError(
            "User {current_user} is trying to install service to run as {username}. Only root can configure a service for another user."
        )

    if configuration_file_path is None:
        configuration_file_path = DEFAULT_USER_CONFIGURATION_DIRECTORY

    if runtime_directory_path is None:
        runtime_directory_path = DEFAULT_USER_RUNTIME_DIRECTORY

    if python_executable is None:
        python_executable = sys.executable

    os.makedirs(configuration_file_path.parent, exist_ok=True)

    unit_file_location = (
        Path(os.getenv("XDG_CONFIG_HOME", default="~/.config"))
        / "maaspower"
        / "maaspower.service"
    )

    create_unit_file(
        unit_file_location,
        username,
        runtime_directory_path,
        python_executable,
        configuration_file_path / "maaspower.yaml",
    )


def create_unit_file(
    unit_file_location: Path,
    username: str,
    runtime_directory_path: Path,
    python_executable: Path,
    configuration_file_path: Path,
):
    os.makedirs(unit_file_location.parent, exist_ok=True)

    unit_file_content = SYSTEMD_UNIT_CONFIG_TEMPLATE.substitute(
        {
            "username": username,
            "working_directory": runtime_directory_path,
            "python_executable": python_executable,
            "configuration_file_path": configuration_file_path,
        }
    )

    with open(unit_file_location, "w") as unit_file:
        unit_file.write(unit_file_content)


def configure_system_service(
    config_path, runtime_directory_path, current_user, username, python_executable
):
    if current_user != "root":
        raise ValueError("SystemWide installation must be done as root user.")

    if username is None:
        username = DEFAULT_SYSTEM_CONFIGURATION_DIRECTORY

    create_user(username)
    create_system_configuration_directory(config_path)

    if python_executable is None:
        python_executable = create_new_venv()


def create_new_venv():
    pass


def create_system_configuration_directory(username: str):
    system_configuration_directory_path = Path(DEFAULT_SYSTEM_CONFIGURATION_DIRECTORY)
    try:
        os.mkdirs(system_configuration_directory_path, mode=0o660)
    except FileExistsError:
        pass
    shutil.chown(system_configuration_directory_path, user=username, group="root")
