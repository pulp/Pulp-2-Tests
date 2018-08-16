# coding=utf-8
"""Test the `consumer`_ API endpoints.

.. _consumer:
    https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/consumer/index.html
"""
import os
import tempfile
import unittest
from urllib.parse import urljoin

from pulp_smash import api, config
from pulp_smash.pulp2.constants import CONSUMERS_PATH, REPOSITORY_PATH

from pulp_2_tests.tests.rpm.api_v2.utils import (
    gen_consumer,
    gen_distributor,
    gen_repo,
)
from pulp_2_tests.tests.platform.utils import set_up_module as setUpModule  # pylint:disable=unused-import
from pulp_2_tests.tests.platform.api_v2.utils import make_client_use_cert_auth


class BindConsumerTestCase(unittest.TestCase):
    """Show that one can `bind a consumer to a repository`_.

    .. _bind a consumer to a repository:
        https://docs.pulpproject.org/en/latest/dev-guide/integration/rest-api/consumer/bind.html#bind-a-consumer-to-a-repository
    """

    def test_all(self):
        """Bind a consumer to a distributor.

        Do the following:

        1. Create a repository with a distributor.
        2. Create a consumer.
        3. Bind the consumer to the distributor.

        Assert that:

        * The response has an HTTP 200 status code.
        * The response body contains the correct values.
        """
        cfg = config.get_config()
        client = api.Client(cfg)

        # Steps 1–2
        body = gen_repo()
        body['distributors'] = [gen_distributor()]
        repo = client.post(REPOSITORY_PATH, body).json()
        self.addCleanup(client.delete, repo['_href'])
        consumer = client.post(CONSUMERS_PATH, gen_consumer()).json()
        self.addCleanup(client.delete, consumer['consumer']['_href'])

        # Step 3
        repo = client.get(repo['_href'], params={'details': True}).json()
        path = urljoin(CONSUMERS_PATH, consumer['consumer']['id'] + '/')
        path = urljoin(path, 'bindings/')
        body = {
            'binding_config': {'B': 21},
            'distributor_id': repo['distributors'][0]['id'],
            'notify_agent': False,
            'repo_id': repo['id'],
        }
        response = client.post(path, body)

        with self.subTest(comment='check response status code'):
            self.assertEqual(response.status_code, 200)

        result = response.json()['result']
        with self.subTest(comment='check response body'):
            self.assertEqual(result['binding_config'], body['binding_config'])
            self.assertEqual(result['consumer_id'], consumer['consumer']['id'])
            self.assertEqual(result['distributor_id'], body['distributor_id'])
            self.assertEqual(result['repo_id'], body['repo_id'])


class RegisterAndUpdateConsumerTestCase(unittest.TestCase):
    """Show that one can `register and update a consumer`_.

    The call to *consumer register api* should return a x.509 certificate,
    that should be useful in updating a consumer and for other actions.

    .. _register and update a consumer:
        https://docs.pulpproject.org/dev-guide/integration/rest-api/consumer/cud.html#register-a-consumer
    """

    def test_all(self):
        """Register and Update a consumer.

        Do the following:

        1. Register a consumer with the consumer API
        2. Save the certificate returned in the response
        3. Update the same consumer with new details by using the client certificates

        Assert that:

        * The response for registering a consumer has a x.509 certificate.
        * The response body contains the correct values.

        Refer:

        * `Pulp Smash #1007 <https://github.com/PulpQE/pulp-smash/issues/1007>`_
        """
        cfg = config.get_config()
        client = api.Client(cfg, api.json_handler)
        tmp_cert_file = tempfile.NamedTemporaryFile(delete=False)
        self.addCleanup(os.unlink, tmp_cert_file.name)

        # Step 1
        consumer = client.post(CONSUMERS_PATH, gen_consumer())
        self.addCleanup(client.delete, consumer['consumer']['_href'])
        self.assertIn('certificate', consumer, 'certificate not found in the response')

        # Step 2
        with open(tmp_cert_file.name, 'w') as file_writer:
            file_writer.write(consumer['certificate'])

        # step 3
        make_client_use_cert_auth(client, tmp_cert_file.name)
        body = {
            'delta': {
                'display_name': 'Test Consumer',
                'notes': {'arch': 'x86_64'},
                'description': 'QA automation testing machine'
            }
        }
        result = client.put(consumer['consumer']['_href'], body)
        with self.subTest(comment='check display name'):
            self.assertEqual(result['display_name'], body['delta']['display_name'])
        with self.subTest(comment='check notes'):
            self.assertEqual(result['notes'], body['delta']['notes'])
        with self.subTest(comment='check description'):
            self.assertEqual(result['description'], body['delta']['description'])
