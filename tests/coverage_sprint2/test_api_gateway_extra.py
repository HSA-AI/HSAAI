
def test_api_gateway_import():

    import services.api_gateway.main

    assert services.api_gateway.main


def test_gateway_functions():

    import services.api_gateway.main as m

    assert len(dir(m)) > 0
