import logging
from datetime import datetime

from common.database import (
    get_game_session,
    get_tasks_by_email_and_game,
    get_user_data,
    save_game_session,
)
from common.file import clear_tmp_directory, create_json_input, write_user_files
from common.handler import (
    error_response,
    extract_k8s_credentials,
    get_email_and_game_from_event,
    ok_response,
    setup_paths,
    test_result_response,
)
from common.pytest import (
    GamePhrase,
    TestResult,
    get_current_task,
    get_instruction,
    get_next_game_phrase,
    run_tests,
)
from common.s3 import generate_presigned_url, upload_test_result
from common.session import generate_session

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

setup_paths()


def lambda_handler(event, context):  # pylint: disable=W0613

    email, game = get_email_and_game_from_event(event)
    if not email or not game:
        return error_response("Email and Game parameter is missing")
    if not game.isalnum():
        return error_response("Game parameter must be a single alphanumeric word")

    finished_tasks = get_tasks_by_email_and_game(email, game)
    current_task = get_current_task(game, finished_tasks)
    logger.info(current_task)
    if not current_task:
        return ok_response("All tasks are completed")

    user_data = get_user_data(email)
    if not user_data:
        return error_response(f"{email} not found in the database")

    client_certificate, client_key, endpoint = extract_k8s_credentials(user_data)

    if not all([client_certificate, client_key, endpoint]):
        return error_response("K8s confdential is missing.")

    clear_tmp_directory()
    write_user_files(client_certificate, client_key)

    instruction = None
    session = get_game_session(email, game, current_task)
    if session is None:
        session = generate_session(email, game, current_task)
        instruction = get_instruction(game, current_task, session)
        if not instruction:
            return error_response("Instruction not found!")
    else:
        instruction = session["$instruction"]
    session["$instruction"] = instruction
    session["$client_certificate"] = client_certificate
    session["$client_key"] = client_key
    session["$endpoint"] = endpoint

    try:
        create_json_input(endpoint, session)
        test_result = run_tests(GamePhrase.SETUP, game, current_task)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        upload_test_result(
            "/tmp/report.html", GamePhrase.CHECK, now_str, email, game, current_task
        )
        report_url = generate_presigned_url(
            GamePhrase.CHECK, now_str, email, game, current_task
        )

    except (FileNotFoundError, ValueError, KeyError) as e:
        return error_response(f"{type(e).__name__}: {str(e)}")

    if test_result == TestResult.OK:
        save_game_session(email, game, current_task, session)
        logger.info(session)

    next_game_phrase = get_next_game_phrase(game, current_task, GamePhrase.SETUP)
    return test_result_response(
        GamePhrase.SETUP,
        next_game_phrase,
        test_result,
        instruction,
        report_url,
    )
