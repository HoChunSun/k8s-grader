import json
import os
import shutil
import threading
import urllib.request
from enum import Enum

import pytest
from jinja2 import Environment


class GamePhrase(Enum):
    SETUP = "setup"
    READY = "ready"
    ANSWER = "answer"
    CHALLENGE = "challenge"
    CHECK = "check"
    CLEANUP = "cleanup"


ROOT_PATH = "/tmp/k8s-game-rule-main"
TEST_BASE_PATH = "/tmp/k8s-game-rule-main/tests"


class TestResult(Enum):
    OK = 0
    TESTS_FAILED = 1
    INTERRUPTED = 2
    INTERNAL_ERROR = 3
    USAGE_ERROR = 4
    NO_TESTS_COLLECTED = 5
    TIME_OUT = 6


MAPPING = {
    GamePhrase.SETUP: "01_setup",
    GamePhrase.READY: "02_ready",
    GamePhrase.ANSWER: "03_answer",
    GamePhrase.CHALLENGE: "04_challenge",
    GamePhrase.CHECK: "05_check",
    GamePhrase.CLEANUP: "06_cleanup",
}

GAME_PHRASE_ORDER = [
    GamePhrase.SETUP,
    GamePhrase.READY,
    GamePhrase.CHALLENGE,
    GamePhrase.CHECK,
    GamePhrase.CLEANUP,
]


def run_tests(test_phase: GamePhrase, game: str, task: str):
    get_tests()

    def run_pytest():
        nonlocal retcode
        retcode = pytest.main(
            [
                f"--rootdir={ROOT_PATH}",
                "--import-mode=importlib",
                "--html=/tmp/report.html",
                "--self-contained-html",
                "-x",
                f"{TEST_BASE_PATH}/{game}/{task}/test_{MAPPING[test_phase]}.py",
            ]
        )

    retcode = TestResult.OK.value
    thread = threading.Thread(target=run_pytest)
    thread.start()
    thread.join(timeout=25)

    if thread.is_alive():
        retcode = TestResult.TIME_OUT.value
    return TestResult(retcode)


def get_tests():
    # TODO: Change this to S3 bucket download
    if not os.path.exists("/tmp/k8s-game-rule-main.zip"):
        url = "https://github.com/HoChunSun/k8s-game-rule/archive/refs/heads/main.zip"
        urllib.request.urlretrieve(url, "/tmp/k8s-game-rule-main.zip")
        shutil.unpack_archive("/tmp/k8s-game-rule-main.zip", "/tmp/")


def get_tasks(game: str):
    get_tests()
    folder = f"{TEST_BASE_PATH}/{game}/"
    tasks = []
    for file in sorted(os.listdir(folder)):
        if os.path.isdir(os.path.join(folder, file)) and "99_test_template" not in file:
            tasks.append(file)
    return tasks


def get_session_template(game: str, task: str):
    get_tests()
    session = {}
    game_session_file = f"{TEST_BASE_PATH}/{game}/session.json"
    task_session_file = f"{TEST_BASE_PATH}/{game}/{task}/session.json"
    if os.path.exists(game_session_file):
        with open(game_session_file, "r", encoding="utf-8") as file:
            game_session = json.load(file)
            session.update(game_session)
    if os.path.exists(task_session_file):
        with open(task_session_file, "r", encoding="utf-8") as file:
            task_session = json.load(file)
            session.update(task_session)

    return session


def get_current_task(game: str, finished_tasks):
    all_tasks = get_tasks(game)
    current_task = None
    for task in all_tasks:
        if task not in [task for task in finished_tasks]:
            current_task = task
            break
    return current_task


def render(template, session):
    env = Environment()
    jinja_template = env.from_string(template)
    template_string = jinja_template.render(session)
    return template_string


def get_instruction(game: str, task: str, session: dict):
    get_tests()
    instructions_file = f"{TEST_BASE_PATH}/{game}/{task}/instruction.md"

    if os.path.exists(instructions_file):
        with open(instructions_file, "r", encoding="utf-8") as file:
            instruction = file.read()
        return render(instruction, session)
    else:
        return None


def get_next_game_phrase(game: str, task: str, current_game_phrase: GamePhrase):
    get_tests()

    current_index = GAME_PHRASE_ORDER.index(current_game_phrase)
    for next_index in range(current_index + 1, len(GAME_PHRASE_ORDER)):
        test_file = f"{TEST_BASE_PATH}/{game}/{task}/test_{MAPPING[GAME_PHRASE_ORDER[next_index]]}.py"
        if os.path.exists(test_file):
            return GAME_PHRASE_ORDER[next_index]
    return None
