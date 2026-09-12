from experiments.huawei_grammar.command_tree import CommandTree, Resolution


def test_shortest_unique_prefix() -> None:
    tree = CommandTree({("display", "current-configuration"), ("display", "clock")})
    assert tree.resolve(("dis", "cur")) == Resolution.MATCH
    assert tree.resolve(("d", "c")) == Resolution.AMBIGUOUS
    assert tree.resolve(("show",)) == Resolution.UNKNOWN
