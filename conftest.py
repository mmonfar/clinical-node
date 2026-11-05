def pytest_addoption(parser):
    parser.addoption("--live-pubmed", action="store_true", default=False,
                     help="run the one optional live NCBI esummary check")


def pytest_configure(config):
    config.addinivalue_line("markers", "live: optional check that uses the real network")
