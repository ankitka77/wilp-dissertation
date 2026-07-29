from phase9.exceptions import ConfigError, Phase9Error


def test_exceptions_to_dict():
    e = ConfigError(message="bad config", context={"path": "x"})
    d = e.to_dict()
    assert d["message"] == "bad config"
    assert d["context"]["path"] == "x"
