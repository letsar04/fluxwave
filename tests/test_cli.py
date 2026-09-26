from fluxwave.cli import build_parser


def test_cli_commands():
    parser = build_parser()
    assert parser.parse_args(["split", "input.bin", "chunks"])
    assert parser.parse_args(["reconstruct", "chunks", "manifest.json", "output.bin"])
    assert parser.parse_args(["serve", "chunks", "--certfile", "a.crt", "--keyfile", "a.key"])
    assert parser.parse_args(["discover", "--timeout", "1"])
    assert parser.parse_args(["download", "received", "--peer", "http://127.0.0.1:8765"])
