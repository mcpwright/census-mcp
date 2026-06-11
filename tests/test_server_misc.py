

def test_http_request_logging_is_capped():
    # httpx logs request URLs (incl. the api key query param) at INFO;
    # main() must cap it so `setup` never echoes the key.
    import logging

    from census_mcp.server import _quiet_http_logging

    _quiet_http_logging()
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING
