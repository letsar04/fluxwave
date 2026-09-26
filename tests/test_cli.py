from fluxwave.cli import build_parser


def test_cli_has_split_and_reconstruct_commands():
    parser = build_parser()
    assert parser.parse_args(["split", "input.bin", "chunks"])
    assert parser.parse_args(["reconstruct", "chunks", "manifest.json", "output.bin"])
