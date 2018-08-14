# coding=utf-8
"""Utility functions for Platform tests."""


def make_client_use_cert_auth(client, cert):
    """Make an API client use certificate authentication.

    Mutate the given ``client`` by doing the following:

    * Delete ``'auth'`` from the client's ``request_kwargs``. ``'auth'`` is
      typcially a ``(username, password)`` tuple.
    * Insert the given ``cert`` into the client's ``request_kwargs``.

    :param client: An API client.
    :param cert: Path to the Client Certificate file
            that is used for authenticating the client
    :returns: Nothing. The client is mutated in place.
    """
    del client.request_kwargs['auth']
    client.request_kwargs['cert'] = cert
