# coding=utf-8
"""Test the API's `authentication`_ functionality.

.. _authentication:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/authentication.html
"""
import unittest

from pulp_smash import api, config, selectors
from pulp_smash.pulp2.constants import ERROR_KEYS, LOGIN_KEYS, LOGIN_PATH

from pulp_2_tests.tests.platform.utils import set_up_module as setUpModule  # pylint:disable=unused-import


class LoginTestCase(unittest.TestCase):
    """Tests for logging in."""

    def test_success(self):
        """Successfully log in to the server.

        Assert that:

        * The response has an HTTP 200 status code.
        * The response body is valid JSON and has correct keys.
        """
        response = api.Client(config.get_config()).post(LOGIN_PATH)
        with self.subTest(comment='check response status code'):
            self.assertEqual(response.status_code, 200)
        with self.subTest(comment='check response body'):
            self.assertEqual(frozenset(response.json().keys()), LOGIN_KEYS)

    def test_failure(self):
        """Unsuccessfully log in to the server.

        Assert that:

        * The response has an HTTP 401 status code.
        * The response body is valid JSON and has correct keys.
        """
        cfg = config.get_config()
        response = (
            api.Client(cfg, api.echo_handler).post(LOGIN_PATH, auth=('', ''))
        )
        with self.subTest(comment='check response status code'):
            self.assertEqual(response.status_code, 401)
        if selectors.bug_is_fixed(1412, cfg.pulp_version):
            with self.subTest(comment='check response body'):
                self.assertEqual(frozenset(response.json().keys()), ERROR_KEYS)
