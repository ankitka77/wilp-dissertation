from phase8.analysis.statistical_analysis import _compute_basic_stats, MetricStats


def test_compute_basic_stats_empty():
    s = _compute_basic_stats([])
    assert isinstance(s, MetricStats)
    assert s.count == 0
    assert s.mean is None


def test_compute_basic_stats_single():
    s = _compute_basic_stats([0.5])
    assert s.count == 1
    assert s.mean == 0.5
    assert s.median == 0.5
    assert s.variance == 0.0
    assert s.std == 0.0
    assert s.ci_low is None and s.ci_high is None


def test_compute_basic_stats_multiple():
    s = _compute_basic_stats([0.0, 1.0, 1.0])
    assert s.count == 3
    assert abs(s.mean - (2 / 3)) < 1e-8
    assert s.minimum == 0.0
    assert s.maximum == 1.0
    assert s.std > 0.0
