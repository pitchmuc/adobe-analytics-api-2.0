import pytest

import aanalytics2


def test_should_raise_on_empty_path_and_empty_private_key():
    with pytest.raises(ValueError):
        aanalytics2.configure(org_id='org_id',
                              tech_id='tech_id',
                              secret='secret',
                              path_to_key='',
                              client_id='client_id')


def test_private_key_should_be_used_if_provided():
    expected_private_key = 'private_key'
    aanalytics2.configure(org_id='org_id',
                          tech_id='tech_id',
                          secret='secret',
                          path_to_key=None,
                          client_id='client_id',
                          private_key=expected_private_key)
    config = aanalytics2.config_object
    assert aanalytics2.configs.get_private_key_from_config(config) == expected_private_key
