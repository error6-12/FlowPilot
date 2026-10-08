from agents.appointment.input_parser import InputParser


def parse(payload: str) -> dict:
    parser = InputParser.__new__(InputParser)
    return parser.parse_data(payload)


def test_parse_data_coerces_string_booleans():
    result = parse(
        '{"project":"按摩","unrelated":"false","info_complete":"true",'
        '"missing_info":""}'
    )

    assert result["unrelated"] is False
    assert result["info_complete"] is True
    assert result["missing_info"] == []


def test_parse_data_accepts_json_code_fence():
    result = parse('```json\n{"unrelated": true, "missing_info": ["start_time"]}\n```')

    assert result["unrelated"] is True
    assert result["missing_info"] == ["start_time"]


def test_parse_data_returns_safe_defaults_for_invalid_json():
    result = parse("not-json")

    assert result["unrelated"] is False
    assert result["info_complete"] is False
    assert result["missing_info"] == ["所有信息"]
