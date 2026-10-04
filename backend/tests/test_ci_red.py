def test_ci_goes_red_on_a_failing_test():
    assert 1 == 2, "deliberately failing: CI must turn red"
