from exonview3d.colours import exon_colours


def test_colours_are_distinct_and_valid():
    colours = exon_colours(120)
    assert len(set(colours)) == 120
    assert all(c.startswith("#") and len(c) == 7 for c in colours)


def test_prefix_is_stable():
    assert exon_colours(30)[:10] == exon_colours(10)
