Installation
============

Location: :doc:`/index` → :doc:`/installation`

There are several different ways to install Python packages, and Pulp 2 Tests
supports some of the most common methods. For example, an end user interested in
testing a Pulp 2 application might want to install Pulp 2 tests into a
virtualenv:

.. code-block:: sh

    python3 -m venv ~/.venvs/pulp-2-tests
    source ~/.venvs/pulp-2-tests/bin/activate
    pip install --upgrade pip
    pip install git+https://github.com/PulpQE/Pulp-2-Tests.git#egg=pulp-2-tests
    pulp-smash settings create  # declare information about Pulp
    # Run the tests using unittest or use the test runner of your preference.
    python3 -m unittest discover pulp_2_tests.tests 

For an explanation of key concepts and more installation strategies, see
`Installing Python Modules`_. For an explanation of virtualenvs, see `Virtual
Environments and Packages`_.

In addition to the dependencies listed in ``setup.py``, install OpenSSH if
testing is to be performed against a remote host. [1]_

.. [1] This hard dependency is a design bug in Pulp Smash. It would be better to
    require _an_ SSH implementation, whether provided by OpenSSH, Paramiko,
    Dropbear, or something else.

.. _Installing Python Modules: https://docs.python.org/3/installing/
.. _Virtual Environments and Packages: https://docs.python.org/3/tutorial/venv.html
