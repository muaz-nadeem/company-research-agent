from graph.routing import MAX_RESEARCH_ATTEMPTS, route_after_clarity, route_after_research, route_after_validator


def test_every_research_pass_is_validated():
    assert route_after_research({}) == 'validator'


def test_clarification_and_small_talk_routes():
    assert route_after_clarity({'clarity_status': 'needs_clarification'}) == 'clarify'
    assert route_after_clarity({'final_answer': 'Hello'}) == 'end'
    assert route_after_clarity({'clarity_status': 'clear'}) == 'research'


def test_research_retries_are_bounded_and_require_useful_next_step():
    assert route_after_validator({'validation_result': 'insufficient', 'retry_recommended': True, 'research_attempts': 1}) == 'research'
    assert route_after_validator({'validation_result': 'insufficient', 'retry_recommended': True, 'research_attempts': MAX_RESEARCH_ATTEMPTS}) == 'synthesis'
    assert route_after_validator({'validation_result': 'insufficient', 'retry_recommended': False, 'research_attempts': 1}) == 'synthesis'
    assert route_after_validator({'validation_result': 'sufficient'}) == 'synthesis'
